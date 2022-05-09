#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import logging
import os
import shutil
import time
import unittest

import tjmonopix2
import yaml
from tjmonopix2.scans.scan_analog import AnalogScan
from tjmonopix2.tests.test_software import utils as sw_utils
from tjmonopix2.tests.test_software.mock import TJMonopix2_Mock

scan_configuration = {
    'start_column': 0,
    'stop_column': 512,
    'start_row': 0,
    'stop_row': 512,
    'n_injections': 50
}

tjmonopix2_path = os.path.dirname(tjmonopix2.__file__)
bench_config = os.path.abspath(os.path.join(tjmonopix2_path, 'testbench.yaml'))


class TestScans(unittest.TestCase):
    """ Testing scan scripts with mocked BDAQ53 class to run without actual hardware.
    This test just covers software and does not check for actual chip behavior and data.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Load standard bench config to change in test cases
        with open(bench_config) as f:
            cls.bench_config = yaml.full_load(f)
        cls.bench_config['analysis']['skip'] = True  # deactivate failing feature

        cls.hw_mock = TJMonopix2_Mock()
        cls.hw_mock.start()

    def test_scans(self) -> None:
        # Catch scan output to check for errors reported
        scan_logger = logging.getLogger(AnalogScan.__name__)
        scan_log_handler = sw_utils.MockLoggingHandler(level='DEBUG')
        scan_logger.addHandler(scan_log_handler)
        scan_log_messages = scan_log_handler.messages

        with AnalogScan(scan_config=scan_configuration, bench_config=self.bench_config) as scan:
            scan.start()

        assert self.check_scan_success(scan_log_messages)

    def check_scan_success(self, scan_log_messages: dict) -> bool:
        """ Check the log output if scan was successfull """
        if scan_log_messages['error']:
            return False
        if 'Scan finished' not in scan_log_messages['success'] or 'All done!' not in scan_log_messages['success']:
            return False
        return True

    def tearDown(self) -> None:
        self.hw_mock.reset()
        shutil.rmtree('output_data', ignore_errors=True)  # always delete output from previous test
        time.sleep(0.25)  # shutil.rmtree does not block until file is really deleted, https://bugs.python.org/issue22024

    @classmethod
    def tearDownClass(cls) -> None:
        cls.hw_mock.stop()


if __name__ == "__main__":
    unittest.main()
