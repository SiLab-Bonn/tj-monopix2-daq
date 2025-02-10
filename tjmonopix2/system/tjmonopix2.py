#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import time
from collections import OrderedDict

import numpy as np
import yaml
from numba import njit

# Try to use fast c parser based on libyaml
try:
    from yaml import CSafeLoader as SafeLoader
except ImportError:  # fallback to python parser
    from yaml import SafeLoader  # noqa

from tjmonopix2.system import logger

FLAVOR_COLS = {'MONOPIX2': range(0, 224),
               'MONOPIX2_CASC': range(224, 448),
               'MONOPIX2_HV': range(448, 480),
               'MONOPIX2_HV_CASC': range(480, 512)}


def get_flavor(col):
    for fe, cols in FLAVOR_COLS.items():
        if col in cols:
            return fe


def gray2bin(gray):
    b6 = gray & 0x40
    b5 = (gray & 0x20) ^ (b6 >> 1)
    b4 = (gray & 0x10) ^ (b5 >> 1)
    b3 = (gray & 0x08) ^ (b4 >> 1)
    b2 = (gray & 0x04) ^ (b3 >> 1)
    b1 = (gray & 0x02) ^ (b2 >> 1)
    b0 = (gray & 0x01) ^ (b1 >> 1)
    return b6 + b5 + b4 + b3 + b2 + b1 + b0


@njit(cache=True, fastmath=True)
def encode_cmd(address, data):
    ''' Encodes address + data information into the custom 5bit values -> 8bit symbols protocol '''
    # Lookup table, 5-bit values to 8-bit symbols, index = value
    symbols = [0b01101010, 0b01101100, 0b01110001, 0b01110010, 0b01110100, 0b10001011, 0b10001101, 0b10001110, 0b10010011, 0b10010101,  # value 0 - 9
               0b10010110, 0b10011001, 0b10011010, 0b10011100, 0b10100011, 0b10100101, 0b10100110, 0b10101001, 0b01011001, 0b10101100,  # value 10 - 19
               0b10110001, 0b10110010, 0b10110100, 0b11000011, 0b11000101, 0b11000110, 0b11001001, 0b11001010, 0b11001100, 0b11010001,  # value 20 - 29
               0b11010010, 0b11010100]  # value 30 - 31

    word_1 = address >> 5  # Write mode + first 4 bits of address
    word_2 = address & 0x1f  # Last 5 bits of address
    word_3 = data >> 11  # First 5 bits of data
    word_4 = (data >> 6) & 0x1f  # Middle 5 bits of data
    word_5 = (data >> 1) & 0x1f  # Middle 5 bits of data
    word_6 = (data & 0x1) << 4  # Last bit of data

    return [symbols[word_1], symbols[word_2], symbols[word_3], symbols[word_4], symbols[word_5], symbols[word_6]]


