import numpy as np
import numba
from tqdm import tqdm


class_spec = [
    ('sof', numba.boolean),
    ('eof', numba.boolean),
    ('token_id', numba.uint32),
    ('tj_data_flag', numba.uint8),
    ('meta_idx', numba.uint32),
    ('raw_idx', numba.uint32),
    ('error_cnt', numba.int32),
    ('col', numba.int16),
    ('row', numba.int16),
    ('le', numba.int8),
    ('te', numba.int8),

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

]


@numba.njit
def is_tjmono(word):
    return (word & 0xF8000000) == 0x40000000


@numba.njit
def is_tlu(word):
    return word & 0x80000000 == 0x80000000


@numba.njit
def get_tlu_number(word):
    return word & 0xFFFF


@numba.njit
def get_tlu_timestamp(word):
    return (word >> 12) & 0x7FFF0


@numba.experimental.jitclass(class_spec)
class RawDataInterpreter(object):
    def __init__(self):
        self.sof = False
        self.eof = False
        self.error_cnt = 0
        self.token_id = 0
        self.raw_idx = 0
        self.meta_idx = 0

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
        
        for raw_data_word in raw_data:
            #############################
            # Part 1: interpret TJ word #
            #############################
            if is_tjmono(raw_data_word):
                dat = np.zeros(3, dtype=np.uint16)
                dat[0] = (raw_data_word & 0x7FC0000) >> 18
                dat[1] = (raw_data_word & 0x003FE00) >> 9
                dat[2] = (raw_data_word & 0x00001FF)

                for d in dat:
                    if d == 0x1bc:  # SOF hit data
                        if self.sof:
                            self.error_cnt += 1  # SOF before EOF
                        self.sof = True
                        self.col = self.row = self.le = self.te = -1
                    elif d == 0x17c:  # EOF hit data
                        if not self.sof:
                            self.error_cnt += 1  # EOF before SOF
                        self.sof = False
                        self.token_id += 1
                    elif d == 0x13c:  # IDLE
                        pass
                    else:
                        if not self.sof:
                            self.error_cnt += 1

                        if not self.tj_data_flag:  # Start block of hit words
                            self.tj_data_flag = 1  # Starting with column data
                            self.col = (d & 0xFF) << 1
                        elif self.tj_data_flag == 1:
                            self.tj_data_flag = 2
                            self.le = self.gray2bin((d & 0xfe) >> 1)
                            self.te = (d & 0x01) << 6
                        elif self.tj_data_flag == 2:
                            self.tj_data_flag = 3
                            self.te = self.gray2bin(self.te | ((d & 0xfc) >> 2))
                            self.row = (d & 0x01) << 8
                            self.col = self.col + ((d & 0x02) >> 1)
                        elif self.tj_data_flag == 3:
                            self.tj_data_flag = 0  # Reset data flag, all blocks should be there
                            self.row = self.row | (d & 0xff)

                            hit_data[hit_index]["col"] = self.col
                            hit_data[hit_index]["row"] = self.row
                            hit_data[hit_index]["le"] = self.le
                            hit_data[hit_index]["te"] = self.te
                            hit_data[hit_index]["token_id"] = self.token_id
                            hit_data[hit_index]["scan_param_id"] = self.raw_idx
                            hit_index += 1
                        else:
                            self.error_cnt += 1

            ##############################
            # Part 2: interpret TLU word #
            ##############################
            elif is_tlu(raw_data_word):
                tlu_word = get_tlu_number(raw_data_word)
                tlu_timestamp_low_res = get_tlu_timestamp(raw_data_word)  # TLU data contains a 15bit timestamp

                hit_data[hit_index]["col"] = 0x400
                hit_data[hit_index]["row"] = 0
                hit_data[hit_index]["le"] = 0
                hit_data[hit_index]["te"] = 0
                hit_data[hit_index]["token_id"] = tlu_word
                # hit_data[hit_index]["timestamp"] = tlu_timestamp_low_res
                hit_data[hit_index]["scan_param_id"] = self.raw_idx

                # Prepare for next data block. Increase hit index
                hit_index += 1

            self.raw_idx += 1
        hit_data = hit_data[:hit_index]

        # Find correct scan_param_id in meta data and attach to hit
        for scan_idx, param_id in enumerate(hit_data["scan_param_id"]):
            while self.meta_idx < len(meta_data):
                if param_id >= meta_data[self.meta_idx]['index_start'] and param_id < meta_data[self.meta_idx]['index_stop']:
                    hit_data[scan_idx]['scan_param_id'] = meta_data[self.meta_idx]['scan_param_id']
                    break
                elif param_id >= meta_data[self.meta_idx]['index_stop']:
                    self.meta_idx += 1
        return hit_data