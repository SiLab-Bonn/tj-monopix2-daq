#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import time
import threading
import numpy as np
import tables as tb
from tqdm import tqdm

from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.system.scan_base import ScanBase

scan_configuration = {
    'start_column': 0,
    'stop_column': 448,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': 10,
    'min_occupancy': 1,
}


class NoiseOccScan(ScanBase):
    scan_id = 'noise_occupancy_scan'

    stop_scan = threading.Event()

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][:, :] = False

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

    def _scan(self, start_column=0, stop_column=400, start_row=0, stop_row=192, scan_timeout=2, min_occupancy=1, **_):
        '''
        Noise occupancy scan main loop

        Parameters
        ----------
        scan_timeout : int
            Time of data taking
        min_occupancy : int
            Maximum allowed hits for a pixel to not be classified noisy
        '''

        def timed_out():
            if scan_timeout:
                current_time = time.time()
                if current_time - start_time > scan_timeout:
                    return True
            return False

        self.data.n_pixels = (stop_column - start_column) * (stop_row - start_row)
        self.data.min_occupancy = min_occupancy
        
        self.pbar = tqdm(total=scan_timeout, unit='')
        start_time = time.time()

        with self.readout():
            self.stop_scan.clear()
            while not (self.stop_scan.is_set() or timed_out()):
                # Update progress bar
                time.sleep(1)
                self.pbar.update(1)

        self.pbar.close()
        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()
            with tb.open_file(a.analyzed_data_file) as in_file:
                occupancy = in_file.root.HistOcc[:].sum(axis=2)
                disable_mask = ~(occupancy > self.data.min_occupancy)  # Mask everything larger than min. occupancy
            n_disabled_pixels = np.count_nonzero(np.concatenate(np.invert(disable_mask)))
            self.chip.masks.disable_mask &= disable_mask
            self.chip.masks.apply_disable_mask()

        self.log.success('Found and disabled {0} noisy pixels.'.format(n_disabled_pixels))

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with NoiseOccScan(scan_config=scan_configuration) as scan:
        scan.start()