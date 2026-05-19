import numpy as np
import numba

from tjmonopix2.analysis import analysis_utils as au

class_spec = [
    ('sof', numba.boolean),
    ('eof', numba.boolean),
    ('token_id', numba.uint32),
    ('tj_data_flag', numba.uint8),
    ('ptdc_data_flag', numba.uint8),
    ('error_cnt', numba.int32),
    ('col', numba.int16),
    ('row', numba.int16),
    ('le', numba.int8),
    ('te', numba.int8),
    ('tj_timestamp', numba.int64),
    ('n_scan_params', numba.int32),
    ('trigger_data_format', numba.uint8),
    ('rx_id', numba.uint8),

    ('ptdc_tdl_lut', numba.float64[:]),
    ('ptdc_trigger_time', numba.int32),
    ('ptdc_rising_time', numba.int32),
    ('ptdc_falling_time', numba.int32),

    ('hist_occ', numba.uint32[:, :, :]),
    ('hist_tot', numba.uint16[:, :, :, :]),
    ('hist_tdc', numba.uint32[:]),
    ('hist_trigger_dist', numba.uint32[:]),
    ('n_triggers', numba.int64),
    ('n_tdc', numba.int64),
]

HEADER_MASK = 0xF0000000
PTDC_HEADER = 0x60000000
TLU_HEADER = 0x80000000

PTDC_TRIGGER = 0x0
PTDC_RISING =  0x2000000
PTDC_FALLING = 0x4000000
PTDC_TIMESTAMP = 0x6000000
PTDC_CALIB = 0x8000000
PTDC_MISS = 0xA000000

@numba.njit
def is_tjmono(word, rx_id=0):
    return (word & 0xF8000000) == 0x40000000 + rx_id * 0x10000000


@numba.njit
def is_tlu(word):
    return word & 0x80000000 == au.TRIGGER_HEADER


@numba.njit
def is_tdc(word):
    return word & 0xF0000000 == au.TDC_HEADER


@numba.njit
def is_tjmono_timestamp_msb(word, rx_id=0):
    return (word & 0xFC000000) == 0x4C000000 + rx_id * 0x10000000


@numba.njit
def is_tjmono_timestamp_lsb(word, rx_id=0):
    return (word & 0xFC000000) == 0x48000000 + rx_id * 0x10000000


@numba.njit
def get_tlu_word(word, trigger_data_format):
    if trigger_data_format == 2:
        return word & 0xFFFF, (word >> 16) & 0x7FFF
    elif trigger_data_format == 1:
        return 0, word & 0x7FFFFFFF
    elif trigger_data_format == 0:
        return word & 0x7FFFFFFF, 0


@numba.njit
def is_ptdc(word):
    return word & HEADER_MASK == PTDC_HEADER


@numba.njit
def get_ptdc_word_type(word):
    return word & 0xE00_0000


@numba.njit
def get_ptdc_timestamp(word):
    return word & 0x1FF_FFFF


@numba.njit
def get_ptdc_time(word, lut):
    tdl = word & 0x7F  # Value of tapped delay line
    fine_counter = (word >> 7) & 0x3  # 480 MHz
    coarse_counter = (word >> 9) & 0xFFFF  # 160 MHz

    return int((1 / 0.000480) * (3 * coarse_counter + fine_counter - lut[tdl]))  # Time in ps to store as int


@numba.njit
def get_tdc_value(word):
    return word & 0xFFF


