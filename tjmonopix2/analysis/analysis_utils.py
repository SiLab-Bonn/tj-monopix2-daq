#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import ast
import logging
import tables as tb
import numpy as np

logger = logging.getLogger('Analysis')

hit_dtype = np.dtype([
    ("col", "<i2"),
    ("row", "<i2"),
    ("le", "<i1"),
    ("te", "<i1"),
    ("token_id", "<i8"),
    ("scan_param_id", "<i4")
])


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
