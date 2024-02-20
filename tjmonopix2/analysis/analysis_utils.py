#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import ast
import logging
import multiprocessing as mp
import warnings
from functools import partial

import numba
import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit
from scipy.special import erf
from tqdm import tqdm

logger = logging.getLogger('Analysis')

hit_dtype = np.dtype([
    ("col", "<i2"),
    ("row", "<i2"),
    ("le", "<i1"),
    ("te", "<i1"),
    ("token_id", "<i4"),
    ("timestamp", "<i8"),
    ("scan_param_id", "<i2"),
])

event_dtype = np.dtype([
    ("event_number", "<u4"),
    ("trigger_number", "<u4"),
    ("frame", "<u1"),
    ("column", "<u2"),
    ("row", "<u2"),
    ("charge", "<u2"),
    ("timestamp", "<i8"),
])


class ConfigDict(dict):
    ''' Dictionary with different value data types:
        str / int / float / list / tuple depending on value

        key can be string or byte-array. Contructor can
        be called with all data types.

        If cast of object to known type is not possible the
        string representation is returned as fallback
    '''

    def __init__(self, *args):
        for key, value in dict(*args).items():
            self.__setitem__(key, value)

    def __setitem__(self, key, val):
        # Change types on value setting
        key, val = self._type_cast(key, val)
        dict.__setitem__(self, key, val)

    def _type_cast(self, key, val):
        ''' Return python objects '''
        # Some data is in binary array representation (e.g. pytable data)
        # These must be convertet to string
        if isinstance(key, (bytes, bytearray)):
            key = key.decode()
        if isinstance(val, (bytes, bytearray)):
            val = val.decode()
        if 'chip_sn' in key:
            return key, val
        try:
            if isinstance(val, np.generic):
                return key, val.item()
            return key, ast.literal_eval(val)
        except (ValueError, SyntaxError):  # fallback to return the object
            return key, val


def _tot_response_func(x, a, b, d):
    return (a / x + 1 / b) * (x - d)


@numba.njit
def _inv_tot_response_func(tot, a, b, d):
    return (np.sqrt(b**2 * (a - tot)**2 + 2 * b * d * (a + tot) + d**2) - b * a + b * tot + d) * 0.5


def scurve(x, A, mu, sigma):
    return 0.5 * A * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5 * A


def zcurve(x, A, mu, sigma):
    return -0.5 * A * erf((x - mu) / (np.sqrt(2) * sigma)) + 0.5 * A


def gauss(x, A, mu, sigma):
    return A * np.exp(-(x - mu) * (x - mu) / (2 * sigma * sigma))


def imap_bar(func, args, n_processes=None, unit='it', unit_scale=False):
    ''' Apply function (func) to interable (args) with progressbar
    '''
    p = mp.Pool(n_processes)
    res_list = []
    pbar = tqdm(total=len(args), unit=unit, unit_scale=unit_scale)
    for _, res in enumerate(p.imap(func, args)):
        pbar.update()
        res_list.append(res)
    pbar.close()
    p.close()
    p.join()
    return res_list


@numba.njit(locals={'cluster_shape': numba.int64})
def calc_cluster_shape(cluster_array):
    '''Boolean 8x8 array to number.
    '''
    cluster_shape = 0
    indices_x, indices_y = np.nonzero(cluster_array)
    for index in np.arange(indices_x.size):
        cluster_shape += 2**xy2d_morton(indices_x[index], indices_y[index])
    return cluster_shape


@numba.njit(numba.int64(numba.uint32, numba.uint32))
def xy2d_morton(x, y):
    ''' Tuple to number.

    See: https://stackoverflow.com/questions/30539347/
         2d-morton-code-encode-decode-64bits
    '''
    x = (x | (x << 16)) & 0x0000FFFF0000FFFF
    x = (x | (x << 8)) & 0x00FF00FF00FF00FF
    x = (x | (x << 4)) & 0x0F0F0F0F0F0F0F0F
    x = (x | (x << 2)) & 0x3333333333333333
    x = (x | (x << 1)) & 0x5555555555555555

    y = (y | (y << 16)) & 0x0000FFFF0000FFFF
    y = (y | (y << 8)) & 0x00FF00FF00FF00FF
    y = (y | (y << 4)) & 0x0F0F0F0F0F0F0F0F
    y = (y | (y << 2)) & 0x3333333333333333
    y = (y | (y << 1)) & 0x5555555555555555

    return x | (y << 1)


