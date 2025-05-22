#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import copy
import shutil
import math
import tables as tb
import matplotlib
import numpy as np
import matplotlib.pyplot as plt
import datetime

from collections import OrderedDict
from scipy.optimize import curve_fit
from matplotlib.figure import Figure
from matplotlib.artist import setp
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from mpl_toolkits.axes_grid1 import make_axes_locatable
from matplotlib import colors, cm
from matplotlib.backends.backend_pdf import PdfPages

from tjmonopix2.system import logger
from tjmonopix2.analysis import analysis_utils as au

TITLE_COLOR = '#07529a'
OVERTEXT_COLOR = '#07529a'

SCURVE_CHI2_UPPER_LIMIT = 50

DACS = {'TJMONOPIX2': ['IBIAS', 'ITHR',
                       'ICASN', 'IDB',
                       'ITUNE', 'ICOMP',
                       'IDEL', 'IRAM',
                       'VRESET', 'VCASP',
                       'VCASC', 'VCLIP', ]
        }


class Plotting(object):
    def __init__(self, analyzed_data_file, pdf_file=None, level='preliminary', mask_noisy_pixels=False, internal=False, save_single_pdf=False, save_png=False):
        self.log = logger.setup_derived_logger('Plotting')

        self.plot_cnt = 0
        self.save_single_pdf = save_single_pdf
        self.save_png = save_png
        self.level = level
        self.mask_noisy_pixels = mask_noisy_pixels
        self.internal = internal
        self.clustered = False
        self.skip_plotting = False
        self.cb_side = False
        self._module_type = None

        if pdf_file is None:
            self.filename = '.'.join(
                analyzed_data_file.split('.')[:-1]) + '.pdf'
        else:
            self.filename = pdf_file
        self.out_file = PdfPages(self.filename)

        try:
            if isinstance(analyzed_data_file, str):
                in_file = tb.open_file(analyzed_data_file, 'r')
                root = in_file.root
            else:
                root = analyzed_data_file
        except IOError:
            self.log.warning('Interpreted data file does not exist!')
            self.skip_plotting = True
            return

        self.scan_config = au.ConfigDict(root.configuration_in.scan.scan_config[:])
        self.run_config = au.ConfigDict(root.configuration_in.scan.run_config[:])
        self.chip_settings = au.ConfigDict(root.configuration_in.chip.settings[:])
        self.cols = 512
        self.rows = 512
        self.num_pix = self.rows * self.cols
        self.plot_box_bounds = [0.5, self.cols + 0.5, self.rows + 0.5, 0.5]
        try:
            self.scan_params = root.configuration_in.scan.scan_params[:]
        except tb.NoSuchNodeError:
            self.scan_params = None

        self.registers = au.ConfigDict(root.configuration_in.chip.registers[:])

        if self.run_config['scan_id']:  # TODO: define 'usual' scans
            self.enable_mask = self._mask_disabled_pixels(root.configuration_in.chip.use_pixel[:], self.scan_config)
            self.n_enabled_pixels = len(self.enable_mask[~self.enable_mask])
            self.tdac_mask = root.configuration_in.chip.masks.tdac[:]

        # self.calibration = {e[0].decode('utf-8'): float(e[1].decode('utf-8')) for e in root.configuration_in.chip.calibration[:]}

        if 'VCAL_LOW' in self.scan_params.dtype.names:
            self.scan_parameter_range = np.array(self.scan_params['VCAL_HIGH'] - self.scan_params['VCAL_LOW'], dtype=float)
        elif 'VCAL_LOW_start' in self.scan_config:
            self.scan_parameter_range = [self.scan_config['VCAL_HIGH'] - v for v in
                                         range(self.scan_config['VCAL_LOW_start'],
                                               self.scan_config['VCAL_LOW_stop'] - 1,
                                               self.scan_config['VCAL_LOW_step'])]
        elif 'VTH_start' in self.scan_config:
            self.scan_parameter_range = list(range(self.scan_config['VTH_start'],
                                                   self.scan_config['VTH_stop'],
                                                   -1 * self.scan_config['VTH_step']))
        else:
            self.scan_parameter_range = None

        try:
            self.HistTdcStatus = root.HistTdcStatus[:]
        except tb.NoSuchNodeError:
            self.HistTdcStatus = None
        self.HistOcc = root.HistOcc[:]
        self.HistTot = root.HistTot[:]
        if self.run_config['scan_id'] in ['threshold_scan', 'calibrate_tot', 'fast_threshold_scan', 'global_threshold_tuning', 'in_time_threshold_scan', 'autorange_threshold_scan', 'crosstalk_scan']:
            self.ThresholdMap = root.ThresholdMap[:, :]
            self.Chi2Map = root.Chi2Map[:, :]
            self.Chi2Sel = (self.Chi2Map > 0) & (self.Chi2Map < SCURVE_CHI2_UPPER_LIMIT) & (~self.enable_mask)
            self.n_failed_scurves = self.n_enabled_pixels - len(self.Chi2Map[self.Chi2Sel])
            self.NoiseMap = root.NoiseMap[:]

        if self.mask_noisy_pixels:
            noisy_pixels = np.where(self.HistOcc > self.mask_noisy_pixels)
            for i in range(len(noisy_pixels[0])):
                self.log.warning('Disabling noisy pixel ({0}, {1})'.format(noisy_pixels[0][i], noisy_pixels[1][i]))
                self.enable_mask[noisy_pixels[0][i], noisy_pixels[1][i]] = True
            self.n_enabled_pixels = len(self.enable_mask[~self.enable_mask])
            self.log.warning('Disabled {} noisy pixels in total.'.format(len(noisy_pixels[0])))

        try:
            _ = root.Cluster
            self.HistClusterSize = root.HistClusterSize[:]
            self.HistClusterShape = root.HistClusterShape[:]
            self.HistClusterTot = root.HistClusterTot[:]
            self.clustered = True
        except tb.NoSuchNodeError:
            pass

        try:
            conversion_factors = au.ConfigDict(root.configuration_in.bench.electron_conversion[:])
            if self.scan_config['start_column'] in range(0, 448) and self.scan_config['stop_column'] in range(0, 448):  # TODO: Get rid of hardcoded values.
                self.electron_conversion = conversion_factors['DC_coupled']
            elif self.scan_config['start_column'] in range(448, 512) and self.scan_config['stop_column'] in range(448, 512):
                self.electron_conversion = conversion_factors['AC_coupled']
            else:
                self.log.warning('Both DC and AC coupled pixels enabled. Choose ambiguous electron conversion factor of DC falvors!')
                self.electron_conversion = conversion_factors['DC_coupled']
            self.plot_electron_axis = True
        except tb.NoSuchNodeError:
            self.plot_electron_axis = False

        try:
            in_file.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.out_file is not None and isinstance(self.out_file, PdfPages):
            self.log.info('Closing output PDF file: {0}'.format(self.out_file._file.fh.name))
            self.out_file.close()
            shutil.copyfile(self.filename, os.path.join(os.path.split(self.filename)[0], 'last_scan.pdf'))

    ''' User callable plotting functions '''
    def create_standard_plots(self):
        if self.skip_plotting:
            return
        self.log.info('Creating selected plots...')
        if self.run_config['scan_id'] in ['dac_linearity_scan', 'adc_tuning']:
            self.create_parameter_page()
            self.create_dac_linearity_plot()
        else:
            self.create_parameter_page()
            self.create_occupancy_map()
            if self.run_config['scan_id'] in ['source_scan', 'ext_trigger_scan', 'eudaq_scan']:
                self.create_fancy_occupancy()
            if self.run_config['scan_id'] in ['analog_scan', 'threshold_scan', 'global_threshold_tuning', 'source_scan', 'ext_trigger_scan', 'eudaq_scan', 'calibrate_tot']:
                self.create_hit_pix_plot()
                self.create_tdac_plot()
                self.create_tdac_map()
                self.create_tot_plot()
            if self.run_config['scan_id'] in ['threshold_scan', 'calibrate_tot']:
                self.create_tot_hist()
                self.create_scurves_plot()
                self.create_threshold_plot()
                self.create_stacked_threshold_plot()
                self.create_threshold_map()
                self.create_noise_plot()
                self.create_noise_map()
            if self.run_config['scan_id'] == 'global_threshold_tuning':
                self.create_scurves_plot()
                self.create_threshold_plot()
                self.create_threshold_map()
                self.create_noise_plot()
                self.create_noise_map()

            if self.clustered:
                self.create_cluster_tot_plot()
                self.create_cluster_shape_plot()
                self.create_cluster_size_plot()
            if self.HistTdcStatus is not None:  # Check if TDC analysis is activated.
                self.create_tdc_status_plot()

    def create_parameter_page(self):
        try:
            self._plot_parameter_page()
        except Exception:
            self.log.error('Could not create parameter page!')

    def create_occupancy_map(self):
        try:
            if self.run_config['scan_id'] in ['threshold_scan', 'fast_threshold_scan', 'autorange_threshold_scan', 'global_threshold_tuning', 'injection_delay_scan', 'in_time_threshold_scan', 'injection_delay_scan', 'crosstalk_scan']:
                title = 'Integrated occupancy'
                z_max = 'maximum'
            else:
                title = 'Occupancy'
                z_max = None

            self._plot_occupancy(hist=np.ma.masked_array(self.HistOcc[:].sum(axis=2), self.enable_mask).T,
                                 z_max=z_max,
                                 suffix='occupancy',
                                 title=title)
        except Exception:
            self.log.error('Could not create occupancy map!')

    def create_fancy_occupancy(self):
        try:
            self._plot_fancy_occupancy(hist=np.ma.masked_array(self.HistOcc[:].sum(axis=2), self.enable_mask).T)
        except Exception:
            self.log.error('Could not create fancy occupancy plot!')

    def create_tot_plot(self):
        ''' Create 1D tot plot '''
        try:
            title = ('Time-over-Threshold distribution ($\\Sigma$ = {0:1.0f})'.format(np.sum(self.HistTot.sum(axis=(0, 1, 2)).T)))
            self._plot_1d_hist(hist=self.HistTot.sum(axis=(0, 1, 2)).T,
                               title=title,
                               log_y=False,
                               plot_range=range(0, self.HistTot.shape[3]),
                               x_axis_title='ToT code',
                               y_axis_title='# of hits',
                               color='b',
                               suffix='tot')
        except Exception:
            self.log.error('Could not create tot plot!')

    def create_tot_hist(self):
        try:
            data = self.HistTot
            self._plot_2d_param_hist(hist=data.sum(axis=(0, 1)).T,
                                     y_max=data.shape[3],
                                     scan_parameters=self.scan_parameter_range,
                                     electron_axis=False,
                                     scan_parameter_name='$\\Delta$ VCAL',
                                     title='ToT Scan Parameter Histogram',
                                     ylabel='ToT code',
                                     suffix='tot_param_hist')
        except Exception as e:
            self.log.error('Could not create tot param histogram plot! ({0})'.format(e))

    def create_scurves_plot(self, scan_parameter_name='Scan parameter'):
        try:
            if self.run_config['scan_id'] == 'injection_delay_scan':
                scan_parameter_name = 'Finedelay [LSB]'
                plot_electron_axis = False
                scan_parameter_range = range(0, 16)
            elif self.run_config['scan_id'] == 'global_threshold_tuning':
                scan_parameter_name = self.scan_config['VTH_name']
                plot_electron_axis = False
                scan_parameter_range = self.scan_parameter_range
            else:
                scan_parameter_name = '$\\Delta$ VCAL'
                scan_parameter_range = self.scan_parameter_range
                plot_electron_axis = self.plot_electron_axis

            params = [{'scurves': self.HistOcc[:].ravel().reshape((self.rows * self.cols, -1)).T,
                       'scan_parameters': scan_parameter_range,
                       'electron_axis': plot_electron_axis,
                       'scan_parameter_name': scan_parameter_name}]

            for param in params:
                self._plot_scurves(**param)
        except Exception as e:
            self.log.error('Could not create scurve plot! ({0})'.format(e))

    def create_threshold_plot(self, logscale=False, scan_parameter_name='Scan parameter'):
        try:
            title = 'Threshold distribution for enabled pixels'
            if self.run_config['scan_id'] == 'injection_delay_scan':
                scan_parameter_name = 'Finedelay [LSB]'
                plot_electron_axis = False
                plot_range = range(0, 16)
                title = 'Fine delay distribution for enabled pixels'
            elif self.run_config['scan_id'] == 'global_threshold_tuning':
                plot_range = self.scan_parameter_range
                scan_parameter_name = self.scan_config['VTH_name']
                plot_electron_axis = False
            else:
                plot_range = self.scan_parameter_range
                scan_parameter_name = '$\\Delta$ VCAL'
                plot_electron_axis = self.plot_electron_axis

            self._plot_distribution(self.ThresholdMap[self.Chi2Sel].T,
                                    plot_range=plot_range,
                                    electron_axis=plot_electron_axis,
                                    x_axis_title=scan_parameter_name,
                                    title=title,
                                    log_y=logscale,
                                    y_axis_title='# of pixels',
                                    print_failed_fits=True,
                                    suffix='threshold_distribution')
        except Exception as e:
            self.log.error('Could not create threshold plot! ({0})'.format(e))

    def create_stacked_threshold_plot(self, scan_parameter_name='Scan parameter'):
        try:
            min_tdac, max_tdac, range_tdac, _ = (1, 7, 7, 1)

            plot_range = self.scan_parameter_range
            if self.run_config['scan_id'] == 'global_threshold_tuning':
                scan_parameter_name = self.scan_config['VTH_name']
                plot_electron_axis = False
            else:
                scan_parameter_name = '$\\Delta$ VCAL'
                plot_electron_axis = self.plot_electron_axis

            self._plot_stacked_threshold(data=self.ThresholdMap[self.Chi2Sel].T,
                                         tdac_mask=self.tdac_mask[self.Chi2Sel].T,
                                         plot_range=plot_range,
                                         electron_axis=plot_electron_axis,
                                         x_axis_title=scan_parameter_name,
                                         y_axis_title='# of pixels',
                                         title='Threshold distribution for enabled pixels',
                                         suffix='tdac_threshold_distribution',
                                         min_tdac=min(min_tdac, max_tdac),
                                         max_tdac=max(min_tdac, max_tdac),
                                         range_tdac=range_tdac, centered_ticks=True)
        except Exception:
            self.log.error('Could not create stacked threshold plot!')

    def create_threshold_map(self):
        try:
            mask = self.enable_mask.copy()
            sel = self.Chi2Map[:] > 0.  # Mask not converged fits (chi2 = 0)
            mask[~sel] = True
            if self.run_config['scan_id'] == 'injection_delay_scan':
                plot_electron_axis = False
                use_electron_offset = False
                z_label = 'Finedelay [LSB]'
                title = 'Injection Delay'
                z_min = 0
                z_max = 16
            else:
                plot_electron_axis = self.plot_electron_axis
                use_electron_offset = False
                z_label = 'Threshold'
                title = 'Threshold'
                z_min = None
                z_max = None

            self._plot_occupancy(hist=np.ma.masked_array(self.ThresholdMap, mask).T,
                                 electron_axis=plot_electron_axis,
                                 z_label=z_label,
                                 title=title,
                                 use_electron_offset=use_electron_offset,
                                 show_sum=False,
                                 z_min=z_min,
                                 z_max=z_max,
                                 suffix='threshold_map')
        except Exception:
            self.log.error('Could not create threshold map!')

    def create_noise_plot(self, logscale=False, scan_parameter_name='Scan parameter'):
        try:
            mask = self.enable_mask.copy()
            sel = self.Chi2Map[:] > 0.  # Mask not converged fits (chi2 = 0)
            mask[~sel] = True

            plot_range = None
            if self.run_config['scan_id'] in ['threshold_scan', 'fast_threshold_scan', 'in_time_threshold_scan', 'autorange_threshold_scan', 'crosstalk_scan']:
                scan_parameter_name = '$\\Delta$ VCAL'
                plot_electron_axis = self.plot_electron_axis
            elif self.run_config['scan_id'] == 'global_threshold_tuning':
                scan_parameter_name = self.scan_config['VTH_name']
                plot_electron_axis = False
            elif self.run_config['scan_id'] == 'injection_delay_scan':
                scan_parameter_name = 'Finedelay [LSB]'
                plot_electron_axis = False

            self._plot_distribution(np.ma.masked_array(self.NoiseMap, mask).T,
                                    title='Noise distribution for enabled pixels',
                                    plot_range=plot_range,
                                    electron_axis=plot_electron_axis,
                                    use_electron_offset=False,
                                    x_axis_title=scan_parameter_name,
                                    y_axis_title='# of pixels',
                                    log_y=logscale,
                                    print_failed_fits=True,
                                    suffix='noise_distribution')
        except Exception:
            self.log.error('Could not create noise plot!')

    def create_noise_map(self):
        try:
            mask = self.enable_mask.copy()
            sel = self.Chi2Map[:] > 0.  # Mask not converged fits (chi2 = 0)
            mask[~sel] = True
            z_label = 'Noise'
            title = 'Noise'
            plot_electron_axis = self.plot_electron_axis

            if self.run_config['scan_id'] == 'injection_delay_scan':
                z_label = 'Finedelay [LSB]'
                title = 'Injection Delay Noise'
                plot_electron_axis = False
            self._plot_occupancy(hist=np.ma.masked_array(self.NoiseMap, mask).T,
                                 electron_axis=plot_electron_axis,
                                 use_electron_offset=False,
                                 z_label=z_label,
                                 z_max='median',
                                 title=title,
                                 show_sum=False,
                                 suffix='noise_map')
        except Exception:
            self.log.error('Could not create noise map!')

    def create_tdac_plot(self):
        try:
            mask = self.enable_mask.copy()
            min_tdac, max_tdac, _, tdac_incr = (0, 8, 8, 1)
            plot_range = range(min_tdac, max_tdac + tdac_incr, tdac_incr)
            self._plot_distribution(self.tdac_mask[~mask].T,
                                    plot_range=plot_range,
                                    title='TDAC distribution for enabled pixels',
                                    x_axis_title='TDAC',
                                    y_axis_title='# of pixels',
                                    align='center',
                                    suffix='tdac_distribution')
        except Exception:
            self.log.error('Could not create TDAC plot!')

    def create_tdac_map(self):
        try:
            mask = self.enable_mask.copy()
            min_tdac, max_tdac = (1, 7)
            self._plot_fancy_occupancy(hist=np.ma.masked_array(self.tdac_mask, mask).T,
                                       title='TDAC map',
                                       z_label='TDAC',
                                       z_min=min(min_tdac, max_tdac),
                                       z_max=max(min_tdac, max_tdac),
                                       log_z=False, centered_ticks=True,
                                       norm_projection=True)
        except Exception:
            self.log.error('Could not create TDAC map!')

    def create_chi2_map(self):
        try:
            mask = self.enable_mask.copy()
            chi2 = self.Chi2Map[:]
            sel = chi2 > 0.  # Mask not converged fits (chi2 = 0)
            mask[~sel] = True

            self._plot_occupancy(hist=np.ma.masked_array(chi2, mask).T,
                                 z_label='Chi2/ndf.',
                                 z_max='median',
                                 title='Chi2 over ndf of S-Curve fits',
                                 show_sum=False,
                                 suffix='chi2_map')
        except Exception:
            self.log.error('Could not create chi2 map!')

    def create_cluster_size_plot(self):
        ''' Create 1D cluster size plot '''
        try:
            self._plot_1d_hist(hist=self.HistClusterSize[:], title='Cluster size',
                               log_y=False, plot_range=range(0, 10),
                               x_axis_title='Cluster size',
                               y_axis_title='# of clusters', suffix='cluster_size')
        except Exception:
            self.log.error('Could not create cluster size plot!')

    def create_cluster_tot_plot(self):
        ''' Create 1D cluster ToT plot '''
        try:
            if np.max(np.nonzero(self.HistClusterTot)) < 128:
                plot_range = range(0, 128)
            else:
                plot_range = range(0, np.max(np.nonzero(self.HistClusterTot)))

            tot_calib_file = self.configuration['scan'].get('tot_calib_file', None)
            if tot_calib_file is not None:
                x_axis_title = 'Cluster charge [e⁻]'
                plot_range = plot_range * self.electron_conversion
            else:
                x_axis_title = 'Cluster ToT [25 ns]'

            self._plot_1d_hist(hist=self.HistClusterTot[:], title='Cluster ToT',
                               log_y=False, plot_range=plot_range,
                               x_axis_title=x_axis_title,
                               y_axis_title='# of clusters', suffix='cluster_tot')
        except Exception:
            self.log.error('Could not create cluster TOT plot!')

    def create_cluster_shape_plot(self):
        try:
            self._plot_cl_shape(self.HistClusterShape[:])
        except Exception:
            self.log.error('Could not create cluster shape plot!')

    def create_hit_pix_plot(self):
        try:
            occ_1d = np.ma.masked_array(self.HistOcc[:].sum(axis=2), self.enable_mask).ravel()

            if occ_1d.sum() == 0:
                plot_range = np.arange(0, 100, 1)
            else:
                plot_range = np.arange(0, occ_1d.max() + 0.05 * occ_1d.max(), occ_1d.max() / 100)
            self._plot_distribution(data=occ_1d,
                                    plot_range=plot_range,
                                    title='Hits per Pixel',
                                    x_axis_title='# of Hits',
                                    y_axis_title='# of Pixel',
                                    log_y=True,
                                    align='center',
                                    fit_gauss=False,
                                    suffix='hit_pix')
        except Exception:
            self.log.error('Could not create hits per pixel plot!')

    '''Internal functions not meant to be called by user'''

    def _mask_disabled_pixels(self, enable_mask, scan_config):
        mask = np.invert(enable_mask)
        mask[:scan_config['start_column'], :] = True
        mask[scan_config['stop_column']:, :] = True
        mask[:, :scan_config['start_row']] = True
        mask[:, scan_config['stop_row']:] = True

        return mask

    def _save_plots(self, fig, suffix=None, tight=False):
        increase_count = False
        bbox_inches = 'tight' if tight else ''
        if suffix is None:
            suffix = str(self.plot_cnt)
        self.out_file.savefig(fig, bbox_inches=bbox_inches)
        if self.save_png:
            fig.savefig(self.filename[:-4] + '_' + suffix + '.png', bbox_inches=bbox_inches)
            increase_count = True
        if self.save_single_pdf:
            fig.savefig(self.filename[:-4] + '_' + suffix + '.pdf', bbox_inches=bbox_inches)
            increase_count = True
        if increase_count:
            self.plot_cnt += 1

    def _add_text(self, fig):
        fig.subplots_adjust(top=0.85)
        y_coord = 0.92
        fig.text(0.1, y_coord, '{0} {1}'.format("TJ-Monopix2", self.level), fontsize=12, color=OVERTEXT_COLOR, transform=fig.transFigure)
        if self._module_type is None:
            module_text = 'Chip S/N: {0}'.format(self.run_config['chip_sn'])
        else:
            module_text = 'Module: {0}'.format(self.module_settings['identifier'])
        fig.text(0.7, y_coord, module_text, fontsize=12, color=OVERTEXT_COLOR, transform=fig.transFigure)
        if self.internal:
            fig.text(0.1, 1, 'Internal', fontsize=16, color='r', rotation=45, bbox=dict(boxstyle='round', facecolor='white', edgecolor='red', alpha=0.7), transform=fig.transFigure)

    def _convert_to_e(self, dac, use_offset=False):
        if use_offset:
            e = dac * self.calibration['e_conversion_slope'] + self.calibration['e_conversion_offset']
            de = math.sqrt((dac * self.calibration['e_conversion_slope_error'])**2 + self.calibration['e_conversion_offset_error']**2)
        else:
            e = dac * self.electron_conversion
            de = dac * self.electron_conversion * 0.15  # TODO: Assume generic 15% error of conversion factor, need precise measurement.
        return e, de

    def _add_electron_axis(self, fig, ax, use_electron_offset=False):
        fig.subplots_adjust(top=0.75)
        ax.title.set_position([.5, 1.15])

        fig.canvas.draw()
        ax2 = ax.twiny()

        xticks = []
        for t in ax.get_xticks(minor=False):
            xticks.append(int(self._convert_to_e(float(t), use_offset=use_electron_offset)[0]))

        ax2.set_xticklabels(xticks)

        l1 = ax.get_xlim()
        l2 = ax2.get_xlim()

        def f(x):
            return l2[0] + (x - l1[0]) / (l1[1] - l1[0]) * (l2[1] - l2[0])

        ticks = f(ax.get_xticks())
        ax2.xaxis.set_major_locator(matplotlib.ticker.FixedLocator(ticks))
        ax2.set_xlabel('Electrons', labelpad=7)

        return ax2

    def _plot_parameter_page(self):
        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        ax.axis('off')

        scan_id = self.run_config['scan_id']
        run_name = self.run_config['run_name']
        if self._module_type is None:
            file_type = 'chip'
            chip_sn = self.run_config['chip_sn']
        else:
            file_type = 'module'
            chip_sn = self.run_config['module']

        sw_ver = self.run_config['software_version']
        timestamp = datetime.datetime.strptime(' '.join(run_name.split('_')[:2]), '%Y%m%d %H%M%S')  # FIXME: Workaround while there is no timestamp saved in h5 file

        text = 'This is a TJ-Monopix2 {0} for {1} {2}.\nRun {3} was started {4}.'.format(scan_id, file_type, chip_sn, run_name, timestamp)

        ax.text(0.01, 0.9, text, fontsize=10)
        ax.text(-0.1, -0.11, 'Software version: {0}'.format(sw_ver), fontsize=3)

        if 'maskfile' in self.scan_config.keys() and self.scan_config['maskfile'] is not None and not self.scan_config['maskfile'] == 'None':
            ax.text(0.01, -0.05, 'Maskfile:\n{0}'.format(self.scan_config['maskfile']), fontsize=6)

        scan_config_dict = OrderedDict()
        dac_dict = OrderedDict()
        scan_config_trg_tdc_dict = OrderedDict()

        exclude_run_conf_items = ['scan_id', 'run_name', 'timestamp', 'chip_sn', 'software_version', 'maskfile', 'TDAC']
        run_conf_trg_tdc = ['TRIGGER_MODE', 'TRIGGER_SELECT', 'TRIGGER_INVERT', 'TRIGGER_LOW_TIMEOUT', 'TRIGGER_VETO_SELECT',
                            'TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES', 'DATA_FORMAT', 'EN_TLU_VETO', 'TRIGGER_DATA_DELAY',
                            'EN_WRITE_TIMESTAMP', 'EN_TRIGGER_DIST', 'EN_NO_WRITE_TRIG_ERR', 'EN_INVERT_TDC', 'EN_INVERT_TRIGGER']

        for key, value in sorted(self.scan_config.items()):
            if key not in (exclude_run_conf_items + run_conf_trg_tdc):
                if key == 'module' and value.startswith('module_'):  # Nice formatting
                    value = value.split('module_')[1]
                if key == 'trigger_pattern':  # Nice formatting
                    value = hex(value)
                scan_config_dict[key] = value
            if key in run_conf_trg_tdc:
                scan_config_trg_tdc_dict[key] = value

        for flavor in DACS.keys():
            dac_dict[flavor] = OrderedDict()
            for reg, value in self.registers.items():
                if any(reg.startswith(dac) for dac in DACS[flavor]):
                    dac_dict[flavor][reg] = value
        tb_list = []
        for i in range(max(len(scan_config_dict), len(dac_dict['TJMONOPIX2']), len(scan_config_dict))):
            try:
                key1 = list(scan_config_dict.keys())[i]
                value1 = scan_config_dict[key1]
            except IndexError:
                key1 = ''
                value1 = ''
            try:
                key2 = list(dac_dict['TJMONOPIX2'].keys())[i]
                value2 = dac_dict['TJMONOPIX2'][key2]
            except IndexError:
                key2 = ''
                value2 = ''

            tb_list.append([key1, value1, '', key2, value2, ''])

        widths = [0.18, 0.10, 0.03, 0.18, 0.10, 0.03]
        labels = ['Scan config', 'Value', '', 'TJ-Monopix2 config', 'Value', '']

        table = ax.table(cellText=tb_list, colWidths=widths, colLabels=labels, cellLoc='left', loc='center')
        table.scale(0.8, 0.8)
        table.auto_set_font_size(False)

        for key, cell in table.get_celld().items():
            cell.set_fontsize(3.5)
            row, col = key
            if row == 0:
                cell.set_color('#ffb300')
                cell.set_fontsize(5)
            if col in [2, 5]:
                cell.set_color('white')
            if col in [1, 4, 7, 10, 13]:
                cell._loc = 'center'

        self._save_plots(fig, suffix='parameter_page')

    def _plot_occupancy(self, hist, electron_axis=False, use_electron_offset=False, title='Occupancy', z_label='# of hits', z_min=None, z_max=None, show_sum=True, suffix=None, extend_upper_bound=True):
        if z_max == 'median':
            z_max = 2 * np.ma.median(hist)
        elif z_max == 'maximum':
            z_max = np.ma.max(hist)
        elif z_max is None:
            try:
                z_max = np.nanpercentile(hist.filled(np.nan), q=90)
                if np.any(hist[np.isfinite(hist)] > z_max):
                    z_max = 1.1 * z_max
            except TypeError:
                z_max = np.ma.max(hist)
        if z_max < 1 or hist.all() is np.ma.masked:
            z_max = 1.0

        if z_min is None:
            z_min = np.ma.min(hist)
            if z_min < 0:
                z_min = 0
        if z_min == z_max or hist.all() is np.ma.masked:
            z_min = 0

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        ax.set_adjustable('box')
        extent = self.plot_box_bounds
        bounds = np.linspace(start=z_min, stop=z_max + (1 if extend_upper_bound else 0), num=255, endpoint=True)
        cmap = copy.copy(cm.get_cmap('plasma'))
        cmap.set_bad('w')
        cmap.set_over('r')  # Make noisy pixels red
        cmap.set_under('g')
        norm = colors.BoundaryNorm(bounds, cmap.N)

        im = ax.imshow(hist, interpolation='none', aspect='equal', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
        ax.set_ylim((self.plot_box_bounds[2], self.plot_box_bounds[3]))
        ax.set_xlim((self.plot_box_bounds[0], self.plot_box_bounds[1]))
        if not show_sum:
            ax.set_title(title, color=TITLE_COLOR)
        else:
            ax.set_title(title + ' ($\\Sigma$ = {0})'.format((0 if hist.all() is np.ma.masked else np.ma.sum(hist))), color=TITLE_COLOR)

        if self._module_type is None or not self._module_type.switch_axis():
            ax.set_xlabel('Column')
            ax.set_ylabel('Row')
        else:
            ax.set_xlabel('Row')
            ax.set_ylabel('Column')

        divider = make_axes_locatable(ax)
        ticks = np.linspace(start=z_min, stop=z_max + (1 if extend_upper_bound else 0), num=10, endpoint=True)
        if self.cb_side:  # and not electron_axis:
            pad = 0.8 if electron_axis else 0.2
            cax = divider.append_axes("right", size="5%", pad=pad)
            cb = fig.colorbar(im, cax=cax, ticks=ticks)
            cax.set_yticklabels([round(x, 1) for x in ticks])
        else:
            pad = 1.0 if electron_axis else 0.6
            cax = divider.append_axes("bottom", size="5%", pad=pad)
            cb = fig.colorbar(im, cax=cax, ticks=ticks, orientation='horizontal')
            cax.set_xticklabels([round(x, 1) for x in ticks])
        cb.set_label(z_label)

        if electron_axis:
            def f(x):
                return np.array([self._convert_to_e(x, use_offset=use_electron_offset)[0] for x in x])

            if self.cb_side:
                ax2 = cb.ax.secondary_yaxis('left', functions=(lambda x: x, lambda x: x))
                e_ax = ax2.yaxis
            else:
                ax2 = cb.ax.secondary_xaxis('top', functions=(lambda x: x, lambda x: x))
                e_ax = ax2.xaxis
            e_ax.set_ticks(ticks)
            e_ax.set_ticklabels(f(ticks).round().astype(int))
            e_ax.set_label_text('{0} [Electrons]'.format(z_label))
            cb.set_label('{0} [$\\Delta$ VCAL]'.format(z_label))

        self._save_plots(fig, suffix=suffix)

    def _plot_2d_param_hist(self, hist, scan_parameters, y_max=None, electron_axis=False, scan_parameter_name=None, title='Scan Parameter Histogram', ylabel='', suffix=None):

        if y_max is None:
            y_max = hist.shape[0]

        x_bins = scan_parameters[:]  # np.arange(-0.5, max(scan_parameters) + 1.5)
        y_bins = np.arange(-0.5, y_max + 0.5)

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        fig.patch.set_facecolor('white')

        # log scale
        norm = colors.LogNorm()

        im = ax.pcolormesh(x_bins, y_bins, hist, norm=norm, rasterized=True)
        ax.set_xlim(x_bins[0], x_bins[-1])
        ax.set_ylim(-0.5, y_max)

        cb = fig.colorbar(im, fraction=0.04, pad=0.05)

        cb.set_label("# of pixels")
        ax.set_title(title + " for {0} pixel(s)".format(self.n_enabled_pixels), color=TITLE_COLOR)
        if scan_parameter_name is None:
            ax.set_xlabel('Scan parameter')
        else:
            ax.set_xlabel(scan_parameter_name)
        ax.set_ylabel(ylabel)

        if electron_axis:
            self._add_electron_axis(fig, ax)

        self._save_plots(fig, suffix='histogram')

    def _plot_fancy_occupancy(self, hist, title='Occupancy', z_label='#', z_min=None, z_max=None, log_z=True, norm_projection=False, show_sum=True, centered_ticks=False, suffix='fancy_occupancy'):
        if log_z:
            title += '\n(logarithmic scale)'
        title += '\nwith projections'

        if z_min is None:
            z_min = np.ma.min(hist)
        if log_z and z_min == 0:
            z_min = 0.1
        if z_max is None:
            z_max = np.ma.max(hist)

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        extent = self.plot_box_bounds
        if log_z:
            bounds = np.logspace(start=np.log10(z_min), stop=np.log10(z_max), num=255, endpoint=True)
        else:
            bounds = np.linspace(start=z_min, stop=z_max, num=int(z_max + 1), endpoint=True)
        if centered_ticks:
            cmap = copy.copy(cm.get_cmap('plasma', (z_max)))
        else:
            cmap = copy.copy(cm.get_cmap('plasma'))
        cmap.set_bad('w')
        norm = colors.BoundaryNorm(bounds, cmap.N)

        im = ax.imshow(hist, interpolation='none', aspect='auto', cmap=cmap, norm=norm, extent=extent)  # TODO: use pcolor or pcolormesh
        ax.set_ylim((self.plot_box_bounds[2], self.plot_box_bounds[3]))
        ax.set_xlim((self.plot_box_bounds[0], self.plot_box_bounds[1]))
        if self._module_type is None or not self._module_type.switch_axis():
            ax.set_xlabel('Column')
            ax.set_ylabel('Row')
        else:
            ax.set_xlabel('Row')
            ax.set_ylabel('Column')

        # create new axes on the right and on the top of the current axes
        # The first argument of the new_vertical(new_horizontal) method is
        # the height (width) of the axes to be created in inches.
        divider = make_axes_locatable(ax)
        axHistx = divider.append_axes("top", 1.2, pad=0.2, sharex=ax)
        axHisty = divider.append_axes("right", 1.2, pad=0.2, sharey=ax)

        cax = divider.append_axes("right", size="5%", pad=0.1)
        if log_z:
            cb = fig.colorbar(im, cax=cax, ticks=np.logspace(start=np.log10(z_min), stop=np.log10(z_max), num=9, endpoint=True))
        elif centered_ticks:
            ctick_size = (z_max - z_min) / (z_max)
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=colors.Normalize(vmin=z_min - ctick_size / 2, vmax=z_max + ctick_size / 2))
            sm.set_array([])
            cb = fig.colorbar(sm, cax=cax, ticks=np.linspace(start=z_min, stop=z_max, num=int((z_max - z_min) + 1), endpoint=True))
        else:
            cb = fig.colorbar(im, cax=cax, ticks=np.linspace(start=z_min, stop=z_max, num=int((z_max - z_min) + 1), endpoint=True))
        cb.set_label(z_label)
        # make some labels invisible
        setp(axHistx.get_xticklabels() + axHisty.get_yticklabels(), visible=False)
        if norm_projection:
            hight = np.ma.mean(hist, axis=0)
        else:
            hight = np.ma.sum(hist, axis=0)

        axHistx.bar(x=range(1, hist.shape[1] + 1), height=hight, align='center', linewidth=0)
        axHistx.set_xlim((self.plot_box_bounds[0], self.plot_box_bounds[1]))
        if hist.all() is np.ma.masked:
            axHistx.set_ylim((0, 1))
        axHistx.locator_params(axis='y', nbins=3)
        axHistx.ticklabel_format(style='sci', scilimits=(0, 4), axis='y')
        axHistx.set_ylabel(z_label)
        if norm_projection:
            width = np.ma.mean(hist, axis=1)
        else:
            width = np.ma.sum(hist, axis=1)

        axHisty.barh(y=range(1, hist.shape[0] + 1), width=width, align='center', linewidth=0)
        axHisty.set_ylim((self.plot_box_bounds[2], self.plot_box_bounds[3]))
        if hist.all() is np.ma.masked:
            axHisty.set_xlim((0, 1))
        axHisty.locator_params(axis='x', nbins=3)
        axHisty.ticklabel_format(style='sci', scilimits=(0, 4), axis='x')
        axHisty.set_xlabel(z_label)

        if not show_sum:
            ax.set_title(title, color=TITLE_COLOR, x=1.35, y=1.2)
        else:
            ax.set_title(title + '\n($\\Sigma$ = {0})'.format((0 if hist.all() is np.ma.masked else np.ma.sum(hist))), color=TITLE_COLOR, x=1.35, y=1.2)

        self._save_plots(fig, suffix=suffix)

    def _plot_scurves(self, scurves, scan_parameters, electron_axis=False, scan_parameter_name=None, suffix='scurves', title='S-curves', ylabel='Occupancy'):
        max_occ = np.max(scurves) + 50
        if self.run_config['scan_id'] == 'autorange_threshold_scan':
            max_occ = int(np.max(scurves) + 5)
        n_injections = self.scan_config.get('n_injections', 100)
        y_max = int(n_injections * 1.5)
        x_bins = scan_parameters  # np.arange(-0.5, max(scan_parameters) + 1.5)
        y_bins = np.arange(-0.5, max_occ + 0.5)

        coords = {}
        for col in range(self.cols):
            for row in range(self.rows):
                coords[col * self.rows + row] = (col, row)
        noisy_pixels = []
        for param in scurves:
            for pixel_num, pixel_occ in enumerate(param):
                c = coords[pixel_num]
                if pixel_occ > y_max and c not in noisy_pixels:
                    noisy_pixels.append(c)
        n_noisy_pixels = len(noisy_pixels)

        param_count = scurves.shape[0]
        hist = np.empty([param_count, max_occ], dtype=np.uint32)

        for param in range(param_count):
            if self.run_config['scan_id'] == 'autorange_threshold_scan':
                hist[param] = np.bincount(scurves[param, ~self.enable_mask.reshape((scurves.shape[-1]))].astype(int), minlength=max_occ)
            else:
                hist[param] = np.bincount(scurves[param, ~self.enable_mask.reshape((scurves.shape[-1]))], minlength=max_occ)

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        fig.patch.set_facecolor('white')
        cmap = copy.copy(cm.get_cmap('cool'))
        if np.allclose(hist, 0.0) or hist.max() <= 1:
            z_max = 1.0
        else:
            z_max = hist.max()
        # for small z use linear scale, otherwise log scale
        if z_max <= 10.0:
            bounds = np.linspace(start=0.0, stop=z_max, num=255, endpoint=True)
            norm = colors.BoundaryNorm(bounds, cmap.N)
        else:
            bounds = np.linspace(start=1.0, stop=z_max, num=255, endpoint=True)
            norm = colors.LogNorm()

        im = ax.pcolormesh(x_bins, y_bins, hist.T, norm=norm, rasterized=True, shading='flat')
        ax.set_ylim(-0.5, y_max)

        if z_max <= 10.0:
            cb = fig.colorbar(im, ticks=np.linspace(start=0.0, stop=z_max, num=min(
                11, math.ceil(z_max) + 1), endpoint=True), fraction=0.04, pad=0.05)
        else:
            cb = fig.colorbar(im, fraction=0.04, pad=0.05)
        cb.set_label("# of pixels")
        ax.set_title(title + ' for {0} pixel(s)'.format(self.n_enabled_pixels), color=TITLE_COLOR)
        if scan_parameter_name is None:
            ax.set_xlabel('Scan parameter')
        else:
            ax.set_xlabel(scan_parameter_name)
        ax.set_ylabel(ylabel)

        text = 'Failed fits: {0}\nNoisy pixels: {1}'.format(self.n_failed_scurves, n_noisy_pixels)
        props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
        ax.text(0.05, 0.88, text, transform=ax.transAxes,
                fontsize=8, verticalalignment='top', bbox=props)

        if electron_axis:
            self._add_electron_axis(fig, ax)

        self._save_plots(fig, suffix=suffix)

    def _plot_stacked_threshold(self, data, tdac_mask, plot_range=None, electron_axis=False, x_axis_title=None, y_axis_title='# of hits', z_axis_title='TDAC',
                                title=None, suffix=None, min_tdac=15, max_tdac=0, range_tdac=16,
                                fit_gauss=True, plot_legend=True, centered_ticks=False, print_failed_fits=False):

        if plot_range is None:
            diff = np.amax(data) - np.amin(data)
            if (np.amax(data)) > np.median(data) * 5:
                plot_range = np.arange(
                    np.amin(data), np.median(data) * 5, diff / 100.)
            else:
                plot_range = np.arange(np.amin(data), np.amax(data) + diff / 100., diff / 100.)

        tick_size = plot_range[1] - plot_range[0]

        hist, bins = np.histogram(np.ravel(data), bins=plot_range)

        bin_centres = (bins[:-1] + bins[1:]) / 2
        p0 = (np.amax(hist), np.nanmean(bins), (max(plot_range) - min(plot_range)) / 3)

        if fit_gauss:
            try:
                coeff, _ = curve_fit(au.gauss, bin_centres, hist, p0=p0)
            except Exception:
                coeff = None
                self.log.warning('Gauss fit failed!')
        else:
            coeff = None

        if coeff is not None:
            points = np.linspace(min(plot_range), max(plot_range), 500)
            gau = au.gauss(points, *coeff)

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        cmap = copy.copy(cm.get_cmap('viridis', (range_tdac)))
        # create dicts for tdac data
        data_thres_tdac = {}
        hist_tdac = {}
        tdac_bar = {}

        # select threshold data for different tdac values according to tdac map
        for tdac in range(range_tdac + 1):
            data_thres_tdac[tdac] = data[tdac_mask == tdac]
            # histogram threshold data for each tdac
            hist_tdac[tdac], _ = np.histogram(np.ravel(data_thres_tdac[tdac]), bins=bins)
            tdac_bar[tdac] = ax.bar(bins[:-1], hist_tdac[tdac], bottom=np.sum([hist_tdac[i] for i in range(tdac)], axis=0), width=tick_size, align='edge', color=cmap(1. / range_tdac * tdac), linewidth=0)

        fig.subplots_adjust(right=0.85)
        cax = fig.add_axes([0.89, 0.11, 0.02, 0.645])
        if centered_ticks:
            ctick_size = (max_tdac - min_tdac) / (range_tdac)
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=colors.Normalize(vmin=min_tdac - ctick_size / 2, vmax=max_tdac + ctick_size / 2))
        else:
            sm = plt.cm.ScalarMappable(cmap=cmap, norm=colors.Normalize(vmin=min_tdac, vmax=max_tdac))
        sm.set_array([])
        cb = fig.colorbar(sm, cax=cax, ticks=np.linspace(start=min_tdac, stop=max_tdac, num=range_tdac, endpoint=True))
        cb.set_label(z_axis_title)

        if coeff is not None:
            ax.plot(points, gau, "r-", label='Normal distribution')

        ax.set_xlim((min(plot_range), max(plot_range)))
        ax.set_title(title, color=TITLE_COLOR)
        if x_axis_title is not None:
            ax.set_xlabel(x_axis_title)
        if y_axis_title is not None:
            ax.set_ylabel(y_axis_title)
        ax.grid(True)

        if plot_legend:
            sel = (data < 1e5)
            mean = np.nanmean(data[sel])
            rms = np.nanstd(data[sel])
            if electron_axis:
                textright = '$\\mu={0:1.1f}\\;\\Delta$VCAL\n$\\;\\;\\,=({1[0]:1.0f} \\pm {1[1]:1.0f}) \\; e^-$\n\n$\\sigma={2:1.1f}\\;\\Delta$VCAL\n$\\;\\;\\,=({3[0]:1.0f} \\pm {3[1]:1.0f}) \\; e^-$'.format(mean, self._convert_to_e(mean), rms, self._convert_to_e(rms, use_offset=False))
            else:
                textright = '$\\mu={0:1.1f}\\;\\Delta$VCAL\n$\\sigma={1:1.1f}\\;\\Delta$VCAL'.format(mean, rms)

            # Fit results
            if coeff is not None:
                textright += '\n\nFit results:\n'
                if electron_axis:
                    textright += '$\\mu={0:1.1f}\\;\\Delta$VCAL\n$\\;\\;\\,=({1[0]:1.0f} \\pm {1[1]:1.0f}) \\; e^-$\n\n$\\sigma={2:1.1f}\\;\\Delta$VCAL\n$\\;\\;\\,=({3[0]:1.0f} \\pm {3[1]:1.0f}) \\; e^-$'.format(abs(coeff[1]), self._convert_to_e(abs(coeff[1])), abs(coeff[2]), self._convert_to_e(abs(coeff[2]), use_offset=False))
                else:
                    textright += '$\\mu={0:1.1f}\\;\\Delta$VCAL\n$\\sigma={1:1.1f}\\;\\Delta$VCAL'.format(abs(coeff[1]), abs(coeff[2]))

                textright += '\n\nFailed fits: {0}'.format(self.n_failed_scurves)
                props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
                ax.text(0.03, 0.95, textright, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)

        if electron_axis:
            self._add_electron_axis(fig, ax)

        self._save_plots(fig, suffix=suffix)

    def _plot_distribution(self, data, plot_range=None, x_axis_title=None, electron_axis=False, use_electron_offset=False, y_axis_title='# of hits', log_y=False, align='edge', title=None, print_failed_fits=False, fit_gauss=True, plot_legend=True, suffix=None):
        if plot_range is None:
            diff = np.amax(data) - np.amin(data)
            median = np.ma.median(data)
            if (np.amax(data)) > median * 5:
                plot_range = np.arange(np.amin(data), median * 2, median / 100.)
            else:
                plot_range = np.arange(np.amin(data), np.amax(data) + diff / 100., diff / 100.)
        tick_size = np.diff(plot_range)[0]

        hist, bins = np.histogram(np.ravel(data), bins=plot_range)

        bin_centres = (bins[:-1] + bins[1:]) / 2
        p0 = (np.amax(hist), np.nanmean(bins), (max(plot_range) - min(plot_range)) / 3)

        if fit_gauss:
            try:
                coeff, _ = curve_fit(au.gauss, bin_centres, hist, p0=p0)
            except Exception:
                coeff = None
                self.log.warning('Gauss fit failed!')
        else:
            coeff = None

        if coeff is not None:
            points = np.linspace(min(plot_range), max(plot_range), 500)
            gau = au.gauss(points, *coeff)

        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        ax.bar(bins[:-1], hist, width=tick_size, align=align)
        if coeff is not None:
            ax.plot(points, gau, "r-", label='Normal distribution')

        if log_y:
            if title is not None:
                title += ' (logscale)'
            ax.set_yscale('log')

        ax.set_xlim(min(plot_range), max(plot_range))
        ax.set_title(title, color=TITLE_COLOR)
        if x_axis_title is not None:
            ax.set_xlabel(x_axis_title)
        if y_axis_title is not None:
            ax.set_ylabel(y_axis_title)
        ax.grid(True)

        if plot_legend:
            sel = (data < 1e5)
            mean = np.nanmean(data[sel])
            rms = np.nanstd(data[sel])
            if electron_axis:
                textright = '$\\mu={0:1.2f}\\;\\Delta$VCAL\n$\\;\\;\\,=({1[0]:1.0f} \\pm {1[1]:1.0f}) \\; e^-$\n\n$\\sigma={2:1.2f}\\;\\Delta$VCAL\n$\\;\\;\\,=({3[0]:1.0f} \\pm {3[1]:1.0f}) \\; e^-$'.format(mean, self._convert_to_e(mean, use_offset=use_electron_offset), rms, self._convert_to_e(rms, use_offset=False))
            else:
                textright = '$\\mu={0:1.2f}\\;\\Delta$VCAL\n$\\sigma={1:1.2f}\\;\\Delta$VCAL'.format(mean, rms)
            if print_failed_fits:
                textright += '\n\nFailed fits: {0}'.format(self.n_failed_scurves)

            # Fit results
            if coeff is not None:
                textright += '\n\nFit results:\n'
                if electron_axis:
                    textright += '$\\mu={0:1.2f}\\;\\Delta$VCAL\n$\\;\\;\\,=({1[0]:1.0f} \\pm {1[1]:1.0f}) \\; e^-$\n\n$\\sigma={2:1.2f}\\;\\Delta$VCAL\n$\\;\\;\\,=({3[0]:1.0f} \\pm {3[1]:1.0f}) \\; e^-$'.format(abs(coeff[1]), self._convert_to_e(abs(coeff[1]), use_offset=use_electron_offset), abs(coeff[2]), self._convert_to_e(abs(coeff[2]), use_offset=False))
                else:
                    textright += '$\\mu={0:1.2f}\\;\\Delta$VCAL\n$\\sigma={1:1.2f}\\;\\Delta$VCAL'.format(abs(coeff[1]), abs(coeff[2]))
                if print_failed_fits:
                    textright += '\n\nFailed fits: {0}'.format(self.n_failed_scurves)

            props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
            ax.text(0.03, 0.95, textright, transform=ax.transAxes, fontsize=8, verticalalignment='top', bbox=props)

        if electron_axis:
            self._add_electron_axis(fig, ax, use_electron_offset=use_electron_offset)

        self._save_plots(fig, suffix=suffix)

    def _plot_1d_hist(self, hist, yerr=None, title=None, x_axis_title=None, y_axis_title=None, x_ticks=None, color='r',
                      plot_range=None, log_y=False, suffix=None):
        fig = Figure()
        FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        hist = np.array(hist)
        if plot_range is None:
            plot_range = range(0, len(hist))
        plot_range = np.array(plot_range)
        plot_range = plot_range[plot_range < len(hist)]
        if yerr is not None:
            ax.bar(x=plot_range, height=hist[plot_range], color=color, align='center', yerr=yerr)
        else:
            ax.bar(x=plot_range, height=hist[plot_range], color=color, align='center')
        ax.set_xlim((min(plot_range) - 0.5, max(plot_range) + 0.5))

        ax.set_title(title, color=TITLE_COLOR)
        if x_axis_title is not None:
            ax.set_xlabel(x_axis_title)
        if y_axis_title is not None:
            ax.set_ylabel(y_axis_title)
        if x_ticks is not None:
            ax.set_xticks(plot_range)
            ax.set_xticklabels(x_ticks)
            ax.tick_params(which='both', labelsize=8)
        if np.allclose(hist, 0.0):
            ax.set_ylim((0, 1))
        else:
            if log_y:
                ax.set_yscale('log')
                ax.set_ylim((1e-1, np.amax(hist) * 2))
        ax.grid(True)

        self._save_plots(fig, suffix=suffix)

    def _plot_cl_shape(self, hist):
        ''' Create a histogram with selected cluster shapes '''
        x = np.arange(12)
        fig = Figure()
        _ = FigureCanvas(fig)
        ax = fig.add_subplot(111)
        self._add_text(fig)

        selected_clusters = hist[[1, 3, 5, 6, 9, 13, 14, 7, 11, 19, 261, 15]]
        ax.bar(x, selected_clusters, align='center')
        ax.xaxis.set_ticks(x)
        fig.subplots_adjust(bottom=0.2)
        ax.set_xticklabels(["\u2004\u2596",
                            # 2 hit cluster, horizontal
                            "\u2597\u2009\u2596",
                            # 2 hit cluster, vertical
                            "\u2004\u2596\n\u2004\u2598",
                            "\u259e",  # 2 hit cluster
                            "\u259a",  # 2 hit cluster
                            "\u2599",  # 3 hit cluster, L
                            "\u259f",  # 3 hit cluster
                            "\u259b",  # 3 hit cluster
                            "\u259c",  # 3 hit cluster
                            # 3 hit cluster, horizontal
                            "\u2004\u2596\u2596\u2596",
                            # 3 hit cluster, vertical
                            "\u2004\u2596\n\u2004\u2596\n\u2004\u2596",
                            # 4 hit cluster
                            "\u2597\u2009\u2596\n\u259d\u2009\u2598"])
        ax.set_title('Cluster shapes', color=TITLE_COLOR)
        ax.set_xlabel('Cluster shape')
        ax.set_ylabel('# of clusters')
        ax.grid(True)
        ax.set_yscale('log')
        ax.set_ylim(ymin=1e-1)

        self._save_plots(fig, suffix='cluster_shape')
