#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.scans.shift_and_inject import (get_scan_loop_mask_steps,
                                               shift_and_inject)
from tjmonopix2.system.scan_base import ScanBase
from tqdm import tqdm

scan_configuration = {
    'start_column': 0,
    'stop_column': 4,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 200,
    'VCAL_LOW_start': 180,
    'VCAL_LOW_stop': 100,
    'VCAL_LOW_step': -1
}


class ThresholdScan(ScanBase):
    scan_id = 'threshold_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

    def _scan(self, n_injections=100, VCAL_HIGH=80, VCAL_LOW_start=80, VCAL_LOW_stop=40, VCAL_LOW_step=-1, **_):
        """
        Injects charges from VCAL_LOW_START to VCAL_LOW_STOP in steps of VCAL_LOW_STEP while keeping VCAL_HIGH constant.
        """

        self.chip.registers["VH"].write(VCAL_HIGH)
        vcal_low_range = range(VCAL_LOW_start, VCAL_LOW_stop, VCAL_LOW_step)

        pbar = tqdm(total=get_scan_loop_mask_steps(self.chip) * len(vcal_low_range), unit='Mask steps')
        for scan_param_id, vcal_low in enumerate(vcal_low_range):
            self.chip.registers["VL"].write(vcal_low)

            self.store_scan_par_values(scan_param_id=scan_param_id, vcal_high=VCAL_HIGH, vcal_low=vcal_low)
            with self.readout(scan_param_id=scan_param_id):
                shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param_id)
        pbar.close()
        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with ThresholdScan(scan_config=scan_configuration) as scan:
        scan.start()
