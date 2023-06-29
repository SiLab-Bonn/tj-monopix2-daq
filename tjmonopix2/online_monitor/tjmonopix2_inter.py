import numpy as np

from online_monitor.converter.transceiver import Transceiver
from online_monitor.utils import utils

from tjmonopix2.analysis.interpreter import RawDataInterpreter
from tjmonopix2.analysis import analysis_utils as au


class TJMonopix2(Transceiver):

    def setup_transceiver(self):
        ''' Called at the beginning

            We want to be able to change the histogrammmer settings
            thus bidirectional communication needed
        '''
        self.set_bidirectional_communication()

    def setup_interpretation(self):
        ''' Objects defined here are available in interpretation process '''
        utils.setup_logging(self.loglevel)

        self.chunk_size = self.config.get('chunk_size', 1000000)
        self.analyze_tdc = self.config.get('analyze_tdc', False)
        # self.rx_id = int(self.config.get('rx', 'rx0')[2])
        # Mask pixels that have a higher occupancy than 3 * the median of all firering pixels
        self.noisy_threshold = self.config.get('noisy_threshold', 3)

        self.mask_noisy_pixel = False

        # Init result hists
        self.interpreter = RawDataInterpreter()
        self.reset_hists()

        # Number of readouts to integrate
        self.int_readouts = 0

        # Variables for meta data time calculations
        self.ts_last_readout = 0.  # Time stamp last readout
        self.hits_last_readout = 0.  # Number of hits
        self.triggers_last_readout = 0.  # Number of trigger words
        self.fps = 0.  # Readouts per second
        self.hps = 0.  # Hits per second
        self.tps = 0.  # Triggers per second
        self.total_trigger_words = 0

    def deserialize_data(self, data):
        ''' Inverse of TJ-Monopix2 serialization '''
        return utils.simple_dec(data)

    def _add_to_meta_data(self, meta_data):
        ''' Meta data interpratation is deducing timings '''

        ts_now = float(meta_data['timestamp_stop'])

        # Calculate readout per second with smoothing
        if ts_now != self.ts_last_readout:
            recent_fps = 1.0 / (ts_now - self.ts_last_readout)
            self.fps = self.fps * 0.95 + recent_fps * 0.05

            # Calulate hits per second with smoothing
            recent_hps = self.hits_last_readout * recent_fps
            self.hps = self.hps * 0.95 + recent_hps * 0.05

            # Calculate trigger rate with smoothing
            recent_tps = self.triggers_last_readout * recent_fps
            self.tps = self.tps * 0.95 + recent_tps * 0.05

        self.ts_last_readout = ts_now

        # Add info to meta data
        meta_data.update(
            {'fps': self.fps,
             'hps': self.hps,
             'tps': self.tps,
             'total_hits': self.total_hits,
             'total_triggers': self.total_trigger_words})
        return meta_data

    def interpret_data(self, data):
        ''' Called for every chunk received '''
        raw_data, meta_data = data[0][1]
        meta_data = self._add_to_meta_data(meta_data)

        hit_buffer = np.zeros(4 * len(raw_data), dtype=au.hit_dtype)
        hits = self.interpreter.interpret(raw_data, hit_buffer)

        n_hits = len(hits[hits['col'] < 512])

        last_triggers = self.total_trigger_words
        n_triggers = self.interpreter.get_n_triggers()
        self.hits_last_readout = n_hits
        self.total_hits += n_hits
        self.triggers_last_readout = n_triggers - last_triggers
        self.total_trigger_words = n_triggers
        self.readout += 1

        self.hist_occ, self.hist_tot, self.hist_tdc, _ = self.interpreter.get_histograms()
        occupancy_hist = self.hist_occ.sum(axis=2)

        # Mask noisy pixels
        if self.mask_noisy_pixel:
            sel = occupancy_hist > self.noisy_threshold * np.median(occupancy_hist[occupancy_hist > 0])
            occupancy_hist[sel] = 0

        interpreted_data = {
            'meta_data': meta_data,
            'occupancy': occupancy_hist,
            'tot_hist': self.hist_tot.sum(axis=(0, 1, 2)),
            'tdc_hist': self.hist_tdc,
        }

        if self.int_readouts != 0:  # = 0 for infinite integration
            if self.readout % self.int_readouts == 0:
                self.reset_hists()

        return [interpreted_data]

    def serialize_data(self, data):
        ''' Serialize data from interpretation '''
        return utils.simple_enc(None, data)

    def handle_command(self, command):
        ''' Received commands from GUI receiver '''
        if command[0] == 'RESET':
            self.reset_hists()
            self.last_event = -1
            self.trigger_id = -1
        elif 'MASK' in command[0]:
            if '0' in command[0]:
                self.mask_noisy_pixel = False
            else:
                self.mask_noisy_pixel = True
        else:
            self.int_readouts = int(command[0])

    def reset_hists(self):
        ''' Reset the histograms '''
        self.total_hits = 0
        self.total_trigger_words = 0
        # Readout number
        self.readout = 0

        self.interpreter.reset()