def get_threshold(x, y, n_injections):
    ''' Fit less approximation of threshold from s-curve.

        From: https://doi.org/10.1016/j.nima.2013.10.022

        Parameters
        ----------
        x, y : numpy array like
            Data in x and y
        n_injections: integer
            Number of injections
    '''

    # Sum over last dimension to support 1D and 2D hists
    M = y.sum(axis=len(y.shape) - 1)  # is total number of hits
    d = np.diff(x)[0]  # Delta x
    if not np.all(np.diff(x) == d):
        raise NotImplementedError('Threshold can only be calculated for equidistant x values!')
    return x.max() - (d * M).astype(float) / n_injections


def get_noise(x, y, n_injections):
    ''' Fit less approximation of noise from s-curve.

        From: https://doi.org/10.1016/j.nima.2013.10.022

        Parameters
        ----------
        x, y : numpy array like
            Data in x and y
        n_injections: integer
            Number of injections
    '''

    mu = get_threshold(x, y, n_injections)
    d = np.abs(np.diff(x)[0])

    mu1 = y[x < mu].sum()
    mu2 = (n_injections - y[x > mu]).sum()

    return d * (mu1 + mu2).astype(float) / n_injections * np.sqrt(np.pi / 2.)


def fit_scurve(scurve_data, scan_params, n_injections, sigma_0):
    '''
        Fit one pixel data with Scurve.
        Has to be global function for the multiprocessing module.

        Returns:
            (mu, sigma, chi2/ndf)
    '''

    # Typecast to working types
    scurve_data = np.array(scurve_data, dtype=float)
    # Scipy bug: fit does not work on float32 values, without any error message
    scan_params = np.array(scan_params, dtype=float)

    # Deselect masked values (== nan)
    x = scan_params[~np.isnan(scurve_data)]
    y = scurve_data[~np.isnan(scurve_data)]

    # Only fit data that is fittable
    if np.all(y == 0) or np.all(np.isnan(y)) or x.shape[0] < 3:
        return (0., 0., 0.)
    if y.max() < 0.2 * n_injections:
        return (0., 0., 0.)

    # Calculate data errors, Binomial errors
    min_err = np.sqrt(0.5 - 0.5 / n_injections)  # Set arbitrarly to error of 0.5 injections, needed for fit minimizers
    yerr = np.full_like(y, min_err, dtype=float)
    yerr[y <= n_injections] = np.sqrt(y[y <= n_injections] * (1. - y[y <= n_injections].astype(float) / n_injections))  # Binomial errors
    yerr[yerr < min_err] = min_err
    # Additional hits not following fit model set high error
    sel_bad = y > n_injections
    yerr[sel_bad] = (y - n_injections)[sel_bad]

    # Calculate threshold start value:
    mu = get_threshold(x=x, y=y, n_injections=n_injections)

    # Set fit start values
    p0 = [mu, sigma_0]

    # Bounds makes the optimizer 5 times slower and are therefore deactivated.
    # TODO: Maybe we find a better package?
    # bounds = [[x.min() - 5 * np.diff(x)[0], 0.05 * np.min(np.diff(x))],
    #           [x.max() + 5 * np.diff(x)[0], x.max() - x.min()]]

    # Special case: step function --> omit fit, set to result
    if not np.any(np.logical_and(y != 0, y != n_injections)):
        # All at n_inj or 0 --> set to mean between extrema
        return (mu + np.min(np.diff(x)) / 2., 0.01 * np.min(np.diff(x)), 1e-6)

    # Special case: Nothing to optimize --> set very good start values
    # Will trigger OptimizeWarning
    if np.count_nonzero(np.logical_and(y != 0, y != n_injections)) == 1:
        # Only one not at n_inj or 0 --> set mean to the point
        idx = np.ravel(np.where(np.logical_and(y != 0, y != n_injections)))[0]
        p0 = (x[idx], 0.1 * np.min(np.diff(x)))

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt = curve_fit(f=lambda x, mu, sigma: scurve(x, n_injections, mu, sigma),
                             xdata=x, ydata=y, p0=p0, sigma=yerr,
                             absolute_sigma=True if np.any(yerr) else False)[0]
            chi2 = np.sum((y - scurve(x, n_injections, popt[0], popt[1])) ** 2)
    except RuntimeError:  # fit failed
        return (0., 0., 0.)

    # Treat data that does not follow an S-Curve, every fit result is possible here but not meaningful
    max_threshold = x.max() + 5. * np.abs(popt[1])
    min_threshold = x.min() - 5. * np.abs(popt[1])
    if popt[1] <= 0 or not min_threshold < popt[0] < max_threshold:
        return (0., 0., 0.)

    return (popt[0], popt[1], chi2 / (y.shape[0] - 3 - 1))


