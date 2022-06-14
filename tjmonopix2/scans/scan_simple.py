#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import time
import threading
from tqdm import tqdm

from tjmonopix2.analysis import analysis
from tjmonopix2.system.scan_base import ScanBase

scan_configuration = {
    'start_column': 0,
    'stop_column': 224,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': False,    # Timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time
    'max_triggers': 1000000,  # Number of maximum received triggers after stopping readout, if False no limit on received trigger
}


class SimpleScan(ScanBase):
    scan_id = 'simple_scan'

    stop_scan = threading.Event()

    def _configure(self, scan_timeout=10, max_triggers=False, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        if scan_timeout and max_triggers:
            self.log.warning('You should only use one of the stop conditions at a time.')

        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks.apply_disable_mask()
        self.chip.masks.update()

        self.daq.configure_tlu_veto_pulse(veto_length=500)
        self.daq.configure_tlu_module(max_triggers=max_triggers)

    def _scan(self, scan_timeout=10, max_triggers=False, **_):
        def timed_out():
            if scan_timeout:
                current_time = time.time()
                if current_time - start_time > scan_timeout:
                    self.log.info('Scan timeout was reached')
                    return True
            return False

        if scan_timeout:
            self.pbar = tqdm(total=scan_timeout, unit='')  # [s]
        elif max_triggers:
            self.pbar = tqdm(total=max_triggers, unit=' Triggers')
        start_time = time.time()

        with self.readout():
            self.stop_scan.clear()
            self.daq.enable_tlu_module()

            while not (self.stop_scan.is_set() or timed_out()):
                try:
                    if max_triggers:
                        triggers = self.daq.get_trigger_counter()
                    time.sleep(1)

                    # Update progress bar
                    try:
                        if scan_timeout:
                            self.pbar.update(1)
                        elif max_triggers:
                            self.pbar.update(self.daq.get_trigger_counter() - triggers)
                    except ValueError:
                        pass

                    # Stop scan if reached trigger limit
                    if max_triggers and triggers >= max_triggers:
                        self.stop_scan.set()
                        self.log.info('Trigger limit was reached: {0}'.format(max_triggers))

                except KeyboardInterrupt:  # React on keyboard interupt
                    self.stop_scan.set()
                    self.log.info('Scan was stopped due to keyboard interrupt')

        self.pbar.close()
        if max_triggers:
            self.daq.disable_tlu_module()

        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()


if __name__ == "__main__":
    with SimpleScan(scan_config=scan_configuration) as scan:
        scan.start()
