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

import yaml

scan_configuration = {
    'start_column': 449,
    'stop_column': 480,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,

    # Target threshold
    'VCAL_LOW': 30,
    'VCAL_HIGH': 30+13
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

        # Read masked pixels from masked_pixels.yaml
        with open("output_data/module_0/chip_0/masked_pixels.yaml") as f:
            masked_pixels = yaml.full_load(f)

        for i in range(0, len(masked_pixels['masked_pixels'])):
            row = masked_pixels['masked_pixels'][i]['row']
            col = masked_pixels['masked_pixels'][i]['col']
            self.chip.masks.disable_mask[col, row] = False
            # self.chip.masks['tdac'][col, row] = 0 # --> Max solution to disable the pixel BUT not store in use_pixel NOR in masks.enable

        col_bad = [] #
        # W8R6 bad columns (246 to 251 included: double-cols will be disabled)
        col_bad += [248]

        # # W8R13 pixels that fire even when disabled
        # col_bad += list(range(383,415)) # chip w8r13
        # col_bad += list(range(0,40)) # chip w8r13

        # Disable readout for double-columns of col_disabled and those outside start_column:stop_column
        col_disabled = col_bad
        col_disabled += list(range(0, start_column & 0xfffe))
        col_disabled += list(range(stop_column + 1, 512))
        reg_values = [0xffff] * 16
        for col in col_disabled:
            dcol = col // 2
            reg_values[dcol//16] &= ~(1 << (dcol % 16))
        print(" ".join(f"{x:016b}" for x in reg_values))
        for i, v in enumerate(reg_values):
            # EN_RO_CONFsource /home/labb2/tj-monopix2-daq-development/venv/bin/activate
            self.chip._write_register(155+i, v)
            # EN_BCID_CONF (to disable BCID distribution on cols under test, use 0 instead of v, doing this the TOT is 0 since Le and trailing edge are not assigned BCID is missing)
            # To enable it all the matrix (higher I_LV and Temp), use  self.chip._write_register(171+i, 0xffff)
            # To enable only the used columns, use  self.chip._write_register(171+i, v)
            # To disable BCID distribution in all columns, use  self.chip._write_register(171+i, 0)
            #self.chip._write_register(171+i, v)
            self.chip._write_register(171+i, 0xffff)
            # self.chip._write_register(171+i, 0)
            # EN_RO_RST_CONF
            self.chip._write_register(187+i, v)
            # EN_FREEZE_CONF
            self.chip._write_register(203+i, v)
            # Read back
            print(f"{i:3d} {v:016b} {self.chip._get_register_value(155+i):016b} {self.chip._get_register_value(171+i):016b} {self.chip._get_register_value(187+i):016b} {self.chip._get_register_value(203+i):016b}")



        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        # W8R06 irradiated HVC used TB2024 run 1566 TH=15.9 @30C
        self.chip.registers["IBIAS"].write(100)
        self.chip.registers["ITHR"].write(30) #def 30
        self.chip.registers["ICASN"].write(30) #def 30
        self.chip.registers["IDB"].write(100)
        self.chip.registers["ITUNE"].write(250)
        self.chip.registers["IDEL"].write(88)
        self.chip.registers["IRAM"].write(50)
        self.chip.registers["VRESET"].write(50)
        self.chip.registers["VCASP"].write(40)
        self.chip.registers["VCASC"].write(140)
        self.chip.registers["VCLIP"].write(255)

        # # # W2R17 irradiated 2.5e14 DCC
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(40)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)



        # # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(10)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143)
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        #  # # W8R13 not irradiate
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(2)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(110) # TB 143 but this chip with VRESET at 110 doens't work well
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        # # configuration to monitor ITUNE
        #self.chip.registers["MON_EN_ITUNE"].write(1)
        #self.chip.registers["OVR_EN_ITUNE"].write(0)

        # # configuration to overwrite ITUNE
        # self.chip.registers["MON_EN_ITUNE"].write(0)
        # self.chip.registers["OVR_EN_ITUNE"].write(1) # 1 se voglio abilitare OVRITUNE


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
            print(f"Iteration {scan_param}")
            # Set new TDACs
            print("Setting TDACs =", self.data.tdac_map[start_column:stop_column, start_row:stop_row])
            self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = self.data.tdac_map[start_column:stop_column, start_row:stop_row]
            self.chip.masks.update()
            # Inject target charge
            with self.readout(scan_param_id=scan_param, callback=self.analyze_data_online):
                shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param,PulseStartCnfg=19)
            # Get hit occupancy using online analysis
            occupancy = self.data.hist_occ.get()
            print("Occupancy =", occupancy[start_column:stop_column, start_row:stop_row])

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
