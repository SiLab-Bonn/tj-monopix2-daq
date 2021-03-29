#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
import logging
from cocotb.binary import BinaryValue
from cocotb.drivers import BusDriver
from cocotb.triggers import FallingEdge, ReadOnly, RisingEdge, Timer
from cocotb.clock import Clock
from cocotb.result import ReturnValue

from basil.utils.BitLogic import BitLogic

import csv 
import sys 
import numpy as np 
from numpy.polynomial.chebyshev import chebx


class HitFile(BusDriver):

    _signals = ['CLK_BX', 'HIT', 'RESET_TB', 'TRIG_EXT']

    def __init__(self, entity, filename):
        self.filename = filename
        logging.info('Loading file...' + filename)

        BusDriver.__init__(self, entity, "", entity.CLK_BX)
        self.hit = BinaryValue(bits=len(self.bus.HIT))

        self.bus.TRIG_EXT <= 0

    @cocotb.coroutine
    def run(self):
        self.bus.HIT <= self.hit
        self.bus.TRIG_EXT <= 0

        res = 0
        bx = 0

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

        bv_size = len(self.bus.HIT)
        bv = BitLogic(bv_size)

        tot_hist = np.zeros([bv_size], dtype=np.uint8)
        trigger = 0

        with open(self.filename) as hit_file:
            csv_reader = csv.reader(hit_file, delimiter=',')

            for file_row in csv_reader:

                bcid = int(file_row[0])
                col = int(file_row[1])
                row = int(file_row[2])
                tot = int(file_row[3])
                trg = int(file_row[4])

                print('loading bcid=', bcid, ' mc=', col, ' row=', row, ' tot=', tot, ' trg=', trg, ' bx=', bx)

                while bx < bcid:
                    yield RisingEdge(self.clock)
                    # yield Timer(1000)

                    for pix in np.where(tot_hist > 0)[0]:
                        bv[int(pix)] = 1

                    self.hit.assign(str(bv))
                    self.bus.HIT <= self.hit
                    self.bus.TRIG_EXT <= trigger
                    tot_hist[tot_hist > 0] -= 1
                    trigger = 0
                    bv.setall(False)
                    bx += 1

                if bx == bcid:
                    if trg:
                        print("+++++++++++++++++++I am going to send a trigger+++++++++++++++++++++++++++++++")
                        trigger = 1

                    if col >= 0 and col < 224 and row >= 0 and row < 224:
                        pixn = row + col * 448
                        tot_hist[pixn] = tot_hist[pixn] + tot
#                     else:
#                         raise ValueError("Error")
            # Enters when csv file is completly read
            else:
                while np.any(tot_hist > 0):  # Process hits until tot_hist is empty
                    yield RisingEdge(self.clock)
                    # yield Timer(1000)
                    for pix in np.where(tot_hist > 0)[0]:
                        bv[int(pix)] = 1
                    self.hit.assign(str(bv))
                    self.bus.HIT <= self.hit
                    self.bus.TRIG_EXT <= trigger
                    tot_hist[tot_hist > 0] -= 1
                    trigger = 0
                    bv.setall(False)
                    bx += 1

        yield RisingEdge(self.clock)
        #yield Timer(1000)
        self.bus.HIT <= 0
        self.bus.TRIG_EXT <= 0
        logging.info('End of self.filename')

