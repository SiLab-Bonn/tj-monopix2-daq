#!/usr/bin/env python3
"""Standard plots like hitmap and ToT histogram (HistOcc and HistToT not required)."""
import argparse
import glob
import os
import traceback
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import numpy as np
import tables as tb
from tqdm import tqdm
from plot_utils_pisa import *


def main(input_file, overwrite=False):
    output_file = os.path.splitext(input_file)[0] + ".pdf"
    if os.path.isfile(output_file) and not overwrite:
        return
    print("Plotting", input_file)
    with tb.open_file(input_file) as f, PdfPages(output_file) as pdf:
        cfg = get_config_dict(f)
        chip_serial_number = cfg["configuration_in.chip.settings.chip_sn"]
        plt.figure(figsize=(6.4, 4.8))
        plt.annotate(
            split_long_text(f"{os.path.abspath(input_file)}\n"
                            f"Chip {chip_serial_number}\n"
                            f"Version {get_commit()}"),
            (0.5, 0.5), ha='center', va='center')
        plt.gca().set_axis_off()
        pdf.savefig(); plt.clf()

        hits = f.root.Dut[:]
        counts2d, edges, _ = np.histogram2d(hits["col"], hits["row"], bins=[512, 512], range=[[0, 512], [0, 512]])
        with np.errstate(all='ignore'):
            tot = (hits["te"] - hits["le"]) & 0x7f

        bins = 100 if counts2d.max() > 200 else max(counts2d.max(), 5)
        plt.hist(counts2d.reshape(-1), bins=bins, range=[0.5, max(counts2d.max(), 5) + 0.5])
        plt.title("Hits per pixel")
        plt.xlabel("Number of hits")
        plt.ylabel("Pixels / bin")
        plt.yscale('log')
        plt.grid(axis='y')
        pdf.savefig(); plt.clf()

        plt.hist(tot, bins=128, range=[-0.5, 127.5])
        plt.title("ToT")
        plt.xlabel("ToT [25 ns]")
        plt.ylabel("Hits / bin")
        plt.yscale('log')
        plt.grid(axis='y')
        pdf.savefig(); plt.clf()

        plt.hist2d(hits["col"], hits["row"], bins=[512, 512], range=[[0, 512], [0, 512]],
                   rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("Hit map")
        plt.xlabel("Col")
        plt.ylabel("Row")
        cb = plt.colorbar()
        cb.set_label("Hits / pixel")
        pdf.savefig(); plt.clf()

        tot2d, _, _ = np.histogram2d(
            hits["col"], hits["row"], bins=[512, 512], range=[[0, 512], [0, 512]],
            weights=tot)
        with np.errstate(all='ignore'):
            totavg = tot2d /counts2d
        plt.pcolormesh(edges, edges, totavg.transpose(), vmin=-0.5, vmax=127.5,
                       rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("Average ToT map")
        plt.xlabel("Col")
        plt.ylabel("Row")
        cb = plt.colorbar()
        cb.set_label("ToT [25 ns]")
        pdf.savefig(); plt.clf()

        plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_file", nargs="*",
        help="The _interpreted.h5 file(s). If not given, looks in output_data/module_0/chip_0.")
    parser.add_argument("-f", "--overwrite", action="store_true",
                        help="Overwrite plots when already present.")
    args = parser.parse_args()

    files = []
    if args.input_file:  # If anything was given on the command line
        for pattern in args.input_file:
            files.extend(glob.glob(pattern, recursive=True))
    else:
        files.extend(glob.glob("output_data/module_0/chip_0/*_interpreted.h5"))

    for fp in tqdm(files):
        try:
            main(fp, args.overwrite)
        except Exception:
            print(traceback.format_exc())
