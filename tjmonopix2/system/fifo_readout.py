#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import sys
import datetime
import ctypes
import threading
import multiprocessing
import numpy as np

from threading import Thread
from collections import deque
from queue import Queue, Empty
from time import sleep, time, mktime

from tjmonopix2.system import logger
# from bdaq53.analysis import analysis_utils as au


data_iterable = ("data", "timestamp_start", "timestamp_stop", "error")


class FifoError(Exception):
    pass


class SoftError(Exception):  # happens more often and can be ignored
    pass


class RxSyncError(FifoError):  # no aurora sync
    pass


class HardError(FifoError):  # aurora hard error
    pass


class FifoDiscardError(FifoError):  # fpga fifo overflowing --> data loss
    pass


class NoDataTimeout(FifoError):
    pass


class StopTimeout(FifoError):
    pass


class ReadoutChannel(object):

    def __init__(self, receiver, callback=None, clear_buffer=False, fill_buffer=False):
        self.receiver = receiver
        self.rx_id = int(self.receiver[2])
        self.thread_ident = 'WorkerThread-' + receiver
        self.callback = callback
        self.clear_buffer = clear_buffer
        self.fill_buffer = fill_buffer

        self._data_queue = multiprocessing.Queue()
        self.data_buffer_queue = multiprocessing.Queue()

        self.data_buffer_array = np.array([])

        self.total_word_count = multiprocessing.Value(ctypes.c_longlong, 0)

        self.worker_thread = Thread(target=self.worker, name=self.thread_ident)
        self.worker_thread.daemon = True

        self.polling_interval = 0.05

    def worker(self):
        '''
            Worker thread continuously calling callback function when data is available.
        '''
        while True:
            try:
                data = self._data_queue.get(block=False)
            except Empty:
                sleep(self.polling_interval)   # Sleep a little bit, reducing CPU usage
            else:
                if data is None:    # If None then store data buffer and exit
                    tmp_buffer = []
                    while True:
                        try:
                            data = self.data_buffer_queue.get(block=True, timeout=0.1)
                        except Empty:
                            break
                        tmp_buffer.append(data[0])
                    if tmp_buffer == []:
                        self.data_buffer_array = np.array([])
                    else:
                        self.data_buffer_array = np.concatenate(tmp_buffer)

                    break
                else:
                    self.callback(data_tuple=data, receiver=self.receiver)


