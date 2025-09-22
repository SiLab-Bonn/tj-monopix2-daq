# start with taskset -c 0  python threshold_plot.py -p path_to_files

import argparse
import os
import sys
import shutil
from datetime import datetime
import matplotlib.backends.backend_pdf as pdf

import numpy as np
import tables as tb
import matplotlib.pyplot as plt
from matplotlib import cm
from matplotlib import colormaps
from matplotlib.colors import ListedColormap
from scipy.optimize import curve_fit
#from tqdm import tqdm
from typing import List, Tuple
import pandas as pd
import matplotlib.ticker as ticker
import matplotlib.colors as colors
from matplotlib.backends.backend_pdf import PdfPages

DEFAULT_PATH = '/home/labb2/tj-monopix2-daq-development/tjmonopix2/scans/output_data/module_0/chip_0/'


def find_latest_file(directory, partial_name):
    # List all files in the given directory
    files = [f for f in os.listdir(directory) if partial_name in f and os.path.isfile(os.path.join(directory, f))]

    if not files:
        print("No files found with the specified name part.")
        return None

    # Find the latest file based on modification time
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(directory, f)))

    # Return the latest file with its full path
    return os.path.join(directory, latest_file)


# Parse the path to the folder as an argument
parser = argparse.ArgumentParser(
    description='Combine HistOcc arrays from multiple h5 files')
# parser.add_argument('-p', '--path',type=str, default='/home/labb2/tj-monopix2-daq-development/tjmonopix2/scans/output_data/module_0/chip_0/',
#                     help='Path to the folder containing h5 files (default: %(default)s)')
# parser.add_argument('-f', '--file_name', type=str, default=None,
#                     help='Ph5 filename (default: latest .h5 file in path if not specified)')
parser.add_argument('-f', '--input_file', type=str, default=None,
                    help='Full path to HDF5 file or just the file name (from default path). If not provided, the latest .h5 file in default path is used.')
parser.add_argument('-fit_HV', '--fit_range_HV', type=int,
                    default=0,
                    help='where the fit range starts in DAC')
parser.add_argument('-fit_HVCASC', '--fit_range_HVCASC', type=int,
                    default=0,
                    help='where the fit range starts in DAC')
parser.add_argument('-fit_NF', '--fit_range_NF', type=int,
                    default=0,
                    help='where the fit range starts in DAC')
parser.add_argument('-fit_NFCASC', '--fit_range_NFCASC', type=int,
                    default=0,
                    help='where the fit range starts in DAC')
parser.add_argument('-plot', '--plot_range', type=int,
                    default=0,
                    help='where the plot range starts in DAC')
parser.add_argument('-center', '--center', type=int,
                    default=0,
                    help='givees center for threshold fit, if needed')
args = parser.parse_args()

viridis = cm.get_cmap('viridis', 256)
# viridis = colormaps.get_cmap('viridis').resampled(256)
newcolors = viridis(np.linspace(0, 1, 256))
white = np.array([1, 1, 1, 1])
newcolors[0, :] = white
newcmp = ListedColormap(newcolors)


d_fixed=27.


# Caso 1: Non è stato fornito nulla → prendi l’ultimo file nella cartella di default
if args.input_file is None:
    full_file_path = find_latest_file(DEFAULT_PATH, '_threshold_scan_interpreted.h5')
    if full_file_path is None:
        print(f"[INFO] Nessun file .h5 trovato nella cartella {DEFAULT_PATH}. Il programma termina.")
        sys.exit(0)
    print(f"[INFO] Nessun file specificato: uso il più recente → {full_file_path}")

# Caso 2: È stato fornito solo un nome file (senza slash)
elif os.sep not in args.input_file:
    full_file_path = os.path.join(DEFAULT_PATH, args.input_file)
    if not os.path.exists(full_file_path):
        print(f"[ERRORE] File {full_file_path} non trovato nella cartella default.")
        sys.exit(1)

# Caso 3: È stato fornito un path completo
else:
    full_file_path = args.input_file
    if not os.path.exists(full_file_path):
        print(f"[ERRORE] Il file {full_file_path} non esiste.")
        sys.exit(1)

# Ora puoi separare path e file name
folder_path = os.path.dirname(full_file_path)
file_name = os.path.basename(full_file_path)

print(f"[INFO] File selezionato: {file_name}")
print(f"[INFO] Cartella: {folder_path}")


def is_in_range(val, lower, upper):
    return lower <= val < upper


def get_scan_config(file_name, folder_path):
    with tb.open_file(os.path.join(folder_path, file_name), 'r') as f:
        # Get the HistOcc array
        start_column = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"start_column"')['value']
        start_column = int(start_column[0].decode("utf-8"))
        stop_column = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"stop_column"')['value']
        stop_column = int(stop_column[0].decode("utf-8"))
        start_row = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"start_row"')['value']
        start_row = int(start_row[0].decode("utf-8"))
        stop_row = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"stop_row"')['value']
        stop_row = int(stop_row[0].decode("utf-8"))
        n_injections = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"n_injections"')['value']
        n_injections = int(n_injections[0].decode("utf-8"))
        v_low_start = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"VCAL_LOW_start"')['value']
        v_low_start = int(v_low_start[0].decode("utf-8"))
        v_low_stop = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"VCAL_LOW_stop"')['value']
        v_low_stop = int(v_low_stop[0].decode("utf-8"))
        v_high = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"VCAL_HIGH"')['value']
        v_high = int(v_high[0].decode("utf-8"))
        v_step = f.root.configuration_in.scan.scan_config.read_where(
            'attribute == b"VCAL_LOW_step"')['value']
        v_step = int(v_step[0].decode("utf-8"))
    return [start_column, stop_column, start_row, stop_row, n_injections,v_low_start,v_low_stop,v_step,v_high]

