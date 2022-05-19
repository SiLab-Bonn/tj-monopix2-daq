#! /usr/bin/env python
# load binary lib/pyeudaq.so
import ctypes
import time

import pyeudaq

import numpy as np
# import tables as tb
from tqdm import tqdm
import yaml
import threading

from tjmonopix2.system import logger
from tjmonopix2.scans import scan_ext_trigger
from tjmonopix2.analysis import analysis_utils as au

scan_configuration = {
    'start_column': 128,
    'stop_column': 264,
    'start_row': 0,
    'stop_row': 192,

    'scan_timeout': False,
    # timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time
    'max_triggers': False,
    # number of maximum received triggers after stopping readout, if False no limit on received trigger

    'trigger_latency': 100,  # latency of trigger in units of 25 ns (BCs)
    'trigger_delay': 57,  # trigger delay in units of 25 ns (BCs)
    'trigger_length': 32,  # length of trigger command (amount of consecutive BCs are read out)
    'veto_length': 210,
    # length of TLU veto in units of 25 ns (BCs). This vetos new triggers while not all data is revieved. Should be adjusted for longer trigger length.

    # Trigger configuration
    'bench': {'TLU': {
        'TRIGGER_MODE': 3,
        # Selecting trigger mode: Use trigger inputs/trigger select (0), TLU no handshake (1), TLU simple handshake (2), TLU data handshake (3)
        'TRIGGER_SELECT': 0,  # Selecting trigger input: HitOR (1), disabled (0)
        'TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES': 20
        # TLU trigger minimum length in TLU clock cycles. Change default here in order to ignore glitches from buggy original TLU FW.
    }
    }
}


class EudaqScan(scan_ext_trigger.ExtTriggerScan):
    scan_id = 'eudaq_scan'

    min_spec_occupancy = False  # needed for handle data function of ext. trigger scan

    def __init__(self, daq_conf=None, bench_config=None, scan_config={}, scan_config_per_chip=None, suffix=''):
        super().__init__(daq_conf, bench_config, scan_config, scan_config_per_chip, suffix)
        self.last_readout_data = None
        self.last_trigger = None

    def _configure(self, callback=None, **_):
        super(EudaqScan, self)._configure(**_)

        self.last_readout_data = np.array([], dtype=np.uint32)

    def handle_data(self, data_tuple, receiver=None):
        '''
        Called on every readout (a few Hz)
        Sends data per event by checking for the trigger word that comes first.
        '''

        super(EudaqScan, self).handle_data(data_tuple, receiver)

        raw_data = data_tuple[0]

        print('handling data raw:')
        print(raw_data)

        if np.any(self.last_readout_data):  # no last readout data for first readout
            actual_data = np.concatenate((self.last_readout_data, raw_data))
        else:
            actual_data = raw_data

        trg_idx = np.where(actual_data & au.TRIGGER_HEADER > 0)[0]
        trigger_data = np.split(actual_data, trg_idx)

        print('trigger')
        print(trigger_data)

        # Send data of each trigger
        for dat in trigger_data[:-1]:
            glitch_detected = False
            # Split can return empty data, thus do not return send empty data
            # Otherwise fragile EUDAQ will fail. It is based on very simple event counting only
            if np.any(dat):
                trigger = dat[0] & au.TRG_MASK
                if self.last_trigger > 0 and trigger != self.last_trigger + 1:  # Trigger number jump
                    if (self.last_trigger + 1) == (
                            trigger >> 1):  # Measured trigger number is exactly shifted by 1 bit, due to glitch
                        glitch_detected = True
                    else:
                        self.log.warning('Expected != Measured trigger number: %d != %d', self.last_trigger + 1,
                                         trigger)
                self.last_trigger = trigger if not glitch_detected else (trigger >> 1)
                self.callback(dat)
                print('we did get data, callback = ')
                print(self.callback)


        self.last_readout_data = trigger_data[-1]

    def _scan(self, start_column=0, stop_column=400, scan_timeout=10, max_triggers=False, min_spec_occupancy=False,
              fraction=0.99, use_tdc=False, **_):
        super(EudaqScan, self)._scan(start_column, stop_column, scan_timeout, max_triggers, min_spec_occupancy,
                                     fraction, use_tdc)
        # Send remaining data after stopped readout
        self.callback(self.last_readout_data)

    def get_last_trigger(self):
        return self.last_trigger


class Monopix2Producer(pyeudaq.Producer):
    def __init__(self, name, runctrl):
        # pyeudaq.Producer.__init__(self, 'PyProducer', name, runctrl)
        pyeudaq.Producer.__init__(self, name, runctrl)

        self.scan = None
        self.scan_thread = None

        self.is_running = 0
        print('New instance of Monopix2Producer')

    def DoInitialise(self):
        print('DoInitialise')
                
        board_ip = self.GetInitItem("BOARD_IP")
        testbench_file = self.GetInitItem("TESTBENCH_FILE")
        bdaq_conf_file = self.GetInitItem("BDAQ_CONF_FILE")

        bdaq_conf = None
        if bdaq_conf_file:
            with open(bdaq_conf_file) as f:
                bdaq_conf = yaml.full_load(f)

            if board_ip:
                # override values for more comfortable usage with eudaq
                bdaq_conf['transfer_layer'][0]['init']['ip'] = board_ip

        bench_conf = None
        if testbench_file:
            with open(testbench_file) as f:
                bench_conf = yaml.full_load(f)

        self.scan = EudaqScan(daq_conf=bdaq_conf, bench_config=bench_conf, scan_config=scan_configuration)

        self.scan.init()

    def DoConfigure(self):
        print('DoConfigure')

        self.scan.configure()
        self.scan.callback = self.build_event

    def DoStartRun(self):
        print('DoStartRun')
        self.is_running = 1
        self.scan_thread = threading.Thread(target=self.scan.scan)
        self.scan_thread.start()

    def DoStopRun(self):
        print('DoStopRun')
        self.is_running = 0
        self.scan.stop_scan.set()
        #self.scan.stop_readout()
        self.scan_thread.join()

    def DoReset(self):
        print('DoReset')
        self.is_running = 0
        self.scan.stop_scan.set()
        self.scan_thread.join()

    def RunLoop(self):
        print("Start of RunLoop in Monopix2Producer")
        trigger_n = 0
        while self.is_running:
            # doing nothing special here, different thread is handling FIFO read out and sending data to "build_event"
            self.sleep(1)

        print("End of RunLoop in Monopix2Producer")

    def build_event(self, data):
        if data.size > 0:
            print('trying to send event')
            print('test' + str(data))
            ev = pyeudaq.Event("RawEvent", "idk")
            ev.SetTriggerN(self.scan.get_last_trigger())
            #self.buffer.put(data)
            block = bytes(data)
            ev.AddBlock(0, block)

            self.sendEvent(ev)
        else:
            print('trtying to send empty data in event')


if __name__ == "__main__":
    producer = Monopix2Producer("monopix2", "tcp://localhost:44000")
    print("connecting to runcontrol in localhost:44000", )
    producer.Connect()
    time.sleep(2)
    while producer.IsConnected():
        time.sleep(1)
