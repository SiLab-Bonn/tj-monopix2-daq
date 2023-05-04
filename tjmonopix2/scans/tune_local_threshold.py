#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    Injection tuning:
    Iteratively inject target charge and evaluate if more or less than 50% of expected hits are seen in any pixel
'''

from tqdm import tqdm
import numpy as np

from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.shift_and_inject import shift_and_inject, get_scan_loop_mask_steps
from tjmonopix2.analysis import online as oa

scan_configuration = {
    'start_column': 0,
    'stop_column': 64,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,

    # Target threshold
    'VCAL_LOW': 30,
    'VCAL_HIGH': 55
}


class TDACTuning(ScanBase):
    scan_id = 'local_threshold_tuning'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, VCAL_LOW=30, VCAL_HIGH=60, **_):
        '''
        Parameters
        ----------
        start_column : int [0:512]
            First column to scan
        stop_column : int [0:512]
            Column to stop the scan. This column is excluded from the scan.
        start_row : int [0:512]
            First row to scan
        stop_row : int [0:512]
            Row to stop the scan. This row is excluded from the scan.

        VCAL_LOW : int
            Injection DAC low value.
        VCAL_HIGH : int
            Injection DAC high value.
        '''

        self.data.start_column, self.data.stop_column, self.data.start_row, self.data.stop_row = start_column, stop_column, start_row, stop_row
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 0b100

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["VL"].write(VCAL_LOW)
        self.chip.registers["VH"].write(VCAL_HIGH)

        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

        self.data.hist_occ = oa.OccupancyHistogramming()

    def _scan(self, start_column=0, stop_column=512, start_row=0, stop_row=512, n_injections=100, **_):
        '''
        Global threshold tuning main loop

        Parameters
        ----------
        n_injections : int
            Number of injections.
        '''

        target_occ = n_injections / 2

        self.data.tdac_map = np.zeros_like(self.chip.masks['tdac'])
        best_results_map = np.zeros((self.chip.masks['tdac'].shape[0], self.chip.masks['tdac'].shape[1], 2), dtype=float)
        retune = False  # Default is to start with default TDAC mask

        # Check if re-tune: In case one TDAC is not the default one.
        tdacs = self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row]
        if np.any(np.logical_and(tdacs != 0, tdacs != 4)):
            self.data.tdac_map[:] = self.chip.masks['tdac'][:]
            retune = True
            steps = [1, 1, 1, 1]
            self.log.info('Use existing TDAC mask (TDAC steps = {0})'.format(steps))

        # Define stepsizes and startvalues for TDAC in case of new tuning
        # Binary search will not converge if all TDACs are centered, so set
        #   half to 7 and half to 8 for LIN
        #   leave half at 0 and divide the other half between +1 and -1 for DIFF/ITkPixV1
        if not retune:
            steps = [2, 1, 1]
            self.data.tdac_map[max(0, start_column):min(512, stop_column), start_row:stop_row] = 4
            self.log.info('Use default TDAC mask (TDAC steps = {0})'.format(steps))

        self.log.info('Searching optimal local threshold settings')
        pbar = tqdm(total=get_scan_loop_mask_steps(self.chip) * len(steps), unit=' Mask steps')
        for scan_param, step in enumerate(steps):
            # Set new TDACs
            self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = self.data.tdac_map[start_column:stop_column, start_row:stop_row]
            self.chip.masks.update()
            # Inject target charge
            with self.readout(scan_param_id=scan_param, callback=self.analyze_data_online):
                shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param)
            # Get hit occupancy using online analysis
            occupancy = self.data.hist_occ.get()

            # Calculate best (closest to target) TDAC setting and update TDAC setting according to hit occupancy
            diff = np.abs(occupancy - target_occ)  # Actual (absolute) difference to target occupancy
            update_sel = np.logical_or(diff <= best_results_map[:, :, 1], best_results_map[:, :, 1] == 0)  # Closer to target than before
            best_results_map[update_sel, 0] = self.data.tdac_map[update_sel]  # Update best TDAC
            best_results_map[update_sel, 1] = diff[update_sel]  # Update smallest (absolute) difference to target occupancy (n_injections / 2)
            larger_occ_sel = (occupancy > target_occ + round(target_occ * 0.02))  # Hit occupancy larger than target
            self.data.tdac_map[larger_occ_sel] += step  # Increase threshold
            smaller_occ_and_not_stuck_sel = (occupancy < target_occ - round(target_occ * 0.02))  # Hit occupancy smaller than target
            self.data.tdac_map[smaller_occ_and_not_stuck_sel] -= step  # Decrease threshold

            # Make sure no invalid TDACs are used
            self.data.tdac_map[:, :] = np.clip(self.data.tdac_map[:, :], 1, 7)

        # Finally use TDAC value which yielded the closest to target occupancy
        self.data.tdac_map[:, :] = best_results_map[:, :, 0]

        pbar.close()
        self.data.hist_occ.close()  # stop analysis process
        self.log.success('Scan finished')

        enable_mask = self.chip.masks['enable'][start_column:stop_column, start_row:stop_row]
        tdac_mask = self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row]
        mean_tdac = np.mean(tdac_mask[enable_mask])
        self.log.success('Mean TDAC is {0:1.2f}.'.format(mean_tdac))
        self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = self.data.tdac_map[start_column:stop_column, start_row:stop_row]

    def analyze_data_online(self, data_tuple):
        raw_data = data_tuple[0]
        self.data.hist_occ.add(raw_data)
        super(TDACTuning, self).handle_data(data_tuple)

    def analyze_data_online_no_save(self, data_tuple):
        raw_data = data_tuple[0]
        self.data.hist_occ.add(raw_data)

    def _analyze(self):
        pass


if __name__ == '__main__':
    with TDACTuning(scan_config=scan_configuration) as tuning:
        tuning.start()
