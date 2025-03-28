#!/usr/bin/env python3
"""Plots the results of scan_threshold (HistOcc and HistToT not required)."""
import argparse
import glob
from itertools import chain
import os
import traceback
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.cm
import matplotlib.pyplot as plt
from matplotlib.colors import LogNorm
import numpy as np
from scipy.optimize import curve_fit
from scipy.special import erf
import tables as tb
from tqdm import tqdm
from uncertainties import ufloat
from plot_utils_pisa import *

VIRIDIS_WHITE_UNDER = matplotlib.cm.get_cmap('viridis').copy()
VIRIDIS_WHITE_UNDER.set_under('w')


@np.errstate(all='ignore')
def average(a, axis=None, weights=1, invalid=np.NaN):
    """Like np.average, but returns `invalid` instead of crashing if the sum of weights is zero."""
    return np.nan_to_num(np.sum(a * weights, axis=axis).astype(float) / np.sum(weights, axis=axis).astype(float), nan=invalid)


def s_curve(x, mu, sigma):
    return 0.5 + 0.5 * erf((x - mu) / np.sqrt(2) / sigma)


def main(input_file, overwrite=False, no_fit=False):
    output_file = os.path.splitext(input_file)[0] + "_scurve.pdf"
    if os.path.isfile(output_file) and not overwrite:
        return
    print("Plotting", input_file)
    # Open file and fill histograms (actual plotting below)
    with tb.open_file(input_file) as f:
        cfg = get_config_dict(f)
        tdac = f.root.configuration_out.chip.masks.tdac[:]


        n_hits = f.root.Dut.shape[0]

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
        n_injections = int(cfg["configuration_in.scan.scan_config.n_injections"])
        the_vh = int(cfg["configuration_in.scan.scan_config.VCAL_HIGH"])
        start_vl = int(cfg["configuration_in.scan.scan_config.VCAL_LOW_start"])
        stop_vl = int(cfg["configuration_in.scan.scan_config.VCAL_LOW_stop"])
        step_vl = int(cfg["configuration_in.scan.scan_config.VCAL_LOW_step"])
        charge_dac_values = [
            the_vh - x for x in range(start_vl, stop_vl, step_vl)]
        subtitle = f"VH = {the_vh}, VL = {start_vl}..{stop_vl} (step {step_vl})"
        charge_dac_bins = len(charge_dac_values)
        charge_dac_range = [min(charge_dac_values) - 0.5, max(charge_dac_values) + 0.5]
        row_start = int(cfg["configuration_in.scan.scan_config.start_row"])
        row_stop = int(cfg["configuration_in.scan.scan_config.stop_row"])
        col_start = int(cfg["configuration_in.scan.scan_config.start_column"])
        col_stop = int(cfg["configuration_in.scan.scan_config.stop_column"])
        row_n, col_n = row_stop - row_start, col_stop - col_start

        # Prepare histograms
        occupancy = np.zeros((col_n, row_n, charge_dac_bins))
        tot_hist = [np.zeros((charge_dac_bins, 128)) for _ in range(len(FRONTENDS) + 1)]
        dt_tot_hist = [np.zeros((128, 479)) for _ in range(len(FRONTENDS) + 1)]
        dt_q_hist = [np.zeros((charge_dac_bins, 479)) for _ in range(len(FRONTENDS) + 1)]
        tot_per_pixel_hist = np.zeros((col_n, row_n, 128))

        # Process one chunk of data at a time
        csz = 2**24
        for i_first in tqdm(range(0, n_hits, csz), unit="chunk", disable=n_hits/csz<=1):
            i_last = min(n_hits, i_first + csz)

            # Load hits
            hits = f.root.Dut[i_first:i_last]
            # Filter only the hits in the scan area (from col/row_start to col/row_stop)
            # Sometimes disabled pixels outside of the scan area still fire for some reason
            scan_area_mask = (hits["col"] >= col_start) & (hits["col"] < col_stop) & (hits["row"] >= row_start) & (hits["row"] < row_stop)
            hits = hits[scan_area_mask]
            del scan_area_mask

            with np.errstate(all='ignore'):
                tot = (hits["te"] - hits["le"]) & 0x7f
            fe_masks = [(hits["col"] >= fc) & (hits["col"] <= lc) for fc, lc, _ in FRONTENDS]


            # Determine injected charge for each hit
            vh = scan_params["vcal_high"][hits["scan_param_id"]]
            vl = scan_params["vcal_low"][hits["scan_param_id"]]
            charge_dac = vh - vl
            del vl, vh
            # Count hits per pixel per injected charge value
            occupancy_tmp, occupancy_edges = np.histogramdd(
                (hits["col"], hits["row"], charge_dac),
                bins=[col_n, row_n, charge_dac_bins],
                range=[[col_start, col_stop], [row_start, row_stop], charge_dac_range])
            occupancy_tmp /= n_injections
            occupancy += occupancy_tmp
            del occupancy_tmp

            # Fill histogram with ToT distribution per pixel
            tot_per_pixel_tmp, tot_per_pixel_edges = np.histogramdd(
                (hits["col"], hits["row"], tot), bins=[col_n, row_n, 128],
                range=[[col_start, col_stop], [row_start, row_stop], [-0.5, 127.5]])
            tot_per_pixel_hist += tot_per_pixel_tmp
            del tot_per_pixel_tmp

            for i, ((fc, lc, _), mask) in enumerate(zip(chain([(0, 511, 'All FEs')], FRONTENDS), chain([slice(-1)], fe_masks))):
                if fc >= col_stop or lc < col_start:
                    continue

                # ToT vs injected charge as 2D histogram
                tot_hist[i] += np.histogram2d(
                    charge_dac[mask], tot[mask], bins=[charge_dac_bins, 128],
                    range=[charge_dac_range, [-0.5, 127.5]])[0]

                # Histograms of time since previous hit vs TOT and QINJ
                dt_tot_hist[i] += np.histogram2d(
                    tot[mask][1:], np.diff(hits["timestamp"][mask]) / 40.,
                    bins=[128, 479], range=[[-0.5, 127.5], [25e-3*16, 12*16]])[0]
                dt_q_hist[i] += np.histogram2d(
                    charge_dac[mask][1:], np.diff(hits["timestamp"][mask]) / 40.,
                    bins=[charge_dac_bins, 479], range=[charge_dac_range, [25e-3*16, 12*16]])[0]

            del charge_dac

    # Do the actual plotting
    with PdfPages(output_file) as pdf:
        plt.figure(figsize=(6.4, 4.8))

        draw_summary(input_file, cfg)
        pdf.savefig(); plt.clf()


        # # #### HERE
        # for t in zip(tdac):
        #     # draw_summary(input_file, c)
        #     # pdf.savefig(); plt.clf()

        #     # TDAC map
        #     plt.axes((0.125, 0.11, 0.775, 0.72))
        #     nzc, nzr = np.nonzero(t)
        #     if not nzc.size:
        #         fc, lc, fr, lr = 0, 512, 0, 512
        #     else:
        #         fc, lc = nzc.min(), nzc.max() + 1
        #         fr, lr = nzr.min(), nzr.max() + 1
        #     del nzc, nzr
        #     plt.pcolormesh(np.arange(fc, lc + 1), np.arange(fr, lr + 1),
        #                 t[fc:lc, fr:lr].transpose(),
        #                 vmin=-0.5, vmax=7.5, cmap=TDAC_CMAP, rasterized=True)
        #     plt.xlabel("Column")
        #     plt.ylabel("Row")
        #     plt.title("Map of TDAC values")
        #     frontend_names_on_top()
        #     integer_ticks_colorbar().set_label("TDAC")
        #     pdf.savefig(); plt.clf()
        # # print("Summary")

        if n_hits == 0:
            plt.annotate("No hits recorded!", (0.5, 0.5), ha='center', va='center')
            plt.gca().set_axis_off()
            pdf.savefig(); plt.clf()
            return

        # Look for the noisiest pixels
        top_left = np.array([[col_start, row_start]])
        max_occu = np.max(occupancy, axis=2)
        mask = max_occu > 1.05  # Allow a few extra hits
        noisy_list = np.argwhere(mask) + top_left
        noisy_indices = np.nonzero(mask)
        srt = np.argsort(-max_occu[noisy_indices])
        noisy_indices = tuple(x[srt] for x in noisy_indices)
        noisy_list = noisy_list[srt]
        if len(noisy_list):
            mi = min(len(noisy_list), 25)
            tmp = "\n".join(
                ",    ".join(f"({a}, {b}) = {float(c):.1f}" for (a, b), c in g)
                for g in groupwise(zip(noisy_list[:mi], max_occu[tuple(x[:mi] for x in noisy_indices)]), 4))
            plt.annotate(
                split_long_text(
                    "Noisiest pixels (col, row) = occupancy$_{max}$\n"
                    f"{tmp}"
                    f'{", ..." if len(noisy_list) > mi else ""}'
                    f"\nTotal = {len(noisy_list)} pixels ({len(noisy_list)/row_n/col_n:.1%})"
                ), (0.5, 0.5), ha='center', va='center')
            print(f"Noisy pixels (n = {len(noisy_list)})")
            print("[" + ", ".join(str((a, b)) for a, b in noisy_list) + "]")
            output_file_txt = os.path.splitext(input_file)[0]
            with open(output_file_txt + "_noisy_pixels_occu.txt", "w") as f1:
                print("[" + ", ".join(f'"{int(a)}, {int(b)}"' for a, b in noisy_list) + "]", file=f1)
        else:
            plt.annotate("No noisy pixel found.", (0.5, 0.5), ha='center', va='center')
        plt.gca().set_axis_off()
        pdf.savefig(); plt.clf()

        # Look for pixels with random ToT (those with hits with ToT ≥ 100)
        n_crazy_hits = np.sum(tot_per_pixel_hist[:,:,100:], axis=2)
        mask = n_crazy_hits > 0
        crazy_list = np.argwhere(mask) + top_left
        crazy_indices = np.nonzero(mask)
        srt = np.argsort(-n_crazy_hits[crazy_indices])
        crazy_indices = tuple(x[srt] for x in crazy_indices)
        crazy_list = crazy_list[srt]
        if len(crazy_list):
            mi = min(len(crazy_list), 50)
            tmp = "\n".join(
                ",    ".join(f"({a}, {b}) = {float(c):.0f}" for (a, b), c in g)
                for g in groupwise(zip(crazy_list[:mi], n_crazy_hits[tuple(x[:mi] for x in crazy_indices)]), 3))
            plt.annotate(
                split_long_text(
                    "Crazy pixels search (i.e. pixels with random ToT)\n"
                    "Pixels with ≥ 1 hit with ToT ≥ 100 (col, row)\n"
                    f"{tmp}"
                    f'{", ..." if len(crazy_list) > mi else ""}'
                    f"\nTotal = {len(crazy_list)} pixels ({len(crazy_list)/row_n/col_n:.1%})"
                ), (0.5, 0.5), ha='center', va='center')
            # print(f"Crazy pixels (n = {len(crazy_list)})")
            # print("\n".join(f"({a}, {b}) = {float(c):.0f}" for (a, b), c in zip(
            #     crazy_list, n_crazy_hits[tuple(x for x in crazy_indices)])))
            # print("[" + ", ".join(str((a, b)) for a, b in crazy_list) + "]")
        else:
            plt.annotate("No crazy pixel found.", (0.5, 0.5), ha='center', va='center')
        plt.gca().set_axis_off()
        pdf.savefig(); plt.clf()

        # S-Curve as 2D histogram
        occupancy_charges = occupancy_edges[2].astype(np.float32)
        occupancy_charges = (occupancy_charges[:-1] + occupancy_charges[1:]) / 2
        occupancy_charges = np.tile(occupancy_charges, (col_n, row_n, 1))
        for fc, lc, name in chain([(0, 511, 'All FEs')], FRONTENDS):
            if fc >= col_stop or lc < col_start:
                continue
            fc = max(0, fc - col_start)
            lc = min(col_n - 1, lc - col_start)
            plt.hist2d(occupancy_charges[fc:lc+1,:,:].reshape(-1),
                       occupancy[fc:lc+1,:,:].reshape(-1),
                       bins=[charge_dac_bins, 150], range=[charge_dac_range, [0, 2.5]],
                       norm=LogNorm(), cmin=1, rasterized=True)  # Necessary for quick save and view in PDF
            plt.title(subtitle)
            plt.suptitle(f"S-Curve ({name})")
            plt.xlabel("Injected charge [DAC]")
            plt.ylabel("Occupancy")
            plt.ylim(0, 1.5)
            plt.xlim(0, 70)
            plt.grid()
            set_integer_ticks(plt.gca().xaxis)
            cb = plt.colorbar()
            cb.set_label("Pixels / bin")
            pdf.savefig(); plt.clf()




        # Compute the threshold for each pixel as the weighted average
        # of the injected charge, where the weights are given by the
        # occupancy such that occu = 0.5 has weight 1, occu = 0,1 have
        # weight 0, and anything in between is linearly interpolated
        # Assuming the shape is an erf, this estimator is consistent
        w = np.maximum(0, 0.5 - np.abs(occupancy - 0.5))
        threshold_DAC = average(occupancy_charges, axis=2, weights=w, invalid=0)
        # Compute the noise (the width of the up-slope of the s-curve)
        # as a variance with the weights above
        noise_DAC = np.sqrt(average((occupancy_charges - np.expand_dims(threshold_DAC, -1))**2, axis=2, weights=w, invalid=0))
       #print("Pixels with THR  < 1")
        #for col, row in zip(*np.nonzero(threshold_DAC < 1)):
        #    print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        # print("Pixels with 1 < THR < 25")
        # for col, row in zip(*np.nonzero((1 < threshold_DAC) & (threshold_DAC < 25))):
        #     print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        print("THR for selected pixels pixels with weighted average")
        for col, row in [(300,509),(300,409),(300,309), (300,209), (300,109), (300,9), (300,2)]\
        :
            if not (col_start <= col < col_stop and row_start <= row < row_stop):
                continue
            print(f"    ({col:3d}, {row:3d}), THR = {threshold_DAC[col-col_start,row-row_start]:.2f}, noise = {noise_DAC[col-col_start,row-row_start]:.2f}")
        print("Pixels with THR > 70")
        for col, row in zip(*np.nonzero(threshold_DAC > 70)):
             print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]:.2f}")
         #print("First 10 pixels with 34 < THR < 36")
         #for i, (col, row) in enumerate(zip(*np.nonzero((34 < threshold_DAC) & (threshold_DAC < 36)))):
         #    if i >= 100:
         #        break
         #    print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")


        print("BEFORE fit First 500 pixels with THR < 30")
        # print("Number of pixel with THR < 30 ",len(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 30))))
        index = -1
        for i, (col, row) in enumerate(zip(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 30)))):
            index = i
            if i >= 500:
                a = 0
            else:
                print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]:.1f}, Noise = {noise_DAC[col,row]:.1f}, TDAC= {tdac[col+col_start,row+row_start]}")
            #print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        print("Number of pixel with THR < 30 ",index+1)

        print("First 100 pixels with noise > 4")
        # print("# of pixel with THR < 28 ",len(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 28))))
        index = -1
        for i, (col, row) in enumerate(zip(*np.nonzero((noise_DAC > 4 )))):
            index = i
            if i >= 100:
                a = 0
            else:
                print(f"    ({col+col_start:3d}, {row+row_start:3d}), Noise = {noise_DAC[col,row]:.1f}, THR = {threshold_DAC[col,row]:.1f}, TDAC= {tdac[col+col_start,row+row_start]}")
            #print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        print("Number of pixel with noise > 4 ",index+1)

        charge_dac_np = np.array(charge_dac_values)
        if not no_fit:
            # Compute the threshold and noise for each pixels by fitting
            # each s-curve with an error function
            threshold_DAC = np.zeros((col_n, row_n))
            noise_DAC = np.zeros((col_n, row_n))
            for c in tqdm(range(col_n), unit='col', desc='fit', delay=2):
                for r in range(row_n):
                    o = np.clip(occupancy[c,r], 0, 1)
                    if not (np.any(o == 0) and np.any(o == 1)):
                        continue
                    thr = charge_dac_np[np.argmin(np.abs(o - 0.5))]
                    try:
                        popt, pcov = curve_fit(s_curve, charge_dac_np, o, p0=(thr, 1))
                    except RuntimeError:
                        popt = np.full(2, np.nan)
                        pcov = np.full((2, 2), np.nan)
                    if not np.all(np.isfinite(popt)) or not np.all(np.isfinite(pcov)):
                        print("Fit failed:", c + col_start, r + row_start, o)
                        continue
                    threshold_DAC[c,r], noise_DAC[c,r] = popt

            #print("Pixels with THR  < 1")
            #for col, row in zip(*np.nonzero(threshold_DAC < 1)):
            #    print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
            # print("Pixels with 1 < THR < 25")
            # for col, row in zip(*np.nonzero((1 < threshold_DAC) & (threshold_DAC < 25))):
            #     print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
            print("THR for selected pixels pixels with fit")
            for col, row in [(300,509),(300,409),(300,309), (300,209), (300,109), (300,9), (300,2)]\
            :
                if not (col_start <= col < col_stop and row_start <= row < row_stop):
                    continue
                print(f"    ({col:3d}, {row:3d}), THR = {threshold_DAC[col-col_start,row-row_start]:.2f}, noise = {noise_DAC[col-col_start,row-row_start]:.2f}")
            print("Pixels with THR > 70")
            for col, row in zip(*np.nonzero(threshold_DAC > 70)):
                print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]:.2f}")
            #print("First 10 pixels with 34 < THR < 36")
            #for i, (col, row) in enumerate(zip(*np.nonzero((34 < threshold_DAC) & (threshold_DAC < 36)))):
            #    if i >= 100:
            #        break
            #    print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")

        print("AFTER fit: First 500 pixels with THR < 30")
        # print("Number of pixel with THR < 30 ",len(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 30))))
        index = -1
        for i, (col, row) in enumerate(zip(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 30)))):
            index = i
            if i >= 500:
                a = 0
            else:
                print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]:.1f}, Noise = {noise_DAC[col,row]:.1f}, TDAC= {tdac[col+col_start,row+row_start]}")
            #print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        print("Number of pixel with THR < 30 ",index+1)

        print("First 100 pixels with noise > 4")
        # print("# of pixel with THR < 28 ",len(*np.nonzero((threshold_DAC > 0 )&(threshold_DAC < 28))))
        index = -1
        for i, (col, row) in enumerate(zip(*np.nonzero((noise_DAC > 4 )))):
            index = i
            if i >= 100:
                a = 0
            else:
                print(f"    ({col+col_start:3d}, {row+row_start:3d}), Noise = {noise_DAC[col,row]:.1f}, THR = {threshold_DAC[col,row]:.1f}, TDAC= {tdac[col+col_start,row+row_start]}")
            #print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        print("Number of pixel with noise > 4 ",index+1)

        # S-Curve for specific pixels
