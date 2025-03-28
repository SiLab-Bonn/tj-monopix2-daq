#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import time
import threading
from tqdm import tqdm

import yaml

from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.system.scan_base import ScanBase

scan_configuration = {
    'start_column': 449,
    'stop_column': 480,
    'start_row': 0,
    'stop_row': 512,

    'scan_timeout': 60,    # Timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time

    'tot_calib_file': None#'output_data/module_0/chip_0/20240806_121701_threshold_scan_interpreted.h5'    # path to ToT calibration file for charge to e⁻ conversion, if None no conversion will be done

}


class SourceScan(ScanBase):
    scan_id = 'source_scan'

    stop_scan = threading.Event()

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True

 # TDAC=4 for threshold tuning 0b100
        # self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 4 # TDAC=4 (default)

        # Read masked pixels from masked_pixels.yaml
        with open("output_data/module_0/chip_0/masked_pixels.yaml") as f:
            masked_pixels = yaml.full_load(f)

        for i in range(0, len(masked_pixels['masked_pixels'])):
            row = masked_pixels['masked_pixels'][i]['row']
            col = masked_pixels['masked_pixels'][i]['col']
            self.chip.masks.disable_mask[col, row] = False
            # self.chip.masks['tdac'][col, row] = 0 # --> Max solution to disable the pixel BUT not store in use_pixel NOR in masks.enable


        # Disable W8R13 bad/broken columns (25, 160, 161, 224, 274, 383-414 included, 447) and pixels
        #self.chip.masks['enable'][25,:] = False  # Many pixels don't fire
        #self.chip.masks['enable'][160:162,:] = False  # Wrong/random ToT
        # self.chip.masks['enable'][224,:] = False  # Many pixels don't fire
        #self.chip.masks['enable'][274,:] = False  # Many pixels don't fire
        #self.chip.masks['enable'][383:415,:] = False  # Wrong/random ToT
        #self.chip.masks['enable'][447,:] = False  # Many pixels don't fire
        # self.chip.masks['enable'][75,159] = False
        # self.chip.masks['enable'][163,219] = False
        # self.chip.masks['enable'][427,259] = False
        # self.chip.masks['enable'][219,161] = False # disab20230620_153108_threshold_scanle hottest pixel on chip
        # self.chip.masks['enable'][214,88] = False
        # self.chip.masks['enable'][215,101] = False
        # self.chip.masks['enable'][191:223,:] = False  # cols 191-223 are broken since Nov/dec very low THR



        col_bad = [] #
        # W8R6 bad columns (246 to 251 included: double-cols will be disabled)
        # col_bad = [248]
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
            # EN_RO_CONF
            self.chip._write_register(155+i, v)
            # EN_BCID_CONF (to disable BCID distribution on cols under test, use 0 instead of v, doing this the TOT is 0 since Le and trailing edge are not assigned BCID is missing)
            # if below is commented the BCID seems to be enabled in all the matrix higher I_LV and Temp
            # To enable it all the matrix (higher I_LV and Temp), use  self.chip._write_register(171+i, 0xffff)
            # To enable only the used columns, use  self.chip._write_register(171+i, v)
            # To disable BCID distribution in all columns, use  self.chip._write_register(171+i, 0)
            self.chip._write_register(171+i, 0xffff)
            #self.chip._write_register(171+i, 0)
            #self.chip._write_register(171+i, v)
            # EN_RO_RST_CONF
            self.chip._write_register(187+i, v)
            # EN_FREEZE_CONF
            self.chip._write_register(203+i, v)
            # Read back
            print(f"{i:3d} {v:016b} {self.chip._get_register_value(155+i):016b} {self.chip._get_register_value(171+i):016b} {self.chip._get_register_value(187+i):016b} {self.chip._get_register_value(203+i):016b}")





        self.chip.masks.apply_disable_mask()
        self.chip.masks.update()

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

        # # # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(20)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        # # W2R17 irradiated 2.5e14 DCC
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(20)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)


        # # # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        # self.chip.registers["ICASN"].write(20)  # TB ICASN=20
        # self.chip.registers["IDB"].write(100)  # TB IDB=100
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(143) # TB 143
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205)
        # self.chip.registers["VCLIP"].write(255)

        # #W8R06 irradiated HVC used TB2024 run 1566 TH=15.9
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["ITHR"].write(30)
        # self.chip.registers["ICASN"].write(30)
        # self.chip.registers["IDB"].write(100)
        # self.chip.registers["ITUNE"].write(200)
        # self.chip.registers["IDEL"].write(88)
        # self.chip.registers["IRAM"].write(50)
        # self.chip.registers["VRESET"].write(50)
        # self.chip.registers["VCASP"].write(40)
        # self.chip.registers["VCASC"].write(140)
        # self.chip.registers["VCLIP"].write(255)

        # #W8R06 HVC p-irradiatd after DESY 2024
        # self.chip.registers["ITHR"].write(30)
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["VRESET"].write(50)
        # self.chip.registers["ICASN"].write(15)
        # self.chip.registers["IDB"].write(150)
        # self.chip.registers["ITUNE"].write(200)
        # self.chip.registers["IDEL"].write(88)
        # self.chip.registers["VCASP"].write(40)
        # self.chip.registers["VCASC"].write(140)
        # self.chip.registers["VCLIP"].write(255)

        # W8R06 p-irradiatd after DESY 2024 TB settigns as in run 1566 with pwell = -0.%V and HV up to 30 V
    #  'ITHR':30,  # Default 64
    #  'IBIAS': 100,  # Default 50
    #  'VRESET': 50,  # Default TB 143, 110 for lower THR, Lars dec proposal 128
    #  'ICASN': 30,  # Lars proposed 54
    #  'VCASP': 40,  # Default 93
    #  "VCASC": 140,  # Lars proposed 150
    #  "IDB": 100,  # Default 100
    #  'ITUNE': 200,  # Default TB 53, 150 for lower THR tuning
    #  'VCLIP': 255,  # Default 255
    #  'IDEL':88, #def for dev branch


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
