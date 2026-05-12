import numpy as np
import tables as tb

from pathlib import Path


def write_masked_pixels(filepath_in: str, filepath_out: str = None) -> None:
    """Write masked pixels to corryvreckan-compatible mask file.

    Args:
        filepath_in (str): Filepath to h5 file with use_pixel mask.
        filepath_out (str, optional): Filepath for output txt file. Defaults to None.
    """
    print('Using file: %s' % filepath_in)

    with tb.open_file(filepath_in, "r") as in_file:
        pixel_mask = in_file.root.configuration_in.chip.use_pixel[:]

    print('--- Disabled Pixels ---')
    disabled_pixels = np.array(np.where(~pixel_mask))
    print(disabled_pixels)
    print('--- Total Amount of disabled pixels ---')
    print(np.shape(disabled_pixels[1])[0])

    if filepath_out:
        filepath_out = 'masked_pixels.txt'

    with open(filepath_out, 'w') as file:
        for i in range(np.shape(disabled_pixels)[1]):
            file.write('p   ' + str(disabled_pixels[:, i][0]) + '    ' + str(disabled_pixels[:, i][1]) + '\n')

    print('Wrote file to: %s' % filepath_out)


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


if __name__ == '__main__':
    for run in ["run_1", "run_2",]:

        path_in = "/path/to/output/data" + run
        filepath_in = find_latest_file(path=path_in, index="ext_trigger_scan_tj.h5")

        write_masked_pixels(filepath_in,  path_in + '/data/masked_w12r10.txt')
