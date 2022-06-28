#! /usr/bin/env python
# load binary lib/pyeudaq.so
import numpy as np
# import tables as tb
from tqdm import tqdm
import yaml
import threading
import signal
import os
import time
import argparse

import pyeudaq

from tjmonopix2.system import logger
from tjmonopix2.scans import scan_ext_trigger
from tjmonopix2.analysis import analysis_utils as au

scan_configuration = {
    'start_column': 0,
    'stop_column': 512,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': False,
    # timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time
    'max_triggers': False,
    # number of maximum received triggers after stopping readout, if False no limit on received trigger

    'trigger_latency': 100,  # latency of trigger in units of 25 ns (BCs)
    'trigger_delay': 57,  # trigger delay in units of 25 ns (BCs)
    'trigger_length': 32,  # length of trigger command (amount of consecutive BCs are read out)
    'veto_length': 400,
    # length of TLU veto in units of 25 ns (BCs). This vetos new triggers while not all data is received.
    # Should be adjusted for longer trigger length.

    # Trigger configuration
    'bench': {'TLU': {
        'TRIGGER_MODE': 3,
        # Selecting trigger mode: Use trigger inputs/trigger select (0), TLU no handshake (1), TLU simple
        # handshake (2), TLU data handshake (3)
        'TRIGGER_SELECT': 0,  # Selecting trigger input: HitOR (1), disabled (0)
        'TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES': 20
        # TLU trigger minimum length in TLU clock cycles. Change default here in order to ignore glitches from buggy
        # original TLU FW.
    }
    }
}


class EudaqScan(scan_ext_trigger.ExtTriggerScan):
    scan_id = 'eudaq_scan'

    min_spec_occupancy = False  # needed for handle data function of ext. trigger scan

    def __init__(self, daq_conf=None, bench_config=None, scan_config={}, scan_config_per_chip=None, suffix=''):
        super().__init__(daq_conf, bench_config, scan_config, scan_config_per_chip, suffix)
        self.last_readout_data = None
        self.last_trigger = 0
        self.bdaq_recording = True
        self.ovflw_cnt = 0

    def __del__(self):
        pass
        # print('destructor')
        # self.close()

    def _configure(self, callback=None, **_):
        super(EudaqScan, self)._configure(**_)

        self.last_readout_data = np.array([], dtype=np.uint32)

    def handle_data(self, data_tuple, receiver=None):

        if self.bdaq_recording:
            super(EudaqScan, self).handle_data(data_tuple, receiver=None)

        raw_data = data_tuple[0]

        if np.any(self.last_readout_data):  # no last readout data for first readout
            actual_data = np.concatenate((self.last_readout_data, raw_data))
        else:
            actual_data = raw_data

        trg_idx = np.where(actual_data & au.TRIGGER_HEADER > 0)[0]
        trigger_data = np.split(actual_data, trg_idx)

        # Send data of each trigger
        for dat in trigger_data[:-1]:
            glitch_detected = False
            # Split can return empty data, thus do not return send empty data
            # Otherwise fragile EUDAQ will fail. It is based on very simple event counting only

            if np.any(dat):
                trigger = dat[0] & au.TRG_MASK

                if np.bitwise_and(dat[0], au.TRIGGER_HEADER) == 0:
                    # this might happen the very first time we get data
                    # if there is trash data in the FIFO (which does not even start with a trigger word)
                    # we would interpret this trash 'normal' data word as a trigger word
                    # skip this stuff
                    continue

                prev_trg = self.last_trigger
                if self.last_trigger > 0 and trigger != self.last_trigger + 1:    # Trigger number jump
                    if (self.last_trigger + 1) == (trigger >> 1):
                        # Measured trigger number is exactly shifted by 1 bit, due to glitch
                        glitch_detected = True
                    else:
                        self.log.warning('Expected != Measured trigger number: %d != %d',
                                         self.last_trigger + 1, trigger)
                self.last_trigger = trigger if not glitch_detected else (trigger >> 1)

                if self.last_trigger < 100 and prev_trg > 32760:  # trigger number overflow
                    # arbitrary choice of borders, in case we missed triggers do not use a '=='
                    print('looks like an ovrFlw')
                    self.ovflw_cnt += 1

                # print('sending event with trgNmb = ', self.last_trigger)
                self.callback(dat)

        self.last_readout_data = trigger_data[-1]

    def _scan(self, start_column=0, stop_column=400, scan_timeout=10, max_triggers=False, min_spec_occupancy=False,
              fraction=0.99, use_tdc=False, **_):
        super(EudaqScan, self)._scan(start_column, stop_column, scan_timeout, max_triggers, min_spec_occupancy,
                                     fraction, use_tdc)
        # Send remaining data after stopped readout
        self.callback(self.last_readout_data)

    def get_last_trigger(self):
        return self.last_trigger

    def get_trg_ovflw(self):
        return self.ovflw_cnt