def get_frontends(start, stop):
    ranges = {
        "NF": range(0, 224),
        "NF_CASC": range(224, 448),
        "HV_CASC": range(448, 480),
        "HV": range(480, 512),
    }

    frontends = []
    for name, r in ranges.items():
        # Se l'intervallo [start, stop] interseca il range di questo frontend
        if (start in r) or (stop in r) or (start < r.stop and stop >= r.start):
            frontends.append(name)

    return frontends

    ## HOW TO USE IT
    ## frontends = get_frontends(start_column, stop_column)
    ## print(f"Frontend(s): {', '.join(frontends)}")


def get_combined_hist_occ(file_name, delta_v, folder_path):
        with tb.open_file(os.path.join(folder_path, file_name), 'r') as f:
            hist_occ = f.root.HistOcc[:]
            hist_occ = np.asarray(hist_occ)
        return hist_occ


def sigmoid(x, L, x0, k, b):
    y = L / (1 + np.exp(-k*(x-x0))) + b
    return y


def s_curve_fit(i, j):
    try:
        ydata = combined_hist_occ[i, j]
        if all(item == 0 for item in ydata):
            s_curve_x0[i, j] = 0
        else:
            p0 = [max(ydata)-min(ydata), np.median(xdata), 1, min(ydata)]
            popt, pcov = curve_fit(sigmoid, xdata, ydata, p0, method='dogbox')
            s_curve_x0[i, j] = popt[1]
            plt.plot(xdata, ydata)
            # plt.show()

    except:
        s_curve_x0[i, j] = 0


def run_s_curve_fit(args):
    i, j = args
    s_curve_fit(i, j)


# Define a Gaussian function to fit to the histogram
def gauss(x, a, x0, sigma):
    return a * np.exp(-(x - x0)**2 / (2 * sigma**2))


def get_results(file_name, folder_path, col_start, col_stop, row_start, row_stop):
    results = np.zeros(shape=(max(delta_v)+1, 128), dtype='int')
    h5file = tb.open_file(os.path.join(folder_path, file_name),
                              mode="r", title='configuration_in')
    HistToT = h5file.root.HistTot
    arr_ToT = np.asarray(HistToT)

    #arr_ToT_sum = np.zeros(shape=(128), dtype='int')
    for i,v in enumerate(delta_v):
        arr_ToT_sum = np.sum(arr_ToT[col_start:col_stop,row_start:row_stop,i,:], axis=(0, 1))
        for j in range(128):
            results[v, j] = arr_ToT_sum[j]
        # modified to defined TOT not zero: ToT = Te-Le + 1 since in HistToT table is defined as = Te - Le
        # results[v, 0] = 0
        # for j in range(127):
        #     results[v, j+1] = arr_ToT_sum[j]

    h5file.close()

    return results

def get_HistOcc(file_name, folder_path):
    h5file = tb.open_file(os.path.join(folder_path, file_name),
                              mode="r", title='configuration_in')
    HistOcc = h5file.root.HistOcc
    arr_Occ = np.asarray(HistOcc)
    h5file.close()

    return arr_Occ

def get_HistToT(file_name, folder_path):
    h5file = tb.open_file(os.path.join(folder_path, file_name),
                              mode="r", title='configuration_in')
    HistToT = h5file.root.HistTot
    arr_ToT = np.asarray(HistToT).T
    h5file.close()

    return arr_ToT


def get_NoiseMap(file_name, folder_path):
    h5file = tb.open_file(os.path.join(folder_path, file_name),
                              mode="r", title='configuration_in')
    NoiseMap = h5file.root.NoiseMap
    arr_noise = np.asarray(NoiseMap).T
    h5file.close()
    return arr_noise

def get_thresh(file_name, folder_path):
    h5file = tb.open_file(os.path.join(folder_path, file_name),
                              mode="r", title='configuration_in')
    ThresholdMap = h5file.root.ThresholdMap
    s_curve_x0 = np.asarray(ThresholdMap)
    h5file.close()

    return s_curve_x0


def multiply_by_10(x, pos):
    return int(x * 1)

def clean_data_debug(results):
    """
    Fit a Gaussian to each column of the results array and get the mean and std.

    Args:
    results: 2D numpy array of shape (n, m) where n is the number of rows (Qinj values) and m is the number of columns (TOT values)
    x: 1D numpy array of shape (m,) representing the x-axis values.

    Returns:
    Tuple of three 1D numpy arrays: (means, stds, rows).
    """
    # Create the x array
    x = np.arange(0, 128)
    means, stds, rows, nentries = [], [], [], []
    # Iterate over rows (Qinj) and fit with gauss function
    with PdfPages(os.path.join(folder_path, 'tot_distribution_charge_dac_ALL.pdf')) as pdf:
        for i, row in enumerate(results):
            plt.figure()
            plt.plot(np.arange(len(row)), row)
            plt.title(f"ToT distribution for DAC {i}")
            plt.xlabel("ToT bins")
            plt.ylabel("Counts")
            plt.grid(True)
            plt.xlim(0,20)
            plt.tight_layout()
            #pdf.savefig()  # salva la figura corrente nel PDF
            # plt.close()

            # Initial guesses for parameters
            p0 = [row.max(), np.argmax(row), 1]
            entries=np.sum(row)
            # if i == 100:
            N = np.sum(row)
            amplitude, mean, std1 = p0
            #print('i. amplitude, mean std N',i, amplitude, mean, std1,N)
            #print ('i, p0 and N', i, p0, N)
            #print ('row', i, row)

            # Fit with curve_fit
            try:
                popt, pcov = curve_fit(gauss, x, row, p0=p0)
                amplitude, mean, std1 = popt
                #print('mean std N',mean, std1,N)
                #print('i. in try amplitude, mean std N',i, amplitude, mean, std1,N)
                perr = np.sqrt(np.diag(pcov))  # errori standard sui parametri
                A_err, mean_err, std_err = perr
                #print('mean_err std1/sqrt(N) 1/sqrt(12)',mean_err, std1/np.sqrt(N), 1/np.sqrt(12))
                #std = 1/np.sqrt(12)
                #std = std1/np.sqrt(N)
                #std = mean_err
                std = std1
                # if N<Nmin:
                #     print('for i N<Nmin set mean to 0: i, N, Nmin, mean, std',i, N, Nmin,mean, std)
                #     mean=1.
                #     print('for i N<Nmin set mean to 0: i, N, Nmin, mean, std',i, N, Nmin,mean, std)
                    #print('mean , error on mean used',mean, std)

                #print('mean , error on mean used',mean, std)

                # plot del fit
                x_fit = np.linspace(0, len(row)-1, 500)
                plt.plot(x_fit, gauss(x_fit, *popt), 'r--', label="Gaussian fit")

                plt.legend()
                plt.tight_layout()
                pdf.savefig()  # salva la figura corrente nel PDF
                plt.close()

                if mean != 0:
                    rows.append(i)
                    means.append(mean)
                    stds.append(std)
                    nentries.append(entries)
            except:
                # Fit failed, skip this column
                std = std1
                print('fit failed')
                #print('i. in except amplitude, mean std N',i, amplitude, mean, std1,N)
                if mean != 0:
                    rows.append(i)
                    means.append(mean)
                    stds.append(std)
                    nentries.append(entries)
                pdf.savefig()  # salva la figura corrente nel PDF
                plt.close()
                continue
            #except RuntimeWarning:
            #    continue
    nan_indices = np.isnan(means)

    # Remove NaN values and their corresponding elements from both lists
    means = [x for i, x in enumerate(means) if not nan_indices[i]]
    stds = [x for i, x in enumerate(stds) if not nan_indices[i]]
    rows = [x for i, x in enumerate(rows) if not nan_indices[i]]
    # print ('stampa tupla di clean data debug')
    # print ('means' , means)
    # print ('stds' , stds)
    # print ('rows' , rows)
    return np.array(means), np.array(stds), np.array(rows), np.array(nentries)

