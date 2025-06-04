from constellation.core.configuration import Configuration
from constellation.core.satellite import Satellite
import time
from constellation.core.commandmanager import cscp_requestable
from constellation.core.cscp import CSCPMessage
from constellation.core.cmdp import MetricsType
from tjmonopix2.scans.scan_ext_trigger import ExtTriggerScan
import threading

class TJ(Satellite):
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

        'tot_calib_file': None    # path to ToT calibration file for charge to e⁻ conversion, if None no conversion will be done
        }
        self.ext_scan = ExtTriggerScan(scan_config=scan_configuration)
        self.ext_scan.init()

    def do_launching(self):
        self.ext_scan.configure()

    def do_run(self, payload=None) -> None:
        self.thread_scan = threading.Thread(target=self.ext_scan.scan)
        self.thread_scan.start()
        while not self._state_thread_evt.is_set():
            time.sleep(0.1)
        self.ext_scan.stop_scan.set()
        self.thread_scan.join()
        self.ext_scan.close()
        self.ext_scan.analyze()
