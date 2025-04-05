import numpy as np
import tables as tb
from pathlib import Path
import yaml
import glob
import argparse

#
# Finds the lates noise occupancy scan in a given folder and prints the disabled pixels to terminal
# also these are saved in a yaml file
#

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

parser = argparse.ArgumentParser(description="Convert hit table to be compatible with corryvreckan EventLoaderHDF5.")
parser.add_argument("run", type=int, help="Number of run for which the mask file is created.")
args = parser.parse_args()

if args.run:
    run_no = int(args.run)
# # Standard usage
folder_path = '/media/testbeam1/tb2025c/tb2025d/desy-tb-2025/data/dut/module_0/chip_0/'
# filepath_in = find_latest_file(folder_path, 'noise_occupancy_scan_interpreted.h5')

# # Select the wanted file -- COMMENT FOR STANDARD USAGE
# filepath_in = f"/home/bellevtx01/tb2025d/desy-tb-2025/data/dut/module_0/chip_0/run*{run_no}_*_ext_trigger_scan.h5"
filepath_in = f"/media/testbeam1/tb2025c/tb2025d/desy-tb-2025/data/dut/module_0/chip_0/run00{run_no}_*_ext_trigger_scan.h5"

# Expand the wildcard using glob
files = glob.glob(filepath_in)

# Check if any files match the pattern
if not files:
    raise FileNotFoundError(f"No files matching pattern: {filepath_in}")

# Print the path of the first file found
print(f'Using File: {files[0]}')


print('Using File: %s' %filepath_in)
with tb.open_file(files[0], "r") as in_file:
    pixel_mask = in_file.root.configuration_out.chip.use_pixel[:]

    start_col = int(in_file.root.configuration_out.scan.scan_config[2][1])
    stop_col = int(in_file.root.configuration_out.scan.scan_config[3][1])
    start_row = int(in_file.root.configuration_out.scan.scan_config[4][1])
    stop_row = int(in_file.root.configuration_out.scan.scan_config[5][1])


    # pixel_mask = in_file.root.configuration_out.chip.masks.enable[:]

print('--- Disabled Pixels ---')
disabled_pixels = np.array(np.where(pixel_mask==False))
print(disabled_pixels)

# Standard usage
print(folder_path + f"/run00{run_no}_masked_pixels.txt")
with open(folder_path + f"/run00{run_no}_masked_pixels.txt", 'w') as file:
    # file.write('cols , rows\n')
    # for i in range(np.shape(disabled_pixels)[1]):
    #     file.write(str(disabled_pixels[:,i]))
    masked_pixels = []

    for i in range(np.shape(disabled_pixels)[1]):
        row = disabled_pixels[1,i]
        col = disabled_pixels[0,i]
        
        file.write(f'p {col} {row}\n')
    
    disabled_cols = [i for i in range(512) if not (start_col <= i <= stop_col)]
    for i in disabled_cols:
        file.write(f'c {i}\n')
    disabled_rows = [i for i in range(512) if not (start_row <= i <= stop_row)]
    for i in disabled_rows:
        file.write(f'r {i}\n')

# # Enumerating only usage -- COMMENT FOR STANDARD USAGE
# for i in range(np.shape(disabled_pixels)[1]):
#     print(i,str(disabled_pixels[:,i]))
