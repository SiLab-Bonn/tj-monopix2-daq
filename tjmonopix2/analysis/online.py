#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    Online data analysis functions
'''

import ctypes
import logging
import multiprocessing
import time
import queue
from functools import reduce

import numpy as np
import numba

from tjmonopix2.analysis import analysis_utils as au
from tjmonopix2.analysis.interpreter import is_tjmono

logger = logging.getLogger('OnlineAnalysis')


@numba.njit(cache=True, fastmath=True)
def gray2bin(gray):
    b6 = gray & 0x40
    b5 = (gray & 0x20) ^ (b6 >> 1)
    b4 = (gray & 0x10) ^ (b5 >> 1)
    b3 = (gray & 0x08) ^ (b4 >> 1)
    b2 = (gray & 0x04) ^ (b3 >> 1)
    b1 = (gray & 0x02) ^ (b2 >> 1)
    b0 = (gray & 0x01) ^ (b1 >> 1)
    return b6 + b5 + b4 + b3 + b2 + b1 + b0


@numba.njit(cache=True, fastmath=True)
def histogram(raw_data, occ_hist, hit_data, is_sof, is_eof, tj_data_flag):
    ''' Raw data to 2D occupancy histogram '''

    for word in raw_data:
        if not is_tjmono(word):
            continue

        # Split 32bit FPGA word into single data words
        dat = np.zeros(3, dtype=np.uint16)
        dat[0] = (word & 0x7FC0000) >> 18
        dat[1] = (word & 0x003FE00) >> 9
        dat[2] = (word & 0x00001FF)
    
        for d in dat:
            if d == 0x1bc:
                is_sof = 1
                tj_data_flag = 0
            elif d == 0x17c:
                is_eof = 1
            elif d == 0x13c:
                pass
            else:
                if tj_data_flag == 0:
                    tj_data_flag = 1
                    hit_data[0]['col'] = (d & 0xff) << 1
                elif tj_data_flag == 1:
                    tj_data_flag = 2
                    hit_data[0]['le'] = gray2bin((d & 0xfe) >> 1)
                    hit_data[0]['te'] = (d & 0x01) << 6
                elif tj_data_flag == 2:
                    tj_data_flag = 3
                    hit_data[0]['te'] = gray2bin(hit_data[0]['te'] | ((d & 0xfc) >> 2))
                    hit_data[0]['row'] = (d & 0x01) << 8
                    hit_data[0]['col'] = hit_data[0]['col'] + ((d & 0x02) >> 1)
                elif tj_data_flag == 3:
                    tj_data_flag = 0
                    hit_data[0]['row'] = hit_data[0]['row'] | (d & 0xff)

                    # Hit is complete, add to histogram
                    if hit_data[0]['col'] < 512 and hit_data[0]['row'] < 512:
                        occ_hist[hit_data[0]['col'], hit_data[0]['row']] += 1

    return hit_data, is_sof, is_eof, tj_data_flag


class OnlineHistogrammingBase():
    ''' Base class to do online analysis with raw data from chip.

        The output data is a histogram of a given shape.
    '''
    _queue_timeout = 0.01  # max blocking time to delete object [s]

    def __init__(self, shape):
        self._raw_data_queue = multiprocessing.Queue()
        self.stop = multiprocessing.Event()
        self.lock = multiprocessing.Lock()
        self.last_add = None  # time of last add to queue
        self.shape = shape
        self.analysis_function_kwargs = {}
        self.p = None  # process

    def init(self):
        # Create shared memory 32 bit unsigned int numpy array
        n_values = reduce(lambda x, y: x * y, self.shape)
        shared_array_base = multiprocessing.Array(ctypes.c_uint, n_values)
        shared_array = np.ctypeslib.as_array(shared_array_base.get_obj())
        self.hist = shared_array.reshape(*self.shape)
        self.idle_worker = multiprocessing.Event()
        self.p = multiprocessing.Process(target=self.worker,
                                         args=(self._raw_data_queue, shared_array_base,
                                               self.lock, self.stop, self.idle_worker))
        self.p.start()
        logger.info('Starting process %d', self.p.pid)

    def analysis_function(self, raw_data, hist, *args):
        raise NotImplementedError("You have to implement the analysis_funtion")

    def add(self, raw_data, meta_data=None):
        ''' Add raw data to be histogrammed '''
        self.last_add = time.time()  # time of last add to queue
        self.idle_worker.clear()  # after addding data worker cannot be idle
        if meta_data is None:
            self._raw_data_queue.put(raw_data)
        else:
            self._raw_data_queue.put([raw_data, meta_data])

    def _reset_hist(self):
        with self.lock:
            self.hist = self.hist.reshape(-1)
            for i in range(self.hist.shape[0]):
                self.hist[i] = 0
            self.hist = self.hist.reshape(self.shape)

    def reset(self, wait=True, timeout=0.5):
        ''' Reset histogram '''
        if not wait:
            if not self._raw_data_queue.empty() or not self.idle_worker.is_set():
                logger.warning('Resetting histogram while filling data')
        else:
            if not self.idle_worker.wait(timeout):
                logger.warning('Resetting histogram while filling data')
        self._reset_hist()

    def get(self, wait=True, timeout=None, reset=True):
        ''' Get the result histogram '''
        if not wait:
            if not self._raw_data_queue.empty() or not self.idle_worker.is_set():
                logger.warning('Getting histogram while analyzing data')
        else:
            if not self.idle_worker.wait(timeout):
                logger.warning('Getting histogram while analyzing data. Consider increasing the timeout.')

        if reset:
            hist = self.hist.copy()
            # No overwrite with a new zero array due to shared memory
            self._reset_hist()
            return hist
        else:
            return self.hist

    def worker(self, raw_data_queue, shared_array_base, lock, stop, idle):
        ''' Histogramming in seperate process '''
        hist = np.ctypeslib.as_array(shared_array_base.get_obj()).reshape(self.shape)
        while not stop.is_set():
            try:
                data = raw_data_queue.get(timeout=self._queue_timeout)
                idle.clear()
                with lock:
                    return_values = self.analysis_function(data, hist, **self.analysis_function_kwargs)
                    self.analysis_function_kwargs.update(zip(self.analysis_function_kwargs, return_values))
            except queue.Empty:
                idle.set()
                continue
            except KeyboardInterrupt:  # Need to catch KeyboardInterrupt from main process
                stop.set()
        idle.set()

    def close(self):
        ''' Close process and wait till done. Likely needed to give access to pytable file handle.'''
        logger.info('Stopping process %d', self.p.pid)
        self._raw_data_queue.close()
        self._raw_data_queue.join_thread()  # Needed otherwise IOError: [Errno 232] The pipe is being closed
        self.stop.set()
        self.p.join()
        del self.p  # explicit delete required to free memory
        self.p = None

    def __del__(self):
        if self.p and self.p.is_alive():
            logger.warning('Process still running. Was close() called?')
            self.close()


class OccupancyHistogramming(OnlineHistogrammingBase):
    ''' Fast histogramming of raw data to a 2D hit histogramm

        No event building.
    '''

    def __init__(self):
        super().__init__(shape=(512, 512))
        self.analysis_function_kwargs = {'hit_data': np.zeros(1, dtype=au.hit_dtype), 'is_sof': -1, 'is_eof': -1, 'tj_data_flag': 0}

        def analysis_function(self, raw_data, hist, hit_data, is_sof, is_eof, tj_data_flag):
            return histogram(raw_data, hist, hit_data, is_sof, is_eof, tj_data_flag)
        setattr(OccupancyHistogramming, 'analysis_function', analysis_function)

        self.init()
