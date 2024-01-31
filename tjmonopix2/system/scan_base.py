#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import ast
import collections
import inspect
import multiprocessing
import os
import time
import traceback
from collections import OrderedDict
from contextlib import contextmanager
from copy import deepcopy
from threading import Lock

import numpy as np
import tables as tb
import yaml
import zmq
from online_monitor.utils import utils as ou

from tjmonopix2 import utils
from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.system import fifo_readout, logger
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.fifo_readout import FifoReadout
from tjmonopix2.system.mio3 import MIO3
from tjmonopix2.system.tjmonopix2 import TJMonoPix2

# Compression for data files
FILTER_RAW_DATA = tb.Filters(complib='blosc', complevel=5, fletcher32=False)
FILTER_TABLES = tb.Filters(complib='zlib', complevel=5, fletcher32=False)
# Default locations
PROJECT_FOLDER = os.path.join(os.path.dirname(__file__), '..')
SYSTEM_FOLDER = os.path.join(PROJECT_FOLDER, 'system')
DEFAULT_CONFIG_FILE = os.path.join(PROJECT_FOLDER, 'system', 'default.cfg.yaml')
TESTBENCH_DEFAULT_FILE = os.path.join(PROJECT_FOLDER, 'testbench.yaml')


def fill_dict_from_conf_table(table):
    conf = au.ConfigDict()
    for k, v in table[:]:
        conf[k] = v
    return conf


def send_data(socket, data, scan_param_id, name='ReadoutData'):
    '''Sends the data of every read out (raw data and meta data)

        via ZeroMQ to a specified socket.
        Uses a serialization provided by the online_monitor package
    '''

    data_meta_data = dict(
        name=name,
        timestamp_start=data[1],  # float
        timestamp_stop=data[2],  # float
        error=data[3],  # int
        scan_param_id=scan_param_id
    )
    try:
        data_ser = ou.simple_enc(data[0], meta=data_meta_data)
        socket.send(data_ser, flags=zmq.NOBLOCK)
    except zmq.Again:
        pass


class MetaTable(tb.IsDescription):
    index_start = tb.Int64Col(pos=0)
    index_stop = tb.Int64Col(pos=1)
    data_length = tb.UInt32Col(pos=2)
    timestamp_start = tb.Float64Col(pos=3)
    timestamp_stop = tb.Float64Col(pos=4)
    scan_param_id = tb.UInt32Col(pos=5)
    error = tb.UInt32Col(pos=6)
    trigger = tb.Float64Col(pos=7)


class MapTable(tb.IsDescription):
    cmd_number_start = tb.UInt32Col(pos=0)
    cmd_number_stop = tb.UInt32Col(pos=1)
    cmd_length = tb.UInt32Col(pos=2)
    scan_param_id = tb.UInt32Col(pos=3)


class RunConfigTable(tb.IsDescription):
    attribute = tb.StringCol(64)
    value = tb.StringCol(512)


# class ChipStatusTable(tb.IsDescription):
#     attribute = tb.StringCol(64, pos=0)
#     ADC = tb.UInt16Col(pos=1)
#     value = tb.Float64Col(pos=2)


class RegisterTable(tb.IsDescription):
    register = tb.StringCol(64)
    value = tb.StringCol(256)


class ScanData:
    ''' Class to store data created in the scan.

        Shared between the configure(), scan() and analyze() steps
    '''
    pass


class ChipContainer:
    '''
    Data class that collects all chip specific objects, data, and configs

    Is created per chip.
    '''

    def __init__(self, name, chip_settings, chip_conf, module_settings, output_filename, output_dir, log_fh, scan_config, suffix=''):
        self.name = name
        self.chip_settings = chip_settings  # chip settings from testbench; not to be confused with self.chip_settings['chip_config_file']
        self.module_settings = module_settings  # module configuration of this chip from testbench
        self.chip_conf = chip_conf  # configuration object for chip
        if suffix != '' and output_filename is not None:
            self.output_filename = output_filename + suffix
        else:
            self.output_filename = output_filename
        self.output_dir = output_dir
        self.log_fh = log_fh
        self.scan_config = scan_config

        # Set later
        self.chip = None  # the TJ-Monopix2 chip object
        self.data = ScanData()
        self.h5_file = None
        self.raw_data_earray = None
        self.meta_data_table = None
        # self.trigger_table = None
        # self.ptot_table = None
        self.scan_parameters = OrderedDict()
        self.socket = None

    def __repr__(self):
        return 'ChipContainer for %s (%s) of %s with data at %s' % (self.name, self.chip_settings['chip_sn'], self.module_settings['name'], self.output_dir)