class Register(dict):
    def __init__(self, chip, name, address, offset, size, default, value, mode, reset, description):
        self.log = logger.setup_derived_logger('TJ-Monopix2 - Register')

        self.chip = chip
        self.changed = False
        super(Register, self).__init__()

        self['name'] = name
        self['address'] = address
        self['offset'] = offset
        self['size'] = size
        self['default'] = eval(default)
        self['value'] = eval(value)
        self['mode'] = mode
        self['reset'] = reset
        self['description'] = description

    def __str__(self, *args, **kwargs):
        text = self['name']
        text += ': '
        text += self['description']
        text += '\nAddress : '
        text += str(self['address'])
        text += '\nOffset : '
        text += str(self['offset'])
        text += '\nSize    : '
        text += str(self['size'])
        text += '\nValue   : '
        text += ('0b{0:0' + str(self['size']) + 'b} ({1:d})').format(self['value'], self['value'])
        text += '\nDefault : '
        text += ('0b{0:0' + str(self['size']) + 'b} ({1:d})').format(self['default'], self['default'])
        text += '\nMode    : '
        if self['mode'] == 1:
            text += 'r/w'
        else:
            text += 'r'

        return text

    def _assert_value(self, value):
        if isinstance(value, (int, np.integer)):
            return value
        if isinstance(value, str):
            if value[:2] == '0b':
                return int(value, 2)
            if value[:2] == '0x':
                return int(value, 16)
        raise ValueError('Invalid value of type {0}: {1}'.format(type(value), value))

    def set(self, value):
        value = self._assert_value(value)
        if value != self['value']:
            self.changed = True
            self['value'] = value

    def get(self):
        return self['value']

    def print_value(self):
        print(('{0} = 0b{1:0' + str(self['size']) + 'b} ({2:d})').format(self['name'], self['value'], self['value']))

    def write(self, value=None, verify=False, write_ctr=0):
        if value is not None:
            value = self._assert_value(value)
            self['value'] = value
        self.log.debug(('Writing value 0b{0:0' + str(self['size']) + 'b} to register {1}').format(self['value'], self['name']))

        if self['size'] <= 16:
            wr_value = 0x0000
            for reg in self.chip.registers.get_all_at_address(self['address']):
                wr_value |= reg['value'] << reg['offset']

            self.chip._write_register(self['address'], wr_value)
        else:
            raise RuntimeError("Register size is too big, set with _write_register()")

        if verify:
            if self.read() != value:
                if write_ctr >= 10:
                    raise RuntimeError('Could not verify value {0} in register {1}'.format(value, self['name']))
                self.write(value=value, verify=True, write_ctr=write_ctr + 1)

    def get_write_command(self, value=None):
        if value is not None:
            self.set(value)

        if self['size'] <= 16:
            wr_value = 0x0000
            for reg in self.chip.registers.get_all_at_address(self['address']):
                wr_value |= reg['value'] << reg['offset']

            return self.chip._write_register(self['address'], wr_value, write=False)
        else:
            wr_value = eval('0b' + '0' * self['size'])
            indata = []
            for i in range(0, self['size'], 16):
                reg_value = (self['value'] & (0xFF << i)) >> i
                indata += self.chip._write_register(self['address'] + self['size'] // 16 - 1, reg_value, write=False)
            return indata

    def get_read_command(self):
        return self.chip._read_register(self['address'], write=False)

    def read(self):
        val = self.chip._get_register_value(self['address'])
        bit_mask = eval('0b' + '1' * self['size']) << self['offset']
        val = (val & bit_mask) >> self['offset']
        if val != self['value'] and self['mode'] == 1 and self['name'] != 'PIX_PORTAL':
            self.log.warning(
                (
                    'Register {0} did not have the expected value: Expected 0b{2:0'
                    + str(self['size'])
                    + 'b}, got 0b{1:0'
                    + str(self['size'])
                    + 'b}'
                ).format(self['name'], val, self['value'])
            )
        return val

    def reset(self):
        ''' Overwrite a register with its default value'''
        if self['reset'] == 1 and self['mode'] == 1:
            self.write(self['default'])


class RegisterObject(OrderedDict):
    ''' General register object collects all chip registers,
        creates them on initialization from a yaml file and
        handles all manipulation of all registers at once.
    '''

    def __init__(self, chip, lookup_file=None):
        self.chip = chip
        super(RegisterObject, self).__init__()

        if lookup_file is None:
            lookup_file = 'registers.yaml'
        if not os.path.isfile(lookup_file):
            lookup_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), lookup_file)

        with open(lookup_file, 'r') as f:
            regs = yaml.load(f, Loader=SafeLoader)

        for reg in regs['registers']:
            self._add(name=reg['name'],
                      address=reg['address'],
                      offset=reg['offset'],
                      size=reg['size'],
                      default=reg['default'],
                      mode=reg['mode'],
                      reset=reg['reset'],
                      description=reg['description'])

    def _add(self, name, address, offset, size, default, mode, reset, value=None, description=''):
        if value is None:
            value = default
        self[name] = Register(chip=self.chip, name=name, address=address, offset=offset, size=size, default=default, mode=mode, reset=reset, value=value, description=description)

    def get_all_at_address(self, address):
        regs = []
        for reg in self.values():
            if reg['address'] is address:
                regs.append(reg)
        if len(regs) > 0:
            return regs
        raise ValueError('No register found with address {0}'.format(address))

    def write_all(self, force=False):
        '''
        Collect all registers that were changed in software and write to chip
        If force==True, write all software values to chip
        '''
        indata = self.chip.write_sync(write=False)
        for reg in self.values():
            if (reg['mode'] != 1 or (not force and not reg.changed)) and 'PIXEL_PORTAL' not in reg['name']:
                continue

            indata += self[reg['name']].get_write_command()
            indata += self.chip.write_sync(write=False) * 16

            if len(indata) > 3500:
                indata += self.chip.write_sync(write=False) * 16
                self.chip.write_command(indata)
                indata = self.chip.write_sync(write=False)

        self.chip.write_command(indata)

    def check_all(self, correct=False):
        ''' Compare all chip registers to software and log result '''
        errors = 0
        for reg in self.values():
            if reg['mode'] == 1 and reg['name'] not in ['PIX_PORTAL']:
                val = reg.read()
                if val != reg['value']:
                    errors += 1
                    if correct:
                        reg.write()

        return errors

    def update_all(self):
        ''' Set software status to chip registers '''
        for reg in self.values():
            if reg['mode'] == 1:
                reg.read()

    def reset_all(self):
        ''' Set all chip registers to default values '''
        for reg in self.values():
            if reg['reset'] == 1:
                reg.set(reg['default'])
        self.write_all(force=True)

    def dump_all(self, outfile=None):
        ''' Dump all current register values to configuration-style YAML file. '''
        if outfile is None:
            outfile = 'register_dump.yaml'

        self.chip.log.warning('Dumping all registers to file {0}'.format(os.path.abspath(outfile)))

        data = {}
        for reg in self.values():
            data[reg['name']] = hex(reg['value'])

        with open(outfile, 'w') as f:
            yaml.dump({'registers': data}, f)