@numba.experimental.jitclass(class_spec)
class RawDataInterpreter(object):
    def __init__(self, n_scan_params=1, trigger_data_format=1, rx_id=0, ptdc_tdl_lut=np.array([0])):
        self.sof = False
        self.eof = False
        self.error_cnt = 0
        self.token_id = 0
        self.tj_data_flag = 0
        self.ptdc_data_flag = 0

        self.n_scan_params = n_scan_params
        self.trigger_data_format = trigger_data_format
        self.rx_id = rx_id

        # Peviously calculated look-up table for tapped delay line bin width
        # print(ptdc_tdl_lut)
        self.ptdc_tdl_lut = ptdc_tdl_lut

        self.n_triggers = 0
        self.n_tdc = 0

        self.reset()

    def interpret(self, raw_data, hit_data, scan_param_id=0):
        hit_index = 0

        for raw_data_word in raw_data:
            #############################
            # Part 1: interpret TJ word #
            #############################
            if is_tjmono_timestamp_msb(raw_data_word, rx_id=self.rx_id):
                self.tj_timestamp = (raw_data_word & 0x3FFFFFF) << 26
            elif is_tjmono_timestamp_lsb(raw_data_word, rx_id=self.rx_id):
                self.tj_timestamp = self.tj_timestamp | (raw_data_word & 0x3FFFFFF)
            elif is_tjmono(raw_data_word, rx_id=self.rx_id):
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
                        self.tj_data_flag = 0  # Reset data flag
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
                            self.le = self._gray2bin((d & 0xfe) >> 1)
                            self.te = (d & 0x01) << 6
                        elif self.tj_data_flag == 2:
                            self.tj_data_flag = 3
                            self.te = self._gray2bin(self.te | ((d & 0xfc) >> 2))
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
                            hit_data[hit_index]["timestamp"] = self.tj_timestamp
                            hit_data[hit_index]["scan_param_id"] = scan_param_id

                            self._fill_hist(self.col, self.row, (self.te - self.le) & 0x7F, scan_param_id)

                            # Prepare for next data block. Increase hit index
                            hit_index += 1
                        else:
                            self.error_cnt += 1

            ##############################
            # Part 2: interpret TLU word #
            ##############################
            elif is_tlu(raw_data_word):
                trigger_number, trigger_ts = get_tlu_word(raw_data_word, self.trigger_data_format)

                hit_data[hit_index]["col"] = 0x3FF  # 1023 as TLU identifier
                hit_data[hit_index]["row"] = 0
                hit_data[hit_index]["le"] = 0
                hit_data[hit_index]["te"] = 0
                hit_data[hit_index]["token_id"] = trigger_number
                hit_data[hit_index]["timestamp"] = trigger_ts
                hit_data[hit_index]["scan_param_id"] = scan_param_id
                self.n_triggers += 1

                # Prepare for next data block. Increase hit index
                hit_index += 1

            ##############################
            # Part 3: interpret TDC word #
            ##############################
            elif is_tdc(raw_data_word):
                tdc_value = get_tdc_value(raw_data_word)

                hit_data[hit_index]["col"] = 0x3FE  # 1022 as TDC identifier
                hit_data[hit_index]["row"] = 0
                hit_data[hit_index]["le"] = 0
                hit_data[hit_index]["te"] = 0
                hit_data[hit_index]["token_id"] = tdc_value
                hit_data[hit_index]["timestamp"] = 0
                hit_data[hit_index]["scan_param_id"] = scan_param_id
                self.n_tdc += 1

                self.hist_tdc[tdc_value] += 1

                # Prepare for next data block. Increase hit index
                hit_index += 1

            ###############################
            # Part 4: interpret pTDC word #
            ###############################
            elif is_ptdc(raw_data_word):

                # TODO: For now, assume TRIGGER -> RISING -> FALLING -> TIMESTAMP
                if get_ptdc_word_type(raw_data_word) == PTDC_TRIGGER:  # Start pTDC word block
                    if self.ptdc_data_flag:
                        continue

                    self.ptdc_data_flag = 1
                    self.ptdc_trigger_time = get_ptdc_time(raw_data_word, self.ptdc_tdl_lut)
                elif get_ptdc_word_type(raw_data_word) == PTDC_RISING:
                    if self.ptdc_data_flag != 1:
                        continue

                    self.ptdc_data_flag = 2
                    self.ptdc_rising_time = get_ptdc_time(raw_data_word, self.ptdc_tdl_lut)

                elif get_ptdc_word_type(raw_data_word) == PTDC_FALLING:
                    if self.ptdc_data_flag != 2:
                        continue

                    self.ptdc_data_flag = 3
                    self.ptdc_falling_time = get_ptdc_time(raw_data_word, self.ptdc_tdl_lut)

                elif get_ptdc_word_type(raw_data_word) == PTDC_TIMESTAMP:  # Concludes the pTDC data block
                    if self.ptdc_data_flag != 3:
                        continue

                    timestamp = get_ptdc_timestamp(raw_data_word)

                    # So this gets tricky. TDC values relative to timestamp are stored in integer units
                    # of ps in token_id field. (le, te) indicate the type of the word. (0, 0) is trigger
                    # word, (1, 0) rising word, (0, 1) falling word.
                    hit_data[hit_index]["col"] = 0x3FD  # 1021
                    hit_data[hit_index]["timestamp"] = timestamp
                    hit_data[hit_index]["token_id"] = self.ptdc_trigger_time
                    hit_data[hit_index]["le"] = 0
                    hit_data[hit_index]["te"] = 0
                    hit_index += 1

                    hit_data[hit_index]["col"] = 0x3FD  # 1021
                    hit_data[hit_index]["timestamp"] = timestamp
                    hit_data[hit_index]["token_id"] = self.ptdc_rising_time
                    hit_data[hit_index]["le"] = 1
                    hit_data[hit_index]["te"] = 0
                    hit_index += 1

                    hit_data[hit_index]["col"] = 0x3FD  # 1021
                    hit_data[hit_index]["timestamp"] = timestamp
                    hit_data[hit_index]["token_id"] = self.ptdc_falling_time
                    hit_data[hit_index]["le"] = 0
                    hit_data[hit_index]["te"] = 1
                    hit_index += 1

                    # Fill histogram
                    trigger_dist = self.ptdc_rising_time - self.ptdc_trigger_time
                    if trigger_dist < 250000:
                        self.hist_trigger_dist[int(trigger_dist // 50)] += 1  # Bins of 50 ps, max 250 ns

                    self.ptdc_data_flag = 0 # Reset data flag, all blocks should be there, no matter if written or not

        hit_data = hit_data[:hit_index]

        return hit_data

    def get_histograms(self):
        return self.hist_occ, self.hist_tot, self.hist_tdc

    def get_n_triggers(self):
        return self.n_triggers

    def get_n_tdc(self):
        return self.n_tdc

    def reset(self):
        self.hist_occ = np.zeros((512, 512, self.n_scan_params), dtype=numba.uint32)
        self.hist_tot = np.zeros((512, 512, self.n_scan_params, 128), dtype=numba.uint16)
        self.hist_tdc = np.zeros(4096, dtype=numba.uint32)
        self.n_triggers = 0
        self.n_tdc = 0

    def get_error_count(self):
        return self.error_cnt

    def _gray2bin(self, gray):
        b6 = gray & 0x40
        b5 = (gray & 0x20) ^ (b6 >> 1)
        b4 = (gray & 0x10) ^ (b5 >> 1)
        b3 = (gray & 0x08) ^ (b4 >> 1)
        b2 = (gray & 0x04) ^ (b3 >> 1)
        b1 = (gray & 0x02) ^ (b2 >> 1)
        b0 = (gray & 0x01) ^ (b1 >> 1)
        return b6 + b5 + b4 + b3 + b2 + b1 + b0

    def _fill_hist(self, col, row, tot, scan_param_id):
        self.hist_occ[col, row, scan_param_id] += 1
        self.hist_tot[col, row, scan_param_id, tot] += 1
