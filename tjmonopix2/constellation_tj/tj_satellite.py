from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
import threading
import yaml
import os

PROJECT_FOLDER = os.path.join(os.path.dirname(__file__), '..')
TESTBENCH_DEFAULT_FILE = os.path.join(PROJECT_FOLDER, 'testbench.yaml')

class TJ(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:
        configuration = config.get_dict()
        if configuration["tot_calib_file"] == "None":
            configuration["tot_calib_file"] = None
        if configuration["chip_config_file"] == "None":
            configuration["chip_config_file"] = None
        self.config_file = configuration

        with open(TESTBENCH_DEFAULT_FILE, 'r') as f:
            conf = yaml.full_load(f)
            conf['general']['output_directory'] = configuration['output_folder']
            conf['modules']['module_0']['chip_0']['chip_config_file'] = configuration['chip_config_file']

        with open(TESTBENCH_DEFAULT_FILE, 'w') as f:
            yaml.dump(conf, f)

        self.ext_trg_scan = ExtTriggerScan(scan_config=self.config_file)
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