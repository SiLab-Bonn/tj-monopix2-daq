#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest

from tjmonopix2.tests.test_hardware import utils
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2


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

    def test_beam(self) -> None:
        # self.daq.configure_tlu_module()
        # self.daq.configure_tlu_veto_pulse(veto_length=500)
        # self.daq.enable_tlu_module()
        utils.wait_for_sim(self.dut, repetitions=512)


if __name__ == '__main__':
    unittest.main()
