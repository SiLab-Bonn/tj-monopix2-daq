import tables as tb
from tjmonopix2.analysis import analysis, plotting
import numpy as np
from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis import analysis, plotting
from numba import njit
from pathlib import Path

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

@njit
def _calc_mean_avg(array, weights):
    return np.sum(array * weights) / np.sum(weights)


def find_latest_file(path: str, index: str):
    """Find latest file that includes a given subset of strings called index in directory.

    Args:
        path (str): Path to directory. For same directory as python script use for e.q. './target_dir'.
        index (str): Find specific characters in filename.

    Returns:
        path: Path to file in target Director. Use str(find_latest_path(.)) to obtain path as string.
    """
    p = Path(path)
    return max(
        [x for x in p.iterdir() if x.is_file() and index in str(x)],
        key=lambda item: item.stat().st_ctime,
    )

if __name__ == "__main__":

    for run in ["run_26"]:

        try:
            input_path = '/mnt/data/DESY_NOV_2025/' + run + '/'

            input_file = str(find_latest_file(path=input_path, index="threshold_scan.h5"))

            with analysis.Analysis(raw_data_file=input_file) as a:
                a.analyze_data()

            print("Calibrating ToT...")

            analyzed_data_file = input_file[:-3] + '_interpreted.h5'
            with tb.open_file(analyzed_data_file, 'r') as in_file:
                HistTot = in_file.root.HistTot[:, :]
                scan_params = in_file.root.configuration_in.scan.scan_params[:]

            scan_parameter_range = np.array(scan_params['vcal_high'] - scan_params['vcal_low'], dtype=float)
            tot_avg = _create_tot_avg(HistTot)
            inj_tot_cal = au.fit_tot_response_multithread(tot_avg=tot_avg.reshape(512 * 512, -1), scan_params=scan_parameter_range)

            print("{0} pixels with successful ToT calibration".format(int(np.count_nonzero(inj_tot_cal[:, :]) / 4)))

            with tb.open_file(analyzed_data_file, 'r+') as out_file:
                out_file.create_carray(out_file.root,
                                        name='InjTotCalibration',
                                        title='Injection Tot Calibration Fit',
                                        obj=inj_tot_cal,
                                        filters=tb.Filters(complib='blosc',
                                                            complevel=5,
                                                            fletcher32=False))

            with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                p.create_standard_plots()
        except:
            pass