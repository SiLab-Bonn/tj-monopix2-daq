#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest
import utils

from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.tjmonopix2 import TJMonoPix2


class TestFirmware(unittest.TestCase):
    def setUp(self) -> None:
        cfg = utils.setup_cocotb()
        self.daq = BDAQ53(conf=cfg)
        self.daq.init()

        self.dut = TJMonoPix2(daq=self.daq)
        self.dut.init()

        self.daq.rx_channels["rx0"].set_en(True)  # Enable rx module in FPGA

    def tearDown(self) -> None:
        self.daq.close()

    def test_something(self) -> None:
        self.dut.registers["VL"].write(38)
        reg = self.dut.registers["VL"].read()
        self.dut.write_command(self.dut.write_sync(write=False), repetitions=8)
        self.assertEqual(reg, 38)

if __name__ == '__main__':
    unittest.main()
