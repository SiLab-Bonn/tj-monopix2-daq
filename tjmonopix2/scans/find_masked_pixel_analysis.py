import numpy as np
import tables as tb
from pathlib import Path
import yaml
import glob

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


run_no=1634

# # Standard usage
folder_path = '/home/bellevtx01/tb2025d/desy-tb-2025/data/dut/module_0/chip_0'
# filepath_in = find_latest_file(folder_path, 'noise_occupancy_scan_interpreted.h5')

# # Select the wanted file -- COMMENT FOR STANDARD USAGE
# filepath_in = f"/home/bellevtx01/tb2025d/desy-tb-2025/data/dut/module_0/chip_0/run*{run_no}_*_ext_trigger_scan.h5"
filepath_in = f"/media/bellevtx01/tb2025d/desy-tb-2025/data/dut/module_0/chip_0/run00{run_no}_*_ext_trigger_scan.h5"

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


# # Enumerating only usage -- COMMENT FOR STANDARD USAGE
# for i in range(np.shape(disabled_pixels)[1]):
#     print(i,str(disabled_pixels[:,i]))
