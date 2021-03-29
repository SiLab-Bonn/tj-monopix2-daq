#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
from cocotb.binary import BinaryValue
from cocotb.drivers import BusDriver
from cocotb.triggers import RisingEdge, ReadOnly

from basil.utils.BitLogic import BitLogic


class Cmd(BusDriver):

    _signals = ['CLK_BX', 'HIT', 'RESET_TB', 'TRIG_EXT', 'CMD']

    def __init__(self, entity):
        BusDriver.__init__(self, entity, "", entity.CLK_BX)

        self.cmd = BinaryValue(bits=len(self.bus.CMD))
        self.cmd <= 0
        self.bus.TRIG_EXT <= 0
        self.bus.CMD <= self.cmd

    @cocotb.coroutine
    def run(self):
        self.bus.CMD <= 0

        res = 0
        while res == 0:
            # Wait for RESET signal
            yield RisingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESET_TB.value.integer

        while res == 1:
            # Wait for falling edge of RESET signal
            yield RisingEdge(self.clock)
            yield ReadOnly()
            res = self.bus.RESET_TB.value.integer

        for _ in range(5):
            # Delay hit w.r.t. RESET. Minimum 3 clk cycles
            yield RisingEdge(self.clock)

#         bv = BitLogic(len(self.cmd) // 2)
#         bv[:] = 240  # sync
#         self.cmd.assign(2 * str(bv))
#         self.bus.CMD <= self.cmd
# 
#         yield RisingEdge(self.clock)
#         bv = BitLogic(len(self.cmd) // 2)
#         bv[:] = 0  # NOP
#         self.cmd.assign(2 * str(bv))
#         self.bus.CMD <= self.cmd
#  
#         yield RisingEdge(self.clock)
#         bv = BitLogic(len(self.cmd) // 2)
#         bv[:] = 2  # read register
#         self.cmd.assign(2 * str(bv))
#         self.bus.CMD <= self.cmd
#  
#         yield RisingEdge(self.clock)
#         dat = BitLogic(len(self.cmd))
#         dat[:] = 0b0110101001101010  # data = 0b0000100001 = 33
#         self.cmd.assign(str(dat))
#         self.bus.CMD <= self.cmd
#  
#         yield RisingEdge(self.clock)
#         bv = BitLogic(len(self.cmd) // 2)
#         bv.setall(False)
#         self.cmd.assign(2 * str(bv))
#         self.bus.CMD <= self.cmd

        bv = BitLogic(len(self.cmd) // 2)
        bv[:] = 240  # sync
        self.cmd.assign(2 * str(bv))
        self.bus.CMD <= self.cmd

        yield RisingEdge(self.clock)
        bv = BitLogic(len(self.cmd) // 2)
        bv[:] = 0  # NOP
        self.cmd.assign(2 * str(bv))
        self.bus.CMD <= self.cmd

        yield RisingEdge(self.clock)
        bv = BitLogic(len(self.cmd) // 2)
        bv[:] = 3  # write register
        self.cmd.assign(2 * str(bv))
        self.bus.CMD <= self.cmd

        yield RisingEdge(self.clock)
        dat = BitLogic(len(self.cmd))
        dat[:] = 0b0110101001101010  # data = 0b0000100001 = 33
        self.cmd.assign(str(dat))
        self.bus.CMD <= self.cmd

        yield RisingEdge(self.clock)
        dat = BitLogic(len(self.cmd))
        dat[:] = 0b0111000101110001  # data = 0b0000100001 = 33
        self.cmd.assign(str(dat))
        self.bus.CMD <= self.cmd

        yield RisingEdge(self.clock)
        bv = BitLogic(len(self.cmd) // 2)
        bv.setall(False)
        self.cmd.assign(2 * str(bv))
        self.bus.CMD <= self.cmd