def clean_data(results):
    """
    Fit a Gaussian to each column of the results array and get the mean and std.

    Args:
    results: 2D numpy array of shape (n, m) where n is the number of rows (Qinj) and m is the number of columns (TOT values.
    x: 1D numpy array of shape (m,) representing the x-axis values.

    Returns:
    Tuple of three 1D numpy arrays: (means, stds, rows).
    """
    # Create the x array
    x = np.arange(0, 128)
    means, stds, rows, nentries = [], [], [], []
    # Iterate over rows (Qinj) and fit with gauss function
    for i, row in enumerate(results):
        # Initial guesses for parameters
        p0 = [row.max(), np.argmax(row), 5]
        entries=np.sum(row)
        # Fit with curve_fit
        try:
            popt, pcov = curve_fit(gauss, x, row, p0=p0)
            amplitude, mean, std = popt
            if mean != 0:
                rows.append(i)
                means.append(mean)
                stds.append(std)
                nentries.append(entries)
        except:
            # Fit failed, skip this column
            continue
        #except RuntimeWarning:
        #    continue
    nan_indices = np.isnan(means)

    # Remove NaN values and their corresponding elements from both lists
    means = [x for i, x in enumerate(means) if not nan_indices[i]]
    stds = [x for i, x in enumerate(stds) if not nan_indices[i]]
    rows = [x for i, x in enumerate(rows) if not nan_indices[i]]
    return np.array(means), np.array(stds), np.array(rows), np.array(nentries)

# Define the fit function


def func(x, a, b, d):
    #d=27.
    return (a / x + 1 / b) * (x - d)
    # return (a / x + 1 / b) * (x - d) + 1 # to have d=thr and with TOT defined as Te-Le +1

def func_d_fixed(x, a, b, d=d_fixed):
    #d=27.
    return (a / x + 1 / b) * (x - d)
    # return (a / x + 1 / b) * (x - d) + 1 # to have d=thr and with TOT defined as Te-Le +1


def inv_func(tot, a, b, d): # from https://github.com/SiLab-Bonn/tj-monopix2-daq/blob/development/tjmonopix2/analysis/analysis_utils.py
    #d = 27.
    return (np.sqrt(b**2 * (a - tot)**2 + 2 * b * d * (a + tot) + d**2) - b * a + b * tot + d) * 0.5
    # return (np.sqrt(b**2 * (a - (tot-1.))**2 + 2 * b * d * (a + (tot-1.)) + d**2) - b * a + b * (tot-1.) + d) * 0.5

def chisq(f, x, y, dy, pars, label="Chi²"):
    """
    Compute chi-squared value for a fit.

    Parameters:
    - f:     function used for fit
    - x, y:  data
    - dy:    uncertainties
    - pars:  fit parameters
    - label: optional label for printing

    Returns:
    - chi2:  chi-squared
    - ndof:  degrees of freedom
    """
    # Avoid division by zero
    dy = np.where(dy == 0, 1e-9, dy)

    residuals = (y - f(x, *pars)) / dy
    chi2 = np.sum(residuals**2)
    ndof = len(y) - len(pars)
    print(f"{label} = {chi2:.3f} ({ndof} dof)")
    return chi2, ndof


def get_label(start_col):
    if start_col < 224:
        return "DC coupled"
    elif start_col < 448:
        return "DC coupled Casc"
    elif start_col < 480:
        return "AC coupled Casc"
    else:
        return "AC coupled"

def get_label_region(region):
    if region[1] == 224:
        return "DC coupled"
    elif region[1] == 448:
        return "DC coupled Casc"
    elif region[1] == 480:
        return "AC coupled Casc"
    else:
        return "AC coupled"


