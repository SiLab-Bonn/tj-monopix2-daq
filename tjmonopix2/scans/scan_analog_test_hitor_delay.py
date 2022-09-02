#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from tqdm import tqdm
import time

from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.shift_and_inject import shift_and_inject, get_scan_loop_mask_steps
from tjmonopix2.analysis import analysis

scan_configuration = {
    # 'start_column': 448,
    # 'stop_column': 464,
    'start_column': 511,
    'stop_column': 512,
    'start_row': 0,
    'stop_row': 512,
}

register_overrides = {
    'n_injections' : 20000,
    "CMOS_TX_EN_CONF": 1,
    'VL': 1,
    'VH': 140,
    'ITHR': 64,
    'IBIAS': 100,
    'VRESET': 143,
    'ICASN': 0,
    'VCASP': 93,
    'VCASC': 228,  # Default
    'IDB': 100
}

registers = ['IBIAS', 'ICASN', 'IDB', 'ITUNE', 'ITHR', 'ICOMP', 'IDEL', 'VRESET', 'VCASP', 'VH', 'VL', 'VCLIP', 'VCASC', 'IRAM']

class AnalogScan(ScanBase):
    scan_id = 'analog_scan'

    def _configure(self, start_column=0, stop_column=512, start_row=0, stop_row=512, **_):
        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['tdac'][start_column:stop_column, start_row:stop_row] = 0b100
        #self.chip.masks['hitor'][0, 0] = True

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        for r in self.register_overrides:
            if r != 'n_injections':
                self.chip.registers[r].write(self.register_overrides[r])
            #print("Write: ", r, " to ", self.register_overrides[r])

        # Enable hitor is in _scan()

        # Enable injection (active high) only on row 509 (the analog pixel) and no column (no matrix pixel)
        for i in range(512//16):
            scan.chip._write_register(82+i, 0xffff)
            scan.chip._write_register(114+i, 0xffff)
        # scan.chip._write_register(82, 0xffff)
        # scan.chip._write_register(114+31, 8192)

        # # Enable analog monitoring on HVFE
        # self.chip.registers["EN_PULSE_ANAMON_R"].write(1)
        # Enable analog monitoring on Normal FE
        self.chip.registers["EN_PULSE_ANAMON_L"].write(1)

        # Asked to do this by Lars Schall
        self.chip.registers['ANAMON_SFN_L'].write(0b0001)
        self.chip.registers['ANAMON_SFP_L'].write(0b1000)
        self.chip.registers['ANAMONIN_SFN1_L'].write(0b1000)
        self.chip.registers['ANAMONIN_SFN2_L'].write(0b1000)
        self.chip.registers['ANAMONIN_SFP_L'].write(0b1000)

        self.daq.rx_channels['rx0']['DATA_DELAY'] = 14

    def _scan(self, n_injections=50, **_):
        n_injections=self.register_overrides.get("n_injections", 50)

        with self.readout(scan_param_id=0):
            # Enable HITOR general output (active low)
            self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)
            # Enable HITOR (active high) on all columns, all rows
            for i in range(512//16):
                self.chip._write_register(18+i, 0xffff)
                self.chip._write_register(50+i, 0xffff)
            self.chip.inject(PulseStartCnfg=1, PulseStopCnfg=512, repetitions=n_injections, latency=1400)

        ret = {}
        for r in registers:
            ret[r] = self.chip.registers[r].read()
        self.scan_registers = ret

        self.log.success('Scan finished')

    def _analyze(self):
        self.hist_occ = 0
        self.hist_tot = 0
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()
            # self.hist_occ = a.hist_occ
            # self.hist_tot = a.hist_tot


if __name__ == "__main__":
    with AnalogScan(scan_config=scan_configuration, register_overrides=register_overrides) as scan:
        scan.start()
