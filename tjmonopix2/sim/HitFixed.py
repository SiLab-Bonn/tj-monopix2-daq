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


class HitFixed(BusDriver):

    _signals = ['CLK_BX', 'HIT', 'RESET_TB', 'TRIG_EXT']

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK_BX)

        self.hit = BinaryValue(bits=len(self.bus.HIT))
        self.hit <= 0
        self.bus.TRIG_EXT <= 0

    @cocotb.coroutine
    def run(self):
        self.bus.HIT <= self.hit
        self.bus.TRIG_EXT <= 0

        res = 0
        while res == 0:
            # Wait for RESET signal
            yield FallingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESET_TB.value.integer

        while res == 1:
            # Wait for falling edge of RESET signal
            yield FallingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESET_TB.value.integer

        for _ in range(5):
            # Delay hit w.r.t. RESET. Minimum 3 clk cycles
            yield FallingEdge(self.clock)

        bv = BitLogic(len(self.hit))
        bv[10] = 1
        bv[15] = 1
        self.hit.assign(str(bv))
        self.bus.HIT <= self.hit
        self.bus.TRIG_EXT <= 0

        for _ in range(14):
            # Stop HIT after 10 CLK_BX
            yield FallingEdge(self.clock)

        bv = BitLogic(len(self.hit))
        bv.setall(False)
        self.hit.assign(str(bv))
        self.bus.HIT <= self.hit
        self.bus.TRIG_EXT <= 1

        yield FallingEdge(self.clock)
        self.bus.TRIG_EXT <= 0

#         for _ in range(5):
#             # Delay hit
#             yield FallingEdge(self.clock)
# 
#         bv = BitLogic(len(self.hit))
#         bv[20] = 1
#         self.hit.assign(str(bv))
#         self.bus.HIT <= self.hit
#         self.bus.TRIG_EXT <= 0
# 
#         for _ in range(10):
#             # Stop HIT after 10 CLK_BX
#             yield FallingEdge(self.clock)
# 
#         bv = BitLogic(len(self.hit))
#         bv.setall(False)
#         self.hit.assign(str(bv))
#         self.bus.HIT <= self.hit
#         self.bus.TRIG_EXT <= 1
#         yield FallingEdge(self.clock)
#         self.bus.TRIG_EXT <= 0

#         for _ in range(5):
#             # Delay hit
#             yield FallingEdge(self.clock)
# #
#         bv = BitLogic(len(self.hit))
#         bv[20] = 1
#         self.hit.assign(str(bv))
#         self.bus.HIT <= self.hit
#         self.bus.TRIG_EXT <= 0
# 
#         for _ in range(10):
#             # Stop HIT after 10 CLK_BX
#             yield FallingEdge(self.clock)
# 
#         bv = BitLogic(len(self.hit))
#         bv.setall(False)
#         self.hit.assign(str(bv))
#         self.bus.HIT <= self.hit
#         self.bus.TRIG_EXT <= 1
#         yield FallingEdge(self.clock)
        self.bus.TRIG_EXT <= 0
