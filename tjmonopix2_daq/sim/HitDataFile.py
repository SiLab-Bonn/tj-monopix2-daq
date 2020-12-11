
#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import cocotb
import logging
from cocotb.binary import BinaryValue
from cocotb.triggers import RisingEdge, Timer, ReadWrite
from cocotb.drivers import BusDriver
from basil.utils.BitLogic import BitLogic
import csv
import numpy as np

COLS=512
ROWS=512


class HitDataFile(BusDriver):

    _signals = ['CLK_HIT', 'HIT', 'READY_HIT', 'RESET_HIT', 'TRIG_HIT']

    def __init__(self, entity, filename):
        BusDriver.__init__(self, entity, "", entity.CLK_HIT)

        val = '0' * len(self.bus.HIT)
        self.hit = BinaryValue(n_bits=len(self.bus.HIT), value=val)
        self.filename = filename
        if isinstance(self.filename, str):
            self.filename = [self.filename]
        print('HitDataFile: Loading file... ' + str(filename))

    @cocotb.coroutine
    def run(self):
        self.bus.HIT <= self.hit
        self.bus.READY_HIT <= 0
        self.bus.TRIG_HIT <= 0
        total_hits = 0
        for f in self.filename:
            logging.info('HitDataFile: filename={0}'.format(f))
            while 1:
                yield RisingEdge(self.clock)
                yield ReadWrite()
                res = self.bus.RESET_HIT.value.integer
                if(res == 1):
                    break
            self.bus.READY_HIT <= 1
            while 1:
                yield RisingEdge(self.clock)
                yield ReadWrite()
                res = self.bus.RESET_HIT.value.integer
                if(res == 0):
                    break
            self.bus.READY_HIT <= 0
            bv = BitLogic(len(self.hit))
            tot_hist = np.full([len(self.hit)], 0, dtype=np.uint16)
            bx = -1
            trig = 0
            with open(f) as csvfile:
                csv_reader = csv.reader(csvfile, delimiter=',')
                logging.info('HitDataFile: starting hits {0}'.format(f))
                for file_row in csv_reader:
                    if file_row[0][0] == "#":
                        continue
                    bxid = int(file_row[0])
                    col = int(file_row[1])
                    row = int(file_row[2])
                    tot = int(file_row[3])
                    trg = int(file_row[4])

                    #print(
                    #    '=====sim=====loading bxid={0:d} trg={1:d} col={2:d} row={3:d} tot={4:d} bx={5:d}'.format(
                    #    bxid, trg, col, row, tot, bx))

                    while bxid > bx:
                        yield RisingEdge(self.clock)
                        yield Timer(5000)
                        bx += 1

                        for pix in np.where(tot_hist > 0)[0]:
                            bv[pix] = '1'
                            total_hits += 1
                        self.hit.assign(str(bv))
                        self.bus.HIT <= self.hit
                        self.bus.TRIG_HIT <= trig
                        trig = 0
                        tot_hist[tot_hist > 0] -= 1
                        bv.setall(False)
                    if bxid == bx:
                        trig = trg
                        if((col >= 0) and (col < COLS) and (row >= 0) and (row < ROWS)):
                            #ANA_HIT[1024 * col_i + row_i]
                            pixn = col * ROWS + row
                            tot_hist[pixn] = tot_hist[pixn] + tot
                    else:
                        raise ValueError("Error,bxid={0:d},bx={1:d}, {2}".format(bxid, bx, bxid==bx))
                    #res=self.bus.RESET_HIT.value.integer
                    #if res==1:
                    #    break
            self.bus.HIT <= 0
            self.bus.TRIG_HIT <= 0
            logging.info('HitDataFile: bx={0:d} End of filename {1:s}'.format(bx,f))
        self.bus.READY_HIT <= 1
        yield RisingEdge(self.clock)
        yield Timer(5000)
        logging.info('=====================HitDataFile: %u hits sent to DUT', total_hits)