#        for col, row in [(219, 161), (219, 160), (220, 160), (221, 160), (220, 159), (221, 159) ,(222,188) , (219,192), (218,155), (216,117), (222,180), (222,170),(221,136),(221,205),(221,174)]:
        # for col, row in [(221, 160),(222,188) , (222,180), (222,170),(221,205),(221,174), (218,155), (218,150), (219,192), (219,180) , (213,213)]:
        i2 = 0
        for i, (col, row) in enumerate(
        #          [(140,132),(132,133),(132,200),(192,4), (192,20),(192,100),(192,200),(193,4), (193,100) ]
        # +        [(193,200),(10,255), (8,447), (36,123), (41,462) , (180, 127), (190, 120), (181, 164), (210, 165),(213, 213)]
        # +        [(217, 150), (214, 151), (213, 151), (218, 155), (213, 121), (213, 122), (214, 121), (217, 122), (218, 123)]
        # +        [(219, 120), (222, 120), (219, 117)]
        # +        [(0, 50), (0, 100), (0,127), (0,130), (0,131), (0,132), (0,133), (0,140)]
        # +        [(240, 390), (240, 181), (50,306), (50,221), (50,500),(50,501),(50,502)]
        # +        [(50,503),(50,504),(50,505),(50,506),(50,507),(50,508),(50,509),(50,510),(50,511)]
        # +        [(300,110),(300,500)]
        [(288,2),(288,100),(288,200),(288,300),(288,400),(288,511),(288,512), (288,342), (289,238)]
        #   [(300,512),(300,511),(301,512), (301,511), (300,500), (301,500),(300,2),(470,137),(471,474),(470,150)]
        # +       [(300,110),(300,118),(300,120),(300,200),(300,300),(300,400),(300,500)]\
            #+        [(300,110),(300,111),(300,112),(300,113),(300,114),(300,115),(300,116),(300,117),(300,118),(300,120),]\
                #+        [(1, 50), (1, 100), (1,127), (1,130), (1,131), (1,132), (1,133)] \
               #+        [(1, 140), (2, 142), (1, 152), (1, 173), (1, 210)] \
        ):
            if not (col_start <= col < col_stop and row_start <= row < row_stop):
                continue
            i2 = (i2 + 1) % len(plt.rcParams['axes.prop_cycle'].by_key()['color'])
            # plt.plot(charge_dac_values, occupancy[col-col_start,row-row_start,:], f'C{i2}.-', label=str((col, row)))
            if no_fit:
                plt.plot(charge_dac_values, occupancy[col-col_start,row-row_start,:], f'C{i2}.-', label=str((col, row)))
            else:
                plt.plot(charge_dac_values, occupancy[col-col_start,row-row_start,:], f'C{i2}.', label=str((col, row)))
                plt.plot(charge_dac_np, s_curve(charge_dac_np, threshold_DAC[col-col_start,row-row_start], noise_DAC[col-col_start,row-row_start]), f'C{i2}-')
        plt.title(subtitle)
        plt.suptitle(f"S-Curve of specific pixels")
        plt.xlabel("Injected charge [DAC]")
        plt.ylabel("Occupancy")
        plt.ylim(0, 1.5)
        plt.xlim(0, 70)
        plt.grid()
        plt.legend(ncol=2)
        set_integer_ticks(plt.gca().xaxis)
        pdf.savefig(); plt.clf()

        # ToT vs injected charge as 2D histogram
        for (fc, lc, name), hist in zip(chain([(0, 511, 'All FEs')], FRONTENDS), tot_hist):
            if fc >= col_stop or lc < col_start:
                continue
            # create hist_odd and even to separate them
            hist_even_cols = hist[fc:lc+1:2,:]
            hist_odd_cols = hist[fc+1:lc+1:2,:]

            plt.pcolormesh(
                occupancy_edges[2], np.linspace(-0.5, 127.5, 129, endpoint=True),
                hist.transpose(), vmin=1, cmap=VIRIDIS_WHITE_UNDER, rasterized=True)  # Necessary for quick save and view in PDF
            plt.title(subtitle)
            plt.suptitle(f"ToT curve ({name})")
            plt.xlabel("Injected charge [DAC]")
            plt.ylabel("ToT [25 ns]")
            plt.ylim(0,40)
            plt.xlim(0,220)
            plt.grid(axis='both',)
            set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
            cb = integer_ticks_colorbar()
            cb.set_label("Hits / bin")
            pdf.savefig(); plt.clf()

            # plt.pcolormesh(
            #     occupancy_edges[2], np.linspace(-0.5, 127.5, 129, endpoint=True),
            #     hist_even_cols.transpose(), vmin=1, cmap=VIRIDIS_WHITE_UNDER, rasterized=True)  # Necessary for quick save and view in PDF
            # plt.title(subtitle)
            # plt.suptitle(f"ToT curve ({name} even cols)")
            # plt.xlabel("Injected charge [DAC]")
            # plt.ylabel("ToT [25 ns]")
            # plt.ylim(0,70)
            # plt.xlim(0,250)
            # plt.grid(axis='both',)
            # set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
            # cb = integer_ticks_colorbar()
            # cb.set_label("Hits / bin")
            # pdf.savefig(); plt.clf()

            # plt.pcolormesh(
            #     occupancy_edges[2], np.linspace(-0.5, 127.5, 129, endpoint=True),
            #     hist_odd_cols.transpose(), vmin=1, cmap=VIRIDIS_WHITE_UNDER, rasterized=True)  # Necessary for quick save and view in PDF
            # plt.title(subtitle)
            # plt.suptitle(f"ToT curve ({name} odd cols)")
            # plt.xlabel("Injected charge [DAC]")
            # plt.ylabel("ToT [25 ns]")
            # plt.ylim(0,70)
            # plt.xlim(0,250)
            # plt.grid(axis='both',)
            # set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
            # cb = integer_ticks_colorbar()
            # cb.set_label("Hits / bin")
            # pdf.savefig(); plt.clf()

        #print("Pixels with THR  < 1")
        #for col, row in zip(*np.nonzero(threshold_DAC < 1)):
        #    print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        # print("Pixels with 1 < THR < 25")
        # for col, row in zip(*np.nonzero((1 < threshold_DAC) & (threshold_DAC < 25))):
        #     print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        # print("Pixels with THR > 50")
        # for col, row in zip(*np.nonzero(threshold_DAC > 50)):
        #     print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")
        # print("First 10 pixels with 34 < THR < 36")
        # for i, (col, row) in enumerate(zip(*np.nonzero((34 < threshold_DAC) & (threshold_DAC < 36)))):
        #     if i >= 100:
        #         break
        #     print(f"    ({col+col_start:3d}, {row+row_start:3d}), THR = {threshold_DAC[col,row]}")

        # Threshold hist
        m1 = int(max(charge_dac_range[0], threshold_DAC.min() - 2))
        m2 = int(min(charge_dac_range[1], threshold_DAC.max() + 2))
        # m1=0
        # m2=35
        for i, (fc, lc, name) in enumerate(FRONTENDS):
            # print(fc,lc)
            if fc >= col_stop or lc < col_start:
                continue
            fc = max(0, fc - col_start)
            lc = min(col_n - 1, lc - col_start)
            # print(fc,lc)
            th = threshold_DAC[fc:lc+1,:]
            #th = threshold_DAC[fc+1:lc+1:2,:]
            th_mean = ufloat(np.mean(th[th>0]), np.std(th[th>0], ddof=1))
            plt.hist(th.reshape(-1), bins=m2-m1, range=[m1, m2],
                     label=f"{name} ${th_mean:L}$", histtype='step', color=f"C{i}")
        plt.title(subtitle)
        plt.suptitle("Threshold distribution all cols")
        plt.xlabel("Threshold [DAC]")
        plt.ylabel("Pixels / bin")
        set_integer_ticks(plt.gca().yaxis)
        plt.legend()
        plt.grid(axis='y')
        plt.grid(axis='x')
        plt.yscale('log')
        pdf.savefig(); plt.clf()

        for i, (fc, lc, name) in enumerate(FRONTENDS):
            # print(fc,lc)
            if fc >= col_stop or lc < col_start:
                continue
            fc = max(0, fc - col_start)
            lc = min(col_n - 1, lc - col_start)
            # print(fc,lc)
            th = threshold_DAC[fc:lc+1:2,:]
            #th = threshold_DAC[fc+1:lc+1:2,:]
            th_mean = ufloat(np.mean(th[th>0]), np.std(th[th>0], ddof=1))
            plt.hist(th.reshape(-1), bins=m2-m1, range=[m1, m2],
                     label=f"{name} ${th_mean:L}$", histtype='step', color=f"C{i}")
        plt.title(subtitle)
        plt.suptitle("Threshold distribution even cols")
        plt.xlabel("Threshold [DAC]")
        plt.ylabel("Pixels / bin")
        set_integer_ticks(plt.gca().yaxis)
        plt.legend()
        plt.grid(axis='y')
        plt.grid(axis='x')
        plt.yscale('log')
        pdf.savefig(); plt.clf()

        for i, (fc, lc, name) in enumerate(FRONTENDS):
            # print(fc,lc)
            if fc >= col_stop or lc < col_start:
                continue
            fc = max(0, fc - col_start)
            lc = min(col_n - 1, lc - col_start)
            # print(fc,lc)
            #th = threshold_DAC[fc:lc+1:2,:]
            th = threshold_DAC[fc+1:lc+1:2,:]
            th_mean = ufloat(np.mean(th[th>0]), np.std(th[th>0], ddof=1))
            plt.hist(th.reshape(-1), bins=m2-m1, range=[m1, m2],
                     label=f"{name} ${th_mean:L}$", histtype='step', color=f"C{i}")
        plt.title(subtitle)
        plt.suptitle("Threshold distribution odd cols")
        plt.xlabel("Threshold [DAC]")
        plt.ylabel("Pixels / bin")
        set_integer_ticks(plt.gca().yaxis)
        plt.legend()
        plt.grid(axis='y')
        plt.grid(axis='x')
        plt.yscale('log')
        pdf.savefig(); plt.clf()




        # Threshold map
        plt.axes((0.125, 0.11, 0.775, 0.72))
        plt.pcolormesh(occupancy_edges[0], occupancy_edges[1], threshold_DAC.transpose(), vmin=20, vmax=33,
                       rasterized=True)  # Necessary for quick save and view in PDF
        plt.title(subtitle)
        plt.suptitle("Threshold map")
        plt.xlabel("Column")
        plt.ylabel("Row")
        set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
        cb = plt.colorbar()
        cb.set_label("Threshold [DAC]")
        frontend_names_on_top()
        pdf.savefig(); plt.clf()

        # Noise hist
        m = int(np.ceil(noise_DAC.max(initial=0, where=np.isfinite(noise_DAC)))) + 1
        for i, (fc, lc, name) in enumerate(FRONTENDS):
            if fc >= col_stop or lc < col_start:
                continue
            fc = max(0, fc - col_start)
            lc = min(col_n - 1, lc - col_start)
            ns = noise_DAC[fc:lc+1,:]
            noise_mean = ufloat(np.mean(ns[ns>0]), np.std(ns[ns>0], ddof=1))
            plt.hist(ns.reshape(-1), bins=min(20*m, 100), range=[0, m],
                     label=f"{name} ${noise_mean:L}$", histtype='step', color=f"C{i}")
        plt.title(subtitle)
        plt.suptitle(f"Noise (width of s-curve slope) distribution")
        plt.xlabel("Noise [DAC]")
        plt.ylabel("Pixels / bin")
        set_integer_ticks(plt.gca().yaxis)
        plt.grid(axis='y')
        plt.grid(axis='x')
        plt.yscale('log')
        plt.legend()
        pdf.savefig(); plt.clf()



        # Noise map
        plt.axes((0.125, 0.11, 0.775, 0.72))
        plt.pcolormesh(occupancy_edges[0], occupancy_edges[1], noise_DAC.transpose(),vmin=0, vmax=8,
                       rasterized=True)  # Necessary for quick save and view in PDF
        plt.title(subtitle)
        plt.suptitle("Noise (width of s-curve slope) map")
        plt.xlabel("Column")
        plt.ylabel("Row")
        set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
        cb = plt.colorbar()
        cb.set_label("Noise [DAC]")
        frontend_names_on_top()
        pdf.savefig(); plt.clf()

        # Time since previous hit vs ToT
        for (fc, lc, name), hist in zip(chain([(0, 511, 'All FEs')], FRONTENDS), dt_tot_hist):
            if fc >= col_stop or lc < col_start:
                continue
            plt.pcolormesh(
                np.linspace(-0.5, 127.5, 129, endpoint=True),
                np.linspace(25e-3, 12, 480, endpoint=True),
                hist.transpose(), vmin=1, cmap=VIRIDIS_WHITE_UNDER, rasterized=True)
            plt.title(subtitle)
            plt.suptitle(f"Time between hits ({name})")
            plt.xlabel("ToT [25 ns]")
            plt.ylabel("$\\Delta t_{{token}}$ from previous hit [μs]")
            set_integer_ticks(plt.gca().xaxis)
            cb = integer_ticks_colorbar()
            cb.set_label("Hits / bin")
            pdf.savefig(); plt.clf()

        # Time since previous hit vs injected charge
        m = 32 if tot.max() <= 32 else 128
        for (fc, lc, name), hist in zip(chain([(0, 511, 'All FEs')], FRONTENDS), dt_q_hist):
            if fc >= col_stop or lc < col_start:
                continue
            plt.pcolormesh(
                occupancy_edges[2],
                np.linspace(25e-3, 12, 480, endpoint=True),
                hist.transpose(), vmin=1, cmap=VIRIDIS_WHITE_UNDER, rasterized=True)
            plt.title(subtitle)
            plt.suptitle(f"Time between hits ({name})")
            plt.xlabel("Injected charge [DAC]")
            plt.ylabel("$\\Delta t_{{token}}$ from previous hit [μs]")
            set_integer_ticks(plt.gca().xaxis)
            cb = integer_ticks_colorbar()
            cb.set_label("Hits / bin")
            pdf.savefig(); plt.clf()

        plt.close()

        # Save some data
        threshold_data = np.full((512, 512), np.nan)
        threshold_data[col_start:col_stop,row_start:row_stop] = threshold_DAC
        noise_data = np.full((512, 512), np.nan)
        noise_data[col_start:col_stop,row_start:row_stop] = noise_DAC
        np.savez_compressed(
            os.path.splitext(output_file)[0] + ".npz",
            thresholds=threshold_data,
            noise=noise_data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "input_file", nargs="*",
        help="The _threshold_scan_interpreted.h5 file(s)."
             " If not given, looks in output_data/module_0/chip_0.")
    parser.add_argument("-f", "--overwrite", action="store_true",
                        help="Overwrite plots when already present.")
    parser.add_argument("--no-fit", action="store_true",
                        help="Compute thresholds and noise with weighted average instead of erf fit.")
    args = parser.parse_args()

    files = []
    if args.input_file:  # If anything was given on the command line
        for pattern in args.input_file:
            files.extend(glob.glob(pattern, recursive=True))
    else:
        files.extend(glob.glob("output_data/module_0/chip_0/*_threshold_scan_interpreted.h5"))
    files.sort()

    for fp in tqdm(files, unit="file"):
        try:
            main(fp, args.overwrite, args.no_fit)
        except Exception:
            print(traceback.format_exc())
