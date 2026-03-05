#!/usr/bin/env python3
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------

import argparse
import os

import numpy as np
import tables as tb

from tjmonopix2.analysis import monitoring


def _get_scan_window(raw_h5):
    try:
        meta = raw_h5.root.meta_data[:]
        if meta.shape[0] == 0:
            return None, None
        scan_start = float(np.min(meta['timestamp_start']))
        scan_stop = float(np.max(meta['timestamp_stop']))
        return scan_start, scan_stop
    except Exception:
        return None, None


def _remove_group(h5, name):
    try:
        if hasattr(h5.root, name):
            h5.remove_node('/', name, recursive=True)
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser(description='Inject monitoring CSV data into interpreted h5 file.')
    parser.add_argument('--raw', required=True, help='Raw h5 file from scan')
    parser.add_argument('--interpreted', required=True, help='Interpreted h5 file to update')
    parser.add_argument('--testbench', default=None, help='Optional testbench.yaml to read monitoring config')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing /monitoring group')
    args = parser.parse_args()

    raw_path = args.raw.replace('.h5', '') + '.h5'
    interp_path = args.interpreted.replace('.h5', '') + '.h5'

    if not os.path.isfile(raw_path):
        raise SystemExit(f'Raw h5 not found: {raw_path}')
    if not os.path.isfile(interp_path):
        raise SystemExit(f'Interpreted h5 not found: {interp_path}')

    with tb.open_file(raw_path, 'r') as raw_h5:
        scan_start, scan_stop = _get_scan_window(raw_h5)
        if args.testbench:
            cfg = monitoring.load_monitoring_config_from_yaml(args.testbench)
        else:
            cfg = monitoring.load_monitoring_config_from_root(raw_h5.root)

        if not cfg or not cfg.get('enable', False):
            raise SystemExit('Monitoring config missing or disabled.')

        with tb.open_file(interp_path, 'r+') as interp_h5:
            if args.overwrite:
                _remove_group(interp_h5, 'monitoring')
            elif hasattr(interp_h5.root, 'monitoring'):
                raise SystemExit('Interpreted file already has /monitoring. Use --overwrite to replace it.')

            monitoring.add_monitoring_to_h5(raw_h5, interp_h5, cfg, scan_start, scan_stop)


if __name__ == '__main__':
    main()