class MaskObject(dict):
    def __init__(self, chip, masks, dimensions):
        self.chip = chip
        self.masks = masks
        self.dimensions = dimensions
        self.defaults = {}
        self.disable_mask = np.ones(self.dimensions, bool)
        self.to_write = np.zeros(self.dimensions, bool)
        self.was = {}

        for name, props in masks.items():
            self.defaults[name] = props['default']
            self.was[name] = np.full(dimensions, props['default'])
            self[name] = np.full(dimensions, props['default'])

        self.supported_mask_patterns = ['default']

        # Initialize mask patterns to None and create pattern only on demand to save time
        self.shift_patterns = dict.fromkeys(self.supported_mask_patterns)

        self.mask_cache = []

        super(MaskObject, self).__init__()

    def _create_shift_pattern(self, pattern):
        ''' Called when pattern is required '''
        if pattern not in self.supported_mask_patterns:
            raise NotImplementedError('Mask pattern not supported:', pattern)
        if not self.shift_patterns[pattern]:  # check if pattern is already created
            if pattern == 'double':
                self.shift_patterns['double'] = DoubleShiftPattern(self.dimensions, mask_step=4)
            elif pattern == 'default':
                self.shift_patterns['default'] = DoubleShiftPattern(self.dimensions, mask_step=4)  # default is double shift pattern

    def get_mask_steps(self, pattern='default'):
        fe_multiplier = 0
        for _, cols in self.chip.flavor_cols.items():
            fe_mask = np.zeros(self.dimensions, bool)
            fe_mask[cols[0]:cols[-1] + 1, :] = True
            if np.any(np.logical_and(fe_mask, self['enable'])):
                fe_multiplier += 1
        self._create_shift_pattern(pattern)
        return self.shift_patterns[pattern]._get_mask_steps() * fe_multiplier

    def shift(self, masks=['enable'], pattern='default', cache=False, skip_empty=True):
        '''
            This function is called from scan loops to loop over 1 FE at a time and
            over the shifting masks as defined by the mask shift pattern
        '''

        original_masks = {name: mask for name, mask in self.items()}
        active_pixels = []

        self._create_shift_pattern(pattern)

        # Cache calculation to speed up repeated use
        if cache and self.mask_cache:
            for fe, data in self.mask_cache:
                for d in data:
                    self.chip.write_command(d)
                if fe != 'reset':
                    yield fe, active_pixels

            for name, mask in original_masks.items():
                self[name] = mask
            return

        for fe, cols in self.chip.flavor_cols.items():
            fe_mask = np.zeros(self.dimensions, bool)
            fe_mask[cols[0]:cols[-1] + 1, :] = True

            if not np.any(np.logical_and(fe_mask, original_masks['enable'])):   # Only loop over frontends that have enabled columns
                continue

            # data = [self.chip.enable_core_col_clock(range(int(cols[0] / 8), int((cols[-1] - 1) / 8 + 1)), write=True)]   # Enable only one frontend at a time
            data = []

            self.shift_patterns[pattern].reset()
            for pat in self.shift_patterns[pattern]:
                if isinstance(pat, np.ndarray):  # If DoubleShiftPattern or ClassicShiftPattern is used
                    for mask in masks:
                        self[mask] = np.logical_and(np.logical_and(original_masks[mask], pat), fe_mask)
                    if not np.any(self['enable'][:]) and skip_empty:   # Skip empty steps for speedup
                        if cache:
                            self.mask_cache.append(('skipped', []))
                        yield 'skipped', active_pixels
                        continue
                else:  # If CrosstalkShiftPattern is used
                    for name, mask in pat.items():
                        self[name] = np.logical_and(np.logical_and(original_masks[name], mask), fe_mask)
                data.extend(self.update())
                if cache:
                    self.mask_cache.append((fe, data))
                    data = []
                active_pixels = np.where(self['enable'][0:self.dimensions[0], 0:self.dimensions[1]])
                yield fe, active_pixels

        for name, mask in original_masks.items():
            self[name] = mask
        self.mask_cache.append(('reset', self.update()))

    def reset_all(self):
        for name, _ in self.items():
            self[name] = np.full(self.dimensions, self.defaults[name])
        self.apply_disable_mask()

    def apply_disable_mask(self):
        self['enable'] = np.logical_and(self['enable'], self.disable_mask)

    def _find_changes(self):
        '''
            Find out which values have changed in any mask compared to last update()
        '''
        self.pix_to_write = np.zeros(self.dimensions, bool)
        self.inj_to_write = np.zeros(self.dimensions, bool)
        self.hor_to_write = np.zeros(self.dimensions, bool)

        for name, mask in self.items():
            if 'injection' in name:
                self.inj_to_write = np.logical_or(self.inj_to_write, np.not_equal(mask, self.was[name]))
            elif 'hitor' in name:
                self.hor_to_write = np.logical_or(self.hor_to_write, np.not_equal(mask, self.was[name]))
            else:
                self.pix_to_write = np.logical_or(self.pix_to_write, np.not_equal(mask, self.was[name]))

    def get_pixel_data(self, col, row):
        tdac = str(bin(self['tdac'][col, row]))[2:].zfill(3)

        return '0' + tdac if self['enable'][col, row] else '0000'

    def get_pixel_portal_data(self, colgroup, row):
        return int(
            '0b'
            + self.get_pixel_data(colgroup * 4 + 3, row)
            + self.get_pixel_data(colgroup * 4 + 2, row)
            + self.get_pixel_data(colgroup * 4 + 1, row)
            + self.get_pixel_data(colgroup * 4, row), 2
        )

    def get_column_group_data(self, mask, colgroup):
        dat = np.logical_or.reduce(self[mask], axis=1)[colgroup * 16: (colgroup + 1) * 16]
        return np.packbits(dat, bitorder='little').view(np.uint16)[0]

    def get_row_group_data(self, mask, rowgroup):
        dat = np.logical_or.reduce(self[mask], axis=0)[rowgroup * 16: (rowgroup + 1) * 16]
        return np.packbits(dat, bitorder='little').view(np.uint16)[0]

    def update(self, force=False):
        ''' Write the actual pixel register configuration

            Only write changes or the complete matrix
        '''

        if force and self.chip.daq.board_version == 'SIMULATION':
            return []

        self._find_changes()
        if force:
            inj_write_mask = np.ones(self.dimensions, bool)
            pix_write_mask = np.ones(self.dimensions, bool)
            hor_write_mask = np.ones(self.dimensions, bool)
        else:   # Find out which pixels need to be updated
            inj_write_mask = self.inj_to_write
            pix_write_mask = self.pix_to_write
            hor_write_mask = self.hor_to_write
        inj_to_write = np.column_stack((np.where(inj_write_mask)))
        pix_to_write = np.column_stack((np.where(pix_write_mask)))
        hor_to_write = np.column_stack((np.where(hor_write_mask)))

        data = []
        indata = self.chip.write_sync(write=False) * 10
        if len(pix_to_write) > 0:
            written = set()
            for (col, row) in pix_to_write:
                colgroup = int(col / 4)

                # Speedup
                if (colgroup, row) in written:
                    continue

                indata += self.chip._write_register(17, (colgroup & 0x7f) << 9 | (row & 0x1ff), write=False)  # Write colgroup and row at the same time for speedup
                indata += self.chip.registers["PIXEL_PORTAL"].get_write_command(self.get_pixel_portal_data(colgroup, row))
                indata += self.chip.write_sync(write=False)
                written.add((colgroup, row))
                if len(indata) > 4000:  # Write command to chip before it gets too long
                    self.chip.write_command(indata)
                    data.append(indata)
                    indata = self.chip.write_sync(write=False)
            self.chip.write_command(indata)
            data.append(indata)
        if len(inj_to_write) > 0:
            written = set()
            for (col, row) in inj_to_write:
                colgroup = int(col / 16)
                rowgroup = int(row / 16)

                # Speedup
                if (colgroup, rowgroup) in written:
                    continue

                indata += self.chip._write_register(82 + colgroup, self.get_column_group_data('injection', colgroup))
                indata += self.chip._write_register(114 + rowgroup, self.get_row_group_data('injection', rowgroup))
                indata += self.chip.write_sync(write=False)
                written.add((colgroup, rowgroup))
                if len(indata) > 4000:  # Write command to chip before it gets too long
                    self.chip.write_command(indata)
                    data.append(indata)
                    indata = self.chip.write_sync(write=False)
            self.chip.write_command(indata)
            data.append(indata)
        if len(hor_to_write) > 0:
            written = set()
            for (col, row) in inj_to_write:
                colgroup = int(col / 16)
                rowgroup = int(row / 16)

                # Speedup
                if (colgroup, rowgroup) in written:
                    continue

                indata += self.chip._write_register(18 + colgroup, self.get_column_group_data('hitor', colgroup))
                indata += self.chip._write_register(50 + rowgroup, self.get_row_group_data('hitor', rowgroup))
                indata += self.chip.write_sync(write=False)
                written.add((colgroup, rowgroup))
                if len(indata) > 4000:  # Write command to chip before it gets too long
                    self.chip.write_command(indata)
                    data.append(indata)
                    indata = self.chip.write_sync(write=False)
            self.chip.write_command(indata)
            data.append(indata)

        # Set this mask as last mask to be able to find changes in next update()
        for name, mask in self.items():
            self.was[name][:] = mask[:]

        return data


