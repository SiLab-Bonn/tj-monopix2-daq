#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from basil.HL.RegisterHardwareLayer import RegisterHardwareLayer


class regs(RegisterHardwareLayer):
    '''
    '''
    _registers = {
          'VERSION': {'descr': {'addr': 0, 'size': 8, 'offset': 0, 'properties': ['ro']}},
          'READY_HIT': {'descr': {'addr': 1, 'size': 1, 'offset': 0, 'properties': ['ro']}},
          'CLK_HIT_GATE': {'descr': {'addr': 1, 'size': 1, 'offset': 1}},
          'RESET_HIT': {'descr': {'addr': 1, 'size': 1, 'offset': 2}},
          'LVDS_TX_EN_HBRIDGE': {'descr': {'addr': 2, 'size': 5, 'offset': 0}},
          'LVDS_TX_ENABLE': {'descr': {'addr': 2, 'size': 1, 'offset': 5}},
          'LVDS_TX_EN_PRE': {'descr': {'addr': 3, 'size': 16,  'offset': 0}},
          'LVDS_TX_EN_CMFB': {'descr': {'addr': 5, 'size': 5, 'offset': 0}},
          'LVDS_TX_SET_IVNH': {'descr': {'addr': 6, 'size': 4, 'offset': 0}},
          'LVDS_TX_SET_IVNL': {'descr': {'addr': 6, 'size': 4, 'offset': 4}},
          'LVDS_TX_SET_IVPH': {'descr': {'addr': 7, 'size': 4, 'offset': 0}},
          'LVDS_TX_SET_IVPL': {'descr': {'addr': 7, 'size': 4, 'offset': 4}},
          'LVDS_TX_SET_IBCMFB': {'descr': {'addr': 8, 'size': 4, 'offset': 0}},
          'SET_IBIAS': {'descr': {'addr': 9, 'size': 8, 'offset': 0}},
          'SET_ITHR':  {'descr': {'addr': 10, 'size': 8, 'offset': 0}},
          'SET_ICASN': {'descr': {'addr': 11, 'size': 8, 'offset': 0}},
          'SET_IDB':   {'descr': {'addr': 12, 'size': 8, 'offset': 0}},
          'SET_ITUNE': {'descr': {'addr': 13, 'size': 8, 'offset': 0}},
          'SET_IDEL':  {'descr': {'addr': 14, 'size': 8, 'offset': 0}},
          'SET_IRAM':  {'descr': {'addr': 15, 'size': 8, 'offset': 0}},
          'SET_ICOMP': {'descr': {'addr': 16, 'size': 8, 'offset': 0}},
          'SET_VRESET': {'descr': {'addr': 17, 'size': 8, 'offset': 0}},
          'SET_VCASP':  {'descr': {'addr': 18, 'size': 8, 'offset': 0}},
          'SET_VCASC':  {'descr': {'addr': 19, 'size': 8, 'offset': 0}},
          'SET_VCLIP':  {'descr': {'addr': 20, 'size': 8, 'offset': 0}},
          'SET_VL':     {'descr': {'addr': 21, 'size': 8, 'offset': 0}},
          'SET_VH':     {'descr': {'addr': 22, 'size': 8, 'offset': 0}},
          'MON_EN_IBIAS': {'descr': {'addr': 23, 'size': 1, 'offset': 0}},
          'MON_EN_ITHR':  {'descr': {'addr': 23, 'size': 1, 'offset': 1}},
          'MON_EN_ICASN': {'descr': {'addr': 23, 'size': 1, 'offset': 2}},
          'MON_EN_IDB':   {'descr': {'addr': 23, 'size': 1, 'offset': 3}},
          'MON_EN_ITUNE': {'descr': {'addr': 23, 'size': 1, 'offset': 4}},
          'MON_EN_IDEL':  {'descr': {'addr': 23, 'size': 1, 'offset': 5}},
          'MON_EN_IRAM':  {'descr': {'addr': 23, 'size': 1, 'offset': 6}},
          'MON_EN_ICOMP': {'descr': {'addr': 23, 'size': 1, 'offset': 7}},
          'OVR_EN_IBIAS': {'descr': {'addr': 24, 'size': 1, 'offset': 0}},
          'OVR_EN_ITHR':  {'descr': {'addr': 24, 'size': 1, 'offset': 1}},
          'OVR_EN_ICASN': {'descr': {'addr': 24, 'size': 1, 'offset': 2}},
          'OVR_EN_IDB':   {'descr': {'addr': 24, 'size': 1, 'offset': 3}},
          'OVR_EN_ITUNE': {'descr': {'addr': 24, 'size': 1, 'offset': 4}},
          'OVR_EN_IDEL':  {'descr': {'addr': 24, 'size': 1, 'offset': 5}},
          'OVR_EN_IRAM':  {'descr': {'addr': 24, 'size': 1, 'offset': 6}},
          'OVR_EN_ICOMP': {'descr': {'addr': 24, 'size': 1, 'offset': 7}},
          'MON_EN_VRESET': {'descr': {'addr': 38, 'size': 1, 'offset': 0}},
          'MON_EN_VCASP':  {'descr': {'addr': 38, 'size': 1, 'offset': 1}},
          'MON_EN_VCASC':  {'descr': {'addr': 38, 'size': 1, 'offset': 2}},
          'MON_EN_VCLIP':  {'descr': {'addr': 38, 'size': 1, 'offset': 3}},
          'MON_EN_VL':     {'descr': {'addr': 38, 'size': 1, 'offset': 4}},
          'MON_EN_VH':     {'descr': {'addr': 38, 'size': 1, 'offset': 5}},
          'OVR_EN_VRESET': {'descr': {'addr': 38, 'size': 1, 'offset': 6}},
          'OVR_EN_VCASP':  {'descr': {'addr': 38, 'size': 1, 'offset': 7}},
          'OVR_EN_VCASC':  {'descr': {'addr': 39, 'size': 1, 'offset': 0}},
          'OVR_EN_VCLIP':  {'descr': {'addr': 39, 'size': 1, 'offset': 1}},
          'OVR_EN_VL':     {'descr': {'addr': 39, 'size': 1, 'offset': 2}},
          'OVR_EN_VH':     {'descr': {'addr': 39, 'size': 1, 'offset': 3}},
          'SET_ANAMON_SFP_L': {'descr': {'addr': 39, 'size': 4, 'offset': 4}},
          'SET_ANAMON_SFN_L': {'descr': {'addr': 25, 'size': 4, 'offset': 0}},
          'SET_ANAMONIN_SFN1_L': {'descr': {'addr': 25, 'size': 4, 'offset': 4}},
          'SET_ANAMONIN_SFP_L':  {'descr': {'addr': 26, 'size': 4, 'offset': 0}},
          'SET_ANAMONIN_SFN2_L': {'descr': {'addr': 26, 'size': 4, 'offset': 4}},
          'SET_ANAMON_SFP_R':    {'descr': {'addr': 27, 'size': 4, 'offset': 0}},
          'SET_ANAMON_SFN_R':    {'descr': {'addr': 27, 'size': 4, 'offset': 4}},
          'SET_ANAMONIN_SFN1_R': {'descr': {'addr': 28, 'size': 4, 'offset': 0}},
          'SET_ANAMONIN_SFP_R':  {'descr': {'addr': 28, 'size': 4, 'offset': 4}},
          'SET_ANAMONIN_SFN2_R': {'descr': {'addr': 29, 'size': 4, 'offset': 0}},
          'TIMESTAMP': {'descr': {'addr': 30, 'size': 4, 'offset': 0}},
          }

    _require_version = "==1"

    def __init__(self, intf, conf):
        super(regs, self).__init__(intf, conf)

    def get_READY_HIT(self):
        #print("=====sim=====regs.py get_READY")
        ret = self._intf.read_str(
            self._conf['base_addr']+self._registers['READY_HIT']['descr']['addr'], 
            size=1)
        return ret[0][7-self._registers['READY_HIT']['descr']['offset']]