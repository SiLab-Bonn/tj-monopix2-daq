#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    TLU data delay tuning.

    This script tries to find a delay value for the TLU module that the error rate in the trigger number transfer is 0.
    An error is detected when the trigger number does not increase by one.

    Note:
    The TLU has to be started with internal trigger generation (e.g. pytlu -c 1000000 -t 10000 -oe CH1 --timeout 5)
    and the trigger data format has to be set to 0 (TLU word consists only of trigger number).
'''

import time
import numpy as np
import tables as tb
from tqdm import tqdm

from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages

# from bdaq53.system.scan_base import ScanBase
# from bdaq53.analysis import analysis_utils as au

from tjmonopix2.system.scan_base import ScanBase
from tjmonopix2.analysis import analysis
from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis import online as oa
#from tjmonopix2.analysis import plotting


scan_configuration = {
    'sleep': 2,                             # Time to record the trigger words per delay setting in seconds
    'trigger_data_delay': range(0, 40, 1),     # Trigger data delay settings to scanned

    'trigger_latency': 100,  # latency of trigger in units of 25 ns (BCs)
    'trigger_delay': 57,  # trigger delay in units of 25 ns (BCs)
    'trigger_length': 32,  # length of trigger command (amount of consecutive BCs are read out)
    'veto_length': 210,

    # Trigger configuration
    'bench': {'TLU': {
        'TRIGGER_MODE': 3,      # Selecting trigger mode: Use trigger inputs/trigger select (0), TLU no handshake (1), TLU simple handshake (2), TLU data handshake (3)
        'TRIGGER_SELECT': 0,     # Selecting trigger input: HitOR (1), disabled (0)
        'TRIGGER_HANDSHAKE_ACCEPT_WAIT_CYCLES': 5
    }
    }
}


class TuneTlu(ScanBase):
    scan_id = 'tune_tlu'

    def _configure(self, **_):
        self.daq.configure_tlu_module()
        self.daq.configure_tlu_veto_pulse(veto_length=500)
        self.configuration['bench']['analysis']['module_plotting'] = False  # Chip data not available

    def _scan(self, trigger_data_delay=range(0, 2**8), sleep=2, **_):
        pbar = tqdm(total=len(trigger_data_delay), unit='Setting')
        for scan_param_id, delay in enumerate(trigger_data_delay):
            # Write trigger data delay values to scan parameter table
            self.store_scan_par_values(scan_param_id=scan_param_id, trigger_data_delay=delay)
            pbar.write('Testing TRIGGER DATA DELAY = {0}...'.format(delay))
            self.daq.set_trigger_data_delay(delay)
            time.sleep(0.1)
            with self.readout(scan_param_id):
                self.daq.enable_tlu_module()
                time.sleep(sleep)
                self.daq.disable_tlu_module()
                if self.daq.get_trigger_counter() == 0:
                    pass
                    #raise RuntimeError('No triggers collected. Check if TLU is on and the IO is set correctly.')
                else:
                    print('trigger nmb ', self.daq.get_trigger_counter())
            pbar.update(1)
        pbar.close()
        self.log.success('Scan finished')

    def _analyze(self):
        with tb.open_file(self.output_filename + '.h5', 'r') as in_file_h5:
            meta_data = in_file_h5.root.meta_data[:]
            data = in_file_h5.root.raw_data

            if data.shape[0] == 0:
                raise RuntimeError('No trigger words recorded')

            # Get scan parameters
            scan_parameters = in_file_h5.root.configuration_out.scan.scan_params[:]['trigger_data_delay']
            n_scan_pars = scan_parameters.shape[0]

            # Output data
            with tb.open_file(self.output_filename + '_interpreted.h5', 'w') as out_file_h5:
                if self.configuration['bench']['analysis']['create_pdf']:
                    output_pdf = PdfPages(self.output_filename + '_interpreted.pdf')
                description = [('TRIGGER_DATA_DELAY', np.uint8), ('error_rate', float)]  # Output data table description
                data_array = np.zeros((n_scan_pars,), dtype=description)
                data_table = out_file_h5.create_table(out_file_h5.root, name='error_rate', description=np.zeros((1,), dtype=description).dtype,
                                                      title='Trigger number error rate for different data delay values')

                for scan_param_id, words in au.words_of_parameter(data, meta_data):
                    print('words ', words)
                    data_array['TRIGGER_DATA_DELAY'][scan_param_id] = scan_parameters[scan_param_id]
                    selection = np.bitwise_and(words, 0x80000000) == 0x80000000  # Select the trigger words in the data stream
                    trigger_words = np.bitwise_and(words[selection], 0x7FFFFFFF)  # Get the trigger values
                    print('trigWords ', trigger_words)
                    if selection.shape[0] != words.shape[0]:
                        self.log.warning('There are not only trigger words in the data stream')
                    actual_errors = np.count_nonzero(np.diff(trigger_words[trigger_words != 0x7FFFFFFF]) != 1)
                    data_array['error_rate'][scan_param_id] = float(actual_errors) / selection.shape[0]

                    if self.configuration['bench']['analysis']['create_pdf']:
                        # Plot trigger number
                        fig = Figure()
                        FigureCanvas(fig)
                        ax = fig.add_subplot(111)
                        ax.plot(range(trigger_words.shape[0]), trigger_words, '-', label='data')
                        ax.set_title('Trigger words for delay setting index {0}'.format(scan_param_id))
                        ax.set_xlabel('Trigger word index')
                        ax.set_ylabel('Trigger word')
                        ax.grid(True)
                        ax.legend(loc=0)
                        output_pdf.savefig(fig, bbox_inches='tight')

                data_table.append(data_array)  # Store valid data
                if np.all(data_array['error_rate'] != 0):
                    self.log.warning('There is no delay setting without errors')
                self.log.info('Errors: {0}'.format(data_array['error_rate']))

                # Determine best delay setting (center of working delay settings)
                good_indices = np.where(np.logical_and(data_array['error_rate'][:-1] == 0, np.diff(data_array['error_rate']) == 0))[0]
                best_index = good_indices[good_indices.shape[0] // 2]
                best_delay_setting = data_array['TRIGGER_DATA_DELAY'][best_index]
                self.log.success('The best delay setting for this setup is {0}. Please set this value in testbench.yaml.'.format(best_delay_setting))

                if self.configuration['bench']['analysis']['create_pdf']:
                    # Plot error rate plot
                    fig = Figure()
                    FigureCanvas(fig)
                    ax = fig.add_subplot(111)
                    ax.plot(data_array['TRIGGER_DATA_DELAY'], data_array['error_rate'], '.-', label='data')
                    ax.plot([best_delay_setting, best_delay_setting], [0, 1], '--', label='best delay setting')
                    ax.set_title('Trigger word error rate for different data delays')
                    ax.set_xlabel('TRIGGER_DATA_DELAY')
                    ax.set_ylabel('Error rate')
                    ax.grid(True)
                    ax.legend(loc=0)
                    output_pdf.savefig(fig, bbox_inches='tight')

                    output_pdf.close()


if __name__ == '__main__':
    with TuneTlu(scan_config=scan_configuration) as tuning:
        tuning.start()
