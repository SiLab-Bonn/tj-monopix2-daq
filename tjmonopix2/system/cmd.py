#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from basil.HL.RegisterHardwareLayer import RegisterHardwareLayer


class cmd(RegisterHardwareLayer):
    '''Implement master RD53 configuration and timing interface driver.
    '''

    _registers = {'RESET': {'descr': {'addr': 0, 'size': 8, 'properties': ['writeonly']}},
                  'VERSION': {'descr': {'addr': 0, 'size': 8, 'properties': ['ro']}},
                  'START': {'descr': {'addr': 1, 'size': 1, 'offset': 7, 'properties': ['writeonly']}},
                  'READY': {'descr': {'addr': 2, 'size': 1, 'offset': 0, 'properties': ['ro']}},
                  'SYNCING': {'descr': {'addr': 2, 'size': 1, 'offset': 1, 'properties': ['ro']}},
                  'EXT_START_EN': {'descr': {'addr': 2, 'size': 1, 'offset': 2, 'properties': ['rw']}},
                  'EXT_TRIGGER_EN': {'descr': {'addr': 2, 'size': 1, 'offset': 3, 'properties': ['rw']}},
                  'OUTPUT_EN': {'descr': {'addr': 2, 'size': 1, 'offset': 4, 'properties': ['rw']}},
                  'BYPASS_MODE': {'descr': {'addr': 2, 'size': 1, 'offset': 5, 'properties': ['rw']}},
                  'CHIP_TYPE': {'descr': {'addr': 2, 'size': 2, 'offset': 6, 'properties': ['rw']}},
                  'SIZE': {'descr': {'addr': 3, 'size': 16}},
                  'REPETITIONS': {'descr': {'addr': 5, 'size': 16}},
                  'MEM_BYTES': {'descr': {'addr': 7, 'size': 16, 'properties': ['ro']}},
                  'AZ_VETO_CYCLES': {'descr': {'addr': 9, 'size': 16}}
                  }

    _require_version = "==2"

    cmd_data_map = {
        0: 0b01101010,
        1: 0b01101100,
        2: 0b01110001,
        3: 0b01110010,
        4: 0b01110100,
        5: 0b10001011,
        6: 0b10001101,
        7: 0b10001110,
        8: 0b10010011,
        9: 0b10010101,
        10: 0b10010110,
        11: 0b10011001,
        12: 0b10011010,
        13: 0b10011100,
        14: 0b10100011,
        15: 0b10100101,
        16: 0b10100110,
        17: 0b10101001,
        18: 0b01011001,
        19: 0b10101100,
        20: 0b10110001,
        21: 0b10110010,
        22: 0b10110100,
        23: 0b11000011,
        24: 0b11000101,
        25: 0b11000110,
        26: 0b11001001,
        27: 0b11001010,
        28: 0b11001100,
        29: 0b11010001,
        30: 0b11010010,
        31: 0b11010100
    }

    CMD_SYNC = [0b10000001, 0b01111110]  # 0x(817E)
    # CMD_PLL_LOCK = [0b01010101, 0b01010101]
    # CMD_READ_TRIGGER = 0b01101001
    CMD_CLEAR = 0b01011010
    CMD_GLOBAL_PULSE = 0b01011100
    CMD_CAL = 0b01100011
    CMD_REGISTER = 0b01100110
    CMD_RDREG = 0b01100101

    def __init__(self, intf, conf):
        super(cmd, self).__init__(intf, conf)
        self._mem_offset = 16   # In bytes

    def init(self):
        super(cmd, self).init()
        self._mem_size = self.get_mem_size()

    def get_mem_size(self):
        return self.MEM_BYTES

    def get_cmd_size(self):
        return self.SIZE

    def reset(self):
        self.RESET = 0

    def start(self):
        self.START = 0

    def set_size(self, value):
        ''' CMD buffer size '''
        self.SIZE = value

    def get_size(self):
        ''' CMD buffer size '''
        return self.SIZE

    def set_repetitions(self, value):
        ''' CMD repetitions '''
        self.REPETITIONS = value

    def get_repetitions(self):
        ''' CMD repetitions '''
        return self.REPETITIONS

    def set_ext_trigger(self, ext_trigger_mode):
        ''' external trigger input enable '''
        self.EXT_TRIGGER_EN = ext_trigger_mode

    def get_ext_trigger(self):
        ''' external trigger input enable '''
        return self.EXT_TRIGGER_EN

    def set_ext_start(self, ext_start_mode):
        ''' external start input enable '''
        self.EXT_START_EN = ext_start_mode

    def get_ext_start(self):
        ''' external start input enable '''
        return self.EXT_START_EN

    def set_output_en(self, value):
        ''' CMD output driver. False=high impedance '''
        self.OUTPUT_EN = value

    def set_bypass_mode(self, value):
        ''' CDR bypass mode (KC705+FMC_LPC). Enables the output drivers and sends cmd and serializer clock to the chip '''
        self.BYPASS_MODE = value

    def get_bypass_mode(self):
        return self.BYPASS_MODE

    def is_done(self):
        return self.READY

    def get_az_veto_cycles(self):
        ''' Veto clock cycles in 1/160 MHz during AZ '''
        return self.AZ_VETO_CYCLES

    def set_az_veto_cycles(self, value):
        ''' Veto clock cycles in 1/160 MHz during AZ '''
        self.AZ_VETO_CYCLES = value

    def set_chip_type(self, value):
        ''' Defines chip type for DAQ 0 = RD53A, 1 = ITKPixV1 '''
        self.CHIP_TYPE = value

    def set_data(self, data, addr=0):
        if self._mem_size < len(data):
            raise ValueError('Size of data (%d bytes) is too big for memory (%d bytes)' % (len(data), self._mem_size))
        self._intf.write(self._conf['base_addr'] + self._mem_offset + addr, data)

    def get_data(self, size=None, addr=0):
        if size and self._mem_size < size:
            raise ValueError('Size is too big')
        if not size:
            return self._intf.read(self._conf['base_addr'] + self._mem_offset + addr, self._mem_size)
        else:
            return self._intf.read(self._conf['base_addr'] + self._mem_offset + addr, size)
