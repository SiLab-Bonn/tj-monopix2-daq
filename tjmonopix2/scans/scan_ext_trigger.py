#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    External trigger scan with RD53A.

    For use with TLU (use RJ45) or RD53A HitOR (BDAQ self-trigger). For BDAQ self-trigger mode is also provided an extra scan script (source_scan.py)

    Note:
    Make sure that `TLU_TRIGGER_MAX_CLOCK_CYCLES` in bdaq_core.v is set correctly, number of bits used for TLU word
    should correspond to `TLU_TRIGGER_MAX_CLOCK_CYCLES - 1`.

    Note:
    When you read out more than one chip, the TLU veto length parameter has to be adjusted to higher values.
    Increasing the veto length limits the maximal trigger rate, so use less chips on the same board for high trigger rates.
    Recommended values for the veto length are:
    +––––––––––––––––––––––––––+–––––––––––––––––––+
    | # of chips | veto_length | max. trigger rate |
    |––––––––––––+–––––––––––––+–––––––––––––––––––|
    | 1          | 500         | ~80kHz            |
    | 2          | 1000        | ~40kHz            |
    | 3          | 1500        | ~25kHz            |
    | 4          | 2500        | ~14kHz            |
    +––––––––––––––––––––––––––+–––––––––––––––––––+
    If the analysis indicates errors (such as ext. trigger errors), try to slightly increase the veto length (if the trigger rate allows it).
    Also note that the recommended veto length can be slightly reduced when a higher trigger rate is needed,
    if reducing the veto length does not cause (increased number of) errors.
