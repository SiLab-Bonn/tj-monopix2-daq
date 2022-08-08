import glob
import os
import yaml
import os.path as path
import shutil

import matplotlib.pyplot as plt
import numpy as np
import tables as tb
import argparse

from tables import NoSuchNodeError
from tjmonopix2.analysis import analysis


def calculate_mean_tot_map(hist_tot):
    mean_tot = np.zeros((512, 512))
    bins = np.linspace(1, 127, 128)

    for col in range(512):
        for row in range(512):
            # print(col)
            # print(row)

            heights = hist_tot[col][row][0]
            if np.sum(heights) > 0:
                mean_tot[col][row] = np.dot(bins, heights) / (np.sum(heights))
            else:
                mean_tot[col][row] = 0
    return mean_tot


def plot_pixmap_generic(map_data, mask_out, props, basename, output_dir):
    run_config = props['run_config']
    scan_config = props['scan_config']
    show_area_only = props.get('show_area_only', True)

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    map_data[mask_out] = float('nan')
    image = plt.imshow(np.transpose(map_data), aspect='auto', interpolation='none')

    ax.set_xlabel('column')
    ax.set_ylabel('row')
    
    if show_area_only:
        ax.set_xlim((float(scan_config['start_column']) - 0.5, float(scan_config['stop_column']) - 0.5))
        ax.set_ylim((float(scan_config['stop_row']) - 0.5, float(scan_config['start_row']) - 0.5))

    cbar = plt.colorbar(image)
    cbar.set_label(props.get('colorbar_label', ''))

    plt.title(run_config['chip_sn'] + ': ' + props.get('title', ''))

    masked_str = "\nnoisy pixels: {}".format(np.sum(mask_out, axis=(0, 1)))
    plt.text(0, -0.1, "Scan id: " + run_config['scan_id'] + masked_str,
             horizontalalignment='center',
             verticalalignment='top',
             transform=ax.transAxes)

    # plt.show()
    plt.tight_layout()
    plt.savefig(
        os.path.join(output_dir, basename + "_hitmap_" + props.get('output-name', 'output_name_undefined') + ".png"))


def plot_tot_histograms(hist_tot, mask_out, props, basename, output_dir):
    run_config = props['run_config']
    scan_config = props['scan_config']

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    hist_tot[mask_out, :] = 0
    bins = np.linspace(1, 127, 128)
    boundaries = [0, 224, 448, 480, 512]
    labs = ['Normal FE', 'Normal casc. FE', 'HV casc. FE', 'HV FE']

    for i in range(4):
        hist = np.sum(hist_tot[boundaries[i]:boundaries[i+1], :, :], axis=(0, 1, 2))
        ax.plot(bins, hist, label=labs[i])

    plt.xlabel('ToT / 25ns')
    plt.ylabel('Occurances')
    plt.title(run_config['chip_sn'] + ': ToT Histogram')
    plt.legend()
    plt.tight_layout()
    plt.grid()
    plt.savefig(
        os.path.join(output_dir, basename + "_hitmap_hist_tot.png"))



def plot_occ_histograms(map_data, mask_out, props, basename, output_dir):
    run_config = props['run_config']
    scan_config = props['scan_config']

    fig, ax = plt.subplots(figsize=(8, 6), dpi=100)
    map_data[mask_out] = 0
    
    boundaries = [0, 224, 448, 480, 512]
    labs = ['Normal FE', 'Normal casc. FE', 'HV casc. FE', 'HV FE']
    
    d = []
    maxs = []
    for i in range(4):
        l = map_data[boundaries[i]:boundaries[i+1], :].reshape(-1)
        l = l[l != 0]
        d.append(l)
        maxs.append(np.amax(l, initial=0))
    
    
    for i in range(4):
        ax.hist(d[i], rwidth=0.9, label=labs[i], alpha=0.6, edgecolor = "black", bins=20, range=(0, np.amax(maxs)))  # on top of each other
        
    #ax.hist(d,  label=labs)  # side by side bars - looks ugly

    plt.xlabel('Number of Hits')
    plt.ylabel('Number of Pixels')
    plt.title(run_config['chip_sn'] + ': Hit Histogram')
    plt.legend()
    plt.tight_layout()
    plt.grid()
    plt.savefig(
        os.path.join(output_dir, basename + "_hitmap_hist_occ.png"))






def export_mask_yaml(basepath, noisy_pixels, occ, clim, measurement):
    masked_pixels = []
    for row in range(512):
        for col in range(512):
            if noisy_pixels[col, row]:
                masked_pixels.append({'row': row, 'col': col, 'hits': float(occ[col, row])})
    output = {'measurement': measurement,
              'median_hits': float(np.median(occ[occ > 0])),
              'std_hits': float(np.std(occ[occ > 0])),
              'cutoff': float(clim),
              'masked_pixels': masked_pixels,
              }
    with open(path.join(basepath, 'masked_pixels.yaml'), 'w') as outfile:
        yaml.dump(output, outfile, default_flow_style=False, sort_keys=False)


def table_to_dict(table_item, key_name='attribute', value_name='value'):
    ret = {}
    for row in table_item.iterrows():
        ret[row[key_name].decode('UTF-8')] = row[value_name].decode('UTF-8')
    return ret


