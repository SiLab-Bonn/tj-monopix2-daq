from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
import threading

class TJ(Satellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:
        configuration = config.get_dict()
        if configuration["tot_calib_file"] == "None":
            configuration["tot_calib_file"] = None
        self.config_file = configuration

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