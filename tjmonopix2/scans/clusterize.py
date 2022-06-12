import os
import argparse
import glob
from math import sqrt
import tables as tb
import numpy as np
from tqdm import tqdm

CLS_DTYPE = np.dtype([
    ("timestamp", "i8"),
    ("n_pixels", "i4"),
    ("mean_col", "f4"),  # ToT-weighted mean of the columns
    ("std_col", "f4"),  # Sample standard deviation of the columns
    ("mean_row", "f4"),  # Same as above, but with the rows
    ("std_row", "f4"),  # Same as above, but with the rows
    ("sum_tot", "i4")])

path = os.path.dirname(__file__)
path = os.path.join(path, "output_data")

####### MAIN #######
parser = argparse.ArgumentParser(description="Clusterizes the _interpreted.h5 files in output_data.")
parser.add_argument("-f", "--overwrite", action="store_true", help="Overwrite files that already exist")
parser.add_argument("-l", "--last", type=int, default=0, metavar="N", help="Only process the last N files")
args = parser.parse_args()

input_files = glob.glob(path + '/module_*/chip_*/*_interpreted.h5')
input_files.sort()
if args.last and len(input_files) > args.last:
    input_files = input_files[-args.last:]
for ifp in input_files:
    ofp = ifp[:-len("_interpreted.h5")] + "_clusterized.h5"
    if os.path.isfile(ofp) and not args.overwrite:
        continue

    print("CLUSTERIZING", os.path.basename(ifp))
    with tb.open_file(ifp) as in_file, tb.open_file(ofp, "w") as out_file:
        # Copy register settings
        in_file.copy_node("/configuration_in", out_file.root)
        in_file.copy_node("/configuration_out", out_file.root)
        in_file.copy_children("/configuration_in", out_file.root.configuration_in, recursive=True)
        in_file.copy_children("/configuration_out", out_file.root.configuration_out, recursive=True)

        # Create the clusters table
        cls_table = out_file.create_table(
            "/", "Cls", CLS_DTYPE, "Clusters", filters=tb.Filters(5, "blosc"))

        # Clusterize
        first = True
        for row in tqdm(in_file.root.Dut.iterrows(), unit="hits", total=in_file.root.Dut.nrows, unit_scale=True):
            if first or row["timestamp"] != cls_table.row["timestamp"]:
                # Write cluster
                if not first:
                    cls_table.row["std_col"] = sqrt(var_col)
                    cls_table.row["std_row"] = sqrt(var_row)
                    cls_table.row.append()
                first = False
                # Reset cluster info
                cls_table.row["timestamp"] = row["timestamp"]
                cls_table.row["n_pixels"] = 0
                cls_table.row["mean_col"] = 0
                cls_table.row["mean_row"] = 0
                cls_table.row["std_row"] = 0
                cls_table.row["sum_tot"] = 0
                var_col, var_row = 0, 0
            # Update cluster info
            cls_table.row["n_pixels"] += 1
            # sum of ToT, which is also needed in the weighted means
            tot = (row["te"] - row["le"]) & 0x7f
            sum_tot_prev = cls_table.row["sum_tot"]
            cls_table.row["sum_tot"] += tot
            # (weighted) mean col and row https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance#Welford's_online_algorithm
            if tot and cls_table.row["sum_tot"]:
                mean_col_prev = cls_table.row["mean_col"]
                mean_row_prev = cls_table.row["mean_row"]
                cls_table.row["mean_col"] += \
                    tot * (row["col"] - cls_table.row["mean_col"]) / cls_table.row["sum_tot"]
                cls_table.row["mean_row"] += \
                    tot * (row["row"] - cls_table.row["mean_row"]) / cls_table.row["sum_tot"]
                if sum_tot_prev:
                    var_col += tot * (row["col"] - mean_col_prev)**2 / cls_table.row["sum_tot"] \
                        - cls_table.row["std_col"] / sum_tot_prev
                    var_row += tot * (row["row"] - mean_row_prev)**2 / cls_table.row["sum_tot"] \
                        - cls_table.row["std_row"] / sum_tot_prev
        # Write last cluster
        if cls_table.row["n_pixels"]:
            cls_table.row["std_col"] = sqrt(var_col)
            cls_table.row["std_row"] = sqrt(var_row)
            cls_table.row.append()
        # Save data to disk
        cls_table.flush()
