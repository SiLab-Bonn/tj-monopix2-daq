#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from basil.HL.RegisterHardwareLayer import RegisterHardwareLayer


class tjmono_direct_rx(RegisterHardwareLayer):
    '''
    '''

    _registers = {'RESET': {'descr': {'addr': 0, 'size': 8, 'properties': ['writeonly']}},
                  'VERSION': {'descr': {'addr': 0, 'size': 8, 'properties': ['ro']}},
                  'EN': {'descr': {'addr': 2, 'size': 1, 'offset': 0}},
                  'DISSABLE_GRAY_DECODER': {'descr': {'addr': 2, 'size': 1, 'offset': 1}},
                  'FORCE_READ': {'descr': {'addr': 2, 'size': 1, 'offset': 2}},
                  'LOST_COUNT': {'descr': {'addr': 3, 'size': 8, 'properties': ['ro']}},
                  'START_FREEZE': {'descr': {'addr': 4, 'size': 16}},
                  'STOP_FREEZE': {'descr': {'addr': 6, 'size': 16}},
                  'START_READ': {'descr': {'addr': 8, 'size': 16}},
                  'STOP_READ': {'descr': {'addr': 10, 'size': 16}},
                  'STOP': {'descr': {'addr': 12, 'size': 16}},
                  'READ_SHIFT': {'descr': {'addr': 14, 'size': 16}},
                  'READY': {'descr': {'addr': 18, 'size': 1, 'offset': 0, 'properties': ['ro']}},
                  'CNT2': {'descr': {'addr': 18, 'size': 8}},
                  }

    _require_version = "==3"

    def __init__(self, intf, conf):
        super(tjmono_direct_rx, self).__init__(intf, conf)

    def reset(self):
        '''Soft reset the module.'''
        self.RESET = 0

    def set_en(self, value):
        self.EN = value

    def get_en(self):
        return self.EN

    def get_lost_count(self):
        return self.LOST_COUNT
