#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from pathlib import Path

import numpy as np
import tables as tb

from tjmonopix2.analysis import analysis


def format_dut(input_filename: str | Path, output_filename: str | Path = None, trigger_mode: str = "AIDA") -> None:
    """Format hit table to be compatible with corryvreckan EventLoaderHDF5 as of commit 149e937f

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

    Raises
    ------
    RuntimeError
        Invalid trigger mode selected
    """
    hit_dtype_converted = np.dtype(
        [("column", "<u2"), ("row", "<u2"), ("charge", "<u2"), ("timestamp", "<u8"), ("trigger_number", "<u4")]
    )

    if type(input_filename) is str:
        input_filename = Path(input_filename)
    if output_filename is None:
        output_filename = Path(input_filename.parent) / Path(input_filename.stem + "_converted" + input_filename.suffix)
    with tb.open_file(input_filename, "r") as in_file:
        if trigger_mode.lower() == "aida":
            hit_table_in = in_file.root.Dut[:]
            sel = hit_table_in["col"] <= 512  # Select only DUT words
            hits_selected = hit_table_in[sel]

            hit_table_converted = np.zeros(len(hits_selected), dtype=hit_dtype_converted)
            with tb.open_file(output_filename, "w") as out_file:
                hit_table_out = out_file.create_table(out_file.root, name="Hits", description=hit_dtype_converted)
                hit_table_converted["column"] = hits_selected["col"]
                hit_table_converted["row"] = hits_selected["row"]
                hit_table_converted["charge"] = (hits_selected["te"] - hits_selected["le"]) & 0x7F  # calculate TOT
                hit_table_converted["timestamp"] = 25 * hits_selected["timestamp"].astype(np.uint64)  # convert to ns
                hit_table_converted["trigger_number"] = 0
                hit_table_out.append(hit_table_converted)
                hit_table_out.flush()
        elif trigger_mode.lower() == "eudet":
            hit_table_in = in_file.root.Hits[:]
            sel = hit_table_in["column"] <= 512
            hits_selected = hit_table_in[sel]

            hit_table_converted = np.zeros(len(hits_selected), dtype=hit_dtype_converted)
            with tb.open_file(output_filename, "w") as out_file:
                hit_table_out = out_file.create_table(out_file.root, name="Hits", description=hit_dtype_converted)
                # Hits are already assiged to TLU number in event builder and data has been pre-formatted
                # Only convert column names and types
                hit_table_converted["column"] = hits_selected["column"]
                hit_table_converted["row"] = hits_selected["row"]
                hit_table_converted["charge"] = hits_selected["charge"]
                hit_table_converted["timestamp"] = 0
                hit_table_converted["trigger_number"] = hits_selected["event_number"].astype(np.uint64)
                hit_table_out.append(hit_table_converted)
                hit_table_out.flush()
        else:
            raise RuntimeError("Invalid trigger mode selected. Accepted options are 'AIDA' or 'EUDET'")


if __name__ == "__main__":
    input_file = "/path/to/file.h5"
    trigger_mode = "aida"

    if "_interpreted.h5" not in input_file:
        with analysis.Analysis(
            raw_data_file=input_file,
            store_hits=True,
            create_pdf=False,
            build_events=True if trigger_mode == "eudet" else False,
        ) as a:
            a.analyze_data()
            input_file = a.analyzed_data_file

    format_dut(input_filename=input_file, trigger_mode=trigger_mode)