def _mask_bad_data(scurve, n_injections):
    ''' This function tries to find the maximum value that is described by an S-Curve
        and maskes all values above.

        Multiple methods are used and the likelyhood that a bad S-Curve can happen
        by chance is valued. Especially these cases are treated:
        1. Additional noisy data
                       *
                      *
        n_inj-     ***
                  *
                 *
          0  - **
        2. Very noisy pixel leading to stuck pixels that see less hits
        n_inj-
                  *
                 * *
          0  - **   *
        3. Double S-Curve
                     *
        n_inj-     **     ***
                  *      *
                 *    * *
          0  - **      *
        4. Noisy data that looks bad but is ok (statistically possible)
        n_inj-          ***
                  * * *
                 * *
          0  - **

        Returns:
        --------
        numpy boolean array as a mask for good settings, True for bad settings
    '''

    scurve_mask = np.ones_like(scurve, dtype=np.bool)

    # Speedup, nothing to do if no slope
    if not np.any(scurve) or np.all(scurve == n_injections):
        return scurve_mask

    # Initialize result to best case (complete range can be used)
    idx_stop = scurve.shape[0]

    # Step 1: Find good maximum setting to restrict the range
    if np.any(scurve == n_injections):  # There is at least one setting seeing all injections
        idcs_stop = np.ravel(np.argwhere(scurve == n_injections))  # setting indices with all injections
        if len(idcs_stop) > 1:  # Several indexes
            # Find last index of the first region at n_injections
            if np.argmin(np.diff(idcs_stop) != 1) != 0:
                idx_stop = idcs_stop[np.argmin(np.diff(idcs_stop) != 1)] + 1
            else:  # Only one settled region, take last index
                idx_stop = idcs_stop[-1] + 1
        else:
            idx_stop = idcs_stop[-1] + 1
        scurve_cut = scurve[:idx_stop]
    elif scurve.max() > n_injections:  # Noisy pixels; no good maximum value; take latest non-noisy setting
        idx_stop = np.ravel(np.argwhere(scurve > n_injections))[0]
        scurve_cut = scurve[:idx_stop]
    else:  # n_injections not reached; scurve not fully recorded or pixel very noisy to have less hits
        scurve_cut = scurve

    # First measurement already with too many hits; no reasonable fit possible
    if idx_stop == 0:
        return scurve_mask

    # Check if first measurement is already noisy (> n_injections or more hits then following stuck settings)
    # Return if very noisy since no fit meaningful possible
    y_idx_sorted = scurve_cut.argsort()  # sort y value indeces to check for monotony
    if y_idx_sorted[0] != 0 and (scurve[0] > n_injections or (scurve[0] - scurve[1]) > 2 * np.sqrt(scurve[0] * (1. - float(scurve[0]) / n_injections))):
        return scurve_mask

    # Step 2: Find first local maximum
    sel = np.r_[True, scurve_cut[1:] >= scurve_cut[:-1]] & np.r_[scurve_cut[:-1] > scurve_cut[1:], True]  # Select local maximum; select last index if flat maximum, flat maximum expected for scurve
    y_max_idcs = np.arange(scurve_cut.shape[0])[sel]
    if np.any(y_max_idcs):  # Check for a maxima
        # Loop over maxima
        for y_max_idx in y_max_idcs:
            y_max = scurve_cut[y_max_idx]
            y_diff = np.diff(scurve_cut.astype(np.int))
            y_dist = (y_max.astype(np.int) - scurve_cut.astype(np.int)).astype(np.int)
            y_dist[y_max_idx + 1:] *= -1
            y_err = np.sqrt(scurve_cut * (1. - scurve_cut.astype(float) / n_injections))
            min_err = np.sqrt(0.5 - 0.5 / n_injections)
            y_err[y_err < min_err] = min_err
            # Only select settings where the slope cannot be explained by statistical fluctuations
            try:
                if np.any(y_diff < -2 * y_err[1:]):
                    idx_stop_diff = np.ravel(np.where(y_diff < -2 * y_err[1:]))[0]
                else:
                    idx_stop_diff = idx_stop
                idx_stop_dist = np.ravel(np.where(y_dist < -2 * y_err))[0]
                idx_stop = min(idx_stop_diff + 1, idx_stop_dist)
                break
            except IndexError:  # No maximum found
                pass

    scurve_mask[:idx_stop] = False

    return scurve_mask


