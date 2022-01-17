#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
from cocotb_bus.drivers import BusDriver
from cocotb.clock import Clock


class Drive320Clock(BusDriver):

    _signals = ["CLK320"]

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK320)

    async def run(self):

        cocotb.fork(Clock(self.clock, 3120).start())
