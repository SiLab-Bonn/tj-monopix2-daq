#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import re
from importlib import reload
from unittest import mock

import numpy as np
import tables as tb
import tjmonopix2
# Required to trigger imports of mocked objects
from tjmonopix2.system import scan_base  # noqa: F401


class TJMonopix2_Mock(object):
    """ Mock to use software package without actual hardware to a level that scans work in software

        raw_data_file: h5 raw data file from a scan
            Chip raw data can be simulated by providing a raw_data_file. Timings are not preserved since
            FIFO readout is asynchronous.
        send_commands_file: h5 file
            Create an h5 file and stores *all* commands send to chip. Useful for testing and debuging.
    """

    def __init__(self, raw_data_file=None, send_commands_file=None, create_chip_data=True):
        self.raw_data_file = raw_data_file
        self.send_commands_file = send_commands_file
        self.create_chip_data = create_chip_data
        self.patches = {}
        self.enabled_rx = []

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        """ Mock out all methods and modules that require hardware
        """

        # Mock hardware communication via tjmonopix2.system.bdaq53.BDAQ53
        self.bdaq53_patcher = []

        def init_mock(cls):
            cls.fw_version = '0.0'
            cls.board_version = 'BDAQ53Mock'

            cls.rx_channels = {}
            cls.rx_channels['rx0'] = mock.Mock()
            self.rx_channels = cls.rx_channels

        self.patch_function('tjmonopix2.system.bdaq53.BDAQ53.init', init_mock)
        self.patch_function('tjmonopix2.system.bdaq53.BDAQ53.get_tlu_erros', lambda *args, **kwargs_: (0, 0))

        self.bdaq53_patcher.append(mock.patch('tjmonopix2.system.bdaq53.BDAQ53.__getitem__'))  # basil dict access
        self.bdaq53_patcher[-1].return_value = 0
        self.bdaq53_patcher[-1].start()

        # Store all commands to file
        if self.send_commands_file:
            if os.path.isfile(self.send_commands_file):  # append if already existing
                self.send_commands_h5 = tb.open_file(self.send_commands_file, 'r+')
                commands = self.send_commands_h5.root.commands
            else:
                self.send_commands_h5 = tb.open_file(self.send_commands_file, 'w')
                commands = self.send_commands_h5.create_earray(self.send_commands_h5.root, name='commands',
                                                               atom=tb.UIntAtom(), shape=(0,), title='commands',
                                                               filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))

            def store_cmd(cmd, repetitions=100):  # noqa
                commands.append(cmd)

        # Mock chip
        chip_class = tjmonopix2.system.tjmonopix2.TJMonoPix2
        self.chip_patcher = []
        self._patch_chip_read_write_register(chip_class, chip_class._write_register, chip_class._get_register_value)
        chip_module_str = re.findall("'([^']*)'", str(chip_class))[0]
        if self.send_commands_file:
            self.chip_patcher.append(mock.patch('%s.write_command' % chip_module_str, side_effect=store_cmd))
            self.chip_patcher[-1].start()

        # Mock fifo readout
        def print_readout_status(_, rx_channel=None):
            if rx_channel is None:
                return True
            return True

        self.patch_function('tjmonopix2.system.fifo_readout.FifoReadout.print_readout_status', print_readout_status)
        self.patch_function('tjmonopix2.system.fifo_readout.FifoReadout.reset_sram_fifo')

        def get_count(_, rx_channel=None):
            if rx_channel is None:
                return [0]
            return 0

        self.patch_function('tjmonopix2.system.fifo_readout.FifoReadout.get_rx_fifo_discard_count', get_count)
        self.patch_function('tjmonopix2.system.fifo_readout.FifoReadout.get_rx_8b10b_error_count', get_count)

        # Speed up testing time drastically, by not calling mask shifting
        self.patch_function('tjmonopix2.system.tjmonopix2.MaskObject.update')

        if self.raw_data_file:
            self.in_file_h5 = tb.open_file(self.raw_data_file)
            self.meta_data = self.in_file_h5.root.meta_data[:]
            self.raw_data = self.in_file_h5.root.raw_data
            n_readouts = self.meta_data.shape[0]
            self.i_ro = 0

        def read_data(cls):
            if self.create_chip_data:
                if self.raw_data_file:  # return chip raw data from file
                    if self.i_ro < n_readouts:
                        # Raw data indeces of readout
                        i_start = self.meta_data['index_start'][self.i_ro]
                        i_stop = self.meta_data['index_stop'][self.i_ro]
                        self.i_ro += 1
                        return self.raw_data[i_start:i_stop] | (self.enabled_rx[0] << 20)  # add channel id
                    return np.array([], dtype=np.int32)
                else:  # just count upwards
                    data = []
                    if not cls.stop_readout.is_set():  # Create some fake data
                        # Create one data word per active readout channel with correct rx id to be able to check filtering
                        data.append(0x0 | (0x1 << 20))
                    return np.array(data, dtype=np.int32)

        self.patch_function('tjmonopix2.system.fifo_readout.FifoReadout.read_data', read_data)

        # Reload mocked import
        reload(tjmonopix2.system.scan_base)

    def stop(self):
        ''' Remove mocks to allow normal operation '''

        if self.raw_data_file:
            self.in_file_h5.close()
        if self.send_commands_file:
            self.send_commands_h5.close()

        for patch in self.patches.values():
            patch.stop()
        for patch in self.bdaq53_patcher:
            patch.stop()
        for patch in self.chip_patcher:
            patch.stop()
        self._unpatch_chip_read_write(tjmonopix2.system.tjmonopix2.TJMonoPix2)

    def reset(self):
        self.stop()
        self.start()

    def patch_function(self, target, function=None):
        if target in self.patches:
            try:
                self.patches[target].stop()
            except RuntimeError:  # stop called on not started patcher
                pass
            del self.patches[target]
        self.patches[target] = mock.patch(target, new=function if function else mock.DEFAULT)
        self.patches[target].start()

    def _patch_chip_read_write_register(self, chip_class, write_method, read_method):
        ''' Monkey patch chip write and read

            Add write/read of registers without chip hardware.
            Use storage in software to keep configuration and simulate simple register write and read
        '''
        # Monkey patch register storage in software instead of chip
        chip_class.original_write = write_method
        chip_class.original_read = read_method

        def wrap_write_register(cls, address, data, write=True):
            # BDAQ53 relies on power on reset values
            # Therefore write always to chip storage even if write=false
            try:
                cls.register_values
            except AttributeError:
                cls.register_values = {}
            cls.register_values[address] = data
            return cls.original_write(address, data, write)

        def wrap_read_register(cls, address, *_):
            return cls.register_values[address]

        chip_class._write_register = wrap_write_register
        chip_class._get_register_value = wrap_read_register

    def _unpatch_chip_read_write(self, chip_class):
        ''' Remove patch and restore std. methods '''
        chip_class._write_register = chip_class.original_write
        chip_class._get_register_value = chip_class.original_read