if __name__ == '__main__':
    start_col, stop_col, start_row, stop_row, n_inj,v_low_start,v_low_stop,v_step,v_high = get_scan_config(
        file_name, folder_path)
    delta_v = np.array(range(v_high-v_low_start,v_high-v_low_stop,v_step*-1))
    #print(delta_v)
    # Get tot_cal data
        # Define four different regions to analyze
    region1 = (0,224, start_row, stop_row)
    region2 = (224,448, start_row, stop_row)  # Modify these values
    region3 = (448,448+32, start_row, stop_row)  # Modify these values
    region4 = (448+32, 512, start_row, stop_row)  # Modify these values

    # Create a list of regions to analyze
    tot_cal_args = [region1, region2, region3, region4]

    # Create a list to store the results for each region
    tot_cal_results = []

    #tot_cal_args = [(start_col, stop_col, start_row, stop_row)]
    tot_cal_array = []
    for a in tot_cal_args:
        tot_cal_array.append(get_results(file_name, folder_path, *a))

    combined_hist_occ = get_combined_hist_occ(
        file_name, delta_v, folder_path)

    # Initialize variables
    s_curve_x0 = get_thresh(file_name, folder_path)
    s_curve_x0 = np.multiply(s_curve_x0, 1)
    s_curve_x0 = s_curve_x0.T
    xdata = np.array(range(np.min(delta_v),np.max(delta_v)+1))
    print('Configuration:')
    print('start_col, stop_col, start_row, stop_row, n_inj,v_low_start,v_low_stop,v_step,v_high, nsteps ')
    print(start_col, stop_col, start_row, stop_row, n_inj,v_low_start,v_low_stop,v_step,v_high, range(np.min(delta_v),np.max(delta_v)+1))
    #Nmin=(stop_col-start_col)*(stop_row-start_row)*(v_high-(v_low_stop-v_low_start))/np.abs(v_step)*n_inj/2.
    Nmin=(stop_col-start_col)*(stop_row-start_row)*n_inj/2.
    #print('stop_col-start_col',stop_col-start_col)
    print('Nmin=(stop_col-start_col)*(stop_row-start_row)*n_inj/2.=',Nmin)
    #print(xdata)
    xdata = xdata* 1
    #print(xdata)
    popt_cal_NF = [0,0,0]
    popt_cal_NF_CASC = [0,0,0]
    popt_cal_HV_CASC  = [0,0,0]
    popt_cal_HV  = [0,0,0]

    chi2_ndof_cal_NF = 0.0
    chi2_ndof_cal_NF_CASC = 0.0
    chi2_ndof_cal_HV_CASC = 0.0
    chi2_ndof_cal_HV = 0.0

    base_name = os.path.splitext(file_name)[0]

    thresholds = []

    # Create a PDF file
    with pdf.PdfPages(os.path.join(folder_path, base_name + '_tot_calibration_fit3par.pdf')) as pdf_file:
        # Plot 1: S-Curve Plot
        print(' ')
        print('plot s-curves')
        region1 = [0,224, start_row, stop_row]
        region2 = [224,448, start_row, stop_row]
        region3 = [448,448+32, start_row, stop_row]
        region4 = [448+32, 512, start_row, stop_row]
        regions = [region1, region2, region3, region4]
        #print(regions)
        for r,region in enumerate(regions):
            #print(r,region)
            try:
                fig, ax = plt.subplots()
                # Get the maximum value in the matrix
                matrix = get_HistOcc(file_name, folder_path)[region[0]:region[1],region[2]:region[3]]
                max_value = np.max(matrix)

                # Calculate the occupancy values based on the maximum value
                occupancy_values = list(range(int(max_value) + 1))

                # Get the number of steps (length of entries per pixel)
                num_steps = matrix.shape[2]

                # Initialize an empty array to store the counts
                counts = np.zeros((num_steps, len(occupancy_values)))

                # Iterate over each injection step
                for step in range(num_steps):
                    # Count the number of pixels with each occupancy value for the current step
                    for i, occupancy in enumerate(occupancy_values):
                        counts[step, i] = np.sum(matrix[:, :, step] == occupancy)


                # Scale the x-axis values by 1
                x_values = delta_v * 1
                #print(x_values)
                # Limit the x-axis range up to 700
                x_values = x_values[x_values <= 700]

                # Filter the counts matrix based on the x-axis range
                counts = counts[:len(x_values)]
                #print(counts)
                fig, ax = plt.subplots()
                norm = colors.LogNorm(vmin=1, vmax=np.max(counts))
                occupancy_values = [x / 100 for x in occupancy_values]
                image = ax.pcolormesh(x_values, occupancy_values, counts.T, cmap=newcmp, norm=norm)

                # Create a custom tick formatter for displaying tick labels as '10^x'
                class LogFormatterSciNotation(ticker.LogFormatterSciNotation):
                    def __call__(self, x, pos=None):
                        return r'$10^{{{}}}$'.format(int(np.log10(x)))

                # Create the colorbar with logarithmic scale and custom tick formatter
                cbar = fig.colorbar(image, ax=ax, format=LogFormatterSciNotation(), ticks=ticker.LogLocator(base=10.0))
                cbar.set_label('# of pixels', fontsize=14)

                # Set the axis labels and title with larger font sizes
                ax.set_xlabel('Injected Charge [DAC]', fontsize=16)
                ax.set_ylabel('Occupancy', fontsize=16)
                plt.title('S-Curve Plot' +str(region), fontsize=16)
                plt.tight_layout

                # Increase the font size of tick labels
                ax.tick_params(axis='both', which='both', labelsize=14)

                # Increase the font size of the colorbar tick labels
                cbar.ax.tick_params(labelsize=14)
                # Adjust the bottom margin
                plt.subplots_adjust(bottom=0.15)
                pdf_file.savefig()

                plt.close(fig)

            except Exception as e:
                print(f"Error occurred: {str(e)}")
                print('no clibration')


        # Plot 2: Threshold map
        # Create the figure and axes
        print(' ')
        print('plot threshold map')
        fig, ax = plt.subplots()

        # Plot the image
        image = ax.imshow(s_curve_x0[:, :])

        # Set the color bar limits
        cbar = fig.colorbar(image, ax=ax, ticks=np.arange(0, 501, 100))
        cbar.set_label('Threshold [DAC]', fontsize=14)
        cbar.ax.set_yticklabels(np.arange(0, 501, 100), fontsize=12)

        # Set the axis labels
        ax.set_xlabel('Column', fontsize=14)
        ax.set_ylabel('Row', fontsize=14)
        plt.tight_layout

        # Increase the font size of tick labels
        ax.tick_params(axis='both', which='both', labelsize=12)

        pdf_file.savefig()
        #
        # Plot 3: Threshold distribution
        print(' ')
        print('plot threshold')
        #popt, pcov = [0,0,0,0],0
        for r,region in enumerate(regions):
            print('r, region', r,region)
            fig = plt.figure()
            mean_nf, std_nf, mean_nf_casc, std_nf_casc = None, None, None, None
            for i, data in enumerate([s_curve_x0[region[2]:region[3],region[0]:region[1]],]):
                hist, bins = np.histogram(data, bins=50)
                # print('i',i)
                # print('data',data)
                x_fit = (bins[1:-1] + bins[2:]) / 2
                x_plot = (bins[1:-1] + bins[2:]) / 2
                label = get_label_region(region)
                try:
                    max_value = np.max(hist)
                    if args.center ==0 :
                        #center = np.mean(data)
                        nonzero_data = data[data != 0]
                        print('nonzero_data',nonzero_data)
                        if nonzero_data.size > 0:
                            center = np.mean(nonzero_data)
                        else:
                            center = 0.
                            print('all thr data from this region are zero')
                    else:
                        center = args.center/10.1
                    print('center', center)
                    width = 5
                    #print(max_value, center)
                    print('initial parameters for threhsold fit', f'{max_value:.1f}', f'{center:.1f}', f'{width:.1f}')
                    p0 = [max_value, center, width]
                    popt, pcov = [0,0,0,0],0
                    popt, pcov = curve_fit(gauss, x_fit, hist[1:], p0=p0)
                    plt.plot(x_fit, gauss(x_fit, *popt), 'r-', label=label+ ' fit')
                    mean, std = popt[1], popt[2]
                    print('fitted thr and std',f'{mean:.1f}', f'{std:.1f}')

                    plt.bar(x_plot, hist[1:], width=bins[1] - bins[0], label=label)
                except:
                    continue

            text_box_text =  f"µ = {popt[1]:.1f}DAC\n$\sigma$ = {popt[2]:.1f}DAC"
            if text_box_text:
                fig.text(0.15, 0.55, text_box_text, fontsize=16, bbox=dict(facecolor='white', edgecolor='gray', alpha=0.5))

            # Set the axis labels and title
            plt.legend(fontsize=14)
            plt.xlabel('threshold [DAC]', fontsize=16)
            plt.ylabel('# pixel', fontsize=16)
            #plt.ylim(0, 400)
            #plt.xlim(0, 500)
            # Increase the font size of tick labels
            plt.xticks(fontsize=14)
            plt.yticks(fontsize=14)
            plt.tight_layout
            # plt.savefig(os.path.join(folder_path, 'Threshold_distribution.pdf'), format='pdf')
            pdf_file.savefig()  # Add this plot to the PDF file
            plt.close(fig)
            # plt.show()

            if r ==0:
                threshold_NF, threshold_NF_std =  popt[1], popt[2]
                thresholds.append([threshold_NF, threshold_NF_std])
            elif r ==1:
                threshold_NF_CASC,threshold_NF_CASC_std =   popt[1], popt[2]
                thresholds.append([threshold_NF_CASC, threshold_NF_CASC_std])
            elif r ==2:
                threshold_HV_CASC,threshold_HV_CASC_std =   popt[1], popt[2]
                thresholds.append([threshold_HV_CASC, threshold_HV_CASC_std])
            elif r ==3:
                threshold_HV, threshold_HV_std =   popt[1], popt[2]
                thresholds.append([threshold_HV, threshold_HV_std])

        thresholds = np.array(thresholds)
        print("thresholds all regions", [[f"{thr:.1f}", f"{std:.1f}"] for thr, std in thresholds])

        # Plot 4 Noise: Noise map
        # Create the figure and axes
        print(' ')
        print('plot Noise map')
        fig, ax = plt.subplots()

        # Plot the image
        noise_map=get_NoiseMap(file_name, folder_path)
        noise_map = np.multiply(noise_map, 1)
        #
        image = ax.imshow(noise_map,vmin=0, vmax=20,)

        # Set the color bar limits
        cbar = fig.colorbar(image, ax=ax)

        cbar.set_label('Noise [DAC]', fontsize=14)
        #cbar.ax.set_yticklabels(np.arange(0, 501, 100), fontsize=12)

        # Set the axis labels
        ax.set_xlabel('Column', fontsize=14)
        ax.set_ylabel('Row', fontsize=14)
        plt.tight_layout

        # Increase the font size of tick labels
        #ax.tick_params(axis='both', which='both', labelsize=12)

        pdf_file.savefig()
        plt.close(fig)
        #

       # Plot 5: Noise distribution
        print(' ')
        print('plot Noise')
        for r,region in enumerate(regions):
            #print(r,region)
            fig = plt.figure()
            mean_nf_noise, std_nf_noise, mean_nf_casc_noise, std_nf_casc_noise = None, None, None, None
            noise_map=get_NoiseMap(file_name, folder_path)
            noise_map = np.multiply(noise_map, 1)
            for i, data in enumerate([noise_map[region[2]:region[3],region[0]:region[1]],]):
                hist_noise, bins_noise = np.histogram(data, bins=50)
                x_fit_noise = (bins_noise[1:-1] + bins_noise[2:]) / 2
                x_plot_noise = (bins_noise[1:-1] + bins_noise[2:]) / 2
                try:
                    max_value_noise = np.max(hist)
                    center_noise = np.mean(data)
                    width_noise = 10
                    p0_noise = [max_value_noise, center_noise, width_noise]
                    popt_noise, pcov_noise = curve_fit(gauss, x_fit_noise, hist_noise[1:], p0=p0_noise)
                    label=get_label_region(region)
                    plt.plot(x_fit_noise, gauss(x_fit_noise, *popt_noise), 'r-', label=label+ ' fit')
                    mean_noise, std_noise = popt_noise[1], popt_noise[2]

                    if mean_noise < 1000:  # Exclude plotting if mean is too large
                        if i == 0:
                            mean_nf_noise, std_nf_noise = mean_noise, std_noise
                        else:
                            mean_nf_casc_noise, std_nf_casc_noise = mean_noise, std_noise
                        plt.bar(x_plot_noise, hist_noise[1:], width=bins_noise[1] - bins_noise[0], label=label)
                except:
                    continue

            text_box_text = ''
            if mean_nf_noise is not None and std_nf_noise is not None:
                text_box_text += f"µ = {mean_nf_noise:.2f}\n$\sigma$ = {std_nf_noise:.2f}\n"

            if mean_nf_casc_noise is not None and std_nf_casc_noise is not None:
                text_box_text += f"NF_Casc:\nµ = {mean_nf_casc_noise:.2f}DAC\n$\sigma$ = {std_nf_casc_noise:.2f}DAC"
            # Plot the text box if there is content to display
            if text_box_text:
                fig.text(0.15, 0.55, text_box_text, fontsize=14, bbox=dict(facecolor='white', edgecolor='gray', alpha=0.5))

            # Set the axis labels and title
            plt.legend(fontsize=16)
            plt.xlabel('Noises [DAC]', fontsize=16)
            plt.ylabel('# pixel', fontsize=16)
            # Increase the font size of tick labels
            plt.xticks(fontsize=14)
            plt.yticks(fontsize=14)
            plt.tight_layout
            #plt.ylim(0,400)
            #plt.xlim(0, 20)
            # plt.savefig(os.path.join(folder_path, 'Threshold_distribution.pdf'), format='pdf')
            pdf_file.savefig()  # Add this plot to the PDF file
            plt.close(fig)
            # plt.show()




        # plot 0: tot cal
        print(' ')
        print('plot ToT')
        for i, tot_cal in enumerate(tot_cal_array):
            #print(i)
            if i ==0:
                fit_range = args.fit_range_NF
                section_name = 'NF'
            elif i ==1:
                fit_range = args.fit_range_NFCASC
                section_name = 'NF CASC'
            elif i ==2:
                fit_range = args.fit_range_HVCASC
                section_name = 'HV CASC'
            elif i ==3:
                fit_range = args.fit_range_HV
                section_name = 'HV'

            try:
                #print(tot_cal)
                folder_name = os.path.basename(os.path.normpath(folder_path))
                if i == 2: # for DCC i=1 for HVC i=2
                    print ('flavor i=',i)
                    means, stds, rows, nentries = clean_data_debug(tot_cal)
                    thr, thr_std = thresholds[i]
                    print(f"in tot_cal loop i={i}: threshold={thr:.1f}, std={thr_std:.1f}")
                else:
                    print ('flavor i=',i)
                    means, stds, rows, nentries = clean_data(tot_cal)
                    # means, stds, rows = clean_data_debug(tot_cal)
                    thr, thr_std = thresholds[i]
                    print(f"in tot_cal loop i={i}: threshold={thr:.1f}, std={thr_std:.1f}")
                #means, stds, rows = clean_data(tot_cal)

                fig = plt.figure(figsize=(8, 6))
                x = rows  # Use rows for x-axis dimension
                #print(x)
                x = x* 1
                x_plot = np.linspace(x[args.plot_range],2500,1000)

                y = np.arange(tot_cal.shape[1])  # Use tot_cal.shape[1] for y-axis dimension

                # Create the ScalarMappable object
                cmap = newcmp

                # Plot the colormesh
                mesh = plt.pcolormesh(x, y, tot_cal.T[:,-len(x):], cmap=cmap, norm=colors.LogNorm())

                colorbar = plt.colorbar(mesh)
                colorbar.ax.tick_params(labelsize=12)
                colorbar.set_label('# of pixel', fontsize=14)


                # Set up x-axis tick labels
                ax = plt.gca()
                #ax.xaxis.set_major_formatter(ticker.FuncFormatter(multiply_by_10))
                ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
                ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
                plt.xticks(rotation=45, fontsize=12)

                # Set up y-axis tick labels
                ax = plt.gca()
                #ax.xaxis.set_major_formatter(ticker.FuncFormatter(multiply_by_10))
                ax.yaxis.set_major_locator(ticker.MultipleLocator(2))
                ax.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)
                plt.yticks(rotation=45, fontsize=12)


                # Fit the function to the data BONN function (a,b,d)
                print(f'flavor i={i} has theshold={thresholds[i,0]:.1f}')
                d_fixed = thresholds[i,0]
                print(f'flavor i={i} has theshold={d_fixed:.1f}')
                # p0 = (4.45, 100, thresholds[i,0])
                p0 = (4.45, 100, 27.)
                #p0 = (4.45, 100)
                # param_bounds = ([0, 0, 0, 0], [np.inf, np.inf, np.inf, np.inf])
                param_bounds = ([0, 0, 0], [np.inf, np.inf, np.inf])
                #param_bounds = ([0, 0], [np.inf, np.inf])
                #param_bounds = ([0, 0, 0, 0], [np.inf, np.inf, np.inf, 10])

                try:
                    # Trova l'indice da cui partire per il fit (x[i] >= fit_range)
                    i_start = np.searchsorted(x, fit_range)

                    # Se non ci sono punti validi per il fit, salta
                    if i_start >= len(x):
                        print(f"[{section_name}] WARNING: fit_range ({fit_range}) too high — skipping fit.")
                        continue

                    # Seleziona i dati a partire da i_start
                    x_fit = x[i_start:]
                    means_fit = means[i_start:]
                    stds_fit = stds[i_start:]

                    #add also the points used as input to the fit (TOT mean for each Qinj) on the ToT map
                    # Tutti i dati: triangoli rossi trasparenti
                    plt.plot(x, means,'^', label='All Data', color='red', alpha=0.4, markersize=2)
                    # Dati usati fit: cerchi blu pieni
                    plt.plot(x_fit, means_fit,'o', label='Fit Data', color='blue', markersize=2)


                    # Fit vero e proprio
                    popt_cal, pcov_cal = curve_fit(func, x_fit, means_fit,
                                                sigma=stds_fit, p0=p0, bounds=param_bounds)


                    # popt_cal, pcov_cal = curve_fit(lambda x, a, b: func_d_fixed(x, a, b), x_fit, means_fit,
                    #                                 sigma=stds_fit, p0=p0, bounds=param_bounds)
                    #popt_cal, pcov_cal = curve_fit(func_d_fixed, x_fit, means_fit,
                    #                             sigma=stds_fit, p0=p0, bounds=param_bounds)


                    # # add points with the TOT integer from 0 t0 20 and the associated charge calculated with the inv_func
                    # tot_test = np.arange(0, 21)
                    # plt.plot(inv_func(tot_test, *popt_cal), tot_test, 'go', label='inverted func: $inv_f(int ToT)$', markersize=2)

                    # Calcolo del chi²
                    chi2_val, ndof = chisq(func, x_fit, means_fit, stds_fit, popt_cal, label=f"Chi² - {section_name}")

                    chi2_ndof = chi2_val/ndof

                    # Primo plot: funzione + fit + parametri + points corresponding to mean
                    plt.plot(x_plot, func(x_plot, *popt_cal), color='k', label='fit')
                    #plt.text(10, 40, '$f_{3par}(x)=(a/x +1/b)*(x-d) +1 $', color='k', fontsize=14)
                    plt.text(10, 40, '$f_{3par}(x)=(a/x +1/b)*(x-d)$', color='k', fontsize=14)

                    #plt.plot(x, means, 'ro', label='mean ToT')


                    # Print fit results
                    print('Fit results with f_3par')
                    func_params = ['a', 'b', 'd']
                    func_param_values = popt_cal
                    formatted = ", ".join([f"{v:.2f}" for v in func_param_values])
                    print("Fit results with f_3par:", formatted)
                    print(f"THR average {thresholds[i,0]:.2f}")


                    for j, param in enumerate(popt_cal):
                        plt.text(10, 35 - j * 5, f'{func_params[j]}={param:.2f} ± {np.sqrt(pcov_cal[j, j]):.2f}', color='k', fontsize=14)
                        print(f'{func_params[j]}={param:.2f} ± {np.sqrt(pcov_cal[j, j]):.2f}')


                    # Parameters to compare fit 3 par vs fit 4 par for debugging
                    print()
                    print("Comparison parameters from fit 3 par to fit 4 par, assuming t=0 in fit 4 par")
                    print(f'slope=a_4par=1/b_3par={1/popt_cal[1]:.2f}')
                    print(f'cost=b_4par=a_3par-d_3par/b_3par={popt_cal[0]-popt_cal[2]/popt_cal[1]:.2f}')
                    print(f'c_4par=a_3par*d_3par={popt_cal[0]*popt_cal[2]:.2f}')
                    print()
                    plt.text(100, 35, f'slope=$a_{{4par}}$=1/b={1/popt_cal[1]:.2f}', color='k', fontsize=14)
                    plt.text(100, 35 - 5, f'cost=$b_{{4par}}$=a-c/b={popt_cal[0]-popt_cal[2]/popt_cal[1]:.2f}', color='k', fontsize=14)
                    plt.text(100, 35 - 10, f'$c_{{4par}}$=a*d={popt_cal[0]*popt_cal[2]:.2f}', color='k', fontsize=14)
                    #plt.text(100, 35 - f'slope=a_marilke={1/popt_cal[1]:.2f}', color='k', fontsize=14)

                    # Evidenzia la regione di fit
                    plt.axvspan(x[i_start], x[-1], facecolor='#2ca02c', alpha=0.3)

                    # Stampa chi² sul grafico
                    plt.text(0.05, 0.90, f"$\\chi^2$/ndof = {chi2_val:.3f}/{ndof} = {chi2_val/ndof:.3f}",
                            transform=plt.gca().transAxes, fontsize=12, color='black')

                    # Etichette, limiti e aspetto
                    plt.xlabel('Injected Charge [DAC]', fontsize=14)
                    plt.ylabel('ToT  [25ns]', fontsize=14)
                    plt.title(section_name)
                    plt.ylim(0, 50)
                    plt.xlim(0, 250)
                    plt.gca().set_aspect('auto', adjustable='box')
                    plt.tick_params(axis='both', which='both', labelsize=12)
                    plt.legend(fontsize=14)
                    plt.tight_layout()
                    pdf_file.savefig()
                    plt.close(fig)

                    # Secondo plot: dati + highlight del fit
                    if len(x_fit) == 0:
                        print(f"[{section_name}] WARNING: Empty x_fit — skipping second plot.")
                    else:
                        fig2 = plt.figure(figsize=(8, 6))
                        ax1, ax2 = fig2.subplots(2, 1, sharex=True, gridspec_kw=dict(height_ratios=[2, 1], hspace=0.05))

                        # saving data used for fit in a csv file, that can be used offline for fit
                        csv_file_name = base_name + "ToTmeans_plot.csv"
                        path_csv = os.path.join(folder_path, csv_file_name)
                        df = pd.DataFrame({'x': x,'mean': means,'std': stds,'nentries': nentries})
                        df.to_csv(path_csv, index=False)

                        # Tutti i dati: triangoli rossi trasparenti
                        ax1.errorbar(x, means, yerr=abs(stds), fmt='^', label='All Data', color='red', alpha=0.4, markersize=6)

                        # Dati del fit: cerchi blu pieni
                        ax1.errorbar(x_fit, means_fit, yerr=abs(stds_fit), fmt='o', label='Fit Data', color='blue', markersize=6)

                        # Curva fittata
                        ax1.plot(x_plot, func(x_plot, *popt_cal), 'k--', label='Fit: $f(x)$')

                        #ax1.plot(inv_func(means, *popt_cal), means, 'ro', label='inverted func: $inv_f(meansToT)$')

                        # add points with the TOT integer from 0 t0 20 and the associated charge calculated with the inv_func
                        tot_test = np.arange(0, 21)
                        ax1.plot(inv_func(tot_test, *popt_cal), tot_test, 'go', label='inverted func: $inv_f(int ToT)$')

                        #ax1.xlabel('Injected Charge [DAC]', fontsize=14)
                        ax1.set_ylabel('ToT Mean [25ns]', fontsize=14)
                        ax1.set_title(f'Calibration Curve Fit - {section_name}', fontsize=16)
                        ax1.set_ylim(0, 20)


                        ax1.legend(fontsize=12)
                        ax1.grid(True)

                        res = means_fit - func(x_fit, *popt_cal)
                        #res = means - func(x, *popt_cal)

                        ax2.errorbar(x_fit, res, yerr=abs(stds_fit),color='blue', fmt='o')
                        #ax2.errorbar(x, res, yerr=abs(stds),color='blue', fmt='o')
                        ax2.plot(x_plot, np.full(x_plot.shape, 0.0), '--', color='black')
                        ax2.set_xlim(0, 250)
                        #ax2.set_xlim(0, 50)
                        #ax2.set_ylim(-2, 5)
                        ax2.set_xlabel('d [m]')
                        ax2.set_ylabel('Residuals ToT [25ns]', fontsize=14)
                        ax2.set_xlabel('Injected Charge [DAC]', fontsize=14)
                        ax2.grid(color='lightgray', ls='dashed')
                        plt.tight_layout()
                        pdf_file.savefig()
                        plt.close(fig2)

                        # # Tutti i dati: triangoli rossi trasparenti
                        # plt.errorbar(x, means, yerr=abs(stds), fmt='^', label='All Data', color='red', alpha=0.4, markersize=6)

                        # # Dati del fit: cerchi blu pieni
                        # plt.errorbar(x_fit, means_fit, yerr=abs(stds_fit), fmt='o', label='Fit Data', color='blue', markersize=6)

                        # # Curva fittata
                        # plt.plot(x_plot, func(x_plot, *popt_cal), 'k--', label='Fit: $f_{Bonn}(x)$')

                        # plt.xlabel('Injected Charge [DAC]', fontsize=14)
                        # plt.ylabel('ToT Mean [25ns]', fontsize=14)
                        # plt.title(f'Calibration Curve Fit - {section_name}', fontsize=16)
                        # plt.ylim(0, 50)
                        # plt.xlim(0, 250)
                        # plt.legend(fontsize=12)
                        # plt.grid(True)
                        # plt.tight_layout()
                        # pdf_file.savefig()
                        # plt.close(fig2)

                except Exception as e:
                    print(f"[{section_name}] ERROR during fit: {e}")


                if i ==0:
                    popt_cal_NF = popt_cal
                    chi2_ndof_cal_NF = chi2_ndof
                elif i ==1:
                    popt_cal_NF_CASC = popt_cal
                    chi2_ndof_cal_NF_CASC = chi2_ndof
                elif i ==2:
                    popt_cal_HV_CASC = popt_cal
                    chi2_ndof_cal_HV_CASC = chi2_ndof
                elif i ==3:
                    popt_cal_HV = popt_cal
                    chi2_ndof_cal_HV = chi2_ndof
            except Exception as e:
                    print(f"Error occurred: {str(e)}")
                    print('no calibration')


    inj_tot_cal = np.zeros((512, 512, 4))


    popt_cal_NF       = np.array(popt_cal_NF)
    popt_cal_NF_CASC  = np.array(popt_cal_NF_CASC)
    popt_cal_HV_CASC  = np.array(popt_cal_HV_CASC)
    popt_cal_HV       = np.array(popt_cal_HV)

    # Crea i blocchi per ogni regione
    inj_tot_cal[0:224, :, 0:3]   = popt_cal_NF
    inj_tot_cal[224:448, :, 0:3] = popt_cal_NF_CASC
    inj_tot_cal[448:480, :, 0:3] = popt_cal_HV_CASC
    inj_tot_cal[480:512, :, 0:3] = popt_cal_HV

    # Aggiungi chi2/ndof per pixel se hai mappe 2D
    inj_tot_cal[0:224, :, 3]     = chi2_ndof_cal_NF
    inj_tot_cal[224:448, :, 3]   = chi2_ndof_cal_NF_CASC
    inj_tot_cal[448:480, :, 3]   = chi2_ndof_cal_HV_CASC
    inj_tot_cal[480:512, :, 3]   = chi2_ndof_cal_HV



    # nuovo file h5 che contiene i dati dello scan_threshold_interpreted alla quale aggiungo la tabella con i fit
    original_path = os.path.join(folder_path, file_name)
    new_file_name = base_name + '_tot_calibration_fit3par.h5'
    new_path = os.path.join(folder_path, new_file_name)

    # Copia il file
    shutil.copy(original_path, new_path)

    with tb.open_file(new_path, 'r+') as out_file:
        if hasattr(out_file.root, 'InjTotCalibration'):
            out_file.remove_node(out_file.root, 'InjTotCalibration')

        out_file.create_carray(out_file.root,
                            name='InjTotCalibration',
                            title='Injection Tot Calibration Fit',
                            obj=inj_tot_cal,
                            filters=tb.Filters(complib='blosc', complevel=5))

        out_file.root.InjTotCalibration.attrs.columns = ['a', 'b', 'd', 'chi2_ndof']

    print(f"[INFO] File selezionato: {file_name}")
    formatted = ", ".join([f"{v:.2f}" for v in func_param_values])
    print("Fit results with f_3par:", formatted)
    print(f"THR average DCC {thresholds[1,0]:.2f}")
    print(f"THR average HVC {thresholds[2,0]:.2f}")
    print("thresholds all regions", [[f"{thr:.1f}", f"{std:.1f}"] for thr, std in thresholds])