class ShiftPatternBase(object):
    '''
        Base class for shift patterns
    '''

    def __init__(self, dimensions, mask_step):
        self.dimensions = dimensions
        self.mask_step = mask_step
        self.current_step = -1
        self.base_mask = self.make_first_mask()

    def __iter__(self):
        return self

    def reset(self):
        self.current_step = -1

    def _get_mask_steps(self):
        return self.dimensions[0] * self.mask_step

    def make_first_mask(self):
        raise NotImplementedError('You have to define the initial mask')

    def make_mask_for_step(self, step):
        raise NotImplementedError('You have to define the mask at a given step')

    def __next__(self):
        if self.current_step >= (self.dimensions[0] * self.mask_step) - 1:
            raise StopIteration
        else:
            self.current_step += 1
            return self.make_mask_for_step(self.current_step)


class DoubleShiftPattern(ShiftPatternBase):
    '''
        Enables pixels along one column with specified distance (mask_step)
    '''

    def make_first_mask(self):
        mask = np.zeros(self.dimensions, bool)

        for row in range(0, self.dimensions[1], self.mask_step):
            mask[0, row] = True
        return mask

    def make_mask_for_step(self, step):
        return np.roll(np.roll(self.base_mask, step // self.dimensions[0], 1), step % self.dimensions[0], 0)


class TJMonoPix2(object):

    """ Map hardware IDs for board identification """
    hw_map = {
        0: 'SIMULATION',
    }

    cmd_data_map = {
        0: 0b01101010,
        1: 0b01101100,
        2: 0b01110001,
        3: 0b01110010,
        4: 0b01110100,
        5: 0b10001011,
        6: 0b10001101,
        7: 0b10001110,
        8: 0b10010011,
        9: 0b10010101,
        10: 0b10010110,
        11: 0b10011001,
        12: 0b10011010,
        13: 0b10011100,
        14: 0b10100011,
        15: 0b10100101,
        16: 0b10100110,
        17: 0b10101001,
        18: 0b01011001,
        19: 0b10101100,
        20: 0b10110001,
        21: 0b10110010,
        22: 0b10110100,
        23: 0b11000011,
        24: 0b11000101,
        25: 0b11000110,
        26: 0b11001001,
        27: 0b11001010,
        28: 0b11001100,
        29: 0b11010001,
        30: 0b11010010,
        31: 0b11010100
    }

    CMD_SYNC = [0b10000001, 0b01111110]
    CMD_CLEAR = 0b01011010
    CMD_GLOBAL_PULSE = 0b01011100
    CMD_CAL = 0b0110_0011
    CMD_REGISTER = 0b01100110
    CMD_RDREG = 0b01100101

    flavor_cols = FLAVOR_COLS

    def __init__(self, daq, chip_sn='W00R00', chip_id=0, config=None, receiver="rx0"):
        self.log = logger.setup_derived_logger('TJ-Monopix2 - ' + chip_sn)
        self.daq = daq
        self.proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        if config is None or len(config) == 0:
            self.log.warning("No explicit configuration supplied. Using 'default.cfg.yaml'!")
            with open(os.path.join(os.path.dirname(__file__), 'default.cfg.yaml'), 'r') as f:
                self.configuration = yaml.full_load(f)
        elif isinstance(config, dict):
            self.configuration = config
        elif isinstance(config, str) and os.path.isfile(config):
            with open(config) as f:
                self.configuration = yaml.full_load(f)
        else:
            raise TypeError('Supplied config has unknown format!')

        self.chip_id = chip_id
        self.chip_sn = chip_sn
        self.receiver = receiver

        self.registers = RegisterObject(self, 'registers.yaml')

        masks = {
            'enable': {'default': False},
            'injection': {'default': False},
            'tdac': {'default': 0b100},
            'hitor': {'default': False}
        }
        self.masks = MaskObject(self, masks, (512, 512))

        # Load disabled pixels from chip config
        if 'disable' in self.configuration.keys():
            for pix in self.configuration['disable']:
                self.masks.disable_mask[pix[0], pix[1]] = False

        self.debug = 0

    def get_sn(self):
        return self.chip_sn

    def init(self):
        # super(TJMonoPix2, self).init()
        self.daq['cmd'].set_chip_type(1)  # ITkpixV1-like

        self.write_command(self.write_sync(write=False) * 32)
        self.reset()
        self.configure_rx(delay=40, rd_frz_dly=40)

    def power_on(self, VDDA=1.8, VDDP=1.8, VDDA_DAC=1.8, VDDD=1.8, VPC=1.6):
        # Set power
        # Sense resistor is 0.1Ohm, so 300mA=60mA*5
        self.daq['VDDP'].set_current_limit(200, unit='mA')
        self.daq['VPC'].set_voltage(VPC, unit='V')

        self.daq['VDDP'].set_voltage(VDDP, unit="V")
        self.daq['VDDP'].set_enable(True)

        self.daq['VDDA_DAC'].set_voltage(VDDA_DAC, unit='V')
        self.daq['VDDA'].set_voltage(VDDA, unit='V')

        self.daq['VDDA_DAC'].set_enable(True)
        self.daq['VDDA'].set_enable(True)

        self.daq['VDDD'].set_voltage(VDDD, unit='V')
        self.daq['VDDD'].set_enable(True)

    def power_off(self):
        self['VPC'].set_voltage(0, unit='V')
        for pwr in ['VDDP', 'VDDD', 'VDDA', 'VDDA_DAC']:
            self[pwr].set_enable(False)

    def get_power_status(self):
        status = {}

        for pwr in ['VDDP', 'VDDD', 'VDDA', 'VDDA_DAC', 'VPC']:  # add MONOVR channels also
            status[pwr + ' [V]'] = self.daq[pwr].get_voltage(unit='V')
            status[pwr + ' [mA]'] = 5 * self.daq[pwr].get_current(unit='mA') if pwr in [
                "VDDP", "VDDD", "VDDA", "VDDA_DAC"] else self.daq[pwr].get_current(unit='mA')
        return status

    def configure_rx(self, delay=40, rd_frz_dly=40):
        self.registers["FREEZE_START_CONF"].write(1 + delay)
        self.registers["READ_START_CONF"].write(1 + delay + rd_frz_dly)
        self.registers["READ_STOP_CONF"].write(5 + delay + rd_frz_dly)
        self.registers["LOAD_CONF"].write(39 + delay + rd_frz_dly)
        self.registers["FREEZE_STOP_CONF"].write(40 + delay + rd_frz_dly)
        self.registers["STOP_CONF"].write(40 + delay + rd_frz_dly)

    def reset(self):
        if self.daq.board_version == 'SIMULATION':
            return

        #  Set all registers
        self.registers.reset_all()
        for reg, val in self.configuration['registers'].items():
            self.registers[reg].set(val)
        self.registers.write_all()

        self.masks.reset_all()  # Set all masks to default and
        self.masks.update(force=True)   # write all masks to chip

    def interpret_direct_hit(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("noise", "<u1")])
        hit_data_leterow = raw_data[(raw_data & 0xF0000000) == 0]
        hit_data_col = raw_data[(raw_data & 0xF0000000) == 0x10000000]
        if len(hit_data_leterow) == len(hit_data_col):
            pass
        elif len(hit_data_leterow) == len(hit_data_col) + 1:
            hit_data_leterow = hit_data_leterow[:-1]
        elif len(hit_data_leterow) + 1 == len(hit_data_col):
            hit_data_col = hit_data_col[1:]
        else:
            print("ERROR:interpret_direct_hit: brokendata", len(hit_data_leterow), len(hit_data_col))
            return
        hit = np.empty(hit_data_leterow.shape[0], dtype=hit_dtype)

        hit['row'] = (hit_data_leterow & 0x1FF)
        hit['col'] = (hit_data_col & 0x1FF)
        hit['te'] = (hit_data_leterow & 0x00FE00) >> 9
        hit['le'] = (hit_data_leterow & 0x7F0000) >> 16
        hit['noise'] = (hit_data_leterow & 0x800000) >> 23
        return hit

    def interpret_ts(self, raw_data):
        print("=====sim=====ts", end=" ")
        for r in raw_data:
            print(hex(r), end=" ")
        hit_dtype = np.dtype([("le", "<u8"), ("te", "<u8")])
        hit_le0 = raw_data[(raw_data & 0xFF000000) == 0x61000000] & 0xFFFFFF
        hit_le1 = raw_data[(raw_data & 0xFF000000) == 0x62000000] & 0xFFFFFF
        hit_le2 = raw_data[(raw_data & 0xFF000000) == 0x63000000] & 0xFFFFFF
        hit_te0 = raw_data[(raw_data & 0xFF000000) == 0x65000000] & 0xFFFFFF
        hit_te1 = raw_data[(raw_data & 0xFF000000) == 0x66000000] & 0xFFFFFF
        hit_te2 = raw_data[(raw_data & 0xFF000000) == 0x67000000] & 0xFFFFFF
        hit = np.empty(len(hit_le0), dtype=hit_dtype)
        hit['le'] = hit_le0 | (hit_le1 << 24) | (hit_le2 << 48)
        hit['te'] = hit_te0 | (hit_te1 << 24) | (hit_te2 << 48)
        return hit

    def interpret_no8b10b(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("token_id", "<i8")])
        r = raw_data[(raw_data & 0xF8000000) == 0x40000000]
        r0 = (r & 0x7FC0000) >> 18
        r1 = (r & 0x003FE00) >> 9
        r2 = (r & 0x00001FF)
        for i in range(len(r)):
            print("=====sim=====", i, hex(r0[i]), hex(r1[i]), hex(r2[i]))
        rx_data = np.reshape(np.vstack((r0, r1, r2)), -1, order="F")
        hit = np.empty(len(rx_data) // 4 + 10, dtype=hit_dtype)
        i = 0
        ii = 0
        while i < len(rx_data):
            if rx_data[i] == 0x13C:
                i = i + 1
            elif i + 3 < len(rx_data):
                hit[ii]['col'] = (rx_data[i] << 1) + ((rx_data[i + 2] & 0x2) >> 1)
                hit[ii]['row'] = ((rx_data[i + 2] & 0x1) << 9) + rx_data[i + 3]
                hit[ii]['le'] = gray2bin((rx_data[i + 1] >> 1))
                hit[ii]['te'] = gray2bin(((rx_data[i + 1] & 0x1) << 6) + ((rx_data[i + 2] & 0xFC) >> 2))
                hit[ii]['token_id'] = 0
                ii = ii + 1
                i = i + 4
            else:
                print(i, hex(rx_data[i]))
                i = i + 1
        return hit[:ii]

    def interpret_data(self, raw_data):
        hit_dtype = np.dtype(
            [("col", "<u2"), ("row", "<u2"), ("le", "<u1"), ("te", "<u1"), ("token_id", "<i8")])
        reg_dtype = np.dtype([("address", "<u1"), ("value", "<u2")])
        r = raw_data[(raw_data & 0xF8000000) == 0x40000000]
        r0 = (r & 0x7FC0000) >> 18
        r1 = (r & 0x003FE00) >> 9
        r2 = (r & 0x00001FF)
        rx_data = np.reshape(np.vstack((r0, r1, r2)), -1, order="F")
        hit = np.empty(len(rx_data) // 4 + 10, dtype=hit_dtype)
        reg = np.empty(len(rx_data) // 5 + 10, dtype=reg_dtype)
        h_i = 0
        r_i = 0
        idx = 0
        token_id = 0
        flg = 0
        while idx < len(rx_data):
            if rx_data[idx] == 0x1fc:
                if len(rx_data) > idx + 5 and rx_data[idx + 4] == 0x15c:  # reg data
                    reg[r_i]['address'] = (rx_data[idx + 1] & 0x0FF)
                    reg[r_i]['value'] = ((rx_data[idx + 2] & 0x0FF) << 8) + (rx_data[idx + 3] & 0x0FF)
                    r_i = r_i + 1
                    idx = idx + 5
                else:
                    print("interpret_data: broken reg data", idx)
                    idx = idx + 1
            elif rx_data[idx] == 0x1bc:  # sof
                idx = idx + 1
                if flg != 0:
                    print("interpret_data: eof is missing")
                flg = 1
            elif rx_data[idx] == 0x17c:  # eof
                if flg != 1:
                    print("interpret_data: eof before sof", idx, hex(rx_data[idx]))
                flg = 0
                idx = idx + 1
                token_id = token_id + 1
            elif rx_data[idx] == 0x13c:  # idle (dummy data)
                idx = idx + 1
            else:
                if flg != 1:
                    print("interpret_data: sof is missing", idx, hex(rx_data[idx]))
                if len(rx_data) < idx + 4:
                    print("interpret_data: incomplete data")
                    break
                hit[h_i]['token_id'] = token_id
                hit[h_i]['le'] = (rx_data[idx + 1] & 0xFE) >> 1
                hit[h_i]['te'] = (rx_data[idx + 1] & 0x01) << 6 | ((rx_data[idx + 2] & 0xFC) >> 2)
                hit[h_i]['row'] = ((rx_data[idx + 2] & 0x1) << 8) | (rx_data[idx + 3] & 0xFF)
                hit[h_i]['col'] = ((rx_data[idx] & 0xFF) << 1) + ((rx_data[idx + 2] & 0x2) >> 1)
                idx = idx + 4
                h_i = h_i + 1
        hit = hit[:h_i]
        reg = reg[:r_i]
        hit['le'] = gray2bin(np.copy(hit['le']))
        hit['te'] = gray2bin(np.copy(hit['te']))
        return hit, reg

    def get_temperature(self, n=10):
        # TODO: Why is this needed? Should be handled by basil probably
        vol = self.daq["NTC"].get_voltage()
        if not (vol > 0.5 and vol < 1.5):
            for i in np.arange(2, 200, 2):
                self.daq["NTC"].set_current(i, unit="uA")
                time.sleep(0.1)
                vol = self.daq["NTC"].get_voltage()
                if vol > 0.7 and vol < 1.3:
                    break
            if abs(i) > 190:
                self.log.warn("temperature() NTC error")

        temp = np.empty(n)
        for i in range(len(temp)):
            temp[i] = self.daq["NTC"].get_temperature("C")
        return np.average(temp[temp != float("nan")])

    # COMMAND DECODER
    def write_command(self, data, repetitions=1, wait_for_done=True, wait_for_ready=False):
        '''
            Write data to the command encoder.

            Parameters:
            ----------
                data : list
                    Up to [get_cmd_size()] bytes
                repetitions : integer
                    Sets repetitions of the current request. 1...2^16-1. Default value = 1.
                wait_for_done : boolean
                    Wait for completion after sending the command. Not advisable in case of repetition mode.
                wait_for_ready : boolean
                    Wait for completion of preceding commands before sending the command.
        '''
        if isinstance(data[0], list):
            for indata in data:
                self.write_command(indata, repetitions, wait_for_done)
            return

        assert (0 < repetitions < 65536), "Repetition value must be 0<n<2^16"
        if repetitions > 1:
            self.log.debug("Repeating command %i times." % (repetitions))

        if wait_for_ready:
            while (not self.daq['cmd'].is_done()):
                pass

        self.daq['cmd'].set_data(data)
        self.daq['cmd'].set_size(len(data))
        self.daq['cmd'].set_repetitions(repetitions)
        self.daq['cmd'].start()

        if wait_for_done:
            while (not self.daq['cmd'].is_done()):
                pass

    def write_sync(self, write=True):
        indata = [0b10000001, 0b01111110]
        if write:
            self.write_command(indata)
        return indata

    # def write_ecr(self, write=True):
    #     indata = [self.CMD_CLEAR]
    #     indata += [self.cmd_data_map[self.chip_id]]
    #     if write:
    #         self.write_command(indata)
    #     return indata

    # def write_glr(self, write=True):
    #     indata = [self.CMD_GLOBAL_PULSE]
    #     indata += [self.cmd_data_map[self.chip_id]]
    #     if write:
    #         self.write_command(indata)
    #     return indata

    def _write_register(self, address, data, write=True):
        '''
            Sends write command to register with data

            Parameters:
            ----------
                address : int
                    Address of the register to be written to
                data : int
                    Value to write into register

            Returns:
            ----------
                indata : binarray
                    Boolean representation of register write command.
        '''
        indata = [self.CMD_REGISTER, self.cmd_data_map[self.chip_id]] + encode_cmd(address, data)

        if write:
            self.write_command(indata)

        return indata

    def _read_register(self, address, write=True):
        '''
            Sends read command to register with data

            Parameters:
            ----------
                address : int or str
                    Address or name of the register to be written to

            Returns:
            ----------
                indata : binarray
                    Boolean representation of register write command.
        '''
        if type(address) is str:
            address = self.register_name_map[address]

        indata = [self.CMD_RDREG]
        indata += [self.cmd_data_map[self.chip_id]]
        indata += [self.cmd_data_map[address >> 5]]  # first 4 bits of address
        indata += [self.cmd_data_map[address & 0x1f]]  # last 5 bits of address

        if write:
            self.write_command(indata)
        return indata

    def _get_register_value(self, address, timeout=1000, tries=10):
        for _ in range(tries):
            self._read_register(address)
            self.write_command(self.write_sync(write=False) * 10)
            if self.daq.board_version == 'SIMULATION':
                timeout = 2
            for _ in range(timeout):
                if self.daq['FIFO'].get_FIFO_SIZE() > 0:
                    data = self.daq['FIFO'].get_data()
                    # userk_data = analysis_utils.process_userk(anb.interpret_userk_data(data))
                    _, reg_data = self.interpret_data(data)
                    if len(reg_data) == 1:
                        return reg_data[0]['value']
                    else:
                        continue
                self.write_command(self.write_sync(write=False) * 10)
            else:
                self.log.warning('Timeout while waiting for register response.')
        else:
            raise RuntimeError('Timeout while waiting for register response.')

    def write_cal(self, PulseStartCnfg=1, PulseStopCnfg=10, wait_cycles=0, write=True):
        '''
            Command to send a digital or analog injection to the chip.
            Digital or analog injection is selected globally via the INJECTION_SELECT register.
            Need to reset BCID counter (register address 146) before injection.
            wait_cycle delays injection by 4 BCID CLK cycles.

            For digital injection, only CAL_edge signal is relevant:
                - CAL_edge_mode switches between step (0) and pulse (1) mode
                - CAL_edge_dly is counted in bunch crossings. It sets the delay before the rising edge of the signal
                - CAL_edge_width is the duration of the pulse (only in pulse mode) and is counted in cycles of the 160MHz clock
            For analog injection, the CAL_aux signal is used as well:
                - CAL_aux_value is the value of the CAL_aux signal
                - CAL_aux_dly is counted in cycles of the 160MHz clock and sets the delay before the edge of the signal
            {Cal,ChipId[4:0]}-{PulseStartCnfg[5:1]},{PulseStartCnfg[0], PulseStopCnfg[13:10]}}-{{PulseStopCnfg[9:0]} [Cal +DD +DD]
        '''
        indata = self._write_register(146, 0b100, write=False)
        indata += self._write_register(146, 0b000, write=False)
        indata += self.write_sync(write=False) * wait_cycles
        indata += [self.CMD_CAL]
        indata += [self.cmd_data_map[self.chip_id]]
        indata += [self.cmd_data_map[(PulseStartCnfg & 0b11_1110) >> 1]]
        indata += [self.cmd_data_map[((PulseStartCnfg << 4) & 0b10000) + ((PulseStopCnfg >> 10) & 0b1111)]]
        indata += [self.cmd_data_map[((PulseStopCnfg >> 5) & 0b11111)]]
        indata += [self.cmd_data_map[PulseStopCnfg & 0b11111]]

        if write:
            self.write_command(indata)

        return indata

    def inject(self, PulseStartCnfg=1, PulseStopCnfg=10, repetitions=1, latency=400, wait_cycles=0, write=True):
        indata = self.write_sync(write=False) * 4
        indata += self.write_cal(PulseStartCnfg=PulseStartCnfg, PulseStopCnfg=PulseStopCnfg, wait_cycles=wait_cycles, write=False)  # Injection
        indata += self.write_sync(write=False) * latency

        if write:
            self.write_command(indata, repetitions=repetitions)
        return indata


if __name__ == '__main__':
    chip = TJMonoPix2()
    chip.init()
