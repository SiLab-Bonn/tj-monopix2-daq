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
import time

scan_configuration = {
    'start_column': 448,
    'stop_column': 512,
    'start_row': 0,
    'stop_row': 512,
}


class TemperatureScan(ScanBase):
    scan_id = 'temperature_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        prev = self.daq.get_temperature_NTC(connector=7)
        while(True):
            temp =  self.daq.get_temperature_NTC(connector=7)
            self.log.info(f'Chip temperature: {temp:03.2f}C, delta: {(temp-prev)*2:03.2f}C/min')
            prev = temp
            time.sleep(1)

    def _scan(self, n_injections=100, **_):
        print('This should never execute')

    def _analyze(self):
        print('This should never execute')


if __name__ == "__main__":
    with TemperatureScan(scan_config=scan_configuration) as scan:


        scan.start()
