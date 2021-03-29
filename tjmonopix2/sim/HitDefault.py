#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
from cocotb.binary import BinaryValue
from cocotb.drivers import BusDriver
from cocotb.triggers import Timer

class HitDefault(BusDriver):
   
    _signals = ['CLK_BX', 'HIT', 'TRIGGER', 'RESET']

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK_BX)

        self.hit = BinaryValue(bits=len(self.bus.HIT))
        self.hit <= 0 

    @cocotb.coroutine
    def run(self):

        self.bus.HIT <= self.hit
        self.bus.TRIGGER <= 0

        yield Timer(0)