# Create a directory with the same name as the h5 file and return the path to it
# if it exists it returns None (if force is false) or empties it and returns it's path (if torce is true)
def prepare_output_directory(path_h5, force=True):
    output_dir = path_h5.rsplit("_interpreted.h5")[0]
    if path.isdir(output_dir):
        if force:
            filelist = glob.glob(os.path.join(output_dir, "*"))
            for f in filelist:
                os.remove(f)
        else:
            return None
    else:
        os.mkdir(output_dir)

    return output_dir


def plot_from_file(path_h5, output_dir, clim):
    if output_dir is None:
        return
    basename = path.basename(output_dir)
    try:
        h5file = tb.open_file(path_h5, mode="r", title='configuration_in')

        hist_occ = np.asarray(h5file.root.HistOcc)[:, :, 0].astype(float)
        hist_occ_original = hist_occ.copy()
        hist_tot = np.asarray(h5file.root.HistTot).astype(float)
        avg_tot = calculate_mean_tot_map(hist_tot)

        scan_config = table_to_dict(h5file.root.configuration_in.scan.scan_config)
        run_config = table_to_dict(h5file.root.configuration_in.scan.run_config)

        enable_mask = h5file.root.configuration_in.chip.masks.enable
        registers = h5file.root.configuration_in.chip.registers
    except NoSuchNodeError:
        print("error in reading h5 file: probably not complete")
        return
    finally:
        h5file.close()

    selector = np.zeros(hist_occ.shape, dtype=bool)
    selector[int(scan_config['start_column']):int(scan_config['stop_column']),
    int(scan_config['start_row']):int(scan_config['stop_row'])] = True

    if clim == 'auto':
        if run_config['scan_id'] == 'analog_scan':
            clim = int(scan_config['n_injections'])
        else:
            clim = np.median(hist_occ[selector]) + (np.std(hist_occ[selector]) + 5) * 3
    elif clim != 'off':
        clim = int(clim)
    else:
        clim = None
    if clim:
        noisy_pixels = hist_occ > clim

    prop_occ = {
        'colorbar_label': 'Occupancy',
        'title': 'Occupancy map',
        'output-name': 'occ',
        'run_config': run_config,
        'scan_config': scan_config,
        'show_area_only': True,
    }
    plot_pixmap_generic(hist_occ, noisy_pixels, prop_occ, basename, output_dir)
    prop_occ['show_area_only'] = False
    prop_occ['output-name'] = 'occ-full'
    plot_pixmap_generic(hist_occ, noisy_pixels, prop_occ, basename, output_dir)

    prop_tot = {
        'colorbar_label': 'Mean ToT / 25ns',
        'title': 'average ToT map',
        'output-name': 'tot',
        'run_config': run_config,
        'scan_config': scan_config,
    }
    plot_pixmap_generic(avg_tot, noisy_pixels, prop_tot, basename, output_dir)

    prop_hist = {
        'run_config': run_config,
        'scan_config': scan_config,
    }
    plot_tot_histograms(hist_tot, noisy_pixels, prop_hist, basename, output_dir)
    plot_occ_histograms(hist_occ, noisy_pixels, prop_hist, basename, output_dir)
    export_mask_yaml(output_dir, noisy_pixels, hist_occ_original, clim, basename)



parser = argparse.ArgumentParser()
parser.add_argument('-d', default='./output_data/module_0/chip_0', help='directory to find h5 files')
parser.add_argument('-i', action='store_true', default=None, help='interpret h5 files that are not interpreted')
parser.add_argument('-I', action='store_true', default=None, help='always re-interpret h5 files')
parser.add_argument('-p', action='store_true', default=None, help='plot data from interpreted h5 files')
parser.add_argument('-P', action='store_true', default=None, help='force replot of interpreted h5 files')
parser.add_argument('--clim', default='auto', help='limits of the colorbar for the hitmaps, either a number, auto ('
                                                   'number of injections or by median), or off')
parser.add_argument('--collect-plots', action='store_true', default=None, help='copy all plots to a single "plots" '
                                                                               'directory')
args = parser.parse_args()

# looks for uninterpreted files or reinterprates everything with -I
if args.i or args.I:
    for file in glob.glob(os.path.join(args.d, "*.h5")):
        if file.endswith('_interpreted.h5'):
            continue  # this is an interpreted file
        file_interpreted = file.rsplit(".h5")[0] + "_interpreted.h5"
        if path.isfile(file_interpreted):
            if args.I:
                os.remove(file_interpreted)
            else:
                continue
        print('Analyzing file: ' + path.basename(file))
        with analysis.Analysis(raw_data_file=file) as a:
            a.analyze_data()

collect_dir = os.path.join(args.d, "plots")
if args.collect_plots:
    if not path.isdir(collect_dir):
        os.mkdir(collect_dir)

if args.p or args.P:
    for file in glob.glob(os.path.join(args.d, "*_interpreted.h5")):
        output_dir = prepare_output_directory(file, force=args.P)
        if output_dir:
            print("Plotting: " + path.basename(file))
            plot_from_file(file, output_dir, args.clim)
            if args.collect_plots:
                for file2 in glob.glob(os.path.join(output_dir, "*.png")):
                    shutil.copy(file2, path.join(collect_dir, path.basename(file2)))

exit()
