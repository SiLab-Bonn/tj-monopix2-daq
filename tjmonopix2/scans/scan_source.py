#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import time
import threading
from tqdm import tqdm

from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.system.scan_base import ScanBase

scan_configuration = {
    'start_column': 0,
    'stop_column': 224,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': 30,    # Timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time

    'tot_calib_file': None    # path to ToT calibration file for charge to e⁻ conversion, if None no conversion will be done
}


class SourceScan(ScanBase):
    scan_id = 'source_scan'

    stop_scan = threading.Event()

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks.apply_disable_mask()
        self.chip.masks.update()

    def _scan(self, scan_timeout=10, **_):
        def timed_out():
            if scan_timeout:
                current_time = time.time()
                if current_time - start_time > scan_timeout:
                    self.log.info('Scan timeout was reached')
                    return True
            return False

        self.pbar = tqdm(total=scan_timeout, unit='')  # [s]
        start_time = time.time()

        with self.readout():
            self.stop_scan.clear()

            while not (self.stop_scan.is_set() or timed_out()):
                try:
                    time.sleep(1)

                    # Update progress bar
                    try:
                        self.pbar.update(1)
                    except ValueError:
                        pass

                except KeyboardInterrupt:  # React on keyboard interupt
                    self.stop_scan.set()
                    self.log.info('Scan was stopped due to keyboard interrupt')

        self.pbar.close()
        self.log.success('Scan finished')

    def _analyze(self):
        tot_calib_file = self.configuration['scan'].get('tot_calib_file', None)
        if tot_calib_file is not None:
            self.configuration['bench']['analysis']['cluster_hits'] = True

        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', tot_calib_file=tot_calib_file, **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with SourceScan(scan_config=scan_configuration) as scan:
        scan.start()
