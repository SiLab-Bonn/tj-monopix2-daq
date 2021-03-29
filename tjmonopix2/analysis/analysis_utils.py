import ast
import numpy as np
from numba import njit


class ConfigDict(dict):
    ''' Dictionary with different value data types:
        str / int / float / list / tuple depending on value

        key can be string or byte-array. Contructor can
        be called with all data types.

        If cast of object to known type is not possible the
        string representation is returned as fallback
    '''

    def __init__(self, *args):
        for key, value in dict(*args).items():
            self.__setitem__(key, value)

    def __setitem__(self, key, val):
        # Change types on value setting
        key, val = self._type_cast(key, val)
        dict.__setitem__(self, key, val)

    def _type_cast(self, key, val):
        ''' Return python objects '''
        # Some data is in binary array representation (e.g. pytable data)
        # These must be convertet to string
        if isinstance(key, (bytes, bytearray)):
            key = key.decode()
        if isinstance(val, (bytes, bytearray)):
            val = val.decode()
        if 'chip_sn' in key:
            return key, val
        try:
            if isinstance(val, np.generic):
                return key, val.item()
            return key, ast.literal_eval(val)
        except (ValueError, SyntaxError):  # fallback to return the object
            return key, val


@njit(cache=True, fastmath=True)
def make_tj_data_list(raw_data):
    res = np.zeros(3 * len(raw_data), dtype=np.int16)
    res_idx = 0

    for word in raw_data:
        res[res_idx] = (word & 0x7FC0000) >> 18
        res[res_idx + 1] = (word & 0x003FE00) >> 9
        res[res_idx + 2] = (word & 0x00001FF)
        res_idx += 3
    return res[:res_idx]