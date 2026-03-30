# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------

import ast
import csv
import glob
import json
import os
import re
import datetime
from collections import OrderedDict
from time import mktime
from time import sleep

import numpy as np
import tables as tb
import yaml

from tjmonopix2.system import logger


_LOG = logger.setup_derived_logger('Monitoring')


def _parse_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    s = str(value).strip().lower()
    if s in ['1', 'true', 'yes', 'y', 'on']:
        return True
    if s in ['0', 'false', 'no', 'n', 'off']:
        return False
    return default


def _parse_timestamp(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    # Try numeric first
    try:
        return float(s)
    except ValueError:
        pass
    # Try ISO / common datetime formats
    try:
        dt = datetime.datetime.fromisoformat(s)
        return mktime(dt.timetuple()) + 1e-6 * dt.microsecond
    except Exception:
        pass
    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f']:
        try:
            dt = datetime.datetime.strptime(s, fmt)
            return mktime(dt.timetuple()) + 1e-6 * dt.microsecond
        except Exception:
            continue
    return None


def _sanitize_field_name(name):
    sanitized = re.sub(r'[^0-9a-zA-Z_]+', '_', name.strip())
    if not sanitized:
        sanitized = 'field'
    if sanitized[0].isdigit():
        sanitized = 'f_' + sanitized
    return sanitized


def _extract_unit(label, fallback_name=None):
    if label:
        m = re.search(r'\[([^\]]+)\]', label)
        if m:
            return m.group(1)
    if fallback_name:
        if fallback_name.endswith('_V'):
            return 'V'
        if fallback_name.endswith('_I'):
            return 'A'
    return ''


def _parse_mapping_value(value):
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    s = str(value).strip()
    if not s:
        return {}
    # Try YAML, then literal eval
    try:
        parsed = yaml.safe_load(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    try:
        parsed = ast.literal_eval(s)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass
    # Serialized dicts from H5 config tables can look like:
    # "OrderedDict({...})" or nested OrderedDict objects.
    try:
        parsed = eval(s, {'__builtins__': {}}, {'OrderedDict': OrderedDict})  # noqa: S307
        if isinstance(parsed, dict):
            return dict(parsed)
    except Exception:
        pass
    return {}


def load_monitoring_config_from_root(root):
    try:
        table = root.configuration_in.bench.monitoring
    except Exception:
        return None

    cfg = {}
    for row in table:
        key = row['attribute']
        value = row['value']
        if isinstance(key, bytes):
            key = key.decode('utf-8')
        if isinstance(value, bytes):
            value = value.decode('utf-8')
        cfg[key] = value

    if not cfg:
        return None

    out = {}
    out['enable'] = _parse_bool(cfg.get('enable', False))
    out['include_in_pdf'] = _parse_bool(cfg.get('include_in_pdf', True))
    out['time_margin_s'] = float(cfg.get('time_margin_s', 0.0) or 0.0)
    out['env'] = _parse_mapping_value(cfg.get('env'))
    out['power'] = _parse_mapping_value(cfg.get('power'))
    return out


def load_monitoring_config_from_yaml(path):
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    cfg = data.get('monitoring')
    if not isinstance(cfg, dict):
        return None
    out = {}
    out['enable'] = _parse_bool(cfg.get('enable', False))
    out['include_in_pdf'] = _parse_bool(cfg.get('include_in_pdf', True))
    out['time_margin_s'] = float(cfg.get('time_margin_s', 0.0) or 0.0)
    out['env'] = cfg.get('env', {})
    out['power'] = cfg.get('power', {})
    return out


def _iter_csv_paths(cfg):
    if not cfg:
        return []
    if isinstance(cfg, str):
        return [cfg]
    if isinstance(cfg, (list, tuple)):
        return list(cfg)

    csv_path = cfg.get('csv_path')
    if csv_path:
        return [csv_path]
    csv_dir = cfg.get('csv_dir')
    if not csv_dir:
        return []
    pattern = cfg.get('pattern', '*.csv')
    return sorted(glob.glob(os.path.join(csv_dir, pattern)))


def _read_csv_data(paths, timestamp_column, columns_map, scan_start, scan_stop):
    timestamps = []
    series = {k: [] for k in columns_map.keys()}
    labels = {k: columns_map[k] for k in columns_map.keys()}

    for path in paths:
        if not os.path.isfile(path):
            _LOG.warning('Monitoring CSV not found: %s', path)
            continue
        with open(path, 'r', newline='') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                continue

            header_map = {h.strip(): i for i, h in enumerate(header)}
            if timestamp_column not in header_map:
                _LOG.warning('Timestamp column %s not found in %s', timestamp_column, path)
                continue

            col_indices = {}
            for out_name, col_name in columns_map.items():
                if col_name not in header_map:
                    _LOG.warning('Column %s not found in %s', col_name, path)
                    continue
                col_indices[out_name] = header_map[col_name]

            ts_idx = header_map[timestamp_column]

            for row in reader:
                if not row:
                    continue
                ts = _parse_timestamp(row[ts_idx])
                if ts is None:
                    continue
                if scan_start is not None and ts < scan_start:
                    continue
                if scan_stop is not None and ts > scan_stop:
                    continue
                timestamps.append(ts)
                for out_name in series.keys():
                    idx = col_indices.get(out_name)
                    if idx is None:
                        series[out_name].append(np.nan)
                        continue
                    try:
                        series[out_name].append(float(row[idx]))
                    except Exception:
                        series[out_name].append(np.nan)

    if not timestamps:
        return None

    order = np.argsort(np.array(timestamps))
    ts_arr = np.array(timestamps, dtype=np.float64)[order]
    series_arr = {}
    for k, v in series.items():
        series_arr[k] = np.array(v, dtype=np.float64)[order]

    return ts_arr, series_arr, labels


def _prepare_columns(cfg, default_timestamp, default_columns):
    timestamp_column = cfg.get('timestamp_column', default_timestamp)
    columns_map = cfg.get('columns', default_columns)
    if not isinstance(columns_map, dict):
        columns_map = _parse_mapping_value(columns_map)
    return timestamp_column, columns_map


def _write_monitoring_table(out_file, group, name, ts_arr, series_arr, labels):
    fields = [('timestamp', np.float64)]
    field_map = {}
    unit_map = {}
    for key in series_arr.keys():
        field = _sanitize_field_name(key)
        field_map[field] = labels.get(key, key)
        unit_map[field] = _extract_unit(labels.get(key, key), fallback_name=key)
        fields.append((field, np.float64))

    table = out_file.create_table(group, name=name, description=np.dtype(fields))

    data = np.zeros(shape=(len(ts_arr),), dtype=np.dtype(fields))
    data['timestamp'] = ts_arr
    for key in series_arr.keys():
        field = _sanitize_field_name(key)
        data[field] = series_arr[key]

    table.append(data)
    table.flush()

    table.attrs.label_map = json.dumps(field_map)
    table.attrs.unit_map = json.dumps(unit_map)
    return table, field_map, unit_map


def _append_summary_rows(summary_table, source, field_map, unit_map, series_arr):
    for field, label in field_map.items():
        values = series_arr.get(label, None)
        if values is None:
            # Try using label as key (preferred), else fallback to field
            values = series_arr.get(field, None)
        if values is None:
            continue
        if not np.isfinite(values).any():
            continue
        mean = np.nanmean(values)
        min_v = np.nanmin(values)
        max_v = np.nanmax(values)
        row = summary_table.row
        # Store UTF-8 bytes to support labels with non-ASCII symbols (e.g. "°C")
        row['attribute'] = str(label).encode('utf-8')
        row['mean'] = mean
        row['min'] = min_v
        row['max'] = max_v
        row['unit'] = str(unit_map.get(field, '')).encode('utf-8')
        row['source'] = str(source).encode('utf-8')
        row.append()
    summary_table.flush()


def _select_best_csv(paths, scan_start):
    if not paths:
        return []
    if scan_start is None:
        return sorted(paths)
    best = None
    best_dist = None
    for path in paths:
        try:
            with open(path, 'r', newline='') as f:
                reader = csv.reader(f)
                header = next(reader)
                if not header:
                    continue
                row = next(reader, None)
                if not row:
                    continue
                # Try to detect timestamp column in this file
                col = None
                for candidate in ['timestamp', 'Time [s]']:
                    if candidate in header:
                        col = header.index(candidate)
                        break
                if col is None:
                    continue
                ts = _parse_timestamp(row[col])
                if ts is None:
                    continue
                dist = abs(ts - scan_start)
                if best_dist is None or dist < best_dist:
                    best_dist = dist
                    best = path
        except Exception:
            continue
    if best:
        return [best]
    return sorted(paths)


def add_monitoring_to_h5(in_file, out_file, monitoring_cfg, scan_start, scan_stop):
    if not monitoring_cfg or not monitoring_cfg.get('enable', False):
        return

    wait_s = float(monitoring_cfg.get('wait_for_csv_s', 0.0) or 0.0)
    if wait_s > 0:
        sleep(wait_s)

    time_margin = float(monitoring_cfg.get('time_margin_s', 0.0) or 0.0)
    if scan_start is not None:
        scan_start = scan_start - time_margin
    if scan_stop is not None:
        scan_stop = scan_stop + time_margin

    mon_group = out_file.create_group(out_file.root, 'monitoring', 'Monitoring data')
    mon_group._v_attrs['scan_start'] = scan_start
    mon_group._v_attrs['scan_stop'] = scan_stop

    summary_table = out_file.create_table(
        mon_group,
        name='summary',
        title='Monitoring summary statistics',
        description=np.dtype([
            ('attribute', 'S64'),
            ('mean', np.float64),
            ('min', np.float64),
            ('max', np.float64),
            ('unit', 'S16'),
            ('source', 'S16'),
        ])
    )

    # Power monitoring
    power_cfg = monitoring_cfg.get('power') or {}
    if power_cfg:
        ts_col, columns_map = _prepare_columns(
            power_cfg,
            default_timestamp='timestamp',
            default_columns={
                'HV_V': 'HV_V',
                'HV_I': 'HV_I',
                'PWELL_V': 'PWELL_V',
                'PWELL_I': 'PWELL_I',
                'PSUB_PWELL_V': 'PSUB_PWELL_V',
                'PSUB_PWELL_I': 'PSUB_PWELL_I',
            }
        )
        paths = _iter_csv_paths(power_cfg)
        paths = _select_best_csv(paths, scan_start)
        data = _read_csv_data(paths, ts_col, columns_map, scan_start, scan_stop)
        if data:
            ts_arr, series_arr, labels = data
            table, field_map, unit_map = _write_monitoring_table(out_file, mon_group, 'power', ts_arr, series_arr, labels)
            _append_summary_rows(summary_table, 'power', field_map, unit_map, {labels[k]: v for k, v in series_arr.items()})
            mon_group._v_attrs['power_sources'] = json.dumps(paths)

    # Environmental monitoring
    env_cfg = monitoring_cfg.get('env') or {}
    if env_cfg:
        ts_col, columns_map = _prepare_columns(
            env_cfg,
            default_timestamp='Time [s]',
            default_columns={
                'NTC_C': 'NTC [°C]'
            }
        )
        paths = _iter_csv_paths(env_cfg)
        paths = _select_best_csv(paths, scan_start)
        data = _read_csv_data(paths, ts_col, columns_map, scan_start, scan_stop)
        if data:
            ts_arr, series_arr, labels = data
            table, field_map, unit_map = _write_monitoring_table(out_file, mon_group, 'env', ts_arr, series_arr, labels)
            _append_summary_rows(summary_table, 'env', field_map, unit_map, {labels[k]: v for k, v in series_arr.items()})
            mon_group._v_attrs['env_sources'] = json.dumps(paths)
