#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest
import utils
from basil.utils.sim.utils import cocotb_compile_clean

from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.tjmonopix2 import TJMonoPix2


class TestFirmware(unittest.TestCase):
    def setUp(self) -> None:
        cfg = utils.setup_cocotb()
        self.daq = BDAQ53(conf=cfg)
        self.daq.init()

        self.dut = TJMonoPix2(daq=self.daq)
        self.dut.init()

    def tearDown(self) -> None:
        self.daq.close()
        # cocotb_compile_clean()

    def test_something(self) -> None:
        self.dut.registers["VL"].write(35)

if __name__ == '__main__':
    unittest.main()
