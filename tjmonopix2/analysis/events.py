import tables as tb
import numpy as np
from numba import njit
from tqdm import tqdm

from tjmonopix2.analysis import analysis_utils as au


@njit
def build_events(hits, buffer, trigger_n=0, trigger_ts=0, event_n=0):
    """Build events from interpreted hits (including TLU words). Corrects trigger timestamp overflow
       and searches for hit words within fixed timeframe after trigger word.

    Args:
        hits: Input hit array
        buffer: Output event array
        trigger_n (int, optional): Trigger number from previous function call (when chunking). Defaults to 0.
        event_n (int, optional): Event number from previous function call (when chunking). Defaults to 0.
        trigger_ts (int, optional): _description_. Defaults to 0.

    Returns:
        Filled buffer array
    """

    event_i = 0
    hit_i = 0

    while hit_i < len(hits):
        if hits[hit_i]["col"] == 1023:  # Start at a TLU word and look for DUT hits
            trigger_n += 1
            event_n += 1

            # Correct trigger timestamp overflow for current TLU word
            while hits[hit_i]["timestamp"] < trigger_ts:
                hits[hit_i]["timestamp"] += 0x7FFF_FFFF
            trigger_ts = hits[hit_i]["timestamp"]
        elif hits[hit_i]["col"] <= 512:
            # Iterate over hits after TLU word (until next TLU word) and check if their timestamps
            # are within given time window after TLU (> 100 && < 450). Maximum limit must be
            # shorter than TLU veto length. Otherwise, algorithm will fail and data might be crap.
            if (hits[hit_i]["timestamp"] - trigger_ts) > 100 and ((hits[hit_i]["timestamp"] - trigger_ts) < 450):
                buffer[event_i]['event_number'] = event_n - 1  # TODO: Check if -1 required
                buffer[event_i]['trigger_number'] = trigger_n
                buffer[event_i]['column'] = hits[hit_i]["col"] + 1
                buffer[event_i]['row'] = hits[hit_i]["row"] + 1
                buffer[event_i]['charge'] = ((hits[hit_i]["te"] - hits[hit_i]["le"]) & 0x7F) + 1
                buffer[event_i]['timestamp'] = hits[hit_i]["timestamp"]
                event_i += 1
        hit_i += 1

    return buffer[:event_i], trigger_n, trigger_ts, event_n


if __name__ == "__main__":
    input_file = ''
    output_file = ''

    with tb.open_file(input_file, "r") as in_file:
        with tb.open_file(output_file, "w") as out_file:
            n_words = len(in_file.root.Dut)
            chunk_size = 1000000
            event_table = out_file.create_table(out_file.root, name='Hits',
                                                description=au.event_dtype,
                                                title='events',
                                                expectedrows=chunk_size,
                                                filters=tb.Filters(complib='blosc',
                                                                   complevel=5,
                                                                   fletcher32=False))

            start = 0
            end = min(start + chunk_size, n_words)

            n_events = 0
            trigger_n, trigger_ts, event_n = 0, 0, 0
            pbar = tqdm(total=n_words, unit=' Words', unit_scale=True)
            while start < end:
                hits = in_file.root.Dut[start:end]
                event_buffer = np.zeros(len(hits), dtype=au.event_dtype)
                events, trigger_n, trigger_ts, event_n = build_events(hits, event_buffer, trigger_n, trigger_ts, event_n)
                n_events += len(events)

                event_table.append(events)
                event_table.flush()

                start = start + chunk_size
                end = min(start + chunk_size, n_words)
                pbar.update(len(hits))
            pbar.close()
