import numpy as np
import numba
from tqdm import tqdm

from tjmonopix2.analysis.analysis_utils import make_tj_data_list

class_spec = [
    ('sof', numba.boolean),
    ('eof', numba.boolean),
    ('token_id', numba.uint32),

    ('chunk_size', numba.uint32),
    ('tj_data_flag', numba.uint8),
    ('hitor_timestamp_flag', numba.uint8),
    ('ext_timestamp_flag', numba.uint8),
    ('inj_timestamp_flag', numba.uint8),
    ('tlu_timestamp_flag', numba.uint8),
    ('tj_timestamp', numba.int64),
    ('hitor_timestamp', numba.int64),
    ('hitor_charge', numba.int16),
    ('ext_timestamp', numba.int64),
    ('inj_timestamp', numba.int64),
    ('tlu_timestamp', numba.int64),
    ('error_cnt', numba.int32),
    ('col', numba.uint8),
    ('row', numba.uint16),
    ('le', numba.uint8),
    ('te', numba.uint8),
    ('noise', numba.uint8),
    ('meta_idx', numba.uint32),
    ('raw_idx', numba.uint32)
]


@numba.experimental.jitclass(class_spec)
class RawDataInterpreter(object):
    def __init__(self):
        self.sof = False
        self.eof = False
        self.error_cnt = 0
        self.token_id = 0

    def get_error_count(self):
        return self.error_cnt

    def gray2bin(self, gray):
        b6 = gray & 0x40
        b5 = (gray & 0x20) ^ (b6 >> 1)
        b4 = (gray & 0x10) ^ (b5 >> 1)
        b3 = (gray & 0x08) ^ (b4 >> 1)
        b2 = (gray & 0x04) ^ (b3 >> 1)
        b1 = (gray & 0x02) ^ (b2 >> 1)
        b0 = (gray & 0x01) ^ (b1 >> 1)
        return b6 + b5 + b4 + b3 + b2 + b1 + b0

    def interpret(self, raw_data, meta_data, hit_data):
        hit_index = 0
        raw_i = 0
        raw_data_words = make_tj_data_list(raw_data[(raw_data & 0xF8000000) == 0x40000000])

        while raw_i < len(raw_data_words):
            if raw_data_words[raw_i] == 0x1bc:  # SOF hit data
                if self.sof:
                    self.error_cnt += 1  # SOF before EOF
                self.sof = True
                raw_i += 1
            elif raw_data_words[raw_i] == 0x17c:  # EOF hit data
                if not self.sof:
                    self.error_cnt += 1  # EOF before SOF
                self.sof = False
                raw_i += 1
                self.token_id += 1
            elif raw_data_words[raw_i] == 0x13c:  # IDLE
                raw_i += 1
            else:
                if not self.sof:
                    self.error_cnt += 1
                hit_data[hit_index]['le'] = self.gray2bin((raw_data_words[raw_i+1] & 0xFE) >> 1)
                hit_data[hit_index]['te'] = self.gray2bin((raw_data_words[raw_i+1] & 0x01) << 6 | ((raw_data_words[raw_i+2] & 0xFC) >> 2))
                # hit_data[hit_index]['le'] = (raw_data_words[raw_i + 1] & 0xfe) >> 1 
                # hit_data[hit_index]['te'] = (raw_data_words[raw_i + 1] & 0x01) << 6 | ((raw_data_words[raw_i + 2] & 0xfc) >> 2)
                hit_data[hit_index]['row'] = ((raw_data_words[raw_i + 2] & 0x1) << 8) | (raw_data_words[raw_i + 3] & 0xff)
                hit_data[hit_index]['col'] = ((raw_data_words[raw_i] & 0xff) << 1) + ((raw_data_words[raw_i + 2] & 0x2) >> 1)
                hit_data[hit_index]['token_id'] = self.token_id
                raw_i += 4
                hit_index += 1

        hit_data = hit_data[:hit_index]
        return hit_data