'''

import time
import numpy as np
import threading

from tqdm import tqdm

from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.analysis import analysis
from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis import online as oa
#from tjmonopix2.analysis import plotting


scan_configuration = {
    'start_column': 0,
    'stop_column': 400,
    'start_row': 0,
    'stop_row': 192,

    # Stop conditions (choose one)
    'scan_timeout': False,             # Timeout for scan after which the scan will be stopped, in seconds; if False no limit on scan time
    'max_triggers': False,          # Number of maximum received triggers after stopping readout, if False no limit on received trigger
    'min_spec_occupancy': False,    # Minimum hits for each pixel above which the scan will be stopped; only a fraction of all pixels needs to reach this limit (see below)

    # For stop condition 'min_spec_occupancy' only
    'fraction': 0.99,   # Fraction of enabled pixels that need to reach the minimum occupancy (no hits in dead/disconnected pixels!)

    'trigger_latency': 100,     # Latency of trigger in units of 25 ns (BCs)
    'trigger_delay': 57,        # Trigger delay in units of 25 ns (BCs)
    'trigger_length': 32,       # Length of trigger command (amount of consecutive BCs are read out)
    'veto_length': 500,         # Length of TLU veto in units of 25 ns (BCs). This vetos new triggers while not all data is revieved. Increase by factor of number of connected chips/hitors. Should also be adjusted for longer trigger length.
    'use_tdc': False,           # Enable TDC modules
    # Trigger configuration
    'bench': {'TLU': {
        'TRIGGER_MODE': 3,      # Selecting trigger mode: Use trigger inputs/trigger select (0), TLU no handshake (1), TLU simple handshake (2), TLU data handshake (3)
        'TRIGGER_SELECT': 0     # HitOR [DP_ML_5 and mDP] (3), HitOR [mDP only] (2), HitOR [DP_ML_5 only] (1), disabled (0)
    }
    }
}


class ExtTriggerScan(ScanBase):
    scan_id = 'ext_trigger_scan'

    is_parallel_scan = True     # Parallel readout of ExtTrigger-type scans

    stop_scan = threading.Event()

    def _configure(self, scan_timeout=10, max_triggers=False, min_spec_occupancy=False, trigger_length=32, trigger_delay=57, veto_length=500, use_tdc=False, trigger_latency=100, start_column=0, stop_column=400, start_row=0, stop_row=192, **_):
        '''
        Parameters
        ----------
        max_triggers : int / False
            Maximum amount of triggers to record. Set to False for no limit.
        trigger_length : int
            Amount of BCIDs to read out on every trigger.
        trigger_delay : int
            Delay the trigger command by this amount in units of 25ns.
        veto_length : int
            Length of TLU veto in units of 25ns.
        trigger_latency : int
            Latency of trigger in units of 25ns.
        start_column : int [0:400]
            First column to scan
        stop_column : int [0:400]
            Column to stop the scan. This column is excluded from the scan.
        start_row : int [0:192]
            First row to scan
        stop_row : int [0:192]
            Row to stop the scan. This row is excluded from the scan.
        '''
        if (scan_timeout and max_triggers) or (scan_timeout and min_spec_occupancy) or (max_triggers and min_spec_occupancy):
            self.log.warning('You should only use one of the stop conditions at a time.')

        self.daq.configure_tlu_module(max_triggers=max_triggers)                                           # Configure tlu module using trigger configuration

        # in use in original, might be needed...
        #self.daq.configure_trigger_cmd_pulse(trigger_length=trigger_length, trigger_delay=trigger_delay)   # Configure trigger command pulse
        self.daq.configure_tlu_veto_pulse(veto_length=veto_length)                                         # Configure veto pulse

        #self.old_trigger_latency = self.chip.get_trigger_latency()
        #self.chip.write_trigger_latency(trigger_latency)

        self.data.n_trigger = 0                                                                             # Count trigger words in rawdata stream

        self.chip.masks['enable'][start_column:stop_column, start_row:stop_row] = True
        self.chip.masks['injection'][:] = False
        self.chip.masks.apply_disable_mask()
        if use_tdc:
            # Configure all four TDC modules
            self.daq.configure_tdc_modules()
            # Enable Hitor
            self.chip.masks['hitbus'][:] = self.chip.masks['enable'][:]
#         self.chip.masks.load_logo_mask(masks=['enable'])
        self.chip.masks.update(force=True)

        self.n_trigger = 0      # Init total trigger number already here to prevent misleading, additional error when scan crashes

        self.min_spec_occupancy = min_spec_occupancy
        if min_spec_occupancy:
            self.data.hist_occ = oa.OccupancyHistogramming(chip_type=self.chip.chip_type.lower(), rx_id=int(self.chip.receiver[-1]))
            self.data.occupancy = np.zeros(shape=self.chip.masks['enable'].shape)
            self.data.enabled_pixels = np.logical_and(self.chip.masks['enable'], self.chip.masks.disable_mask)

    def _scan(self, start_column=0, stop_column=400, scan_timeout=10, max_triggers=False, min_spec_occupancy=False, fraction=0.99, use_tdc=False, **_):
        '''
        ExtTriggerScan scan main loop

        Parameters
        ----------
        scan_timeout : int / False
            Number of seconds to records triggers. Set to False for no limit.
        max_triggers : int / False
            Maximum amount of triggers to record. Set to False for no limit.
        '''

        def timed_out():
            if scan_timeout:
                current_time = time.time()
                if current_time - start_time > scan_timeout:
                    self.log.info('Scan timeout was reached')
                    return True
            return False

        if use_tdc:
            self.enable_hitor(True)
            self.daq.enable_tdc_modules()

        # Configure and start AZ prodecure if SYNC FE is activated. Since only one CMD buffer
        # is available, this has to be done after the configure step. Otherwise AZ command will
        # be overwritten.
        if any(x in range(0, 128) for x in range(start_column, stop_column)) and self.chip.chip_type.lower() == 'rd53a':
            self.log.info('SYNC enabled: Enabling auto-zeroing')
            self.daq['tlu']['TRIGGER_VETO_SELECT'] = 2  # Veto trigger during AZ procedure
            az_cmd = self.chip._az_setup(delay=80, repeat=0, width=6, synch=6)  # Configure AZ procedure
            self.chip._az_start()  # Start AZ procedure

        # Sanity check: Check if AZ CMD is loaded into CMD, otherwise SYNC FE will get stuck
        if any(x in range(0, 128) for x in range(start_column, stop_column)) and self.chip.chip_type.lower() == 'rd53a':
            cmd_data = self.daq['cmd'].get_data()[:len(az_cmd)].tolist()
            if cmd_data != az_cmd:
                self.log.warning('AZ CMD is not properly loaded into CMD!')

        if scan_timeout:
            self.pbar = tqdm(total=scan_timeout, unit='')  # [s]
        elif max_triggers:
            self.pbar = tqdm(total=max_triggers, unit=' Triggers')
        elif min_spec_occupancy:
            self.pbar = tqdm(total=100, unit=' % Hits')
        else:  # EUDAQ scan
            self.pbar = tqdm(total=scan_timeout, unit='')  # [s]

        with self.readout():
            self.stop_scan.clear()

            self.daq.enable_ext_trigger()  # Enable external trigger
            self.daq.enable_tlu_module()   # Enable TLU module

            start_time = time.time()

            # Scan loop
            while not (self.stop_scan.is_set() or timed_out()):
                try:
                    triggers = self.daq.get_trigger_counter()

                    # Read tlu error counters
                    trig_low_timeout_errors, trig_accept_errors = self.daq.get_tlu_erros()
                    if trig_low_timeout_errors != 0 or trig_accept_errors != 0:
                        self.log.warning('TLU errors detected! TRIGGER_LOW_TIMEOUT_ERROR_COUNTER: {0}, TLU_TRIGGER_ACCEPT_ERROR_COUNTER: {1}'.format(trig_low_timeout_errors, trig_accept_errors))

                    time.sleep(1)
                    # Update progress bar
                    if scan_timeout:
                        self.pbar.n = int(time.time() - start_time)
                    elif max_triggers:
                        self.pbar.n = triggers
                    self.pbar.refresh()

                    # Stop scan if fraction of pixels reached minimum hits per pixel
                    #if min_spec_occupancy and np.count_nonzero(self.data.occupancy >= min_spec_occupancy) >= fraction * num_enabled_pixels:
                        #self.stop_scan.set()
                        #self.log.info('Reached required minimal number of hits per pixel ({0})'.format(min_spec_occupancy))

                    # Stop scan if reached trigger limit
                    if max_triggers and triggers >= max_triggers:
                        self.stop_scan.set()
                        self.log.info('Trigger limit was reached: {0}'.format(max_triggers))

                except KeyboardInterrupt:  # React on keyboard interupt
                    self.stop_scan.set()
                    self.log.info('Scan was stopped due to keyboard interrupt')

        self.pbar.close()

        # if self.chip.chip_type.lower() == 'rd53a':
            #self.chip._az_stop()

        self.daq.disable_tlu_module()      # disable TLU module
        self.daq.disable_ext_trigger()     # disable external trigger
        if use_tdc:
            self.enable_hitor(False)
            self.daq.disable_tdc_modules()

        if min_spec_occupancy:              # close online analysis for each chip
            for self.data in self._scan_data_containers:
                self.data.hist_occ.close()

        self.n_trigger = self.data.n_trigger    # Print number of triggers in ScanBase

        # Reset latency
        #self.chip.write_trigger_latency(self.old_trigger_latency)

        self.log.success('Scan finished')

    def _analyze(self):
        self.configuration['bench']['analysis']['cluster_hits'] = True
        self.configuration['bench']['analysis']['store_hits'] = True
        self.configuration['bench']['analysis']['analyze_tdc'] = self.configuration['scan'].get('use_tdc', False)
        self.configuration['bench']['analysis']['use_tdc_trigger_dist'] = self.configuration['scan'].get('use_tdc', False)
        self.configuration['bench']['analysis']['align_method'] = 2
        with analysis.Analysis(raw_data_file=self.output_filename + '.h5', **self.configuration['bench']['analysis']) as a:
            a.analyze_data()

        #if self.configuration['bench']['analysis']['create_pdf']:
            #with plotting.Plotting(analyzed_data_file=a.analyzed_data_file) as p:
                #p.create_standard_plots()

    def handle_data(self, data_tuple, receiver=None):
        ''' Check recorded trigger number '''
        super(ExtTriggerScan, self).handle_data(data_tuple)

        raw_data = data_tuple[0]

        print('ext trigger handling')
        print(raw_data)

        if self.min_spec_occupancy:
            self.data.hist_occ.add(raw_data)

        sel = np.bitwise_and(raw_data, au.TRIGGER_HEADER) > 0
        trigger_words = raw_data[sel]
        trigger_number = np.bitwise_and(trigger_words, au.TRG_MASK)
        trigger_inc = np.diff(trigger_number)
        trigger_issues = np.logical_and(trigger_inc != 1, trigger_inc != -2**31)

        self.data.n_trigger += trigger_number.shape[0]

        if np.any(trigger_issues):
            self.log.warning('Trigger numbers not strictly increasing')
            if np.count_nonzero(trigger_issues > 0) <= 10:
                self.log.warning('Trigger delta(s): {0}'.format(str(trigger_inc[trigger_issues > 0])))
            else:
                self.log.warning('More than 10 trigger numbers not strictly increasing in this readout!')


if __name__ == '__main__':
    with ExtTriggerScan(scan_config=scan_configuration) as scan:
        try:
            scan.configure()
            scan.scan()
            scan.notify('BDAQ53 external trigger scan has finished!')
            scan.analyze()
        except Exception as e:
            scan.log.error(e)
            scan.notify('ERROR: BDAQ53 external trigger scan has failed!')
