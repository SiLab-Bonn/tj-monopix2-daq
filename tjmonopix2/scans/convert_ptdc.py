# Converter for data from the tapped delay line TDC provided by basil
#
# Copyright SiLab Bonn, 2025
#

from pathlib import Path

import numpy as np
import tables as tb
from numba import njit
from tqdm import tqdm

from tjmonopix2.analysis import analysis

corry_dtype = [     ("column", "<u2"),     ("row", "<u2"),     ("raw", "<u2"),     ("charge", "<f8"),     ("timestamp", "<f8"),     ("trigger_number", "<u4") ]

@njit
def correct_ts_overflow(original, to_compare):
    while original < to_compare:
        original += 2**31
    return original


@njit
def process_chunk(hits, trg_words, rsg_words, flg_words, trigger_ts, trigger_n):
    hit_i = 0

    trg_i, rsg_i, flg_i = 0, 0, 0  # Index in word table to write corresponding data

    while hit_i < len(hits):
        if hits[hit_i]["col"] == 1023:  # Correct TLU timestamp overflow to match TDC words
            trigger_n += 1

            # Correct trigger timestamp overflow for current TLU word
            trigger_ts = correct_ts_overflow(hits[hit_i]["timestamp"], trigger_ts)
        elif hits[hit_i]["col"] == 1021 and np.abs(hits[hit_i]["timestamp"] - (trigger_ts & 0x1FF_FFFF)) < 15:  # pTDC words
            # Matched, TDC word is within expected time distance from trigger timestamp
            # Use 63 bit only to accomodate for 64-bit integer since python only knows int. Trust that the timestamp will never be that large
            tdc_timestamp = 25. * ((trigger_ts & 0xFF_FFFF_FE00_0000) + (hits[hit_i]["timestamp"] & 0x1FF_FFFF))  # Absolute time in run in ns
            tdc_timestamp = tdc_timestamp - 2 * 6.25  # Timestamp is latched in firmware module two 160 MHz clock cycles after measurement start

            # Lastly, write TDC signals to file
            if hits[hit_i]["le"] == 0 and hits[hit_i]["te"] == 0:  # "triggered" word
                trg_words[trg_i]["timestamp"] = tdc_timestamp + hits[hit_i]["token_id"] / 1000  # Adjust timestamp
                trg_words[trg_i]["trigger_number"] = trigger_n
                trg_i += 1
            elif hits[hit_i]["le"] == 1 and hits[hit_i]["te"] == 0:  # "rising" word
                rsg_words[rsg_i]["timestamp"] = tdc_timestamp + hits[hit_i]["token_id"] / 1000  # Adjust timestamp
                rsg_words[rsg_i]["trigger_number"] = trigger_n
                rsg_i += 1
            elif hits[hit_i]["le"] == 0 and hits[hit_i]["te"] == 1:  # "falling" word
                flg_words[flg_i]["timestamp"] = tdc_timestamp + hits[hit_i]["token_id"] / 1000  # Adjust timestamp
                flg_words[flg_i]["trigger_number"] = trigger_n
                flg_i += 1
        hit_i += 1

    return trg_words, rsg_words, flg_words, trigger_ts, trigger_n


def format_ptdc(input_filename, output_filename=None, chunk_size=500000):
    """Convert Mimosa26 data recorded with pymosa to the corryvreckan EventLoaderHDF5 format. The output is a single
    HDF5 file with one node per telescope plane. The calibration of the delay line is already done at the
    interpretation stage.

    Args:
        input_filename (str): Path and name of the interpreted file (_interpreted.h5)
        output_filename (str | Path, optional): Path and name of the converted file. Defaults to the input filename with
            suffix `_converted`.
        chunk_size (int, optional): Process chunk_size hits of the input file at a time. Defaults to 500000.
    """
    if not output_filename:
        output_filename = input_filename[:-3] + "_ptdc.h5"
    if not isinstance(output_filename, Path):
        output_filename = Path(output_filename)

    # Create output file path if it does not exist
    Path(output_filename.parents[0]).mkdir(parents=True, exist_ok=True)

    with tb.open_file(input_filename, "r") as in_file:
        start_idx = 0
        n_words = len(in_file.root.Dut)

        word_types = ["trigger", "rising", "falling"]  # For now, analyze all possible TDC words

        with tb.open_file(output_filename, "w") as out_file:
            out_tables = [
                out_file.create_table(
                    out_file.root,
                    name=word_types[idx].title(),
                    description=np.dtype(corry_dtype),
                    filters=tb.Filters(complib="blosc", complevel=5, fletcher32=False),
                )
                for idx in range(len(word_types))
            ]

            trigger_ts, trigger_n = 0, 0

            pbar = tqdm(total=n_words)
            while start_idx < n_words:
                end_idx = min(n_words, start_idx + chunk_size)
                hits = in_file.root.Dut[start_idx:end_idx]

                trg_words = np.zeros(len(hits), dtype=corry_dtype)
                rsg_words = np.zeros(len(hits), dtype=corry_dtype)
                flg_words = np.zeros(len(hits), dtype=corry_dtype)
                trg_words, rsg_words, flg_words, trigger_ts, trigger_n = process_chunk(
                    hits, trg_words, rsg_words, flg_words, trigger_ts, trigger_n
                )

                out_tables[0].append(trg_words[trg_words["timestamp"] != 0])
                out_tables[1].append(rsg_words[rsg_words["timestamp"] != 0])
                out_tables[2].append(flg_words[flg_words["timestamp"] != 0])
                for table in out_tables:
                    table.flush
                pbar.update(end_idx - start_idx)
                start_idx += chunk_size
            pbar.close()

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

if __name__ == "__main__":
        
    # for run in ["run_25", "run_24", "run_26"]:

    #     # path_in = "/media/data/DESY_NOV_2025/" + run
    #     # input_file = find_latest_file(path=path_in, index="ext_trigger_scan_interpreted.h5")

    #     # format_ptdc(input_filename=input_file, output_filename=path_in + '/data/ptdc.h5')

    # path_in = "/media/data/DESY_NOV_2025/" + run
    input_file_path = '/home/rasmus/git/tj-monopix2-daq/tjmonopix2/scans/output_data/module_0/chip_0/20260512_143108_ext_trigger_scan.h5'

    if "_interpreted.h5" not in str(input_file_path):
        with analysis.Analysis(
            raw_data_file=str(input_file_path),
            store_hits=True,
            create_pdf=False,
            build_events=False,
            chunk_size = 10000000,
        ) as a:
            a.analyze_data()
            input_file = a.analyzed_data_file

    format_ptdc(input_filename=input_file, output_filename='/home/rasmus/git/tj-monopix2-daq/tjmonopix2/scans/output_data/module_0/chip_0/ptdc.h5')
