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

import os
IDEL = int(os.environ.get('IDEL', 88))

scan_configuration = {
    'start_column': 100,
    'stop_column': 150,
    'start_row': 0,
    'stop_row': 512,
}

class AnalogScan(ScanBase):
    scan_id = 'analog_scan'
    is_parallel_scan = False

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True
        # self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 0b100
        self.chip.masks['hitor'][start_column:stop_column, start_row:stop_row] = True

        # Enable readout and bcid/freeze distribution only to columns we actually use
        dcols_enable = [0] * 16
        for c in range(start_column, stop_column):
            dcols_enable[c // 32] |= (1 << ((c >> 1) & 15))
        for c in []:  # List of disabled columns
            dcols_enable[c // 32] &= ~(1 << ((c >> 1) & 15))
        for i, v in enumerate(dcols_enable):
            self.chip._write_register(155 + i, v)  # EN_RO_CONF
            self.chip._write_register(171 + i, v)  # EN_BCID_CONF
            self.chip._write_register(187 + i, v)  # EN_RO_RST_CONF
            self.chip._write_register(203 + i, v)  # EN_FREEZE_CONF

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["IDEL"].write(IDEL)

        self.chip.registers["CMOS_TX_EN_CONF"].write(1)

        self.chip.registers["VL"].write(1)
        self.chip.registers["VH"].write(140)
        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

    def _scan(self, n_injections=100, **_):
        pbar = tqdm(total=get_scan_loop_mask_steps(self.chip), unit='Mask steps')
        with self.readout(scan_param_id=0):
            shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=0)
        pbar.close()

        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with AnalogScan(scan_config=scan_configuration) as scan:
        scan.start()
