#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from basil.HL.RegisterHardwareLayer import RegisterHardwareLayer


class DAQBoard(RegisterHardwareLayer):
    ''' BDAQ readout board configuration
    '''

    _registers = {'RESET': {'descr': {'addr': 0, 'size': 8, 'properties': ['writeonly']}},
                  'VERSION': {'descr': {'addr': 0, 'size': 8, 'properties': ['ro']}},
                  'VERSION_MINOR': {'descr': {'addr': 1, 'size': 8, 'properties': ['ro']}},
                  'VERSION_MAJOR': {'descr': {'addr': 2, 'size': 8, 'properties': ['ro']}},
                  'BOARD_VERSION': {'descr': {'addr': 3, 'size': 8, 'properties': ['ro']}},
                  'SI570_IS_CONFIGURED': {'descr': {'addr': 4, 'size': 1, 'properties': ['rw']}},
                  }

    _require_version = "==1"

    ''' Map hardware IDs for board identification '''
    hw_map = {
        0: 'SIMULATION',
        1: 'BDAQ53',
    }

    # hw_con_map = {
    #     0: 'SMA',
    #     1: 'FMC_LPC',
    #     2: 'FMC_HPC',
    #     3: 'Displayport',
    #     4: 'Cocotb'
    # }

    def __init__(self, intf, conf):
        super(DAQBoard, self).__init__(intf, conf)

    def init(self):
        super(DAQBoard, self).init()

    def reset(self):
        self.RESET = 0

    def get_daq_version(self):
        fw_version = str('%s.%s' % (self.VERSION_MAJOR, self.VERSION_MINOR))
        board_version = self.hw_map[self.BOARD_VERSION]

        return fw_version, board_version
