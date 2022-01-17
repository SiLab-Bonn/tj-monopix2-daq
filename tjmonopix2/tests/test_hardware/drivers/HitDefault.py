#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
from cocotb.binary import BinaryValue
from cocotb.triggers import RisingEdge, ReadOnly, Timer

from cocotb_bus.drivers import BusDriver

class HitDefault(BusDriver):
   
    _signals = ['CLK40', 'ANALOG_HIT', 'TRIGGER', 'RESETB_EXT']

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK40)

        self.hit = BinaryValue(bits=len(self.bus.ANALOG_HIT))
        self.hit.value = 0 

    @cocotb.coroutine
    def run(self):

        self.bus.ANALOG_HIT <= self.hit
        self.bus.TRIGGER <= 0

        while 1:
            yield RisingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESETB_EXT.value.integer
            if(res == 1):
                break

        yield RisingEdge(self.clock)
        yield Timer(100)
        self.hit.assign(0x3)
        self.bus.ANALOG_HIT.value = self.hit
        