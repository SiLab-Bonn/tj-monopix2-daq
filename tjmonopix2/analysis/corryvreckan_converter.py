#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from pathlib import Path
from tqdm import tqdm

import numpy as np
import tables as tb

from tjmonopix2.analysis import analysis
from tjmonopix2.analysis import analysis_utils as au


def format_dut(input_filename: str | Path, output_filename: str | Path = None, trigger_mode: str = "AIDA", electron_conversion_factor: float = 8.8, chunk_size: int = 1000000) -> None:
    """Format hit table to be compatible with corryvreckan EventLoaderHDF5 as of commit c2e57986

    Parameters
    ----------
    input_filename : str | Path
        Interpreted hit file with Hit and/or Event data depending on trigger_mode
    output_filename : str | Path, optional
         Output file name. If None, defaults to input_filename with suffix '_converted', by default None
    trigger_mode : str, optional
        Trigger mode during data taking. EUDET mode (with trigger handshake) and AIDA, mode (without
        handshake only) are supported. In general, use `DATA_FORMAT=1` in `testbench.yaml` for data
        taking. By default "AIDA"
    electron_conversion_factor : float, optional
        Factor to convert injection DAC to electrons (unit: e / ΔVcal)
    chunk_size : int, optional
        Set the chunk size as integer defaults to 1000000.
    tot_calib_file : str | Path, optional
        Additional file with InjTotCalibration node containing TOT response fit parameters per pixel.

    Raises
    ------
    RuntimeError
        Invalid trigger mode selected
    """
    hit_dtype_converted = np.dtype(
        [("column", "<u2"), ("row", "<u2"), ("raw", "<u2"), ("charge", "<f8"), ("timestamp", "<f8"), ("trigger_number", "<u4")]
    )

    if type(input_filename) is str:
        input_filename = Path(input_filename)
    if output_filename is None:
        output_filename = Path(input_filename.parent) / Path(input_filename.stem + "_converted" + input_filename.suffix)

    if tot_calib_file:
        with tb.open_file(tot_calib_file, "r") as calib_file:
            calib_data = calib_file.root.InjTotCalibration[:]

    with tb.open_file(input_filename, "r") as in_file:
        n_words = in_file.root.Dut.shape[0]

        if trigger_mode.lower() == "aida":
            with tb.open_file(output_filename, "w") as out_file:
                hit_table_out = out_file.create_table(
                    out_file.root, name="Hits",
                    description=hit_dtype_converted,
                    filters=tb.Filters(complib="blosc", complevel=5, fletcher32=False)
                )
                for chunk in tqdm(range(0, n_words, chunk_size)):
                    chunk_offset = chunk
                    stop = chunk_offset + chunk_size
                    if chunk + chunk_size > n_words:
                        stop = n_words
                    hit_table_in = in_file.root.Dut[chunk_offset:stop]
                    sel = hit_table_in["col"] <= 512  # Select only DUT words
                    hits_selected = hit_table_in[sel]
                    hit_table_converted = np.zeros(len(hits_selected), dtype=hit_dtype_converted)
                    hit_table_converted["column"] = hits_selected["col"]
                    hit_table_converted["row"] = hits_selected["row"]
                    hit_table_converted["raw"] = (hits_selected["te"] - hits_selected["le"]) & 0x7F  # calculate TOT
                    if tot_calib_file:
                        hit_table_converted["charge"] = electron_conversion_factor * au._inv_tot_response_func(
                            (hits_selected["te"] - hits_selected["le"]) & 0x7F,
                            calib_data[hits_selected[:]["col"], hits_selected[:]["row"]][:, 0],
                            calib_data[hits_selected[:]["col"], hits_selected[:]["row"]][:, 1],
                            calib_data[hits_selected[:]["col"], hits_selected[:]["row"]][:, 2],
                        )
                    else:
                        hit_table_converted["charge"] = hit_table_converted["raw"]
                    hit_table_converted["timestamp"] = 25. * hits_selected["timestamp"].astype(np.uint64)  # convert to ns
                    hit_table_converted["trigger_number"] = 0
                    hit_table_out.append(hit_table_converted)
                hit_table_out.flush()

        elif trigger_mode.lower() == "eudet":
            with tb.open_file(output_filename, "w") as out_file:
                hit_table_out = out_file.create_table(out_file.root, name="Hits", description=hit_dtype_converted)
                for chunk in tqdm(range(0, n_words, chunk_size)):
                    chunk_offset = chunk
                    stop = chunk_offset + chunk_size
                    if chunk + chunk_size > n_words:
                        stop = n_words
                    hit_table_in = in_file.root.Hits[chunk_offset:stop]
                    sel = hit_table_in["column"] <= 512  # Select only DUT words
                    hits_selected = hit_table_in[sel]
                    # Hits are already assiged to TLU number in event builder and data has been pre-formatted
                    # Only convert column names and types
                    hit_table_converted = np.zeros(len(hits_selected), dtype=hit_dtype_converted)
                    hit_table_converted["column"] = hits_selected["column"]
                    hit_table_converted["row"] = hits_selected["row"]
                    hit_table_converted["raw"] = hits_selected["charge"]
                    if tot_calib_file:
                        hit_table_converted["charge"] = electron_conversion_factor * au._inv_tot_response_func(
                            hits_selected["charge"],
                            # Subtract one since event builder adds + 1 for legacy reasons
                            calib_data[hits_selected[:]["column"] - 1, hits_selected[:]["row"] - 1][:, 0],
                            calib_data[hits_selected[:]["column"] - 1, hits_selected[:]["row"] - 1][:, 1],
                            calib_data[hits_selected[:]["column"] - 1, hits_selected[:]["row"] - 1][:, 2],
                        )
                    hit_table_converted["timestamp"] = 0
                    hit_table_converted["trigger_number"] = hits_selected["event_number"].astype(np.uint64)
                    hit_table_out.append(hit_table_converted)
                hit_table_out.flush()
        else:
            raise RuntimeError("Invalid trigger mode selected. Accepted options are 'AIDA' or 'EUDET'")


if __name__ == "__main__":
    input_file = "/path/to/file.h5"
    trigger_mode = "aida"
    tot_calib_file = None

    if "_interpreted" not in input_file:
        with analysis.Analysis(
            raw_data_file=input_file,
            store_hits=True,
            create_pdf=False,
            build_events=True if trigger_mode == "eudet" else False,
        ) as a:
            a.analyze_data()
            input_file = a.analyzed_data_file

    format_dut(input_filename=input_file, trigger_mode=trigger_mode, tot_calib_file=tot_calib_file)