def fit_scurves_multithread(scurves, scan_params, n_injections=None, invert_x=False, optimize_fit_range=False):
    ''' Fit Scurves on all available cores in parallel.

        Parameters
        ----------
        scurves: numpy array like
            Histogram with S-Curves. Channel index in the first and data in the second dimension.
        scan_params: array like
            Values used durig S-Curve scanning.
        n_injections: integer
            Number of injections
        invert_x: boolean
            True when x-axis inverted
        optimize_fit_range: boolean
            Reduce fit range of each S-curve independently to the S-Curve like range. Take full
            range if false
    '''

    scan_params = np.array(scan_params)  # Make sure it is numpy array

    if invert_x:
        scan_params *= -1

    if optimize_fit_range:
        scurve_mask = np.ones_like(scurves, dtype=np.bool)  # Mask to specify fit range for all scurves
        for i, scurve in enumerate(scurves):
            scurve_mask[i] = _mask_bad_data(scurve, n_injections)
        scurves_masked = np.ma.masked_array(scurves, scurve_mask)
    else:
        scurves_masked = np.ma.masked_array(scurves)

    # Calculate noise median for better fit start value
    logger.info("Calculate S-curve fit start parameters")
    sigmas = []
    for curve in tqdm(scurves_masked, unit=' S-curves', unit_scale=True):
        # Calculate from pixels with valid data (maximum = n_injections)
        if curve.max() == n_injections:
            if np.all(curve.mask == np.ma.nomask):
                x = scan_params
            else:
                x = scan_params[~curve.mask]

            sigma = get_noise(x=x, y=curve.compressed(), n_injections=n_injections)
            sigmas.append(sigma)
    sigma_0 = np.median(sigmas)
    sigma_0 = np.max([sigma_0, np.diff(scan_params).min() * 0.01])  # Prevent sigma = 0

    logger.info("Start S-curve fit on %d CPU core(s)", mp.cpu_count())
    partialfit_scurve = partial(fit_scurve,
                                scan_params=scan_params,
                                n_injections=n_injections,
                                sigma_0=sigma_0)

    result_list = imap_bar(partialfit_scurve, scurves_masked.tolist(), unit=' Fits', unit_scale=True)  # Masked array entries to list leads to NaNs
    result_array = np.array(result_list)
    logger.info("S-curve fit finished")

    thr = result_array[:, 0]
    if invert_x:
        thr *= -1
    sig = np.abs(result_array[:, 1])
    chi2ndf = result_array[:, 2]
    thr2D = np.reshape(thr, (512, 512))
    sig2D = np.reshape(sig, (512, 512))
    chi2ndf2D = np.reshape(chi2ndf, (512, 512))
    return thr2D, sig2D, chi2ndf2D


def fit_tot_response_multithread(tot_avg, scan_params):

    scurves_masked = np.ma.masked_array(tot_avg)

    logger.info("Start injection ToT calibration fit on %d CPU core(s)", mp.cpu_count())
    partialfit_tot_inj_func = partial(_fit_tot_response, scan_params=scan_params)

    result_list = imap_bar(partialfit_tot_inj_func, scurves_masked.tolist(), unit=' Fits', unit_scale=True)  # Masked array entries to list leads to NaNs
    result_array = np.array(result_list)
    logger.info("Fit finished")
    return np.reshape(result_array, (512, 512, 4))


def _fit_tot_response(data, scan_params):
    '''
        Fit one pixel data with injection Tot calibration function.
        Has to be global function for the multiprocessing module.

        Returns:
            (m, b, c, d, chi2/ndf)
    '''

    # Typecast to working types
    data = np.array(data, dtype=float)
    # Scipy bug: fit does not work on float32 values, without any error message
    scan_params = np.array(scan_params, dtype=float)

    # Deselect masked values (== nan)
    x = scan_params[~np.isnan(data)]
    y = data[~np.isnan(data)]
    yerr = np.ones(len(y)) / 2  # Assume +/- 0.5 because of integer values of ToT

    # Only fit data that is fittable
    if np.all(np.isnan(y)) or x.shape[0] < 3 or len(x[y > 0]) == 0:
        return (0., 0., 0., 0.)

    p0 = [40, 0.005, 0.1]

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", OptimizeWarning)
            popt = curve_fit(f=lambda x, a, b, d: _tot_response_func(x, a, b, d),
                             xdata=x[y > 0], ydata=y[y > 0], p0=p0, sigma=yerr[y > 0],
                             absolute_sigma=True)[0]
            chi2 = np.sum((y - _tot_response_func(x, *popt)) ** 2)
    except RuntimeError:  # fit failed
        return (0., 0., 0., 0.)

    return (*popt, chi2 / (y.shape[0] - 3 - 1))
