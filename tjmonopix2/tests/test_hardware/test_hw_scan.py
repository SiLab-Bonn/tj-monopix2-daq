#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import unittest

import numpy as np
import tables as tb
from basil.utils.sim.utils import cocotb_compile_clean
from tjmonopix2.scans.scan_analog import AnalogScan
from tjmonopix2.tests.test_hardware import utils as hw_utils

scan_analog_configuration = {
    'start_column': 0,
    'stop_column': 2,
    'start_row': 0,
    'stop_row': 512,
    'n_injections': 2
}


@unittest.skip
class ScanTest(unittest.TestCase):
    """ Test that runs an actual analog scan on simulated hardware.
    Skipped by default, because runtime is very long.
    """
    def tearDown(self) -> None:
        cocotb_compile_clean()

    def test_analog_scan(self) -> None:
        with AnalogScan(daq_conf=hw_utils.setup_cocotb(), scan_config=scan_analog_configuration) as scan:
            scan.start()
            filename = scan.output_filename + '_interpreted.h5'

        with tb.open_file(filename) as in_file:
            occ = in_file.root.HistOcc[:].sum(axis=2)

        n_cols = scan_analog_configuration['stop_column'] - scan_analog_configuration['start_column']
        n_rows = scan_analog_configuration['stop_row'] - scan_analog_configuration['start_row']

        assert np.count_nonzero(occ) == n_rows * n_cols
        assert np.sum(occ) == n_rows * n_cols * scan_analog_configuration['n_injections']


if __name__ == '__main__':
    unittest.main()
