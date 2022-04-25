#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest

from basil.dut import Dut
from basil.utils.sim.utils import cocotb_compile_clean
from tjmonopix2.tests.test_hardware import utils


class FirmwareTest(unittest.TestCase):
    def setUp(self) -> None:
        conf = utils.setup_cocotb()
        self.daq, self.dut = utils.init_device(conf)

    def tearDown(self) -> None:
        self.daq.close()
        cocotb_compile_clean()

    def test_register_rw(self) -> None:
        self.dut.registers["VL"].write(38)
        reg = self.dut.registers["VL"].read()
        print(reg)
        self.dut.write_command(self.dut.write_sync(write=False), repetitions=8)
        assert reg == 38

    def test_rx(self) -> None:
        self.dut.registers["SEL_PULSE_EXT_CONF"].write(0)  # Use internal injection

        # Activate pixel (1, 128)
        self.dut.masks['enable'][1, 128] = True
        self.dut.masks['tdac'][1, 128] = 0b100
        self.dut.masks['injection'][1, 128] = True
        self.dut.masks.update()

        self.daq.reset_fifo()
        self.dut.inject(PulseStartCnfg=0, PulseStopCnfg=8, repetitions=5)
        utils.wait_for_sim(self.dut, repetitions=4)
        data = self.daq["FIFO"].get_data()
        hit, _ = self.dut.interpret_data(data)
        tot = (hit['te'] - hit['le']) & 0x7F
        assert hit['col'].tolist() ==  [1] * 5
        assert hit['row'].tolist() == [128] * 5
        assert tot.tolist() == [1] * 5


if __name__ == "__main__":
    unittest.main()