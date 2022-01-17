#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest
import numpy as np
import tables as tb

from tjmonopix2.tests.test_hardware import utils
from tjmonopix2.scans.scan_analog import AnalogScan
from tjmonopix2.scans.scan_simple import SimpleScan

scan_analog_configuration = {
    'start_column': 0,
    'stop_column': 2,
    'start_row': 0,
    'stop_row': 512,
    'n_injections': 5
}

scan_simple_configuration = {
    'start_column': 0,
    'stop_column': 2,
    'start_row': 0,
    'stop_row': 512
}


class TestScans(unittest.TestCase):
    def test_analog_scan(self) -> None:
        with AnalogScan(daq_conf=utils.setup_cocotb(), scan_config=scan_analog_configuration) as scan:
            scan.start()
            filename = scan.output_filename + '_interpreted.h5'

        with tb.open_file(filename) as in_file:
            occ = in_file.root.HistOcc[:].sum(axis=2)

        self.assertEqual(np.count_nonzero(occ), 512 * 2)
        self.assertEqual(np.sum(occ), 512 * 2 * scan_analog_configuration['n_injections'])


if __name__ == '__main__':
    unittest.main()