class Monopix2Producer(pyeudaq.Producer):

    def __init__(self, name, runctrl):
        pyeudaq.Producer.__init__(self, name, runctrl)

        self.en_bdaq_recording = True
        self.en_hitor = False
        self.bdaq_conf_file = None
        self.testbench_file = None
        self.board_ip = None
        self.scan = None
        self.thread_scan = None
        self.reg_config = {}
        self.init_register_vals = {}
        self.masked_pixels_file = None
        self.wait_for_fpga = True

        self.is_running = 0
        print('New instance of Monopix2Producer')

    def DoInitialise(self):
        # EUDAQ ini only available during DoInitialise, store to variables
        self.board_ip = self.GetInitItem("BOARD_IP")
        self.testbench_file = self.GetInitItem("TESTBENCH_FILE")
        self.bdaq_conf_file = self.GetInitItem("BDAQ_CONF_FILE")

    def DoConfigure(self):
        # EUDAQ config only available during DoConfigure, store to variables
        print('DoConfigure')

        if self.GetConfigItem('ENABLE_BDAQ_RECORD') == '0':
            self.en_bdaq_recording = False
        else: 
            self.en_bdaq_recording = True

            if self.GetConfigItem('ENABLE_HITOR') == '1':
                self.en_hitor = True
            else:
                self.en_hitor = False

            self.masked_pixels_file = self.GetConfigItem('MASKED_PIXELS_FILE')

            self.wait_for_fpga = self.GetConfigItem('WAIT_FOR_FPGA') == '1'

        configurable_regs = ['VL', 'VH', 'ITHR', 'IBIAS', 'VCASP', 'ICASN', 'VRESET', 'IDB']
        for reg in configurable_regs:
            self.reg_config[reg] = self.GetConfigItem(reg)

        # overriding default values from scan config with EUDAQ config
        tmp = self.GetConfigItem('START_ROW')
        if tmp:
            scan_configuration['start_row'] = int(tmp)

        tmp = self.GetConfigItem('STOP_ROW')
        if tmp:
            scan_configuration['stop_row'] = int(tmp)

        tmp = self.GetConfigItem('START_COLUMN')
        if tmp:
            scan_configuration['start_column'] = int(tmp)

        tmp = self.GetConfigItem('STOP_COLUMN')
        if tmp:
            scan_configuration['stop_column'] = int(tmp)

    def DoStartRun(self):

        if self.wait_for_fpga:
            # in commbinatin with the hameg_producer (PS) it is important to wait for the FPGA board to be reachable
            # via network, otherwise init and config will fail
            # time until FPGA board is reachable from the moment the PS start can vary
            max_retries = 5
            for i in range(1, max_retries):
                if os.system(f'ping -c 1 {self.board_ip}') == 0:
                    break

        self._init()
        self._configure()

        self.is_running = 1
        self.thread_scan = threading.Thread(target=self.scan.scan)
        self.thread_scan.start()

    def DoStopRun(self):
        print('DoStopRun')
        self.is_running = 0

        self.scan.stop_scan.set()
        self.thread_scan.join()

        self._reset_registers()

        # self.scan.analyze()
        self.scan.close()
        self.scan = None  # creating new scan object every time when starting, otherwise some internals are not set up
        # properly (when  _init_hardware of ScanBase is not called) and basil tcp connection fails
        # this is a workaround, TODO: do not always initialise and configure chip when just restarting a new run in eudaq

    def DoReset(self):
        print('DoReset')

        self.is_running = 0
        if self.scan:
            self.scan.stop_scan.set()
            self.scan.close()
        if self.thread_scan and self.is_running:
            self.thread_scan.join()

            self.thread_scan = None
            self.scan = None

    def RunLoop(self):
        print('Start of RunLoop in Monopix2Producer')
        while self.is_running:
            # doing nothing special here, different thread is handling FIFO read out and sending data to datacollector
            time.sleep(1)

        print('End of RunLoop in Monopix2Producer')

    def DoTerminate(self):
        print('terminating')
        if self.scan:
            self.scan.close()
            self.scan = None


    def _build_event(self, data):
        last_trigger = self.scan.get_last_trigger()
        if data.size > 0:
            ev = pyeudaq.Event('RawEvent', 'Monopix2RawEvent')
            if last_trigger:
                ev.SetTriggerN(last_trigger)
            else:
                ev.SetTag('NoTrg', '1')

            block = bytes(data)
            ev.AddBlock(0, block)
            ev.SetTag("trgOvflw", str(self.scan.get_trg_ovflw()))
            self.SendEvent(ev)
            # print(f'sending event with block size = {len(block)} and trigger# = {last_trigger}')
        else:
            print('trying to send empty data in event')

    def _reset_registers(self):
        # we want to reset the registers to the default values when closing
        # they might have been set to different values.
        # calling scan.init() on a chip with already set registers might result in a high current on the 1V8 line
        if self.init_register_vals:
            for reg in self.init_register_vals.keys():
                val = self.init_register_vals[reg]
                self.scan.chip.registers[reg].write(val)

    def _configure(self):
        self.scan.callback = self._build_event

        if self.en_bdaq_recording:
            self.scan.bdaq_recording = True
        else:
            self.scan.bdaq_recording = False

        self.scan.configure()

        # set up configured values for the monopix2 registers
        for reg in self.reg_config.keys():
            reg_val = self.reg_config[reg]
            self.init_register_vals[reg] = self.scan.chip.registers[reg].read()
            if reg_val:
                self.scan.chip.registers[reg].write(int(reg_val))

        self.scan.chip.registers['SEL_PULSE_EXT_CONF'].write(0)
        self.scan.daq.rx_channels['rx0']['DATA_DELAY'] = 14

        if self.en_hitor:
            self.scan.chip.registers['CMOS_TX_EN_CONF'].write(1)

            for i in range(512 // 16):
                #self.scan.chip._write_register(18 + i, 0xffff)
                self.scan.chip._write_register(50 + i, 0xffff)
            self.scan.chip._write_register(18 + 30, 0xffff)  # cols 480 to 495
            #self.scan.chip._write_register(18 + 31, 0xffff)  # cols 497 to 512

        self.scan.chip.masks['tdac'][0:512, 0:512] = 0b100

        if self.masked_pixels_file:
            with open(self.masked_pixels_file) as f:
                masked_pixels = yaml.full_load(f)

            for i in range(0, len(masked_pixels['masked_pixels'])):
                row = masked_pixels['masked_pixels'][i]['row']
                col = masked_pixels['masked_pixels'][i]['col']
                self.scan.chip.masks['tdac'][col, row] = 0

        self.scan.chip.masks.apply_disable_mask()
        self.scan.chip.masks.update(force=True)

    def _init(self):

        bdaq_conf = None
        if self.bdaq_conf_file:
            with open(self.bdaq_conf_file) as f:
                bdaq_conf = yaml.full_load(f)

            if self.board_ip:
                # override values for more comfortable usage with eudaq
                bdaq_conf['transfer_layer'][0]['init']['ip'] = self.board_ip

        bench_conf = None
        if self.testbench_file:
            with open(self.testbench_file) as f:
                bench_conf = yaml.full_load(f)

        self.scan = EudaqScan(daq_conf=bdaq_conf, bench_config=bench_conf, scan_config=scan_configuration)
        self.scan.skip_interpret_data = True
        self.scan.init()


if __name__ == '__main__':
    # Parse program arguments
    description = 'Start EUDAQ producer for Monopix2'
    parser = argparse.ArgumentParser(prog='monopix2_producer',
                                     description=description,
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-r', metavar='address',
                        help='Destination address',
                        default='tcp://localhost:44000',
                        nargs='?')

    args = parser.parse_args()

    producer = Monopix2Producer('monopix2', args.r)
    print('connecting to runcontrol in ', args.r)
    producer.Connect()
    time.sleep(2)
    while producer.IsConnected():
        time.sleep(1)
