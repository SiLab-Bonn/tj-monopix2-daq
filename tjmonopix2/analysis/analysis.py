#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os

import numba
import numpy as np
import tables as tb
from pixel_clusterizer.clusterizer import HitClusterizer
from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis.interpreter import RawDataInterpreter
from tjmonopix2.system import logger
from tqdm import tqdm


class Analysis(object):
    def __init__(self, raw_data_file=None, analyzed_data_file=None,
                 store_hits=True, cluster_hits=False, analyze_tdc=False, use_tdc_trigger_dist=False,
                 build_events=False, chunk_size=1000000, **_):
        self.log = logger.setup_derived_logger('Analysis')

        self.raw_data_file = raw_data_file
        self.analyzed_data_file = analyzed_data_file
        self.store_hits = store_hits
        self.cluster_hits = cluster_hits
        self.chunk_size = chunk_size
        self.analyze_tdc = analyze_tdc
        self.use_tdc_trigger_dist = use_tdc_trigger_dist

        if not os.path.isfile(raw_data_file):
            raise IOError('Raw data file %s does not exist.', raw_data_file)

        if not self.analyzed_data_file:
            self.analyzed_data_file = raw_data_file[:-3] + '_interpreted.h5'

        self.last_chunk = False

        self._get_configs()

        self.columns, self.rows = 512, 512

        self.threshold_map = np.ones(shape=(self.columns, self.rows)) * -1
        self.noise_map = np.ones_like(self.threshold_map) * -1
        self.chi2_map = np.zeros_like(self.threshold_map) * -1

        # Setup clusterizer
        self._setup_clusterizer()


    def _get_configs(self):
        ''' Load run config to allow analysis routines to access these info '''
        with tb.open_file(self.raw_data_file, 'r') as in_file:
            self.run_config = au.ConfigDict(in_file.root.configuration_in.scan.run_config[:])
            self.scan_config = au.ConfigDict(in_file.root.configuration_in.scan.scan_config[:])
            self.chip_settings = au.ConfigDict(in_file.root.configuration_in.chip.settings[:])
            self.tlu_config = au.ConfigDict(in_file.root.configuration_in.bench.TLU[:])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is not None:
            self.log.exception('Exception during analysis', exc_info=(exc_type, exc_value, traceback))

    def get_scan_param_values(self, scan_param_index=None, scan_parameter=None):
        ''' Return the scan parameter value(s)

            scan_param_index: slicing notation of the scan parameter indeces
            scan_parameter: string
                Name of the scan parameter. If not defined all are returned.
        '''
        with tb.open_file(self.raw_data_file, 'r') as in_file:
            scan_param_table = in_file.root.configuration_out.scan.scan_params[:]
            if scan_param_index:
                scan_param_table = scan_param_table[scan_param_index]
            if scan_parameter:
                scan_param_table = scan_param_table[:][scan_parameter]
        return scan_param_table

    def _range_of_parameter(self, meta_data):
        ''' Calculate the raw data word indeces of each scan parameter id
        '''
        index = np.append(np.array([0]), (np.where(np.diff(meta_data['scan_param_id']) != 0)[0] + 1))

        expected_values = np.arange(np.max(meta_data['scan_param_id']) + 1)

        # Check for scan parameter IDs with no data
        sel = np.isin(expected_values, meta_data['scan_param_id'])
        if not np.all(sel):
            self.log.warning('No words for scan parameter IDs: %s', str(expected_values[~sel]))

        start = meta_data[index]['index_start']
        stop = np.append(start[:-1] + np.diff(start), meta_data[-1]['index_stop'])

        return np.column_stack((meta_data['scan_param_id'][index], start, stop))

    def _words_of_parameter(self, par_range, data):
        ''' Yield all raw data words of a scan parameter

            Do not exceed chunk_size. Use a global offset
            parameter.
        '''

        for scan_par_id, start, stop in par_range:
            for i in range(start, stop, self.chunk_size):
                # Shift chunk index to not split events. The offset is determined from previous analyzed chunk.
                # Restrict maximum offset, can happen for readouts without a single event, issue #171
                chunk_offset = max(self.chunk_offset, -self.chunk_size)
                start_chunk = i + chunk_offset

                # Limit maximum read words by chunk size
                stop_limited = min(i + self.chunk_size, stop)
                yield scan_par_id, data[start_chunk:stop_limited]

        # Remaining data of last chunk
        self.last_chunk = True  # Set flag for special treatment
        if self.chunk_offset == 0:
            return
        yield scan_par_id, data[stop + self.chunk_offset:stop]

    def _create_table(self, out_file, name, title, dtype):
        ''' Create hit table node for storage in out_file.
            Copy configuration nodes from raw data file.
        '''
        table = out_file.create_table(out_file.root, name=name,
                                        description=dtype,
                                        title=title,
                                        expectedrows=self.chunk_size,
                                        filters=tb.Filters(complib='blosc',
                                                            complevel=5,
                                                            fletcher32=False))

        return table

    def _setup_clusterizer(self):
        ''' Define data structure and settings for hit clusterizer package '''
        # Define all field names and data types
        hit_fields = {'event_number': 'event_number',
                      'trigger_number': 'trigger_number',
                      'frame': 'frame',
                      'column': 'column',
                      'row': 'row',
                      'charge': 'charge',
                      'timestamp': 'timestamp'
                      }
        hit_description = [('event_number', 'u4'),
                           ('trigger_number', 'u4'),
                           ('frame', 'u1'),
                           ('column', 'u2'),
                           ('row', 'u2'),
                           ('charge', 'u1'),
                           ('timestamp', 'i8')]
        cluster_fields = {'event_number': 'event_number',
                          'column': 'column',
                          'row': 'row',
                          'size': 'n_hits',
                          'id': 'ID',
                          'tot': 'charge',
                          'scan_param_id': 'scan_param_id',
                          'seed_col': 'seed_column',
                          'seed_row': 'seed_row',
                          'mean_col': 'mean_column',
                          'mean_row': 'mean_row'}
        cluster_description = [('event_number', 'u4'),
                               ('id', '<u2'),
                               ('size', '<u2'),
                               ('tot', '<u2'),
                               ('seed_col', '<u2'),
                               ('seed_row', '<u2'),
                               ('mean_col', '<f4'),
                               ('mean_row', '<f4'),
                               ('dist_col', '<u4'),
                               ('dist_row', '<u4'),
                               ('cluster_shape', '<i8'),
                               ('scan_param_id', 'u4')]

        hit_dtype = np.dtype(hit_description)
        self.cluster_dtype = np.dtype(cluster_description)

        hit_dtype = np.dtype(hit_description)
        self.cluster_dtype = np.dtype(cluster_description)

        if self.cluster_hits:  # Allow analysis without clusterizer installed
            # Define end of cluster function to calculate cluster shape
            # and cluster distance in column and row direction
            @numba.njit
            def _end_of_cluster_function(hits, clusters, cluster_size,
                                         cluster_hit_indices, cluster_index,
                                         cluster_id, charge_correction,
                                         noisy_pixels, disabled_pixels,
                                         seed_hit_index):
                hit_arr = np.zeros((15, 15), dtype=np.bool_)
                center_col = hits[cluster_hit_indices[0]].column
                center_row = hits[cluster_hit_indices[0]].row
                hit_arr[7, 7] = 1
                min_col = hits[cluster_hit_indices[0]].column
                max_col = hits[cluster_hit_indices[0]].column
                min_row = hits[cluster_hit_indices[0]].row
                max_row = hits[cluster_hit_indices[0]].row
                for i in cluster_hit_indices[1:]:
                    if i < 0:  # Not used indeces = -1
                        break
                    diff_col = np.int32(hits[i].column - center_col)
                    diff_row = np.int32(hits[i].row - center_row)
                    if np.abs(diff_col) < 8 and np.abs(diff_row) < 8:
                        hit_arr[7 + hits[i].column - center_col,
                                7 + hits[i].row - center_row] = 1
                    if hits[i].column < min_col:
                        min_col = hits[i].column
                    if hits[i].column > max_col:
                        max_col = hits[i].column
                    if hits[i].row < min_row:
                        min_row = hits[i].row
                    if hits[i].row > max_row:
                        max_row = hits[i].row

                if max_col - min_col < 8 and max_row - min_row < 8:
                    # Make 8x8 array
                    col_base = 7 + min_col - center_col
                    row_base = 7 + min_row - center_row
                    cluster_arr = hit_arr[col_base:col_base + 8,
                                          row_base:row_base + 8]
                    # Finally calculate cluster shape
                    # uint64 desired, but numexpr and others limited to int64
                    if cluster_arr[7, 7] == 1:
                        cluster_shape = np.int64(-1)
                    else:
                        cluster_shape = np.int64(
                            au.calc_cluster_shape(cluster_arr))
                else:
                    # Cluster is exceeding 8x8 array
                    cluster_shape = np.int64(-1)

                clusters[cluster_index].cluster_shape = cluster_shape
                clusters[cluster_index].dist_col = max_col - min_col + 1
                clusters[cluster_index].dist_row = max_row - min_row + 1

            def end_of_cluster_function(hits, clusters, cluster_size,
                                        cluster_hit_indices, cluster_index,
                                        cluster_id, charge_correction,
                                        noisy_pixels, disabled_pixels,
                                        seed_hit_index):
                _end_of_cluster_function(hits, clusters, cluster_size,
                                         cluster_hit_indices, cluster_index,
                                         cluster_id, charge_correction,
                                         noisy_pixels, disabled_pixels,
                                         seed_hit_index)

            # Initialize clusterizer with custom hit/cluster fields
            self.clz = HitClusterizer(
                hit_fields=hit_fields,
                hit_dtype=hit_dtype,
                cluster_fields=cluster_fields,
                cluster_dtype=self.cluster_dtype,
                min_hit_charge=1,
                max_hit_charge=128,
                column_cluster_distance=5,
                row_cluster_distance=5,
                frame_cluster_distance=1,
                ignore_same_hits=True)

            # Set end_of_cluster function for shape and distance calculation
            self.clz.set_end_of_cluster_function(end_of_cluster_function)

    def analyze_data(self):
        self.log.info('Analyzing data...')
        self.chunk_offset = 0
        with tb.open_file(self.raw_data_file) as in_file:
            n_words = in_file.root.raw_data.shape[0]
            meta_data = in_file.root.meta_data[:]

            if meta_data.shape[0] == 0:
                self.log.warning('Data is empty. Skip analysis!')
                return

            n_scan_params = np.max(meta_data['scan_param_id']) + 1

            par_range = self._range_of_parameter(meta_data)

            with tb.open_file(self.analyzed_data_file, 'w', title=in_file.title) as out_file:
                out_file.create_group(out_file.root, name='configuration_in', title='Configuration after scan step')
                out_file.copy_children(in_file.root.configuration_out, out_file.root.configuration_in, recursive=True)

                if self.store_hits:
                    hit_table = self._create_table(out_file, name='Dut', title='hit_data', dtype=au.hit_dtype)
                if self.cluster_hits:
                    cluster_table = out_file.create_table(
                        out_file.root, name='Cluster',
                        description=self.cluster_dtype,
                        title='Cluster',
                        filters=tb.Filters(complib='blosc',
                                           complevel=5,
                                           fletcher32=False))
                    hist_cs_size = np.zeros(shape=(100, ), dtype=np.uint32)
                    hist_cs_tot = np.zeros(shape=(100, ), dtype=np.uint32)
                    hist_cs_shape = np.zeros(shape=(300, ), dtype=np.int32)


                interpreter = RawDataInterpreter(n_scan_params=n_scan_params, trigger_data_format=self.tlu_config['DATA_FORMAT'])
                self.last_chunk = False
                pbar = tqdm(total=n_words, unit=' Words', unit_scale=True)
                upd = 0
                for scan_param_id, words in self._words_of_parameter(par_range, in_file.root.raw_data):
                    hit_buffer = np.zeros(shape=4 * self.chunk_size, dtype=au.hit_dtype)

                    hit_dat = interpreter.interpret(
                        words,
                        hit_buffer,
                        scan_param_id
                    )
                    upd = words.shape[0]

                    if self.store_hits:
                        hit_table.append(hit_dat)
                        hit_table.flush()
                    pbar.update(upd)
                pbar.close()

                hist_occ, hist_tot, hist_tdc = interpreter.get_histograms()

        self._create_additional_hit_data(hist_occ, hist_tot)

    def _create_additional_hit_data(self, hist_occ, hist_tot):
        with tb.open_file(self.analyzed_data_file, 'r+') as out_file:
            scan_id = self.run_config['scan_id']

            out_file.create_carray(out_file.root,
                                   name='HistOcc',
                                   title='Occupancy Histogram',
                                   obj=hist_occ,
                                   filters=tb.Filters(complib='blosc',
                                                      complevel=5,
                                                      fletcher32=False))
            out_file.create_carray(out_file.root,
                                   name='HistTot',
                                   title='ToT Histogram',
                                   obj=hist_tot,
                                   filters=tb.Filters(complib='blosc',
                                                      complevel=5,
                                                      fletcher32=False))

            # if self.analyze_tdc:  # Only store if TDC analysis is used.
            #     out_file.create_carray(out_file.root,
            #                            name='HistTdcStatus',
            #                            title='Tdc status Histogram',
            #                            obj=hist_tdc_status,
            #                            filters=tb.Filters(complib='blosc',
            #                                               complevel=5,
            #                                               fletcher32=False))

            if scan_id in ['threshold_scan']:
                n_injections = self.scan_config['n_injections']
                hist_scurve = hist_occ.reshape((self.rows * self.columns, -1))

                if scan_id in ['threshold_scan']:
                    scan_params = [self.scan_config['VCAL_HIGH'] - v for v in range(self.scan_config['VCAL_LOW_start'],
                                                                                    self.scan_config['VCAL_LOW_stop'], self.scan_config['VCAL_LOW_step'])]
                    self.threshold_map, self.noise_map, self.chi2_map = au.fit_scurves_multithread(hist_scurve, scan_params, n_injections, optimize_fit_range=False)
                elif scan_id == 'autorange_threshold_scan':
                    scan_params = self.get_scan_param_values(scan_parameter='vcal_high') - self.get_scan_param_values(scan_parameter='vcal_med')
                    self.threshold_map, self.noise_map, self.chi2_map = au.fit_scurves_multithread(hist_scurve, scan_params, n_injections, optimize_fit_range=False)

                out_file.create_carray(out_file.root, name='ThresholdMap', title='Threshold Map', obj=self.threshold_map,
                                       filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_file.create_carray(out_file.root, name='NoiseMap', title='Noise Map', obj=self.noise_map,
                                       filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
                out_file.create_carray(out_file.root, name='Chi2Map', title='Chi2 / ndf Map', obj=self.chi2_map,
                                       filters=tb.Filters(complib='blosc', complevel=5, fletcher32=False))
