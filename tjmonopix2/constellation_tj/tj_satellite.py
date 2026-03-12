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


class TJMonopix2(TransmitterSatellite):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_initializing(self, config: Configuration) -> None:
        try:
            self.ext_trg_scan.close()
        except AttributeError:
            pass
        self._load_config(config)
        self.ext_trg_scan = ExtTriggerScan(scan_config=self.scan_configuration, bench_config=self.bench_conf)
        self.ext_trg_scan.init()
        return "initializing done"

    def do_launching(self):
        self.ext_trg_scan._init_environment()
        self.ext_trg_scan._init_hardware(force=False)
        self.ext_trg_scan.initialized = True
        self.ext_trg_scan.configure()
        return "launching done"

    def do_run(self, payload=None) -> None:
        self.ext_trg_scan._init_files()
        if hasattr(self.ext_trg_scan, "stop_scan"):
            self.ext_trg_scan.stop_scan.clear()
        self.thread_scan = threading.Thread(target=self.ext_trg_scan.scan)
        self.thread_scan.start()
        while not self._state_thread_evt.is_set():
            time.sleep(1)
        self.ext_trg_scan.stop_scan.set()
        self.thread_scan.join()
        self.ext_trg_scan.analyze()
        return "running done"

    def do_reconfigure(self, config: Configuration) -> str:
        self.ext_trg_scan.close()
        self._load_config(config)
        self.ext_trg_scan = ExtTriggerScan(scan_config=self.scan_configuration, bench_config=self.bench_conf)
        self.ext_trg_scan.init()
        return "reconfiguring done"

    def _load_config(self, config: Configuration) -> None:
        config.set_default(key='tot_calib_file', value=None)
        config.set_default(key='output_directory', value=None)
        config.set_default(key='chip_config_file', value=None)
        config.set_default(key='testbench_path', value=os.path.join(os.path.join(os.path.dirname(__file__), '..'), 'testbench.yaml'))
        config.set_default(key='scan_timeout', value=False)

        config.set_default(key='send_data', value="tcp://127.0.0.1:5500")
        config.set_default(key='trigger_mode', value="eudet")
        config.set_default(key='create_pdf', value=True)

        self.scan_configuration = {
            'start_column': config.get_int(key='start_column'),
            'stop_column': config.get_int(key='stop_column'),
            'start_row': config.get_int(key='start_row'),
            'stop_row': config.get_int(key='stop_row'),

            'scan_timeout': config.get_int(key='scan_timeout'),
            'max_triggers': config.get_int(key='max_triggers'),

            'tot_calib_file': config.get(key='tot_calib_file'),
        }

        self.trigger_mode = config.get('trigger_mode')

        with open(config.get_path(key='testbench_path', check_exists=True), 'r') as f:
            self.bench_conf = yaml.full_load(f)
            self.bench_conf['general']['output_directory'] = config.get(key='output_directory')
            self.bench_conf['modules']['module_0']['chip_0']['chip_config_file'] = config.get('chip_config_file')
            self.bench_conf['modules']['module_0']['chip_0']['chip_sn'] = config.get('chip_sn')
            self.bench_conf['modules']['module_0']['chip_0']['send_data'] = config.get('send_data')
            self.bench_conf['analysis']['create_pdf'] = config.get('create_pdf')
            if self.trigger_mode == 'aida':
                self.bench_conf['TLU']['TRIGGER_MODE'] = 2
                self.bench_conf['TLU']['TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES'] = 1

    @schedule_metric("", 1)
    def trigger_number(self) -> Any:
        if self.fsm.current_state_value == SatelliteState.RUN:
            return self.ext_trg_scan.daq.get_trigger_counter()
        else:
            return None
