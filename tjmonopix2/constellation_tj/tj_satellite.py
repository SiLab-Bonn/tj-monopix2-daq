from constellation.core.configuration import Configuration
from constellation.core.message.cscp1 import SatelliteState
from constellation.core.monitoring import schedule_metric
from constellation.core.transmitter_satellite import TransmitterSatellite

import time
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
import threading
import yaml
import os
from typing import Any

PROJECT_FOLDER = os.path.join(os.path.dirname(__file__), '..')
TESTBENCH_DEFAULT_FILE = os.path.join(PROJECT_FOLDER, 'testbench.yaml')

class TJ(TransmitterSatellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:

        scan_configuration = {
            'start_column': 0,
            'stop_column': 224,
            'start_row': 0,
            'stop_row': 512,

            'scan_timeout': False,    # Timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time
            'max_triggers': 1000000,  # Number of maximum received triggers after stopping readout, if False no limit on received trigger

            'tot_calib_file': None,
            'output_folder' : '/home/rasmus/Documents/constellation_tests'   # path to ToT calibration file for charge to e⁻ conversion, if None no conversion will be done
        }

        with open(TESTBENCH_DEFAULT_FILE, 'r') as f:
            conf = yaml.full_load(f)
            conf['general']['output_directory'] = scan_configuration.get('output_folder')
            conf['modules']['module_0']['chip_0']['chip_config_file'] = scan_configuration.get('chip_config_file')

        with open(TESTBENCH_DEFAULT_FILE, 'w') as f:
            yaml.dump(conf, f)

        self.ext_trg_scan = ExtTriggerScan(scan_config=self.configuration)
        self.ext_trg_scan.init()
        return "init done"

    def do_launching(self):
        self.ext_trg_scan.configure()
        return "launching done"

    def do_run(self, payload=None) -> None:
        self.thread_scan = threading.Thread(target=self.ext_trg_scan.scan)
        self.thread_scan.start()
        while not self._state_thread_evt.is_set():
            time.sleep(1)
        self.ext_trg_scan.stop_scan.set()
        self.thread_scan.join()
        self.ext_trg_scan.close()
        self.ext_trg_scan.analyze()
        return "running done"
    
    @schedule_metric("", 1)
    def trigger_number(self) -> Any:
        if self.fsm.current_state_value == SatelliteState.RUN:
            return self.ext_trg_scan.daq.get_trigger_counter()
        else:
            return None