#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

'''
    This module takes care of the mask shifting and injection of the supported chips
    in order to keep actual scans cleaner.
'''


def shift_and_inject(scan, n_injections, pbar=None, scan_param_id=0, masks=['injection', 'enable'], pattern='default', cache=False, skip_empty=True):
    ''' Regular mask shift and analog injection function.

    Parameters:
    ----------
        scan : scan object
            Scan object
        n_injections : int
            Number of injections per loop.
        pbar : tqdm progressbar
            Tqdm progressbar
        scan_param_id : int
            Scan parameter id of actual scan loop
        masks : list
            List of masks ('injection', 'enable', 'hitbus') which should be shifted during scan loop.
        pattern : string
            Injection pattern ('default', 'hitbus', ...)
        cache : boolean
            If True use mask caching for speedup. Default is False.
        skip_empty : boolean
            If True skip empty mask steps for speedup. Default is True.
    '''
    for fe, active_pixels in scan.chip.masks.shift(masks=masks, pattern=pattern, cache=cache, skip_empty=skip_empty):
        if not fe == 'skipped':
            scan.chip.inject(PulseStartCnfg=1, PulseStopCnfg=512, repetitions=n_injections, latency=1400)
        if pbar is not None:
            pbar.update(1)


def get_scan_loop_mask_steps(scan, pattern='default'):
    ''' Returns total number of mask steps for specific pattern

    Parameters:
    ----------
        scan : scan object
            Scan object
        pattern : string
            Injection pattern ('default', 'hitbus', ...)
    '''

    return scan.chip.masks.get_mask_steps(pattern=pattern)
