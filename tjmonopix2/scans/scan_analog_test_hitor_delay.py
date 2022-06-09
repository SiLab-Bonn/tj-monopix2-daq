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
    'n_injections' : 50,
    "CMOS_TX_EN_CONF": 1,
    'VL': 30,
    'VH': 150,
    'ITHR': 30,
    'IBIAS': 60,
    'VCASC': 150,
    'ICASN': 8,
    'VCASP': 40,
    'VRESET': 100
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

        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

        for r in self.register_overrides:
            if r != 'n_injections':
                self.chip.registers[r].write(self.register_overrides[r])
            #print("Write: ", r, " to ", self.register_overrides[r])

        # Enable HITOR on all columns, no rows
        for i in range(512//16):
            self.chip._write_register(18+i, 0xffff)
            self.chip._write_register(50+i, 0)

        # Enable injection on last column, rows 0 and 509 (at the same time)
        for i in range(512//16):
            scan.chip._write_register(82+i, ~0)
            scan.chip._write_register(114+i, ~0)
        scan.chip._write_register(82+31, ~1)  # Last column
        scan.chip._write_register(114+0, ~1)  # First row
        # scan.chip._write_register(114+31, ~5)  # Last row + row 509
        scan.chip._write_register(114+31, ~4)

        # Enable analog monitoring on HVFE
        self.chip.registers["EN_PULSE_ANAMON_R"].write(1)

        self.daq.rx_channels['rx0']['DATA_DELAY'] = 14

    def _scan(self, n_injections=50, **_):
        n_injections=self.register_overrides.get("n_injections", 50)

        with self.readout(scan_param_id=0):
            # Enable HITOR only on the first 16 rows, and inject once
            self.chip._write_register(50+0, 0xffff)  # First row
            self.chip.inject(PulseStartCnfg=1, PulseStopCnfg=65, repetitions=1, latency=1400)

            # Wait, enable HITOR only on the last 16 rows, and inject once
            time.sleep(0.5)
            self.chip._write_register(50+0, 0)  # First row
            self.chip._write_register(50+31, 0xffff)  # Last row
            self.chip.inject(PulseStartCnfg=1, PulseStopCnfg=65,
                             repetitions=1, latency=1400)

        # pbar = tqdm(total=get_scan_loop_mask_steps(self), unit='Mask steps')
        # with self.readout(scan_param_id=0):
        #     shift_and_inject(scan=self, n_injections=n_injections, pbar=pbar, scan_param_id=0)
        # pbar.close()

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
            self.hist_occ = a.hist_occ
            self.hist_tot = a.hist_tot


if __name__ == "__main__":
    with AnalogScan(scan_config=scan_configuration, register_overrides=register_overrides) as scan:
        scan.start()
