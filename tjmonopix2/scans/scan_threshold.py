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

import yaml
import os

scan_configuration = {
    'start_column': 290,
    'stop_column': 292,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 140,
    'VCAL_LOW_start': 140-0,
    'VCAL_LOW_stop': 140-60,
    'VCAL_LOW_step': -1


}


class ThresholdScan(ScanBase):
    scan_id = 'threshold_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['hitor'][start_column:stop_column, start_row:stop_row] = True
        # print(f"WAS: {self.daq.rx_channels['rx0']['DATA_DELAY']} ___________________________-----")
        self.daq.rx_channels['rx0']['DATA_DELAY'] = 20

        # Read masked pixels from masked_pixels.yaml
        with open("output_data/module_0/chip_0/masked_pixels.yaml") as f:
            masked_pixels = yaml.full_load(f)

        for i in range(0, len(masked_pixels['masked_pixels'])):
            row = masked_pixels['masked_pixels'][i]['row']
            col = masked_pixels['masked_pixels'][i]['col']
            self.chip.masks.disable_mask[col, row] = False  

        # # TDAC=4 for threshold tuning 0b100
        # self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 4# TDAC=4 (default)

        #chip w8r13 bad cols
        # #Disable W8R13 bad/broken columns (25, 160, 161, 224, 274, 383-414 included, 447) and pixels
        # self.chip.masks['enable'][25,:] = False  # Many pixels don't fire

        # Noisy/hot W8R6 pixels AFTER IRRADIATION
        # for col, row in [(300, 138), (318, 318), (296, 333), (304, 246), (308, 322), (297, 485), (311, 260), (319, 382), (308, 508), (306, 58), (294, 488), (317, 395), (318, 308), (290, 257), (292, 133), (312, 279), (295, 419), (280, 76), (286, 31), (316, 17), (282, 374), (283, 284), (307, 185), (297, 92), (317, 137), (285, 411), (295, 378), (310, 98), (300, 7), (280, 69), (289, 299), (305, 177), (309, 479), (294, 479), (284, 173), (318, 339), (299, 230), (312, 111), (285, 288), (284, 111), (281, 197), (319, 360), (304, 301), (290, 42), (285, 122), (295, 396), (301, 373), (309, 396), (290, 183), (316, 94), (314, 152), (306, 383), (302, 417), (306, 323), (304, 440), (316, 502), (299, 103), (304, 137), (305, 195), (295, 71), (318, 494), (281, 202), (300, 249), (289, 216), (280, 97), (292, 45), (293, 88), (311, 154), (296, 498), (301, 304), (283, 437), (291, 347), (314, 345), (281, 231), (288, 316), (285, 239), (286, 216), (319, 509), (302, 432), (319, 427), (310, 449), (316, 253), (293, 190), (287, 481), (297, 276), (314, 466), (300, 132), (319, 319), (318, 505), (300, 200), (293, 124), (318, 322), (301, 179), (290, 320), (304, 442), (289, 91), (316, 138), (293, 270), (302, 257), (312, 385), (287, 159), (285, 484), (299, 474), (294, 270), (303, 278), (288, 412), (309, 399), (281, 80), (294, 288), (304, 482), (310, 8), (306, 95), (308, 79), (291, 316), (287, 498), (303, 332), (302, 348), (306, 256), (292, 61), (294, 184), (297, 95), (300, 263), (294, 241), (306, 127), (318, 40), (286, 315), (286, 504), (295, 481), (318, 218), (319, 486), (318, 174), (301, 336), (302, 217), (281, 353), (311, 498), (305, 420), (294, 87), (293, 165), (293, 349), (318, 304), (306, 222), (297, 32), (294, 171), (301, 118), (286, 441), (296, 274), (296, 184), (312, 198), (314, 502), (317, 355), (283, 215), (287, 76), (298, 120), (319, 60), (317, 44), (308, 163), (280, 469), (314, 15), (287, 410), (293, 414), (313, 443), (305, 410), (303, 159), (298, 196), (286, 257), (318, 228), (288, 24), (302, 57), (313, 38), (310, 67), (298, 44), (294, 90), (284, 70), (305, 339), (283, 164), (284, 463), (284, 114), (290, 225), (317, 402), (298, 253), (298, 392), (308, 198), (318, 177), (289, 360), (317, 491), (304, 228), (291, 245), (296, 170), (316, 432), (313, 321), (295, 491), (298, 470), (314, 247), (282, 153), (297, 59), (285, 262), (300, 257), (314, 490), (291, 115), (296, 465), (305, 19), (315, 424), (298, 486), (309, 476), (308, 177), (312, 287), (287, 510), (293, 496), (294, 214), (283, 134), (283, 402), (296, 212), (282, 314), (282, 313), (285, 374), (281, 366), (282, 310), (316, 143), (291, 372), (281, 320), (300, 337), (299, 231), (297, 73), (281, 330), (303, 424), (317, 370), (294, 89)]:
        #      self.chip.masks['enable'][col,row] = False

        col_bad = [] #
        # W8R6 bad columns (246 to 251 included: double-cols will be disabled)
        col_bad += [248]

        # # W8R13 pixels that fire even when disabled
        # col_bad += list(range(383,415)) # chip w8r13

        # Disable readout for double-columns of col_disabled and those outside start_column:stop_column
        col_disabled = list(col_bad)
        col_disabled += list(range(0, start_column & 0xfffe))
        col_disabled += list(range(stop_column + 1, 512))
        reg_values = [0xffff] * 16
        for col in col_disabled:
            dcol = col // 2
            reg_values[dcol//16] &= ~(1 << (dcol % 16))
        print(" ".join(f"{x:016b}" for x in reg_values))
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

        # Enable hitor outpu
        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)
        self.chip.registers["CMOS_TX_EN_CONF"].write(1)

        # vreset = os.getenv('VRESET')
        # self.chip.registers["VRESET"].write(int(vreset))
        # self.chip.registers["ICASN"].write(30)

        # # # W8R06 irradiated HVC used TB2024 run 1566 TH=15.9 @30C and W8R04
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


        # W8R06 irradiated DCC used TB2024 run 1484 THR=30.6 DAC and W8R4
        self.chip.registers["IBIAS"].write(100)
        self.chip.registers["ITHR"].write(64)  # TB ITHR=64
        self.chip.registers["ICASN"].write(10)  # TB ICASN=20
        self.chip.registers["IDB"].write(100)  # TB IDB=100
        self.chip.registers["ITUNE"].write(250)
        self.chip.registers["IDEL"].write(88)  #prebvious lab test data with 88
        self.chip.registers["IRAM"].write(50)
        self.chip.registers["VRESET"].write(143) # TB 143
        self.chip.registers["VCASP"].write(93)
        self.chip.registers["VCASC"].write(205)
        self.chip.registers["VCLIP"].write(255)

        # # # W2R17 irradiated 2.5e14 DCC
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

        # #W14R12 DCC 
        # self.chip.registers["ITHR"].write(64)
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["VRESET"].write(50)  #VRESET=50 for HVC
        # self.chip.registers["ICASN"].write(5)
        # self.chip.registers["IDB"].write(100)
        # self.chip.registers["ITUNE"].write(250)
        # self.chip.registers["IDEL"].write(255)
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(205) #by mistake was 255 in the THR scan for ITUNE in W8R13
        # self.chip.registers["VCLIP"].write(255)

        # #W14R12 DCC TB23 default parameters
        # self.chip.registers["ITHR"].write(60)
        # self.chip.registers["IBIAS"].write(100)
        # self.chip.registers["VRESET"].write(110)
        # self.chip.registers["ICASN"].write(2)
        # self.chip.registers["IDB"].write(100)
        # self.chip.registers["ITUNE"].write(190)
        # self.chip.registers["IDEL"].write(255)
        # self.chip.registers["VCASP"].write(93)
        # self.chip.registers["VCASC"].write(228)
        # self.chip.registers["VCLIP"].write(255)


        self.chip.registers["FREEZE_START_CONF"].write(250)
        self.chip.registers["READ_START_CONF"].write(253)
        self.chip.registers["READ_STOP_CONF"].write(255)
        self.chip.registers["LOAD_CONF"].write(270)
        self.chip.registers["FREEZE_STOP_CONF"].write(271)
        self.chip.registers["STOP_CONF"].write(271)


        # self.daq.rx_channels['rx0']['DATA_DELAY'] = 1

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
                #shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param_id)
                shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=pbar, scan_param_id=scan_param_id,PulseStartCnfg=19)
                # if we want to measure ANAMON0 and ANAMON1 at the same time, the following line inject in all rows at the same time
                # self.chip.inject(PulseStartCnfg=19, PulseStopCnfg=19+900, repetitions=n_injections, wait_cycles=1, latency=1400)
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
