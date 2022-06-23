import glob
import os
import os.path as path

import matplotlib.pyplot as plt
import numpy as np
import tables as tb
import argparse

from tables import NoSuchNodeError


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
    h5file = tb.open_file(path_h5, mode="r", title='configuration_in')

    try:
        hist_occ = np.asarray(h5file.root.HistOcc)[:, :, 0]
        hist_tot = np.asarray(h5file.root.HistTot)
        avg_tot = calculate_mean_tot_map(hist_tot)
    except NoSuchNodeError:
        print("error in reading h5 file: probably not complete")
        return

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
parser.add_argument('-f', action='store_true', default=None, help='replot even when plots already exist')
parser.add_argument('-d', default='./output_data/module_0/chip_0', help='directory to find h5 files')
args = parser.parse_args()


file = "output_data/module_0/chip_0/20220622_121944_analog_scan_interpreted.h5"
for file in glob.glob(os.path.join(args.d, "*_interpreted.h5")):
    output_dir = prepare_output_directory(file, force=args.f)
    print(output_dir)

    plot_from_file(file, output_dir)


exit()

h5file = tb.open_file("", mode="r", title='configuration_in')

registers = h5file.root.configuration_in.chip.registers
print(registers)
print("---------------")

register_readable = {}
for x in registers.iterrows():
    register_readable[x['register']] = x['value']
print(register_readable)
print("---------------")


enable_mask = h5file.root.configuration_in.chip.masks.enable
print(enable_mask)
print("---------------")


arr = np.asarray(enable_mask)

print(type(arr))
print(arr.shape)
print("---------------")
