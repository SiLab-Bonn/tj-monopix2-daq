#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#
import collections
import os
import time

import pkg_resources
import yaml
import numpy as np
import math
from basil.dut import Dut

from tjmonopix2.system import logger
from tjmonopix2.system.tjmono2_rx import tjmono2_rx

VERSION = pkg_resources.get_distribution("tjmonopix2").version


class BDAQ53(Dut):
    '''
    Main class for BDAQ53 readout system
    '''
    def __init__(self, conf=None, bench_config=None):
        self.log = logger.setup_main_logger()
        self.proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.configuration = {}
        self.board_version = 'bdaq53'

        try:
            if bench_config is None:
                bench_config = os.path.join(self.proj_dir, 'testbench.yaml')
            with open(bench_config) as f:
                self.configuration = yaml.full_load(f)
        except TypeError:
            self.configuration = bench_config

        self.calibration = self.configuration.get('calibration', {})
        self.enable_NTC = self.configuration['hardware'].get('enable_NTC', False)

        self.receivers = ['rx0']

        if not conf:
            conf = os.path.join(self.proj_dir, 'system' + os.sep + 'bdaq53.yaml')
        self.log.debug("Loading configuration file from %s" % conf)

        # Flag indicating of tlu module is enabled.
        self.tlu_module_enabled = False

        super(BDAQ53, self).__init__(conf)

    def init(self, **kwargs):
        super(BDAQ53, self).init()

        self.fw_version, self.board_version = self['system'].get_daq_version()
        self.log.success('Found board %s running firmware version %s' % (self.board_version, self.fw_version))

        if self.fw_version != VERSION.split('.')[0] + '.' + VERSION.split('.')[1]:  # Compare only the first two blocks
            raise Exception("Firmware version (%s) is different than software version (%s)! Please update." % (self.fw_version, VERSION))

        # Initialize readout (only one chip supported at the moment)
        self.rx_channels = {}
        self.rx_channels['rx0'] = tjmono2_rx(self['intf'], {'name': 'rx', 'type': 'tjmonopix2.tjmono2_rx', 'interface': 'intf',
                                                            'base_addr': 0x0200})
        self.rx_channels['rx0'].init()

        # self.rx_lanes = {}
        # for recv in self.receivers:
        #     t_rx_lanes = self.rx_channels[recv].get_rx_config()
        #     self.rx_lanes[recv] = t_rx_lanes

        # Configure cmd encoder
        self.set_cmd_clk(frequency=160.0)
        self['cmd'].reset()
        time.sleep(0.1)

        # # Wait for the chip (model) PLL to lock before establishing a link
        # if self.board_version == 'SIMULATION':
        #     for _ in range(100):
        #         self.rx_channels['rx0'].get_rx_ready()

    def set_cmd_clk(self, frequency=160.0, force=False):
        if self.board_version in {'BDAQ53', 'MIO3'}:
            if self['system']['SI570_IS_CONFIGURED'] == 0 or force is True:
                from basil.HL import si570
                si570_conf = {'name': 'si570', 'type': 'si570', 'interface': 'intf', 'base_addr': 0xba, 'init': {'frequency': frequency}}
                clk_gen = si570.si570(self['i2c'], si570_conf)
                self['cmd'].set_output_en(False)
                for receiver in self.receivers:
                    self.rx_channels[receiver].reset()
                time.sleep(0.1)
                clk_gen.init()
                time.sleep(0.1)
                self['cmd'].set_output_en(True)
                self['system']['SI570_IS_CONFIGURED'] = 1
            else:
                self.log.info('Si570 oscillator is already configured')
        elif self.board_version == 'SIMULATION':
            pass

    def get_chips_cfgs(self):
        module_cfgs = {k: v for k, v in self.configuration['modules'].items() if 'identifier' in v.keys()}
        chip_cfgs = []
        for mod_cfg in module_cfgs.values():
            for k, v in mod_cfg.items():
                if isinstance(v, collections.abc.Mapping) and 'chip_sn' in v:  # Detect chips defined in testbench by the definition of a chip serial number
                    chip_cfgs.append(v)
        return chip_cfgs

    def set_LEMO_MUX(self, connector='LEMO_MUX_TX0', value=0):
        '''
        Sets the multiplexer in order to select which signal is routed to LEMO ports. So far only used
        for LEMO_TX ports.

        Parameters
        ----------
        connector : string
            Name of the LEMO connector. Possible names: LEMO_MUX_TX1, LEMO_MUX_TX0
        value : int
            Value specifying the multiplexer state. Default is 0.
            LEMO_TX_0: not used (3), not used (2), CMD_LOOP_START_PULSE (1), RJ45_CLK (0)
            LEMO_TX_1: not used (3), not used (2), not used (1), RJ45_BUSY (0)
        '''

        # TODO:  LEMO_MUX_RX1 and LEMO_MUX_RX0 not yet used
        # According to FW. None means not used.
        lemo_tx0_signals = ['RJ45_CLK', 'CMD_LOOP_START_PULSE', None, None]
        lemo_tx1_signals = ['RJ45_BUSY', None, None, None]
        if connector in ('LEMO_MUX_TX1', 'LEMO_MUX_TX0') and value in range(4):
            self['DAQ_CONTROL'][connector] = value
            self['DAQ_CONTROL'].write()
            if 'TX0' in connector:
                signal = lemo_tx0_signals[value]
            if 'TX1' in connector:
                signal = lemo_tx1_signals[value]
            self.log.info('%s set to %s (%s)' % (connector, value, signal))
        else:
            self.log.error('%s or %s are invalid' % (connector, value))

    def _bdaq_get_temperature_NTC(self, connector=7, NTC_type='TDK_NTCG163JF103FT1'):
        if not self.enable_NTC:
            raise ValueError('Please mount the correct resistors to your Bdaq board and enable the NTC in the testbench.yaml')

        if NTC_type == 'TDK_NTCG16H' or 'TDK_NTCG163JF103FT1':
            R_RATIO = np.array([18.85, 14.429, 11.133, 8.656, 6.779, 5.346, 4.245, 3.393, 2.728, 2.207, 1.796, 1.47, 1.209, 1.0, 0.831, 0.694, 0.583, 0.491, 0.416, 0.354, 0.302, 0.259, 0.223, 0.192, 0.167, 0.145, 0.127, 0.111, 0.0975, 0.086, 0.076, 0.0674, 0.0599, 0.0534])
            B_CONST = np.array([3140, 3159, 3176, 3194, 3210, 3226, 3241, 3256, 3270, 3283, 3296, 3308, 3320, 3332, 3343, 3353, 3363, 3373, 3382, 3390, 3399, 3407, 3414, 3422, 3428, 3435, 3441, 3447, 3453, 3458, 3463, 3468, 3473, 3478])
            TEMP = np.arange(-40 + 273.15, 130 + 273.15, 5)
            R0 = 10000  # R at 25C
        else:
            raise ValueError('NTC_type %s is not supported.' % NTC_type)

        # Set NTC MUX, with TJ2 only one DP is supported anyway
        self['DAQ_CONTROL']['NTC_MUX'] = connector
        self['DAQ_CONTROL'].write()
        self.log.debug('Set NTC_MUX to %s', connector)
        time.sleep(0.001)
        vpvn_raw = self['gpio_xadc_vpvn'].get_data()  # reads VP - VN voltage generated by NTC readout circuit on BDAQ53 pcb vpvn_raw is /16 becauses XADC is 12bit
        if all(v == 255 for v in vpvn_raw):
            self.log.warning('BDAQ ADC in saturation! Raw values: {}'.format(vpvn_raw))
        Vmeas = float((vpvn_raw[1] + vpvn_raw[0] * 256) / 16) * 1 / (2 ** 12 - 1)

        if 0.26 < Vmeas < 0.28:  # Very old BDAQ: No MUX, resistors, ... mounted
            self.log.warning('NTC measurement is ambiguous! Are you sure you have all necessary devices mounted on your BDAQ board?')
        elif 0.017 < Vmeas < 0.02:  # Wrong resistor values or solder jumpers open
            self.log.warning('NTC measurement is ambiguous! Are you sure you have the correct resistors mounted on your BDAQ board?')

        # r = NTC resistance, is measured by unity gain opamp on BDAQ53 PCB
        # R names taken from BDAQ53 PCB rev. 1.1, adjust to fit input xADC input rage [0-1V]
        # Vmeas = VntcP - VntcN

        R16 = float(self.calibration['bdaq_ntc']['R16'])
        R17 = float(self.calibration['bdaq_ntc']['R17'])
        R19 = float(self.calibration['bdaq_ntc']['R19'])
        VCC_3V3 = 3.3

        VntcP = VCC_3V3 * R19 / (R17 + R19)
        VntcN = VntcP - Vmeas

        r = VntcN * R16 / (VCC_3V3 - VntcN)

        r_ratio = r / R0
        arg = np.argwhere(R_RATIO <= r_ratio)

        if len(arg) == 0:
            j = -1
        else:
            j = arg[0]

        k = 1.0 / (math.log(r_ratio / R_RATIO[j]) / B_CONST[j] + 1 / TEMP[j])[0]
        self.log.debug("Temperature of NTC %s: %.2f [°C]", NTC_type, k - 273.15)

        return round(k - 273.15, 3)

    def _bdaq_get_temperature_FPGA(self):
        '''
        Return temperature of BDAQ FPGA
        '''
        # temp_raw is /16 becauses XADC is 12bit
        # -0x767) * 0.123 - 40 from XADC manual
        fpga_temp_raw = self['gpio_xadc_fpga_temp'].get_data()
        fpga_temp = (float(fpga_temp_raw[1] + fpga_temp_raw[0] * 256) / 16 - 0x767) * 0.123 - 40

        self.log.debug('Internal FPGA temperature: %.2f [°C]', fpga_temp)

        return round(fpga_temp, 3)

    def get_temperature_NTC(self, connector=7):
        '''
            Returns the NTC temperature measured at the selected connector.
            For KC705 the connector parameter takes no effect.

            Parameters:
            ----------
                connector : int or str
                    Determines which connector on the BDAQ board shall be used to readout the NTC.
                    Must be either the receiver name as string (eg. 'rx0') or the actual integer connector ID.
        '''
        if self.board_version == 'BDAQ53':
            return self._bdaq_get_temperature_NTC(connector=connector)
        else:
            self.log.error('NTC readout is not not supported on this hardware platform.')

    def get_temperature_FPGA(self):
        if self.board_version == 'BDAQ53':
            return self._bdaq_get_temperature_FPGA()
        else:
            self.log.error('FPGA temperature readout is not not supported on this hardware platform.')

    def set_chip_type(self):
        ''' Defines chip type ITkPixV1-like '''
        self['cmd'].set_chip_type(1)

    # def enable_auto_sync(self):
    #     '''Enables automatic sending of sync commands'''
    #     self['cmd'].set_auto_sync(1)

    # def disable_auto_sync(self):
    #     '''Disables automatic sending of sync commands'''
    #     self['cmd'].set_auto_sync(0)

    def _set_tdc_registers(self, tdc_module="tdc_lvds"):
        self[tdc_module].EN_WRITE_TIMESTAMP = self.configuration['TDC'].get('EN_WRITE_TIMESTAMP', 1)
        self[tdc_module].EN_TRIGGER_DIST = self.configuration['TDC'].get('EN_TRIGGER_DIST', 1)
        self[tdc_module].EN_NO_WRITE_TRIG_ERR = self.configuration['TDC'].get('EN_NO_WRITE_TRIG_ERR', 1)
        self[tdc_module].EN_INVERT_TDC = self.configuration['TDC'].get('EN_INVERT_TDC', 0)
        self[tdc_module].EN_INVERT_TRIGGER = self.configuration['TDC'].get('EN_INVERT_TRIGGER', 0)

    def _set_tdc_enable(self, tdc_module='tdc_lvds', enable=True):
        self[tdc_module].ENABLE = enable

    def configure_tdc_module(self, input="lvds"):
        """Configuration of TDC module(s) for different kinds of inputs:
           - single ended CMOS at LEMO RX1 (LEMO on chip carrier PCB)
           - differential LVDS at DP_SL1 (DP2 on chip carrier PCB)

        Args:
            input (str, optional): Type of TDC input. Supports "lvds" (DP_SL1), "cmos" (LEMO RX1) or None (both). Defaults to "lvds".

        Raises:
            ValueError: Invalid type of TDC input choice
        """
        self.log.info('Configuring TDC module')
        if input not in ['lvds', 'cmos', None]:
            raise ValueError("Unsupported TDC input")
        if input is None:
            for tdc_module in ['lvds', 'cmos']:
                self._set_tdc_registers(tdc_module=tdc_module)
        else:
            self._set_tdc_registers(tdc_module='tdc_{}'.format(input.lower()))

    def enable_tdc_module(self, input="lvds"):
        if input not in ['lvds', 'cmos', None]:
            raise ValueError("Unsupported TDC input")
        if input is None:
            for tdc_module in ['lvds', 'cmos']:
                self._set_tdc_enable(tdc_module=tdc_module, enable=True)
        else:
            self._set_tdc_enable(tdc_module='tdc_{}'.format(input.lower()), enable=True)

    def disable_tdc_module(self, input="lvds"):
        if input not in ['lvds', 'cmos', None]:
            raise ValueError("Unsupported TDC input")
        if input is None:
            for tdc_module in ['lvds', 'cmos']:
                self._set_tdc_enable(tdc_module=tdc_module, enable=False)
        else:
            self._set_tdc_enable(tdc_module='tdc_{}'.format(input.lower()), enable=False)

    def enable_tlu_module(self):
        self['tlu']['TRIGGER_ENABLE'] = True
        self.tlu_module_enabled = True

    def disable_tlu_module(self):
        self['tlu']['TRIGGER_ENABLE'] = False
        self.tlu_module_enabled = False

    def get_trigger_counter(self):
        return self['tlu']['TRIGGER_COUNTER']

    def set_trigger_data_delay(self, trigger_data_delay):
        self['tlu']['TRIGGER_DATA_DELAY'] = trigger_data_delay

    def configure_tlu_module(self, max_triggers=False):
        self.log.info('Configuring TLU module...')
        self['tlu']['RESET'] = 1    # Reset first TLU module
        for key, value in self.configuration['TLU'].items():    # Set specified registers
            self['tlu'][key] = value
        self['tlu']['TRIGGER_COUNTER'] = 0

        if max_triggers:
            self['tlu']['MAX_TRIGGERS'] = int(max_triggers)  # Set maximum number of triggers
        else:
            self['tlu']['MAX_TRIGGERS'] = 0  # unlimited number of triggers

    def get_tlu_erros(self):
        return (self['tlu']['TRIGGER_LOW_TIMEOUT_ERROR_COUNTER'], self['tlu']['TLU_TRIGGER_ACCEPT_ERROR_COUNTER'])

    def configure_tlu_veto_pulse(self, veto_length):
        # configures pulse for veto of new triggers
        self['tlu_veto'].set_en(True)
        self['tlu_veto'].set_width(1)
        self['tlu_veto'].set_delay(veto_length)
        self['tlu_veto'].set_repeat(1)

    def configure_cmd_loop_start_pulse(self, width=8, delay=140):
        self['pulser_cmd_start_loop'].set_en(True)
        self['pulser_cmd_start_loop'].set_width(width)
        self['pulser_cmd_start_loop'].set_delay(delay)
        self['pulser_cmd_start_loop'].set_repeat(1)

    def reset_fifo(self):
        self['FIFO']['RESET'] = 0

    # def set_timestamp(self, src="rx0"):
    #     self["timestamp_{}".format(src)].reset()
    #     self["timestamp_{}".format(src)]["EXT_TIMESTAMP"] = True
    #     if src == "rx0":
    #         self["timestamp_rx1"]["ENABLE_TRAILING"] = 0
    #         self["timestamp_rx1"]["ENABLE"] = 1
    #     elif src == "hitor":
    #         self["timestamp_hitor"]["ENABLE_TRAILING"] = 1
    #         self["timestamp_hitor"]["ENABLE"] = 1
    #     elif src == "inj":
    #         self["timestamp_inj"]["ENABLE"] = 1

    #     logging.info("Set timestamp: src={}".format(src))

    # def stop_timestamp(self, src="rx0"):
    #     self["timestamp_{}".format(src)]["ENABLE"] = 0
    #     lost_cnt = self["timestamp_{}".format(src)]["LOST_COUNT"]
    #     if lost_cnt != 0:
    #         logging.warn("Stop timestamp: src={} lost_cnt={:d}".format(src, lost_cnt))
    #     return lost_cnt
