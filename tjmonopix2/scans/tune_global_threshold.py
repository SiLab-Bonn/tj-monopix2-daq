#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    Finds the optimum global threshold value for target threshold using binary search.
'''

import numpy as np
from tqdm import tqdm

from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.scans.shift_and_inject import shift_and_inject
from tjmonopix2.analysis import online as oa


scan_configuration = {
    'start_column': 370,
    'stop_column': 372,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,

    # Target threshold
    'VCAL_LOW': 0,
    'VCAL_HIGH': 35,

    # This setting does not have to be changed, it only allows (slightly) faster retuning
    # E.g.: gdac_value_bits = [3, 2, 1, 0] uses the 4th, 3rd, 2nd, and 1st GDAC value bit.
    # GDAC is not an existing DAC, its value is mapped to ITHR currently
    'gdac_value_bits': range(7, -1, -1)
}


class GDACTuning(ScanBase):
    scan_id = 'global_threshold_tuning'

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

        self.chip.masks.apply_disable_mask()
        self.chip.masks.update(force=True)

        self.chip.registers["VL"].write(VCAL_LOW)
        self.chip.registers["VH"].write(VCAL_HIGH)

        self.chip.registers["ITHR"].write(50)
        self.chip.registers["SEL_PULSE_EXT_CONF"].write(0)

        self.data.hist_occ = oa.OccupancyHistogramming()

    def _scan(self, n_injections=100, gdac_value_bits=range(6, -1, -1), **_):
        '''
        Global threshold tuning main loop

        Parameters
        ----------
        n_injections : int
            Number of injections.
        gdac_value_bits : iterable
            Bits to toggle during tuning. Should be monotone.
        '''

        def update_best_gdacs(mean_occ, best_gdacs, best_gdac_offsets):
            if np.abs(mean_occ - n_injections / 2.) < best_gdac_offsets:
                best_gdac_offsets = np.abs(mean_occ - n_injections / 2.)
                best_gdacs = gdac_new
            return best_gdacs, best_gdac_offsets

        def write_gdac_registers(gdac):
            ''' Write new GDAC setting for enabled flavors '''
            self.chip.registers['ITHR'].write(gdac)
            self.chip.configuration['registers']['ITHR'] = int(gdac)

        # Set GDACs to start value
        start_value = 2 ** gdac_value_bits[0]
        # FIXME: keep track of chip config here, since it is not provided by bdaq53 yet?
        gdac_new = start_value
        best_gdacs = start_value

        # Only check pixel that can respond
        sel_pixel = np.zeros(shape=(512, 512), dtype=bool)
        sel_pixel[self.data.start_column:self.data.stop_column, self.data.start_row:self.data.stop_row] = True

        self.log.info('Searching optimal global threshold setting.')
        self.data.pbar = tqdm(total=len(gdac_value_bits) * self.chip.masks.get_mask_steps() * 2, unit=' Mask steps')
        for scan_param_id in range(len(gdac_value_bits)):
            # Set the GDAC bit in all flavours
            gdac_bit = gdac_value_bits[scan_param_id]
            gdac_new = np.bitwise_or(gdac_new, 1 << gdac_bit)
            write_gdac_registers(gdac_new)

            # Calculate new GDAC from hit occupancies: median pixel hits < n_injections / 2 --> decrease global threshold
            hist_occ = self.get_occupancy(scan_param_id, n_injections)
            mean_occ = np.median(hist_occ[sel_pixel])

            # Binary search does not have to converge to best solution for not exact matches
            # Thus keep track of best solution and set at the end if needed
            if not scan_param_id:  # First iteration --> initialize best gdac settings
                best_gdac_offset = np.abs(mean_occ - n_injections / 2.)
            else:  # Update better settings
                best_gdacs, best_gdac_offset = update_best_gdacs(mean_occ, best_gdacs, best_gdac_offset)

            # Seedup by skipping remaining iterations if result for all selected flavors is already found
            if (mean_occ == n_injections / 2.) | np.isnan(mean_occ):
                self.log.info('Found best result, skip remaining iterations')
                break

            # Update GDACS from measured mean occupancy
            if not np.isnan(mean_occ) and mean_occ < n_injections / 2.:  # threshold too low
                gdac_new = np.bitwise_and(gdac_new, ~(1 << gdac_bit))  # decrease threshold

        else:  # Loop finished but last bit = 0 still has to be checked
            self.data.pbar.close()
            scan_param_id += 1
            gdac_new = np.bitwise_and(gdac_new, ~(1 << gdac_bit))
            # Do not check if setting was already used before, safe time of one iteration
            if best_gdacs != gdac_new:
                write_gdac_registers(gdac_new)
                hist_occ = self.get_occupancy(scan_param_id, n_injections)
                mean_occ = np.median(hist_occ[:][sel_pixel[:]])
                best_gdacs, best_gdac_offset = update_best_gdacs(mean_occ, best_gdacs, best_gdac_offset)
        self.data.pbar.close()

        self.log.success('Optimal ITHR value is {0:1.0f} with mean occupancy {1:1.0f}'.format(best_gdacs, int(mean_occ)))

        # Set final result
        self.data.best_gdacs = best_gdacs
        write_gdac_registers(best_gdacs)
        self.data.hist_occ.close()  # stop analysis process

    def get_occupancy(self, scan_param_id, n_injections):
        ''' Analog scan and stuck pixel scan '''
        # Set new TDACs
        # Inject target charge
        with self.readout(scan_param_id=scan_param_id, callback=self.analyze_data_online):
            shift_and_inject(chip=self.chip, n_injections=n_injections, pbar=self.data.pbar, scan_param_id=scan_param_id)
        # Get hit occupancy using online analysis
        occupancy = self.data.hist_occ.get()

        return occupancy

    def analyze_data_online(self, data_tuple):
        raw_data = data_tuple[0]
        self.data.hist_occ.add(raw_data)
        super(GDACTuning, self).handle_data(data_tuple)

    def analyze_data_online_no_save(self, data_tuple):
        raw_data = data_tuple[0]
        self.data.hist_occ.add(raw_data)

    def _analyze(self):
        pass


if __name__ == '__main__':
    with GDACTuning(scan_config=scan_configuration) as tuning:
        tuning.start()
