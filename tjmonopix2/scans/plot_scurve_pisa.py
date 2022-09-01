#!/usr/bin/env python3
"""Plots the results of scan_threshold (HistOcc and HistToT not required)."""
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
    output_file = os.path.splitext(input_file)[0] + "_scurve.pdf"
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

        # Load hits
        hits = f.root.Dut[:]
        with np.errstate(all='ignore'):
            tot = (hits["te"] - hits["le"]) & 0x7f
        # Load information on injected charge and steps taken
        sp = f.root.configuration_in.scan.scan_params[:]
        scan_params = np.zeros(sp["scan_param_id"].max() + 1, dtype=sp.dtype)
        for i in range(len(scan_params)):
            m = sp["scan_param_id"] == i
            if np.any(m):
                scan_params[i] = sp[m.argmax()]
            else:
                scan_params[i]["scan_param_id"] = i
        del sp
        vh = scan_params["vcal_high"][hits["scan_param_id"]]
        vl = scan_params["vcal_low"][hits["scan_param_id"]]
        del scan_params
        charge_dac = vh - vl
        n_injections = int(cfg["configuration_in.scan.scan_config.n_injections"])
        charge_dac_values = [
            int(cfg["configuration_in.scan.scan_config.VCAL_HIGH"]) - x
            for x in range(
                int(cfg["configuration_in.scan.scan_config.VCAL_LOW_start"]),
                int(cfg["configuration_in.scan.scan_config.VCAL_LOW_stop"]),
                int(cfg["configuration_in.scan.scan_config.VCAL_LOW_step"]))]
        charge_dac_bins = len(charge_dac_values)
        charge_dac_range = [min(charge_dac_values) - 0.5, max(charge_dac_values) + 0.5]
        # Count hits per pixel per injected charge value
        row_start = int(cfg["configuration_in.scan.scan_config.start_row"])
        row_stop = int(cfg["configuration_in.scan.scan_config.stop_row"])
        col_start = int(cfg["configuration_in.scan.scan_config.start_column"])
        col_stop = int(cfg["configuration_in.scan.scan_config.stop_column"])
        row_n, col_n = row_stop - row_start, col_stop - col_start
        occupancy, occupancy_edges = np.histogramdd(
            (hits["col"], hits["row"], charge_dac),
            bins=[col_n, row_n, charge_dac_bins],
            range=[[col_start, col_stop], [row_start, row_stop], charge_dac_range])
        occupancy /= n_injections

        occupancy_charges = occupancy_edges[2].astype(np.float32)
        occupancy_charges = (occupancy_charges[:-1] + occupancy_charges[1:]) / 2
        occupancy_charges = np.tile(occupancy_charges, (col_n, row_n, 1))
        plt.hist2d(occupancy_charges.reshape(-1), occupancy.reshape(-1),
                   bins=[charge_dac_bins, 150], range=[charge_dac_range, [0, 1.5]],
                   rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("S-Curve")
        plt.xlabel("Injected charge [DAC]")
        plt.ylabel("Occupancy")
        cb = plt.colorbar()
        cb.set_label("Pixels / bin")
        pdf.savefig(); plt.clf()

        m = 32 if tot.max() <= 32 else 128
        plt.hist2d(charge_dac, tot, bins=[charge_dac_bins, m],
                   range=[charge_dac_range, [-0.5, m + 0.5]],
                   rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("ToT curve")
        plt.xlabel("Injected charge [DAC]")
        plt.ylabel("ToT [25 ns]")
        cb = plt.colorbar()
        cb.set_label("Hits / bin")
        pdf.savefig(); plt.clf()

        # Compute the threshold for each pixel as the weighted average
        # of the injected charge, where the weights are given by the
        # occupancy such that occu = 0.5 has weight 1, occu = 0,1 have
        # weight 0, and anything in between is linearly interpolated
        # Assuming the shape is an erf, this estimator is consistent
        w = np.maximum(0, 0.5 - np.abs(occupancy - 0.5))
        threshold_DAC = np.average(occupancy_charges, axis=2, weights=w)
        plt.hist(threshold_DAC.reshape(-1), bins=charge_dac_bins, range=charge_dac_range)
        plt.title("Threshold distribution")
        plt.xlabel("Threshold [DAC]")
        plt.ylabel("Pixels / bin")
        plt.grid(axis='y')
        pdf.savefig(); plt.clf()

        plt.pcolormesh(occupancy_edges[0], occupancy_edges[1], threshold_DAC.transpose(),
                       rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("Threshold map")
        plt.xlabel("Column")
        plt.ylabel("Row")
        cb = plt.colorbar()
        cb.set_label("Threshold [DAC]")
        pdf.savefig(); plt.clf()

        # Compute the noise (the width of the up-slope of the s-curve)
        # as a variance with the weights above
        noise_DAC = np.sqrt(np.average((occupancy_charges - np.expand_dims(threshold_DAC, -1))**2, axis=2, weights=w))
        m = int(np.ceil(noise_DAC.max(initial=0, where=np.isfinite(noise_DAC)))) + 1
        plt.hist(noise_DAC.reshape(-1), bins=min(2*m, 100), range=[0, m])
        plt.title("Noise (width of s-curve slope) distribution")
        plt.xlabel("Noise [DAC]")
        plt.ylabel("Pixels / bin")
        plt.grid(axis='y')
        pdf.savefig(); plt.clf()

        plt.pcolormesh(occupancy_edges[0], occupancy_edges[1], noise_DAC.transpose(),
                       rasterized=True)  # Necessary for quick save and view in PDF
        plt.title("Noise (width of s-curve slope) map")
        plt.xlabel("Column")
        plt.ylabel("Row")
        cb = plt.colorbar()
        cb.set_label("Noise [DAC]")
        pdf.savefig(); plt.clf()

        plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_file", nargs="*",
        help="The _threshold_scan_interpreted.h5 file(s)."
             " If not given, looks in output_data/module_0/chip_0.")
    parser.add_argument("-f", "--overwrite", action="store_true",
                        help="Overwrite plots when already present.")
    args = parser.parse_args()

    files = []
    if args.input_file:  # If anything was given on the command line
        for pattern in args.input_file:
            files.extend(glob.glob(pattern, recursive=True))
    else:
        files.extend(glob.glob("output_data/module_0/chip_0/*_threshold_scan_interpreted.h5"))

    for fp in tqdm(files):
        try:
            main(fp, args.overwrite)
        except Exception:
            print(traceback.format_exc())
