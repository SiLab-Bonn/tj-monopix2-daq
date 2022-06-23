import glob
import os
import os.path as path

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


def plot_pixmap_generic(map_data, props, basename, output_dir):
    fig, ax = plt.subplots()
    image = plt.imshow(np.transpose(map_data))

    ax.set_xlabel('column')
    ax.set_ylabel('row')

    cbar = plt.colorbar(image)
    cbar.set_label(props.get('colorbar_label', ''))
    # plt.clim(*args.clim)

    plt.title(props.get('title', ''))

    # plt.show()
    plt.savefig(os.path.join(output_dir, basename+ "_hitmap_" + props.get('output-name', 'output_name_undefined') + ".png"))


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


def plot_from_file(path_h5, output_dir):
    if output_dir is None:
        return
    basename = path.basename(output_dir)
    try:
        h5file = tb.open_file(path_h5, mode="r", title='configuration_in')

        hist_occ = np.asarray(h5file.root.HistOcc)[:, :, 0]
        hist_tot = np.asarray(h5file.root.HistTot)
        avg_tot = calculate_mean_tot_map(hist_tot)

        enable_mask = h5file.root.configuration_in.chip.masks.enable
        registers = h5file.root.configuration_in.chip.registers
    except NoSuchNodeError:
        print("error in reading h5 file: probably not complete")
        return
    finally:
        h5file.close()

    prop_occ = {
        'colorbar_label': 'Occupancy',
        'title': 'Occupancy map',
        'output-name': 'occ',
    }
    plot_pixmap_generic(hist_occ, prop_occ, basename, output_dir)

    prop_tot = {
        'colorbar_label': 'Mean ToT / 25ns',
        'title': 'ToT map',
        'output-name': 'tot',
    }
    plot_pixmap_generic(avg_tot, prop_tot, basename, output_dir)


parser = argparse.ArgumentParser()
parser.add_argument('-d', default='./output_data/module_0/chip_0', help='directory to find h5 files')
parser.add_argument('-i', action='store_true', default=None, help='interpret h5 files that are not interpreted')
parser.add_argument('-I', action='store_true', default=None, help='always re-interpret h5 files')
parser.add_argument('-p', action='store_true', default=None, help='plot data from interpreted h5 files')
parser.add_argument('-P', action='store_true', default=None, help='force replot of interpreted h5 files')
args = parser.parse_args()

# looks for uninterpreted files or reinterprates everything with -I
if args.i or args.I:
    for file in glob.glob(os.path.join(args.d, "*.h5")):
        if file.endswith('_interpreted.h5'):
            continue  # this is an interpreted file
        file_interpreted = file.rsplit(".h5")[0]+"_interpreted.h5"
        if path.isfile(file_interpreted):
            if args.I:
                os.remove(file_interpreted)
            else:
                continue
        print('Analyzing file: '+path.basename(file))
        with analysis.Analysis(raw_data_file=file) as a:
            a.analyze_data()

if args.p or args.P:
    for file in glob.glob(os.path.join(args.d, "*_interpreted.h5")):
        output_dir = prepare_output_directory(file, force=args.P)
        if file:
            print("Plotting: " + path.basename(file))
            plot_from_file(file, output_dir)


exit()