class ScanBase(object):
    '''
        Basic run meta class.
        Base class for scan- / tune- / analyze-class.
    '''

    is_parallel_scan = False  # Parallel readout of ExtTrigger-type scans etc.; must be overridden in the derived classes if needed

    def __init__(self, daq_conf=None, bench_config=None, scan_config={}, scan_config_per_chip=None, suffix=''):
        '''
            Initializer.

            Parameters:
            ----------
            daq_conf : str, dict or file
                    Readout board configuration (configuration as dict or file or its filename as string)

            bench_config : str or dict
                    Testbench configuration (configuration as dict or its filename as string)

            scan_config : dict
                    Dictionary of scan parameters. These can be complemented/overwritten per chip by scan_config_per_chip, see below.
                    The scan parameters will be passed to the _configure() and _scan() functions as expanded kwargs.

                    If the dictionary contains a key named 'chip' then the corresponding value (which should be a dict with format/structure
                    compatible to the 'rd53x_default.cfg.yaml') is used to complement/overwrite the chip configuration(s)
                    loaded from the chip_configuration file(s) specified in the testbench configuration.

                    If the dictionary contains a key named 'bdaq' then the corresponding value (which should be a dict with format/structure
                    compatible to the 'testbench.yaml') is used to complement/overwrite the testbench configuration loaded from 'testbench.yaml'.

            scan_config_per_chip : dict
                    Dictionary (format similar as in 'testbench.yaml') containing additional or changed scan parameters
                    for each chips given. Example: {'module_0': {'chip_0': {'start_column': 128, 'stop_column': 148},
                                                                'chip_1': {'start_column': 0, ...}},
                                                   'module_1': {...}, ...}
                    A 'chip' dict as additional parameter will complement/overwrite a 'chip' dict given in scan_config for the corresponding chip.

            record_chip_status : boolean
                    Add chip statuses to the output files after the scan
        '''
        # Allow changes without changing originals
        if isinstance(daq_conf, dict):
            daq_conf = deepcopy(daq_conf)
        if isinstance(bench_config, dict):
            bench_config = deepcopy(bench_config)
        scan_config = deepcopy(scan_config)
        if isinstance(scan_config_per_chip, dict):
            scan_config_per_chip = deepcopy(scan_config_per_chip)

        self.errors_occured = False

        # Configuration parameters
        self.daq_conf_par = daq_conf
        self.bench_config_par = bench_config
        self.scan_config_par = scan_config
        self.scan_config_per_chip_par = scan_config_per_chip

        self.proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.ana_proc = None  # analysis process for non-blocking analysis
        self.log = logger.setup_derived_logger(self.__class__.__name__)  # setup logger
        self._log_handlers_per_scan = []  # FIXME: all log handlers of all chips
        self.hardware_initialized = False
        self.initialized = False

        self.daq = None  # readout system, defined during scan init if not existing

        # Needed for parallel scans where several readout threads change the chip handles
        self.chip_handle_lock = Lock()

        # All chips data containers
        self.chips = {}
        self.suffix = suffix

    def init(self, force=False):
        try:
            self.errors_occured = False
            self._init_environment()
            self._init_hardware(force)
            self._init_files()
            self.initialized = True
        except Exception as e:
            # if self.periphery:
            #     self.periphery.close()
            raise e

    def configure(self):
        ret_values = [None] * self.n_chips()
        try:
            if not self.initialized:
                raise RuntimeError('Cannot call configure() before init() is called!')
            # Deactivate receiver to prevent recording useless data
            for i in self.iterate_chips():
                self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)
                print (f'disabling chip: {self.chip.receiver} at configure')
            for i, _ in enumerate(self.iterate_chips()):
                with self._logging_through_handler(self.log_fh):
                    self.log.info('Configuring chip {0}...'.format(self.chip.get_sn()))
                    # Load masks from config
                    self._set_receiver_enabled(receiver=self.chip.receiver, enabled=True)
                    print(f'enabling chip: {self.chip.receiver} at configure')
                    self._configure_masks()
                    # Scan dependent configuration step before actual scan can be started (set enable masks etc.)
                    ret_values[i] = self._configure(**self.scan_config)
                    # self.periphery.get_module_power(module=self.module_settings['name'], log=True)
                    self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)
                    print (f'disabling chip: {self.chip.receiver} at configure')

            # Create general FIFO readout (for all chips/modules)
            self._configure_fifo_readout()

            # Enable receivers
            # for _ in self.iterate_chips():
            #     self._set_receiver_enabled(receiver=self.chip.receiver, enabled=True)
            #     print(f'enabling chip: {self.chip.receiver} at configure !')
            # # Make sure monitor filter is blocking for all receivers before starting scan
            # self.daq.set_monitor_filter(mode='block')

            return ret_values
        except Exception as e:
            self._on_exception()
            raise e

    def scan(self):
        ret_values = [None] * self.n_chips()
        try:
            if not self.initialized:
                raise RuntimeError('Cannot call scan() before init() is called!')
            # scan() does not the same as start() anymore
            try:
                self.fifo_readout
            except AttributeError:  # configure not called
                raise RuntimeError('scan() called before configure(). This is deprecated!')

            if self.is_parallel_scan:
                # Enable all channels of defined chips
                for _ in self.iterate_chips():
                    self._set_receiver_enabled(receiver=self.chip.receiver, enabled=True)
                    print (f'enabling chip: {self.chip.receiver} at scan')
                self.daq.reset_fifo()
                self._scan(**self.scan_config)
                for _ in self.iterate_chips():
                    self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)
                    print (f'disabling chip: {self.chip.receiver} at scan')
            else:
                self.daq.reset_fifo()
                for i, _ in enumerate(self.iterate_chips()):
                    with self._logging_through_handler(self.log_fh):
                        self._set_receiver_enabled(receiver=self.chip.receiver, enabled=True)
                        print (f'enabling chip: {self.chip.receiver} at scan')
                        ret_values[i] = self._scan(**self.scan_config)
                        self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)
                        print (f'disabling chip: {self.chip.receiver} at configure')
            # Finalize scan
            # Disable tlu module in case it was enabled.
            if self.daq.tlu_module_enabled:
                self.daq.disable_tlu_module()

            # Add status info
            self._set_readout_status()
            for _ in self.iterate_chips():
                # Add additional after scan data
                self._add_chip_status()
                node = self.h5_file.create_group(self.h5_file.root, 'configuration_out', 'Configuration after scan step')
                self._write_config_h5(self.h5_file, node)
                self._store_scan_par_values(self.h5_file)  # store scan params in out node, since it is defined during scan step
                self.h5_file.close()

            return ret_values
        except Exception as e:
            self._on_exception()
            raise e

    def analyze(self):
        '''
            Loop over all chips in testbench and for each perform the analysis routine of the scan:
            - Analyze raw data, plotting
        '''
        ret_values = [None] * self.n_chips()
        try:
            if self.configuration['bench']['analysis'].get('skip', False):
                return
            for i, _ in enumerate(self.iterate_chips()):
                with self._logging_through_handler(self.log_fh):
                    # Perform actual analysis
                    self.log.info('Starting analysis for ' + self.name + ' (' + self.chip_settings['chip_sn'] + ')')
                    if self.configuration['bench']['analysis'].get('blocking', True):
                        ret_values[i] = self._analyze()
                    else:
                        # Sockets must be closed before process fork, otherwise sockets cannot be closed in
                        # main process. This should be OK, since parallel analysis + redoing a scan is unlikely
                        self._close_sockets()

                        def analyze_and_close_file():
                            self._analyze()
                            self._close_h5_file()

                        self.wait_for_analysis()  # wait for previous analysis
                        self.log.info('Analysis in seperate process')
                        self.ana_proc = multiprocessing.Process(target=analyze_and_close_file)
                        self.ana_proc.daemon = True
                        self.ana_proc.start()
            return ret_values
        except Exception as e:
            self._on_exception()
            raise e

    def analyze_file(self, raw_data_file):
        ''' Allows to re-analyze a chip raw data file without hardware

            filename: str
                path to raw data file. h5 suffix can be ommited
        '''

        raw_data_file = raw_data_file.replace('.h5', '') + '.h5'
        # Since the state machine init -> configure -> scan -> analyze -> close is broken here, set the minimum of required variables
        self.bench_config_par = self._load_testbench_cfg(self.bench_config_par)['bench']  # load std testbench settings

        # with tb.open_file(raw_data_file) as in_file:
        #     chip_type = fill_dict_from_conf_table(in_file.root.configuration_in.scan.run_config)['chip_type']

        # Set from filename
        self.bench_config_par['general']['output_directory'] = os.path.dirname(raw_data_file)

        if self.scan_id not in raw_data_file:
            raise RuntimeError('Cannot run the analysis of %s on %s', self.scan_id, raw_data_file)
        self._init_environment()

        # if chip_type.lower() != self.chip_settings['chip_type']:
        #     raise RuntimeError('Raw data file has different chip type than testbench (%s!=%s)' % (chip_type.lower(), self.chip_settings['chip_type']))

        self.output_filename = raw_data_file[:-3]
        self._analyze()

    def close(self):
        ''' Opposite of init

            Free hardware resources and store final config
        '''
        if self.initialized:
            self.daq.close()
            # self.periphery.close()
            self._close_sockets()
            self.initialized = False
        if not self.ana_proc:  # h5 files are closed in ana proc
            for _ in self.iterate_chips():
                self._close_h5_file()
        with self._logging_through_handlers():
            if self.errors_occured:
                self.log.error(self.errors_occured)
                self.log.error('Scan failed!')
            else:
                self.log.success('All done!')
        self._close_logfiles()
        if self.chips:
            self._unset_chip_handles()  # allows for gc of chip objects

    def start(self):
        '''
            Calls all required steps exluding the init/close step
        '''
        self.configure()
        self.scan()
        self.analyze()

        # Get readout status once, for all receiver channels
        with self._logging_through_handlers():
            self._set_readout_status()

    # def enable_hitor(self, enable=True):
    #     '''
    #         Configure the hitor display port connectors depending on scan type.
    #         If enable is False all HitOr ports are disabled.
    #         If enable is True and the scan is a parallel scan (e.g. external trigger scan, source scan),
    #         there is parallel data readout and thus all HitOr ports get activated and or-ed in the FPGA.
    #         If enable is True and the scan is *not* a parallel scan, the available HitOr ports
    #         are activated one after another, always one during the scan of one chip;
    #         the order depends on the sorting order in 'testbench.yaml' module section (see wiki...).

    #         Note: the TDC feature does currently only work with *one* chip.
    #     '''
    #     if enable:
    #         if self.is_parallel_scan:  # Enable all HitOr ports simultaneously
    #             active_ports_conf = 0b000
    #             for _ in range(len(self.chips)):
    #                 active_ports_conf = (active_ports_conf << 1) + 0b001
    #             self.daq.configure_hitor_inputs(active_ports_conf=active_ports_conf)
    #         else:
    #             if not hasattr(self, 'hitor_en'):
    #                 self.hitor_en = 0b001  # Enable first HitOr port (DP)
    #             else:
    #                 self.hitor_en = self.hitor_en << 1  # Enable next HitOr port (mDP)
    #             if self.hitor_en == 0b100:
    #                 self.hitor_en = 0b000  # Only two HitOr ports available
    #             self.daq.configure_hitor_inputs(active_ports_conf=self.hitor_en)
    #     else:
    #         self.daq.configure_hitor_inputs(active_ports_conf=0b000)  # Disable all ports

    def store_scan_par_values(self, scan_param_id, **kwargs):
        '''
            Manually store the scan parameter values for the scan parameter id
            This allows to reconstruct the scan parameter values for a given parameter state vector
        '''
        if self.scan_parameters.get(scan_param_id) and self.scan_parameters.get(scan_param_id) != kwargs:
            raise ValueError('You cannot change the scan parameter value of a scan parameter id')
        self.scan_parameters[scan_param_id] = kwargs

    def iterate_chips(self):
        ''' Iterate through the chips and set all chip handles

            Usage for accessing chip attributes:
            for _ in self.iterate_chips():
                self.name = 'my_chip'
        '''
        for c in self.chips.values():
            self._set_chip_handles(c)
            yield c

    def n_chips(self):
        return len(self.chips)

    def wait_for_analysis(self):
        ''' Block exction until analysis is finished '''
        if self.ana_proc:
            self.log.info('Waiting for analysis process to finish...')
            self.ana_proc.join()

    def get_module_cfgs(self):
        ''' Returns the module configurations defined in the test bench '''
        return {k: v for k, v in self.configuration['bench']['modules'].items() if 'identifier' in v.keys()}

    def get_n_modules(self):
        return len(self.get_module_cfgs())

    def __enter__(self):
        self.initialized = False
        self.init()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()

    def _configure(self, **kwargs):
        '''
            Place here in derived class: configuration steps that need to be performed before each scan,
            but don't belong to the actual scan routine.
        '''
        self.log.info('No _configure() method implemented in scan. Use std. configuration.')

    def _scan(self, **kwargs):
        raise NotImplementedError('ScanBase._scan() not implemented')

    def _analyze(self, **_):
        self.log.warning('analyze() method not implemented; do not analyze data')

    def _init_environment(self):
        self.timestamp = time.strftime("%Y%m%d_%H%M%S")
        self.run_name = self.timestamp + '_' + self.scan_id
        # self.ext_trig_num = 0  # reqired for trigger based analysis
        self.context = zmq.Context.instance()  # one context per process to manage sockets
        # Configuration with testbench and scan configuration configs (dict-like object)
        self.configuration = self._load_testbench_cfg(self.bench_config_par)  # fill self.configuration['bench'] with provided testbench config
        utils.recursive_update(self.configuration['bench'], self.scan_config_par.get('bench', {}))  # Update testbench configuration from scan configuration

        # Main working directory
        if self.configuration['bench']['general']['output_directory'] is not None:
            self.working_dir = self.configuration['bench']['general']['output_directory']
        else:
            self.working_dir = os.path.join(os.getcwd(), "output_data")

        self._create_chip_container(self.scan_config_par, self.scan_config_per_chip_par)  # fill self.chips with chip container objects from testbench and parameters

        # Instantiate periphery and RO hardware (append log to all chip log files)
        with self._logging_through_handlers():
            self.log.info('Initializing %s...', self.__class__.__name__)
            if not self.daq:  # create daq object only once
                if self.configuration['bench']['general']['readout_system'] is not None:
                    readout_system = self.configuration['bench']['general']['readout_system'].lower()
                else:
                    readout_system = 'bdaq53'
                if readout_system == "mio3":
                    self.daq = MIO3(conf=self.daq_conf_par, bench_config=self.configuration['bench'])
                else:
                    self.daq = BDAQ53(conf=self.daq_conf_par, bench_config=self.configuration['bench'])

        # Instantiate TJ-Monopix2 chip
        for _ in self.iterate_chips():
            with self._logging_through_handler(self.log_fh):
                if self.chip:  # create chip object only once
                    continue
                else:
                    self.chip = TJMonoPix2(self.daq, chip_sn=self.chip_settings['chip_sn'], chip_id=self.chip_settings['chip_id'], receiver=self.chip_settings['receiver'], config=self.chip_conf)

    def _init_files(self):
        for _ in self.iterate_chips():
            self.h5_file = tb.open_file(self.output_filename + '.h5', mode='w', title=self.scan_id)
            # Create config nodes
            self.h5_file.create_group(self.h5_file.root, 'configuration_in', 'Configuration before scan')
            self._write_config_h5(self.h5_file, self.h5_file.root.configuration_in)

            # Create data nodes
            self.raw_data_earray = self.h5_file.create_earray(self.h5_file.root, name='raw_data', atom=tb.UIntAtom(),
                                                              shape=(0,), title='raw_data', filters=FILTER_RAW_DATA)
            self.meta_data_table = self.h5_file.create_table(self.h5_file.root, name='meta_data', description=MetaTable,
                                                             title='meta_data', filters=FILTER_TABLES)
            # self.trigger_table = self.h5_file.create_table(self.h5_file.root, name='trigger_table', description=MapTable,
            #                                                title='trigger_table', filters=FILTER_TABLES)
            # self.ptot_table = self.h5_file.create_table(self.h5_file.root, name='ptot_table', description=PtotTable,
            #                                             title='ptot_table', filters=FILTER_TABLES)

            # Setup data sending
            socket_addr = self.chip_settings.get('send_data', None)
            if socket_addr:
                try:
                    self.socket = self.context.socket(zmq.PUB)  # publisher socket
                    self.socket.setsockopt(zmq.LINGER, 0)
                    self.socket.bind(socket_addr)
                    self.log.debug('Sending data to server %s', socket_addr)
                except zmq.error.ZMQError:
                    self.log.exception('Cannot connect to socket for data sending.')
                    self.socket = None
            else:
                self.socket = None

    def _init_hardware(self, force):
        if not self.hardware_initialized or force:
            with self._logging_through_handlers():  # TODO: log power supply logs for chips of same module only
                self.daq.init()
                self.log.info('Initializing chips...')

            # Reset CMD state mashine, creates glitch that requires often a new PLL lock and AURORA sync
            # Likely not required at chip init, was done for RD53A
            self.daq['cmd'].reset()

            for _ in self.iterate_chips():
                with self._logging_through_handler(self.log_fh):
                    # Initialize chip
                    self.chip.init()  # resets masks to std. config
                    # pass

                    # Set mask settings
                    # Set TDAC mask, only available if previous file exists
                    # Do not set other masks, but use std. config for them
                    # Not really easy to understand logic: https://gitlab.cern.ch/silab/bdaq53/-/issues/401
                    if self.chip_conf['masks']:
                        self.chip.masks['tdac'] = deepcopy(self.chip_conf['masks']['tdac'])
                    if not np.any(self.chip_conf['use_pixel']):  # first scan has no use_pixel mask defined
                        self.chip_conf['use_pixel'] = np.ones_like(self.chip.masks['enable'])
                    # # Unset disabled pixels in use_pixel mask, issue #456
                    if self.chip_conf.get('disable_pixel'):
                        for p in self.chip_conf.get('disable_pixel'):
                            p_idx = ast.literal_eval(p)
                            self.chip_conf['use_pixel'][p_idx] = 0
                    self.chip.masks.disable_mask = deepcopy(self.chip_conf['use_pixel'])

                    # # Check if chip is configured properly
                    # if self.daq.board_version != 'SIMULATION':
                    #     self.chip.registers.check_all()

                    self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)
                    print (f'disabling chip: {self.chip.receiver} at _init_hardware')

            self.hardware_initialized = True
        else:
            with self._logging_through_handlers():
                self.log.info('Hardware already initialized, skip initialization!')

    def _set_chip_handles(self, chip):
        ''' Add the chip properties that are kept in the chip container
            to this class.

            This allows to access via the class attributes (handels)
            e.g. the h5 file with self.h5
        '''
        cls = type(self)

        def set_property_one_chip(name, chip):

            def setter(self, value):
                chip.__dict__[name] = value

            def getter(self):
                return chip.__dict__[name]

            setattr(cls, name, property(fset=setter, fget=getter))

        def set_property_many_chips(name):

            def setter(self, value):
                for chip in self.chips:
                    chip.__dict__[name] = value

            def getter(self):
                raise NotImplementedError('Cannot read from handle that points to many chips')

            setattr(cls, name, property(fset=setter, fget=getter))

        if chip:  # set scan base handles to one chip
            for name in chip.__dict__.keys():  # loop instance attributes
                set_property_one_chip(name, chip)
            self.configuration['scan'] = chip.scan_config  # API compatibility
        else:  # set scan base handles to all chips
            raise NotImplementedError('Multi chip handles are not supported')
            for name in self.chip.__dict__.keys():  # loop instance attributes
                set_property_many_chips(name)

    def _unset_chip_handles(self):
        ''' Remove the handles to a chip object.

            Required, otherwise python gc will not collect the chip objects (#442)
        '''
        chip_dummy = ChipContainer(name=None, chip_settings=None, chip_conf=None, module_settings=None, output_filename=None, output_dir=None, log_fh=None, scan_config=None)
        self._set_chip_handles(chip=chip_dummy)

    def _get_chip_at_rx(self, receiver):
        ''' Activates the handles for the chip at the receiver '''
        for _ in self.iterate_chips():
            if self.chip_settings['receiver'] == receiver:
                return self.name

    def _load_testbench_cfg(self, bench_config):
        ''' Load the bench config into the scan

            Parameters:
            ----------
            bench_config : str or dict
                    Testbench configuration (configuration as dict or its filename as string)
        '''
        conf = au.ConfigDict()
        try:
            if bench_config is None:
                bench_config = TESTBENCH_DEFAULT_FILE
            with open(bench_config) as f:
                conf['bench'] = yaml.full_load(f)
        except TypeError:
            conf['bench'] = bench_config

        return conf

    def _parse_chip_cfg_file(self, file_name):
        if file_name.endswith('h5'):  # config from data file
            with tb.open_file(file_name, 'r') as in_file_h5:
                try:
                    configuration = in_file_h5.root.configuration_out
                    self.log.info('Use chip configuration at configuration_out node')
                except tb.NoSuchNodeError:  # out config does not exist due to aborted run
                    try:
                        configuration = in_file_h5.root.configuration_in
                        self.log.info('Use chip configuration at configuration_in node')
                    except tb.NoSuchNodeError:  # out config does not exist due to aborted run
                        configuration = None
                if not configuration:
                    raise RuntimeError('No configuration found in ' + file_name)
                chip_conf = {}
                # settings = fill_dict_from_conf_table(configuration.chip.settings)
                # chip_conf['chip_type'] = settings['chip_type']
                # chip_conf['calibration'] = fill_dict_from_conf_table(configuration.chip.calibration)
                # chip_conf['trim'] = fill_dict_from_conf_table(configuration.chip.trim)
                chip_conf['registers'] = fill_dict_from_conf_table(configuration.chip.registers)
                chip_conf['use_pixel'] = configuration.chip.use_pixel[:]
                chip_conf['masks'] = {}
                for node in configuration.chip.masks:
                    chip_conf['masks'][node.name] = node[:]
        else:  # std config from yaml file
            with open(file_name) as conf_yaml:
                chip_conf = yaml.full_load(conf_yaml)
                # No pixel config in yaml
                chip_conf['masks'] = {}
                chip_conf['use_pixel'] = {}
        return chip_conf

    def _create_chip_container(self, scan_config, scan_config_per_chip):
        ''' Extract the chip and scan configurations from mulitple sources

            Set all configurations that do not require the init step
        '''
        # Load scan configuration from default arguments of _configure() and _scan() and overwrite with scan_config.
        args = inspect.getfullargspec(self._configure)
        scan_configuration = {key: args[3][i] for i, key in enumerate(args[0][1:])}
        args = inspect.getfullargspec(self._scan)
        scan_configuration.update({key: args[3][i] for i, key in enumerate(args[0][1:])})
        scan_configuration.update(scan_config)

        # Detect modules defined in testbench by the definition of a module serial number
        module_cfgs = self.get_module_cfgs()

        for mod_name, mod_cfg in module_cfgs.items():
            for k, v in mod_cfg.items():
                # Detect chips defined in testbench by the definition of a chip serial number
                if isinstance(v, collections.abc.Mapping) and 'chip_sn' in v:
                    output_dir = self.working_dir + os.sep + mod_name + os.sep + k
                    if not os.path.exists(output_dir):
                        os.makedirs(output_dir)
                    name = k  # chip name
                    # Create log file handler for the chip
                    chip_fh = self._create_logfile_handler(output_dir + os.sep + name)
                    self._log_handlers_per_scan.append(chip_fh)
                    # Create module config corresponding to this chip
                    module_settings = deepcopy(mod_cfg)
                    module_settings.pop(k)
                    module_settings['name'] = mod_name
                    # Set chip config file name
                    with self._logging_through_handlers():
                        chip_settings = v
                        if not chip_settings['chip_config_file']:  # take chip cfg from latest scan
                            chip_settings['chip_config_file'] = utils.get_latest_config_node_from_files(directory=output_dir)
                            if not chip_settings['chip_config_file']:  # fallback to yaml
                                chip_settings['chip_config_file'] = utils.get_latest_chip_configuration_file(directory=output_dir)
                            if not chip_settings['chip_config_file']:  # fallback to std. config
                                std_cfg = DEFAULT_CONFIG_FILE
                                self.log.warning("No explicit configuration supplied for chip {0}. Using '{1}'!".format(chip_settings['chip_sn'], std_cfg))
                                chip_settings['chip_config_file'] = std_cfg
                        self.log.info('Loading chip configuration for chip {0} from {1}'.format(chip_settings['chip_sn'], chip_settings['chip_config_file']))
                        chip_conf = self._parse_chip_cfg_file(chip_settings['chip_config_file'])
                    # Set scan and chip configuration
                    scan_config = deepcopy(scan_configuration)  # scan config from scan definition
                    # Update chip config from test bench
                    chip_conf_overwrites = {'registers': deepcopy(chip_settings.get('registers', {})),
                                            # 'trim': deepcopy(chip_settings.get('trim', {})),
                                            # 'calibration': deepcopy(chip_settings.get('calibration', {})),
                                            'masks': deepcopy(chip_settings.get('masks', {})),
                                            'disable_pixel': deepcopy(chip_settings.get('disable_pixel', {}))
                                            }
                    chip_conf = utils.recursive_update(chip_conf, chip_conf_overwrites)
                    # Update chip config from scan definition
                    chip_conf_overwrites = deepcopy(scan_configuration.get('chip', {}))
                    chip_conf = utils.recursive_update(chip_conf, chip_conf_overwrites)
                    if scan_config_per_chip:
                        chip_specific_scan_config = scan_config_per_chip.get(mod_name, {}).get(name, {})  # scan config for this chip
                        chip_conf = utils.recursive_update(chip_conf, chip_specific_scan_config.get('chip', {}))

                    output_filename = os.path.join(output_dir, self.run_name)

                    # Chek if file name exists already, can happen since file names are not guaranteed to be unique, issue # 445
                    i = 2
                    while os.path.isfile(output_filename + '.h5'):
                        output_filename = os.path.join(output_dir, self.run_name + '_%d' % i)  # append an index
                        i += 1

                    self.chips[mod_name + '_' + k] = ChipContainer(name=name, chip_settings=chip_settings, chip_conf=chip_conf, module_settings=module_settings,
                                                                   output_filename=output_filename, output_dir=output_dir, log_fh=chip_fh, scan_config=scan_config, suffix=self.suffix)
        with self._logging_through_handlers():
            self.log.info('Found %d chip(s) of %d module(s) defined in the testbench', len(self.chips), self.get_n_modules())

    def _write_config_h5(self, h5_file, node):
        ''' Write complete configuration to the provided node of a h5 file '''

        def write_dict_to_table(dictionary, node):
            for attr, val in dictionary.items():
                row = node.row
                row['attribute'] = attr
                try:
                    row['value'] = val
                except TypeError:  # value cannot be implicitly converted to string
                    row['value'] = str(val)
                row.append()
            node.flush()

        scan_node = h5_file.create_group(node, 'scan', 'Scan configuration')
        # Run configuration
        run_config_table = h5_file.create_table(scan_node, name='run_config', title='Run config', description=RunConfigTable)
        row = run_config_table.row
        row['attribute'] = 'scan_id'
        row['value'] = self.scan_id
        row.append()
        row = run_config_table.row
        row['attribute'] = 'run_name'
        row['value'] = self.run_name
        row.append()
        row = run_config_table.row
        row['attribute'] = 'software_version'
        row['value'] = utils.get_software_version()
        row.append()
        row = run_config_table.row
        row['attribute'] = 'module'
        row['value'] = self.module_settings['name']
        row.append()
        row = run_config_table.row
        row['attribute'] = 'chip_sn'
        row['value'] = self.chip.get_sn()
        row.append()
        row = run_config_table.row
        # row['attribute'] = 'chip_type'
        # row['value'] = self.chip.get_type()
        # row.append()
        row = run_config_table.row
        row['attribute'] = 'receiver'
        row['value'] = self.chip.receiver
        row.append()

        # Scan configuration as provided during scan __init__
        scan_cfg_table = h5_file.create_table(scan_node, name='scan_config', title='Scan configuration', description=RunConfigTable)
        write_dict_to_table(self.scan_config, scan_cfg_table)

        chip_node = h5_file.create_group(node, 'chip', 'Chip configuration')
        # Chip register table
        register_table = h5_file.create_table(chip_node, name='registers', title='Registers', description=RegisterTable)
        for name, reg in self.chip.registers.items():
            row = register_table.row
            row['register'] = name
            row['value'] = reg.get()
            row.append()
        register_table.flush()
        # # Chip calibration table
        # calibration_table = h5_file.create_table(chip_node, name='calibration', title='Calibration', description=RunConfigTable)
        # write_dict_to_table(self.chip.calibration.return_all_values(), calibration_table)
        # # Chip trim table
        # trim_table = h5_file.create_table(chip_node, name='trim', title='Trim values', description=RunConfigTable)
        # write_dict_to_table(self.chip.configuration['trim'], trim_table)

        # Chip settings table
        settings_table = h5_file.create_table(chip_node, name='settings', title='Chip settings from test bench', description=RunConfigTable)
        write_dict_to_table(self.chip_settings, settings_table)

        # Settings of the module where this chip belongs to
        module_settings_table = h5_file.create_table(chip_node, name='module', title='Module settings from test bench', description=RunConfigTable)
        write_dict_to_table(self.module_settings, module_settings_table)

        # Chip masks
        mask_node = h5_file.create_group(chip_node, 'masks', 'Pixel masks (configuration per pixel and virtual disable mask)')
        for name, value in self.chip.masks.items():
            h5_file.create_carray(mask_node, name=name, title=name.capitalize(), obj=value, filters=FILTER_RAW_DATA)

        # Virtual enable mask
        h5_file.create_carray(chip_node, name='use_pixel', title='Select pixels to be used in scans', obj=self.chip.masks.disable_mask, filters=FILTER_RAW_DATA)

        bench_node = h5_file.create_group(node, 'bench', 'Test bench settings')

        for setting, values in self.configuration['bench'].items():
            if setting in ['modules']:  # settings parsed into chip container and stored seperately
                continue
            table = h5_file.create_table(bench_node, name=setting, title=setting.capitalize(), description=RunConfigTable)
            write_dict_to_table(values, table)

    def _set_readout_status(self):
        self.readout_status = self.fifo_readout.print_readout_status()

    def _get_readout_status(self, receiver):
        discard_counts = self.readout_status
        discard_count = discard_counts[int(receiver[2])]
        return discard_count

    def _add_chip_status(self):
        '''
            Read all important chip values and dump to raw data file
        '''
        # self.h5_file.create_group(self.h5_file.root, 'chip_status', 'Chip status')

        # # Add periphery monitoring data if any
        # if self.periphery.enabled and self.configuration['bench']['periphery'].get('monitoring', False):
        #     monitoring_data = {}
        #     for group_name, group in self.periphery.monitoring_data.items():
        #         monitoring_data[group_name] = {}
        #         for table_name, table in group.items():
        #             t = table[:]
        #             for rid, row in enumerate(t):
        #                 if row['timestamp'] < time.mktime(time.strptime(self.timestamp, "%Y%m%d_%H%M%S")):
        #                     t = np.delete(t, rid, axis=0)

        #             monitoring_data[group_name][table_name] = t

        #     self.h5_file.create_group(self.h5_file.root.chip_status, name='periphery_monitoring', title='Periphery Monitoring')
        #     for grp in monitoring_data.keys():
        #         group = self.h5_file.create_group(self.h5_file.root.chip_status.periphery_monitoring, grp)
        #         for name, table in monitoring_data[grp].items():
        #             self.h5_file.create_table(group, name, table)

        # if self.chip_settings['record_chip_status'] and self.daq.board_version != 'SIMULATION':
        #     discard_count, soft_error_count, hard_error_count = self._get_readout_status(self.chip.receiver)
        #     aurora_table = self.h5_file.create_table(self.h5_file.root.chip_status, name='aurora_link', title='Aurora link status', description=RunConfigTable)
        #     row = aurora_table.row
        #     row['attribute'] = 'discard_counter'
        #     row['value'] = discard_count
        #     row.append()
        #     row['attribute'] = 'soft_error_counter'
        #     row['value'] = soft_error_count
        #     row.append()
        #     row['attribute'] = 'hard_error_counter'
        #     row['value'] = hard_error_count
        #     row.append()
        #     aurora_table.flush()

        #     self._set_receiver_enabled(receiver=self.chip.receiver, enabled=True)
        #     voltages, currents = self.chip.get_chip_status()
        #     temperature = self.chip.get_temperature(log=False)
        #     self._set_receiver_enabled(receiver=self.chip.receiver, enabled=False)

        #     dac_currents_table = self.h5_file.create_table(self.h5_file.root.chip_status, name='ADCCurrents', title='ADC Currents', description=ChipStatusTable)
        #     dac_voltages_table = self.h5_file.create_table(self.h5_file.root.chip_status, name='ADCVoltages', title='ADC Voltages', description=ChipStatusTable)

        #     for name, value in currents.items():
        #         row = dac_currents_table.row
        #         row['attribute'] = name
        #         row['ADC'] = value[0]
        #         row['value'] = value[1]
        #         row.append()
        #     dac_currents_table.flush()
        #     for name, value in voltages.items():
        #         row = dac_voltages_table.row
        #         row['attribute'] = name
        #         row['ADC'] = value[0]
        #         row['value'] = value[1]
        #         row.append()
        #     dac_voltages_table.flush()

        #     # Temperature measurements
        #     other_table = self.h5_file.create_table(self.h5_file.root.chip_status, name='other', title='Other', description=RunConfigTable)
        #     row = other_table.row
        #     row['attribute'] = 'Chip temperature'
        #     row['value'] = temperature
        #     row.append()
        #     other_table.flush()
        pass

    def _store_scan_par_values(self, h5_file):
        '''
            Create scan_params table after a scan
        '''
        # Create parameter description
        keys = set()  # find all keys to make the table column names
        for par_values in self.scan_parameters.values():
            keys.update(par_values.keys())
        fields = [('scan_param_id', np.uint32)]
        # FIXME only float32 supported so far
        fields.extend([(name, np.float32) for name in keys])

        scan_par_table = h5_file.create_table(h5_file.root.configuration_out.scan, name='scan_params', title='Scan parameter values per scan parameter id', description=np.dtype(fields))
        for par_id, par_values in self.scan_parameters.items():
            a = np.full(shape=(1,), fill_value=np.NaN).astype(np.dtype(fields))
            for key, val in par_values.items():
                a['scan_param_id'] = par_id
                a[key] = np.float32(val)
            scan_par_table.append(a)

    def _configure_masks(self):
        '''
            Masks configuring steps always needed after chip reset and before scan configure
        '''

        if self.chip_settings['use_good_pixels_diff']:
            self.chip.masks.apply_good_pixel_mask_diff()
        # if self.chip_settings['chip_type'].lower() == 'itkpixv1':
        #     if self.chip_settings.get('use_ptot', False):
        #         # Automatically enable hitbus if PToT mode is enabled
        #         self.chip.masks['hitbus'] = self.chip.masks['enable']

        self.chip.masks.update(force=True)  # write all masks to chip

    def _configure_fifo_readout(self):
        self.fifo_readout = FifoReadout(self.daq)
        self._first_read = False
        # for receiver in self.daq.receivers:
        #     if self.daq.board_version != 'SIMULATION':  # Causes a timing issue in simulation
        #         self.daq.rx_channels[receiver].reset_logic()  # TODO: was done before at readout start, maybe not needed here
        #     self.daq.rx_channels[receiver].reset_counters()

    def _set_receiver_enabled(self, receiver=None, enabled=True):
        if receiver is not None:
            self.daq.rx_channels[receiver].set_en(enabled)
        else:
            for rx_channel in self.daq.rx_channels.values():
                rx_channel.set_en(enabled)

    def _close_h5_file(self):
        # Must be closed if already opened, otherwise access to file handle is only
        # possible using tb.file._open_files.close_all() (--> memory leak + file cannot be closed anymore)
        try:
            self.h5_file.close()
        except tb.exceptions.ClosedFileError:  # if scan was called the file is already closed
            pass
        # Reopen interpreted file to append final config after analysis
        if not self.errors_occured:
            with tb.open_file(self.output_filename + '_interpreted.h5', 'a') as h5_file:
                node = h5_file.create_group(h5_file.root, 'configuration_out', 'Configuration after scan analysis')
                self._write_config_h5(h5_file, node)
                self._store_scan_par_values(h5_file)

    def _on_exception(self):
        ''' Called when exception occurs in main process '''
        self.errors_occured = traceback.format_exc()
        self.close()

    def _create_logfile_handler(self, output_filename):
        return logger.setup_logfile(output_filename + '.log')

    def _open_logfile(self, handler):
        logger.add_logfile_to_loggers(handler)

    def _close_logfile(self, handler):
        logger.close_logfile(handler)

    def _close_logfiles(self):
        for handler in self._log_handlers_per_scan:
            self._close_logfile(handler)

    def _close_sockets(self):
        if self.context:
            for _ in self.iterate_chips():
                try:
                    if self.socket:
                        self.log.debug('Closing socket connection')
                        self.socket.close()
                        self.socket = None
                except AttributeError:
                    pass
            self.context.term()
            self.context = None

    @contextmanager
    def _logging_through_handler(self, handler):
        self._open_logfile(handler)
        try:
            yield
        finally:
            self._close_logfile(handler)

    @contextmanager
    def _logging_through_handlers(self):
        for handler in self._log_handlers_per_scan:
            self._open_logfile(handler)
        try:
            yield
        finally:
            for handler in self._log_handlers_per_scan:
                self._close_logfile(handler)

    # Readout methods
    @contextmanager
    def readout(self, scan_param_id=0, timeout=10.0, **kwargs):

        self.scan_param_id = scan_param_id

        callback = kwargs.pop('callback', self.handle_data)
        errback = kwargs.pop('errback', self.handle_err)
        fill_buffer = kwargs.pop('fill_buffer', False)
        clear_buffer = kwargs.pop('clear_buffer', False)

        if kwargs:
            self.store_scan_par_values(scan_param_id, **kwargs)

        self.start_readout(callback=callback, clear_buffer=clear_buffer, fill_buffer=fill_buffer, errback=errback, **kwargs)
        try:
            yield
        finally:
            if self.daq.board_version == 'SIMULATION':
                for _ in range(100):
                    self.daq.rx_channels[self.chip.receiver].is_done()
            self.stop_readout(timeout=timeout)

    def start_readout(self, **kwargs):
        # Pop parameters for fifo_readout.start
        callback = kwargs.pop('callback', self.handle_data)
        clear_buffer = kwargs.pop('clear_buffer', False)
        fill_buffer = kwargs.pop('fill_buffer', False)
        reset_sram_fifo = kwargs.pop('reset_sram_fifo', True)
        errback = kwargs.pop('errback', self.handle_err)
        no_data_timeout = kwargs.pop('no_data_timeout', None)

        self.fifo_readout.start(reset_sram_fifo=reset_sram_fifo, fill_buffer=fill_buffer, clear_buffer=clear_buffer,
                                callback=callback, errback=errback, no_data_timeout=no_data_timeout)

    def stop_readout(self, timeout=10.0):
        self.fifo_readout.stop(timeout=timeout)

    def handle_data(self, data_tuple):
        '''
            Handling of the data.
        '''
        total_words = self.raw_data_earray.nrows

        self.raw_data_earray.append(data_tuple[0])
        self.raw_data_earray.flush()

        len_raw_data = data_tuple[0].shape[0]
        self.meta_data_table.row['timestamp_start'] = data_tuple[1]
        self.meta_data_table.row['timestamp_stop'] = data_tuple[2]
        self.meta_data_table.row['error'] = data_tuple[3]
        self.meta_data_table.row['data_length'] = len_raw_data
        self.meta_data_table.row['index_start'] = total_words
        total_words += len_raw_data
        self.meta_data_table.row['index_stop'] = total_words
        self.meta_data_table.row['scan_param_id'] = self.scan_param_id

        self.meta_data_table.row.append()
        self.meta_data_table.flush()

        if self.socket:
            send_data(self.socket, data=data_tuple, scan_param_id=self.scan_param_id)

    def handle_err(self, exc):
        ''' Handle errors when readout is started '''
        msg = '%s' % exc[1]
        if msg:
            self.log.error('%s', msg)
        if self.configuration['bench']['general'].get('abort_on_rx_error', True):
            if issubclass(exc[0], fifo_readout.FifoError):
                self.log.error('Aborting run...')
                self.fifo_readout.stop_readout.set()


if __name__ == '__main__':
    pass
