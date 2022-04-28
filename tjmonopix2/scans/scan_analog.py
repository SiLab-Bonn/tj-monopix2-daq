#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from tqdm import tqdm
 
from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.shift_and_inject import shift_and_inject, get_scan_loop_mask_steps
from tjmonopix2.analysis import analysis

scan_configuration = {
    'start_column': 0,
    'stop_column': 224,
    'start_row': 0,
    'stop_row': 512,
}


class AnalogScan(ScanBase):
    scan_id = 'analog_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 0b100
        #self.chip.masks['hitor'][0, 0] = True

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["ITHR"].write(50)
        self.chip.registers["IDB"].write(100)

        self.chip.registers["VL"].write(30)
        self.chip.registers["VH"].write(150)
        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

        self.daq.rx_channels['rx0']['DATA_DELAY'] = 14

    def _scan(self, n_injections=100, **_):
        pbar = tqdm(total=get_scan_loop_mask_steps(self), unit='Mask steps')
        with self.readout(scan_param_id=0):
            shift_and_inject(scan=self, n_injections=n_injections, pbar=pbar, scan_param_id=0)
        pbar.close()

        self.log.success('Scan finished')

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()


if __name__ == "__main__":
    with AnalogScan(scan_config=scan_configuration) as scan:
        scan.start()
