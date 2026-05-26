
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import datetime
import sys
from collections import deque
from queue import Empty, Queue
from threading import Event, Lock, Thread
from time import mktime, sleep, time

import numpy as np

from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.system import logger

data_iterable = ("data", "timestamp_start", "timestamp_stop", "error")


class FifoError(Exception):
    pass


class EightbTenbError(FifoError):
    pass


class FifoDiscardError(FifoError):
    pass


class NoDataTimeout(Exception):
    pass


class StopTimeout(Exception):
    pass


class FifoReadout(object):
    def __init__(self, daq):
        self.log = logger.setup_derived_logger('FIFO Readout')

        self.daq = daq

        self.readout_thread = None
        self.worker_thread = None
        self.watchdog_thread = None
        self.errback = None

        self.stopped_filter_readout = Event()
        self.stop_readout = Event()
        self.force_stop = Event()

        self.readout_interval = 0.05  # 20 Hz

        # Stuff for calculating rate of readout words per time
        self._moving_average_time_period = 10.0
        self._words_per_read = deque(maxlen=int(self._moving_average_time_period / self.readout_interval))
        self._calculate_word_rate = Event()
        self._word_rate_result = Queue(maxsize=1)

        # Total number of received words
        self._record_count = 0

        self._is_running = False

        self.timestamp = None
        self.update_timestamp()

        self.reset_rx()
        self.reset_sram_fifo()

        self.callback = None  # callback function for data (callback usually stores raw data in scan base)
        self.channels = []  # receiver channels to use (e.g. rx0, RX1, ...)
        self.fill_buffer = False
        self._data_buffers = {}
        self.data_buffer_lock = Lock()

    def reset_channels(self):
        self.channels = []

    def attach_channel(self, channel):
        ''' Add a receiver channel to be used

            channel: string, e.g. 'rx0'
        '''
        self.channels.append(channel)
        if channel not in self._data_buffers:
            with self.data_buffer_lock:
                self._data_buffers[channel] = np.array([], np.uint32)

    def set_callback(self, callback):
        ''' Set the callback to be called with data from a receiver channel (e.g. rx0) '''
        self.callback = callback

    def get_data_buffer(self, receiver):
        ''' Return and reset data buffer '''
        with self.data_buffer_lock:
            ret = np.copy(self._data_buffers[receiver])
            self._data_buffers[receiver] = np.array([], np.uint32)
        return ret

    def start(self, errback=None, reset_rx=False, reset_sram_fifo=False, no_data_timeout=None, fill_buffer=False):
        if self._is_running:
            raise RuntimeError('FIFO readout is already running.')

        self.errback = errback

        self.fill_buffer = fill_buffer

        self.log.debug('Starting main FIFO readout...')

        if reset_rx:
            self.reset_rx()
        if reset_sram_fifo:
            self.reset_sram_fifo()
        else:
            fifo_size = self.daq['FIFO']['FIFO_SIZE']
            if fifo_size != 0:
                self.log.warning('FIFO not empty when starting FIFO readout: size = %i', fifo_size)

        self._record_count = 0
        self._words_per_read.clear()

        # Clear queue
        self._data_queue = Queue()

        # Reset events used to control the readout thread externally
        self.stopped_filter_readout.clear()
        self.stop_readout.clear()
        self.force_stop.clear()

        if self.errback:
            self.watchdog_thread = Thread(target=self.watchdog, name='WatchdogThread')
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()

        # Seperate thread to filter FIFO raw data by receiver channel
        # If too slow should be changed to seperate process
        self.filter_process = Thread(target=self.filter_readout_data, name='ReadoutProcess', args=(self._data_queue, self.stopped_filter_readout, ))
        self.filter_process.daemon = True
        self.filter_process.start()

        # Seperate thread polling data from FIFO
        self.readout_thread = Thread(target=self.readout, name='ReadoutThread', kwargs={'no_data_timeout': no_data_timeout})
        self.readout_thread.daemon = True
        self.readout_thread.start()

        self._is_running = True

    def stop(self, timeout=10.0):
        if not self._is_running:
            raise RuntimeError('Readout not running: use start() before stop()')
        self._is_running = False
        self.stop_readout.set()
        sleep(0.1)
        try:
            self.readout_thread.join(timeout=timeout)
            if self.readout_thread.is_alive():
                if timeout:
                    raise StopTimeout('FIFO stop timeout after %0.1f second(s)' % timeout)
                else:
                    self.log.warning('FIFO stop timeout')
        except StopTimeout as e:
            self.force_stop.set()
            if self.errback:
                self.errback(sys.exc_info())
            else:
                self.log.error(e)
            self.readout_thread.join()
            del self.readout_thread

        # Close filter process
        self.stopped_filter_readout.wait()
        self.filter_process.join()
        del self.filter_process

        if self.errback:
            self.watchdog_thread.join()

        del self._data_queue

        self.errback = None  # callback for errors
        self._is_running = False

        self.log.debug('Stopped main FIFO readout')

    def print_readout_status(self):
        discard_count = self.get_rx_fifo_discard_count()
        decode_err_count = self.get_rx_8b10b_error_count()

        if any(discard_count) or any(decode_err_count):
            try:
                queue_size = self._data_queue.qsize()
            except AttributeError:
                queue_size = 0
            self.log.info('RX errors detected')
            self.log.info('Recived words:               %d', self._record_count)
            self.log.info('Data queue size:             %d', queue_size)
            self.log.info('FIFO size:                   %d', self.daq['FIFO']['FIFO_SIZE'])
            self.log.info('Channel:                     %s', " | ".join([channel.name.rjust(3) for _, channel in sorted(self.daq.rx_channels.items())]))
            # self.log.warning('RX sync:                     %s', " | ".join(["YES".rjust(3) if status is True else "NO".rjust(3) for status in sync_status]))
            self.log.info('RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in discard_count]))
            self.log.info('RX 8b10b error counter       %s', " | ".join([repr(count).rjust(3) for count in decode_err_count]))

        return discard_count, decode_err_count

    def data_words_per_second(self):
        if self._word_rate_result.full():
            self._word_rate_result.get()
        self._calculate_word_rate.set()
        try:
            result = self._word_rate_result.get(timeout=2 * self.readout_interval)
        except Empty:
            self._calculate_word_rate.clear()
            return None
        return result / float(self._moving_average_time_period)

    def filter_readout_data(self, input_queue, stopped_event):
        ''' Runs in seperate process to filter raw data by receiver'''
        stopped_event = stopped_event
        polling_interval = 0.05

        valid_rx_ids = [0x4 + int(channel[2]) for channel in self.channels]  # Valid FIFO word headers. RX ID is last two bits of 0b1XX header

        # If rx_id of a word matches forward to corresponding callback.
        # If rx_id of a word does not match any of the currently active receivers, call callback for every chip and handle/skip it during analysis.

        try:
            while True:
                try:
                    data = input_queue.get(block=False)
                except Empty:
                    sleep(polling_interval)
                else:
                    if data is None:  # Exit if no data
                        break
                    else:
                        for receiver in self.channels:
                            rx_id = int(receiver[2])
                            raw_data = data[0]
                            # Select only certain raw data word for the channel raw data
                            sel = ((raw_data & 0x80000000 == au.TRIGGER_HEADER) |  # Forward all trigger words to every chip
                                   (raw_data & 0xF0000000 == au.TDC_HEADER) |  # Forward all TDC words to every chip
                                   ((raw_data >> 28) & 0xF == 0x4 + rx_id) |  # Match RX ID. RX ID is last two bits of 0b1XX header
                                   np.isin(((raw_data >> 28) & 0xF), valid_rx_ids, invert=True))  # Forward to every chip, if rx_id does not match any active receiver (rx_id must be checked in analysis!)
                            filtered_data = raw_data[sel]
                            if self.fill_buffer:
                                with self.data_buffer_lock:
                                    self._data_buffers[receiver] = np.append(self._data_buffers[receiver], filtered_data)
                            if self.callback:
                                self.callback(data_tuple=(filtered_data, data[1], data[2], data[3]), receiver=receiver)

        except KeyboardInterrupt:   # Need to catch KeyboardInterrupt from main process
            pass

        stopped_event.set()

    def readout(self, no_data_timeout=None):
        '''
            Readout thread continuously reading FIFO. Uses read_data() and appends data to self._data_queue.
        '''
        self.log.debug('Starting %s', self.readout_thread.name)
        curr_time = self.get_float_time()
        time_wait = 0.0
        while not self.force_stop.wait(time_wait if time_wait >= 0.0 else 0.0):
            try:
                time_read = time()
                if no_data_timeout and curr_time + no_data_timeout < self.get_float_time():
                    raise NoDataTimeout('Received no data for %0.1f second(s)' % no_data_timeout)
                data = self.read_data()
                n_words = data.shape[0]
                self._record_count += n_words
            except Exception:
                no_data_timeout = None  # raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
                if self.stop_readout.is_set():
                    break
            else:  # No exception
                if n_words == 0:
                    if self.stop_readout.is_set():
                        break
                    else:
                        continue
                last_time, curr_time = self.update_timestamp()
                status = 0
                self._data_queue.put((data, last_time, curr_time, status))
                self._words_per_read.append(n_words)
            finally:
                time_wait = self.readout_interval - (time() - time_read)

            if self._calculate_word_rate.is_set():
                self._calculate_word_rate.clear()
                self._word_rate_result.put(sum(self._words_per_read))

        self._data_queue.put(None)  # Last item, None will stop filter process and callback threads

        self.log.debug('Stopped %s', self.readout_thread.name)

    def watchdog(self):
        ''' Runs in seperate thread to check reveiver status '''
        self.log.debug('Starting %s', self.watchdog_thread.name)
        n_channels = len(self.daq.rx_channels)
        n_decode_errors = [0] * n_channels
        while not self.stop_readout.wait(self.readout_interval * 10.0):
            try:
                cnt = self.get_rx_8b10b_error_count()
                if any(cnt) and any(cnt[i] > n_decode_errors[i] for i in range(n_channels)):
                    n_decode_errors = cnt
                    raise EightbTenbError('RX 8b10b error(s) detected ', cnt)
                cnt = self.get_rx_fifo_discard_count()
                if any(cnt):
                    raise FifoDiscardError('RX FIFO discard error(s) detected ', cnt)
            except Exception:
                self.errback(sys.exc_info())
        self.log.debug('Stopped %s', self.watchdog_thread.name)

    def read_data(self):
        '''
            Read FIFO and return data array
            Can be used without threading.

            Returns
            ----------
            data : list
                    A list of FIFO data words.
        '''
        return self.daq['FIFO'].get_data()

    def update_timestamp(self):
        curr_time = self.get_float_time()
        last_time = self.timestamp
        self.timestamp = curr_time
        return last_time, curr_time

    def get_float_time(self):
        '''
            Returns time as double precision floats - Time64 in pytables - mapping to and from python datetime's
        '''
        t1 = time()
        t2 = datetime.datetime.fromtimestamp(t1)
        return mktime(t2.timetuple()) + 1e-6 * t2.microsecond

    def reset_sram_fifo(self, timeout=1):
        fifo_size = self.daq['FIFO']['FIFO_SIZE']
        self.log.debug('Resetting FIFO: size = %i', fifo_size)
        
        # First drain the FIFO before resetting
        self.log.debug('Draining FIFO before reset...')
        start = time()
        while time() - start < 0.5:  # Try draining for 500ms
            data = self.daq['FIFO'].get_data()
            if len(data) == 0:
                break

        self.daq.reset_fifo()

        # Wait for FIFO to be empty
        start = time()
        while time() - start < timeout:
            fifo_size = self.daq['FIFO']['FIFO_SIZE']
            if fifo_size == 0:
                self.log.debug('FIFO emptied after reset')
                return
            sleep(0.01)
        
        self.update_timestamp()
        self.log.warning('FIFO not empty after reset: size = %i', fifo_size)

    def reset_rx(self, channels=None):
        self.log.debug('Resetting RX')
        if channels:
            [channel for channel in channels if self.daq.rx_channels[channel].reset()]
        else:
            [rx for _, rx in self.daq.rx_channels.items() if rx.reset()]
        sleep(0.1)  # Sleep here for a while

    def get_rx_8b10b_error_count(self, channel=None):
        if channel is None:
            return [rx.get_decoder_error_counter() for _, rx in sorted(self.daq.rx_channels.items())]
        else:
            return self.daq.rx_channels[channel].get_decoder_error_counter()

    def get_rx_fifo_discard_count(self, channel=None):
        if channel is None:
            return [rx.get_lost_data_counter() for _, rx in sorted(self.daq.rx_channels.items())]
        else:
            return self.daq.rx_channels[channel].get_lost_data_counter()
