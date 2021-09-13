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

    def test_register_rw(self) -> None:
        self.dut.registers["VL"].write(38)
        reg = self.dut.registers["VL"].read()
        self.dut.write_command(self.dut.write_sync(write=False), repetitions=8)
        self.assertEqual(reg, 38)

    def test_rx(self) -> None:
        self.dut.registers["SEL_PULSE_EXT_CONF"].write(0)  # Use internal injection

        # Activate pixel (1, 1)
        self.dut.masks['enable'][1, 128] = True
        self.dut.masks['tdac'][1, 128] = 0b100
        self.dut.masks['injection'][1, 128] = True
        self.dut.masks.update()

        self.daq.reset_fifo()
        self.dut.inject(PulseStartCnfg=0, PulseStopCnfg=8, repetitions=5)
        utils.wait_for_sim(self.dut, repetitions=16)
        data = self.daq["FIFO"].get_data()
        hit, _ = self.dut.interpret_data(data)
        tot = (hit['te'] - hit['le']) & 0x7F
        self.assertListEqual(hit['col'].tolist(), [1] * 5)
        self.assertListEqual(hit['row'].tolist(), [128] * 5)
        self.assertListEqual(tot.tolist(), [1] * 5)


if __name__ == '__main__':
    unittest.main()
