#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import numpy as np
import tables as tb

from numba import njit

from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis import analysis, plotting
from tjmonopix2.scans.scan_threshold import ThresholdScan

scan_configuration = {
    'start_column': 0,
    'stop_column': 32,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 145,
    'VCAL_LOW_start': 130,
    'VCAL_LOW_stop': 0,
    'VCAL_LOW_step': -1,
}


@njit
def _calc_mean_avg(array, weights):
    return np.sum(array * weights) / np.sum(weights)


@njit
def _create_tot_avg(array):
    original_shape = array.shape
    array = array.reshape((original_shape[0] * original_shape[1], original_shape[2], original_shape[3]))
    tot_avg = np.zeros((array.shape[0], array.shape[1]))

    # loop through all pixels
    for pixel in range(array.shape[0]):
        for idx in range(array.shape[1]):
            if array[pixel, idx].any() != 0:
                tot_avg[pixel, idx] = _calc_mean_avg(np.arange(0, 128, 1), array[pixel, idx])

    return np.reshape(tot_avg, (original_shape[0], original_shape[1], original_shape[2]))


class CalibrateToT(ThresholdScan):
    scan_id = 'calibrate_tot'

    def _analyze(self):
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        self.log.info("Calibrating ToT...")

        analyzed_data_file = self.output_filename + '_interpreted.h5'
        with tb.open_file(analyzed_data_file, 'r') as in_file:
            HistTot = in_file.root.HistTot[:, :]
            scan_params = in_file.root.configuration_in.scan.scan_params[:]

        scan_parameter_range = np.array(scan_params['vcal_high'] - scan_params['vcal_low'], dtype=float)
        tot_avg = _create_tot_avg(HistTot)
        inj_tot_cal = au.fit_tot_inj_multithread(tot_avg=tot_avg.reshape(512 * 512, -1), scan_params=scan_parameter_range)

        self.log.success("{0} pixels with successful ToT calibration".format(int(np.count_nonzero(inj_tot_cal[:, :]) / 4)))

        with tb.open_file(analyzed_data_file, 'r+') as out_file:
            out_file.create_carray(out_file.root,
                                   name='InjTotCalibration',
                                   title='Injection Tot Calibration Fit',
                                   obj=inj_tot_cal,
                                   filters=tb.Filters(complib='blosc',
                                                      complevel=5,
                                                      fletcher32=False))

        if self.configuration['bench']['analysis']['create_pdf']:
            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()


if __name__ == "__main__":
    with CalibrateToT(scan_config=scan_configuration) as scan:
        scan.start()