class FifoReadout(object):
    def __init__(self, bdaq):
        self.log = logger.setup_derived_logger('FIFO Readout')

        self.daq = bdaq

        self.readout_thread = None
        self.worker_thread = None
        self.watchdog_thread = None

        self.errback = None

        self.workers_started = threading.Event()
        self.stopped_filter_readout = multiprocessing.Event()
        self.stop_readout = threading.Event()
        self.force_stop = threading.Event()

        self._data_queue = multiprocessing.Queue()

        self._readout_channels = {}
        self._data_buffers = {}

        self.readout_interval = 0.05

        # Stuff for calculating rate of readout words per time
        self._moving_average_time_period = 10.0
        self._words_per_read = deque(maxlen=int(self._moving_average_time_period / self.readout_interval))
        self._calculate_word_rate = threading.Event()
        self._word_rate_result = Queue(maxsize=1)

        # Total number of received words
        self._record_count = 0

        self._is_running = False

        self._clear_channels_next_readout = True

        self.timestamp = None
        self.update_timestamp()

        self.reset_rx()
        self.reset_sram_fifo()

    def attach_channel(self, readout_channel):
        if self._clear_channels_next_readout:
            self._readout_channels.clear()
            self._clear_channels_next_readout = False

        if readout_channel.rx_id not in self._readout_channels.keys():
            self._readout_channels[readout_channel.rx_id] = readout_channel

        if readout_channel.rx_id not in self._data_buffers.keys():
            self._data_buffers[readout_channel.rx_id] = multiprocessing.Queue()
        else:
            if readout_channel.clear_buffer:
                self._data_buffers[readout_channel.rx_id] = multiprocessing.Queue()

        self._readout_channels[readout_channel.rx_id].data_buffer_queue = self._data_buffers[readout_channel.rx_id]

    def get_data_buffer(self, receiver):
        buffer = np.copy(self._readout_channels[int(receiver[2])].data_buffer_array)
        self._readout_channels[int(receiver[2])].data_buffer_array = np.array([])
        return buffer

    def start_workers(self):
        for rx, channel in self._readout_channels.items():
            if channel.callback:
                channel.worker_thread.start()
        self.workers_started.set()

        self.log.debug('Started worker threads.')

    def start(self, errback=None, reset_rx=False, reset_sram_fifo=False, no_data_timeout=None):
        if self._is_running:
            raise RuntimeError('FIFO readout is already running.')

        self._clear_channels_next_readout = True

        self.errback = errback

        self.log.debug('Starting main FIFO readout...')

        if reset_rx:
            channels = [('rx' + str(channel.rx_id)) for channel in self._readout_channels]
            self.reset_rx(channels=channels)
        if reset_sram_fifo:
            self.reset_sram_fifo()
        else:
            fifo_size = self.daq['FIFO']['FIFO_SIZE']
            if fifo_size != 0:
                self.log.warning('FIFO not empty when starting FIFO readout: size = %i', fifo_size)

        self._record_count = 0
        self._words_per_read.clear()

        # Clear queue
        self._data_queue = multiprocessing.Queue()

        # Reset events used to control the readout thread externally
        self.workers_started.clear()
        self.stopped_filter_readout.clear()
        self.stop_readout.clear()
        self.force_stop.clear()

        if self.errback:
            self.watchdog_thread = Thread(target=self.watchdog, name='WatchdogThread')
            self.watchdog_thread.daemon = True
            self.watchdog_thread.start()

        readout_channel_buffers = {}
        for _, channel in self._readout_channels.items():
            queue = channel._data_queue if channel.callback else None
            data_buffer = channel.data_buffer_queue if channel.fill_buffer else None
            readout_channel_buffers.update({str(channel.rx_id): (channel.total_word_count, queue, data_buffer)})
        self.filter_process = multiprocessing.Process(target=self.filter_readout_data, name='ReadoutProcess', args=(self._data_queue, self.stopped_filter_readout, readout_channel_buffers,))
        self.filter_process.daemon = True
        self.filter_process.start()

        self.start_workers()

        self.readout_thread = Thread(target=self.readout, name='ReadoutThread', kwargs={'no_data_timeout': no_data_timeout})
        self.readout_thread.daemon = True
        self.readout_thread.start()

        self._is_running = True

    def stop(self, timeout=10.0):
        if not self._is_running:
            raise RuntimeError('Readout not running: use start() before stop()')

        self.stop_readout.set()
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

        # Wait for all readout channel threads finished here before continuing
        for _, channel in self._readout_channels.items():
            if channel.callback:
                channel.worker_thread.join()

        # Close filter process
        self.stopped_filter_readout.wait()
        self.filter_process.join()
        self.filter_process.close()
        del self.filter_process

        if self.errback:
            self.watchdog_thread.join()

        self.errback = None
        self._is_running = False

        self.log.debug('Stopped main FIFO readout')

    def print_readout_status(self):
        discard_count = self.get_rx_fifo_discard_count()

        if any(discard_count):
            try:
                queue_size = self._data_queue.qsize()
            except NotImplementedError as e:
                self.log.warning(e)
                queue_size = -1
            self.log.warning('RX errors detected')
            self.log.warning('Recived words:               %d', self._record_count)
            self.log.warning('Data queue size:             %d', queue_size)
            self.log.warning('FIFO size:                   %d', self.daq['FIFO']['FIFO_SIZE'])
            self.log.warning('Channel:                     %s', " | ".join([channel.name.rjust(3) for _, channel in sorted(self.daq.rx_channels.items())]))
            # self.log.warning('RX sync:                     %s', " | ".join(["YES".rjust(3) if status is True else "NO".rjust(3) for status in sync_status]))
            self.log.warning('RX FIFO discard counter:     %s', " | ".join([repr(count).rjust(3) for count in discard_count]))
            # self.log.warning('RX soft errors:              %s', " | ".join([repr(count).rjust(3) for count in soft_error_count]))
            # self.log.warning('RX hard errors:              %s', " | ".join([repr(count).rjust(3) for count in hard_error_count]))

        return discard_count

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

    def filter_readout_data(self, input_queue, stopped_event, readout_channel_buffers):

        self.stopped_event = stopped_event

        polling_interval = 0.05

        class DataFilter():
            def __init__(self, rx_id, total_word_count, queue, buffer):
                self.rx_id = rx_id
                self.out_queue = queue
                self.out_buffer = buffer
                self.total_word_count = total_word_count

        filters = []
        active_receivers = []
        for rx_id, (total_word_count, queue, buffer) in readout_channel_buffers.items():
            filters.append(DataFilter(int(rx_id), total_word_count, queue, buffer))
            active_receivers.append(int(rx_id))

        # If rx_id of a word matches one of the active receivers, forward to corresponding chip.
        # If rx_id of a word does not match any of the currently active receivers, forward to every chip and handle/skip it during analysis.
        valid_rx_ids = active_receivers

        try:
            while True:
                try:
                    data = input_queue.get(block=False)
                except Empty:
                    sleep(polling_interval)
                else:
                    if data is None:    # If None then exit
                        break
                    else:
                        for data_filter in filters:

                            # filtered_data = (data[0])[(data[0] & au.TRIGGER_HEADER == au.TRIGGER_HEADER) |  # Forward all trigger headers to every chip
                            #                           ((data[0] & au.TDC_HEADER) == au.TDC_ID_0) |  # Forward all TDC headers to every chip
                            #                           ((data[0] & au.TDC_HEADER) == au.TDC_ID_1) |  # Forward all TDC headers to every chip
                            #                           ((data[0] & au.TDC_HEADER) == au.TDC_ID_2) |  # Forward all TDC headers to every chip
                            #                           ((data[0] & au.TDC_HEADER) == au.TDC_ID_3) |  # Forward all TDC headers to every chip
                            #                           (((data[0] >> 20) & 0xf) == data_filter.rx_id) |  # Forward if rx_id matches (USER_K/AURORA, (also UNKNOWN_WORD))
                            #                           np.isin(((data[0] >> 20) & 0xf), valid_rx_ids, invert=True)]  # Forward to every chip, if rx_id does not match any active receiver (rx_id must be checked in analysis!)

                            filtered_data = (data[0])
                            with data_filter.total_word_count.get_lock():
                                data_filter.total_word_count.value += len(filtered_data)

                            if data_filter.out_queue:
                                data_filter.out_queue.put((filtered_data, data[1], data[2], data[3]))
                            if data_filter.out_buffer:
                                data_filter.out_buffer.put((filtered_data, data[1], data[2], data[3]))

        except KeyboardInterrupt:   # Need to catch KeyboardInterrupt from main process
            pass
        finally:
            for data_filter in filters:
                if data_filter.out_queue:
                    data_filter.out_queue.put(None)
                    data_filter.out_queue.close()
                    data_filter.out_queue.join_thread()
                if data_filter.out_buffer:
                    data_filter.out_buffer.close()
                    data_filter.out_buffer.join_thread()
            input_queue.close()
            input_queue.join_thread()

        self.stopped_event.set()

    def readout(self, no_data_timeout=None):
        '''
            Readout thread continuously reading FIFO. Uses read_data() and appends data to self._data_queue (multiprocessing.Queue).
        '''
        self.log.debug('Starting %s', self.readout_thread.name)
        curr_time = self.get_float_time()
        time_wait = 0.0

        # Wait for worker threads to start
        self.workers_started.wait()

        while not self.force_stop.wait(time_wait if time_wait >= 0.0 else 0.0):
            try:
                time_read = time()
                if no_data_timeout and curr_time + no_data_timeout < self.get_float_time():
                    raise NoDataTimeout('Received no data for %0.1f second(s)' % no_data_timeout)
                data = self.read_data()
                n_words = data.shape[0]
                self._record_count += n_words
            except Exception:
                no_data_timeout = None  # Raise exception only once
                if self.errback:
                    self.errback(sys.exc_info())
                else:
                    raise
                if self.stop_readout.is_set():
                    break
            else:
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

        self._data_queue.put(None)    # Last item, will stop filter process and callback threads
        self._data_queue.close()
        self._data_queue.join_thread()

        self.log.debug('Stopped %s', self.readout_thread.name)

    def watchdog(self):
        self.log.debug('Starting %s', self.watchdog_thread.name)
        n_channels = len(self.daq.rx_channels)
        n_soft_errors = [0] * n_channels
        n_hard_errors = [0] * n_channels
        while not self.stop_readout.wait(self.readout_interval * 10):
            try:
                # if not any(self.get_rx_sync_status()):
                #     raise RxSyncError('Aurora sync lost')
                # cnt = self.get_rx_hard_error_count()
                # if any(cnt) and any(cnt[i] > n_hard_errors[i] for i in range(n_channels)):
                #     n_hard_errors = cnt
                #     raise HardError('Aurora hard errors detected ', cnt)
                # cnt = self.get_rx_soft_error_count()
                # if any(cnt) and any(cnt[i] > n_soft_errors[i] for i in range(n_channels)):
                #     n_soft_errors = cnt
                #     raise SoftError('Aurora soft errors detected ', cnt)
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

    def reset_sram_fifo(self):
        fifo_size = self.daq['FIFO']['FIFO_SIZE']
        self.log.debug('Resetting FIFO: size = %i', fifo_size)
        self.update_timestamp()
        self.daq['FIFO']['RESET']
        sleep(0.01)     # Sleep here for a while
        fifo_size = self.daq['FIFO']['FIFO_SIZE']
        if fifo_size != 0:
            self.log.warning('FIFO not empty after reset: size = %i', fifo_size)

    def reset_rx(self, channels=None):
        self.log.debug('Resetting RX')
        if channels:
            [channel for channel in channels if self.daq.rx_channels[channel].reset()]
        else:
            [rx for _, rx in self.daq.rx_channels.items() if rx.reset()]
        sleep(0.1)  # Sleep here for a while

    def get_rx_fifo_discard_count(self, rx_channel=None):
        if rx_channel is None:
            return [rx.get_lost_data_counter() for _, rx in sorted(self.daq.rx_channels.items())]
        else:
            return self.daq.rx_channels[rx_channel].get_lost_data_counter()
