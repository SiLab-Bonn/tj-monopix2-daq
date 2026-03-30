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

import yaml

scan_configuration = {
    'start_column': 360,
    'stop_column': 448,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': 300,
    'min_occupancy': 10,
}


class NoiseOccScan(ScanBase):
    scan_id = 'noise_occupancy_scan'

    stop_scan = threading.Event()

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][:, :] = False

        # # Read masked pixels from masked_pixels.yaml
        # with open("output_data/module_0/chip_0/masked_pixels.yaml") as f:
        #     masked_pixels = yaml.full_load(f)

        # for i in range(0, len(masked_pixels['masked_pixels'])):
        #     row = masked_pixels['masked_pixels'][i]['row']
        #     col = masked_pixels['masked_pixels'][i]['col']
        #     self.chip.masks.disable_mask[col, row] = False
        #     # self.chip.masks['tdac'][col, row] = 0 # --> Max solution to disable the pixel BUT not store in use_pixel NOR in masks.enable


        col_bad = []
        # W8R6 bad columns (246 to 251 included: double-cols will be disabled)
        col_bad += [248]
        # col_bad += [436]
        # # W8R13 pixels that fire even when disabled
        # col_bad += list(range(383,415)) # chip w8r13
        # col_bad += list(range(0,40)) # chip w8r13
        # col_bad += list(range(448,512)) # HV col disabled
        # Disable readout for double-columns of col_disabled and those outside start_column:stop_column
        col_disabled = col_bad
        col_disabled += list(range(0, start_column & 0xfffe))
        col_disabled += list(range(stop_column + 1, 512))
        reg_values = [0xffff] * 16
        for col in col_disabled:
            dcol = col // 2
            reg_values[dcol//16] &= ~(1 << (dcol % 16))
        # print(" ".join(f"{x:016b}" for x in reg_values))
        for i, v in enumerate(reg_values):
            #print(f"test i {enumerate(reg_values)}")
            # EN_RO_CONFsource /home/labb2/tj-monopix2-daq-development/venv/bin/activate
            self.chip._write_register(155+i, v)
            # EN_BCID_CONF (to disable BCID distribution on cols under test, use 0 instead of v, doing this the TOT is 0 since Le and trailing edge are not assigned BCID is missing)
            # To enable it all the matrix (higher I_LV and Temp), use  self.chip._write_register(171+i, 0xffff)
            # To enable only the used columns, use  self.chip._write_register(171+i, v)
            # To disable BCID distribution in all columns, use  self.chip._write_register(171+i, 0)
            # self.chip._write_register(171+i, v)
            self.chip._write_register(171+i, 0xffff)
            # self.chip._write_register(171+i, 0)
            # EN_RO_RST_CONF
            self.chip._write_register(187+i, v)
            # EN_FREEZE_CONF
            self.chip._write_register(203+i, v)
            # Read back
            # print(f"{i:3d} {v:016b} {self.chip._get_register_value(155+i):016b} {self.chip._get_register_value(171+i):016b} {self.chip._get_register_value(187+i):016b} {self.chip._get_register_value(203+i):016b}")



        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        # # # # W8R06 irradiated HVC used TB2024 run 1566 TH=15.9 @30C and also W8R04
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(30) #def 30
        # self.chip.registers["ICASN"].write(30) #def 30
        # self.chip.registers["IDB"].write(100)
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(50)
        # self.chip.registers["VCASP"].write(40)
        # self.chip.registers["VCASC"].write(140)
        # self.chip.registers["VCLIP"].write(255)

        # # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC  and also W8R04
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(10)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        # # # configuration to monitor ITUNE
        # self.chip.registers["MON_EN_ITUNE"].write(1)
        # self.chip.registers["OVR_EN_ITUNE"].write(0)

        # # configuration to overwrite ITUNE
        # self.chip.registers["MON_EN_ITUNE"].write(0)
        # self.chip.registers["OVR_EN_ITUNE"].write(1) # 1 se voglio abilitare OVRITUNE


        self.daq.rx_channels['rx0']['DATA_DELAY'] = 14



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

            # If the two lines below are commented noisy pixels are not disabled in the interpreted.h5 file
            # self.chip.masks.disable_mask &= disable_mask
            # self.chip.masks.apply_disable_mask()

        # self.log.success('Found and disabled {0} noisy pixels.'.format(n_disabled_pixels))
        self.log.success('Found BUT NOT disabled {0} noisy pixels.'.format(n_disabled_pixels))

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with NoiseOccScan(scan_config=scan_configuration) as scan:
        scan.start()
