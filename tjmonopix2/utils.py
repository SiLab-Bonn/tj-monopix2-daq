#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import collections
import os
from copy import deepcopy
from importlib.metadata import version

import tables as tb

VERSION = version('tjmonopix2')


def recursive_update(first, second={}):
    '''
        Recursively updates a nested dict with another nested dict (can be any dict-like collections.Mapping objects).
        Each value in 'second' that is not of dict-like type overwrites the corresponding (same key) value in 'first'.
        If it is of dict-like type, it updates the corresponding dict-like object in first,
        using this function again, i.e. recursively.
        If a key in 'second' doesn't exist in 'first' the value from 'second' is simply appended.

        Before updating, a deep copy of 'first' is created such that the two function arguments stay unchanged!

        Parameters:
        ----------
        first : dict-like object
                The dict that is to be updated.
        second : dict-like object
                Updates the 'first' dict.

        Returns:
        ----------
        The merged dict.
    '''
    for k, v in second.items():
        if isinstance(v, collections.abc.Mapping):
            first[k] = recursive_update(first.get(k, {}), v)
        else:
            first[k] = v
    return first


def recursive_update_deep(first, second={}):
    '''
        Recursively updates a nested dict with another nested dict, see recursive_update().

        Before updating, a deep copy of 'first' is created such that
        the two function arguments, 'first' and 'second', stay unchanged!

        Parameters:
        ----------
        first : dict-like object
                The dict that is to be updated.
        second : dict-like object
                Updates the 'first' dict.

        Returns:
        ----------
        The merged dict.
    '''

    ret_val = deepcopy(first)
    ret_val = recursive_update(ret_val, second)
    return ret_val


def get_latest_file(directory, condition, file_timestamps=False):
    files = [os.path.join(directory, f) for f in os.listdir(directory) if os.path.isfile(os.path.join(directory, f))]
    files = filter(condition, files)

    if file_timestamps:
        files = sorted(files, key=lambda t: os.stat(t).st_mtime, reverse=True)
    else:
        files = sorted(files, reverse=True)

    # Check if file can be opened in read only mode (as the scan_base does)
    for file in files:
        try:
            f = tb.open_file(file)
            f.close()
            return file
        except ValueError:  # file handle in use
            pass


def get_latest_config_node_from_files(directory):
    ''' Returns the latest usable h5 file in the directory for the config.

        Usable means: file handel available and file not broken
    '''
    # Naming suffices of scans
    scan_pattern = ('scan', 'tuning', 'calibration', 'scan_interpreted', 'tuning_interpreted', 'calibration_interpreted')
    files = []

    for f in os.listdir(directory):
        if (os.path.isfile(os.path.join(directory, f)) and
            f.lower().endswith('.h5') and
                f.split('.')[-2].endswith(scan_pattern)):
            files.append(os.path.join(directory, f))

    # Sort via time stamp in file name and put _interpreted files first
    files = sorted(files, reverse=True)

    # Get latest usable file
    for file in files:
        try:   # Check if file can be opened in read only mode (as the scan_base does)
            f = tb.open_file(file)
        except (ValueError, tb.exceptions.HDF5ExtError):  # file handle in use
            continue
        try:   # Check if file has a configuration_out node
            f.root.configuration_out
            f.root.configuration_out.chip
            f.root.configuration_out.scan
            f.close()
            return file
        except tb.exceptions.NoSuchNodeError:
            pass
        try:   # Check if file has a configuration_in node
            f.root.configuration_in
            f.root.configuration_in.chip
            f.root.configuration_in.scan
            f.close()
            return file
        except tb.exceptions.NoSuchNodeError:
            pass
        finally:  # always close the open file
            f.close()


def get_software_version():
    return VERSION


def get_latest_h5file(directory, scan_pattern=('scan', 'tuning', 'calibration'), interpreted=False, file_timestamps=False):
    ''' Return the latest h5 file in a given directory

        scan_pattern: string or tuple of strings
    '''
    scan_pattern = (scan_pattern) if isinstance(scan_pattern, str) else scan_pattern
    if interpreted:
        scan_pattern = tuple(i + '_interpreted' for i in scan_pattern)
    return get_latest_file(directory=directory, condition=lambda file: (file.lower().endswith('.h5') and file.split('.')[-2].endswith(scan_pattern)), file_timestamps=file_timestamps)


def get_latest_chip_configuration_file(directory, file_timestamps=False):
    return get_latest_file(directory=directory, condition=lambda file: (file.split('.')[-1] == 'yaml' and file.split('.')[-2] == 'cfg'), file_timestamps=file_timestamps)
