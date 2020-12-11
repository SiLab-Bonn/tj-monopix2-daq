#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
from cocotb.binary import BinaryValue
from cocotb.drivers import BusDriver
from cocotb.triggers import FallingEdge, ReadOnly

from basil.utils.BitLogic import BitLogic


class HitInj(BusDriver):

    _signals = ['CLK_BX', 'HIT', 'RESET_TB', 'TRIG_EXT']

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK_BX)

        self.hit = BinaryValue(bits=len(self.bus.HIT))
        self.hit <= 0
        self.bus.TRIG_EXT <= 0

    @cocotb.coroutine
    def run(self):
        self.bus.TRIG_EXT <= 0

        res = 0
        while res == 0:
            # Wait for RESET signal
            yield FallingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESET_TB.value.integer

        self.bus.TRIG_EXT <= 0
