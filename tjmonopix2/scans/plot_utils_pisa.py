"""Utilities for plotting scripts."""
import re
import os
import subprocess
import tables as tb

__all__ = ['get_config_dict', 'split_long_text', 'get_commit']


def get_config_dict(h5_file):
    """Returns the configuration stored in an h5 as a dictionary of strings.

    Example usage:
        f = tb.open_file("path/to/file.h5")
        cfg = get_config_dict(f)
        chip_serial_number = cfg["configuration_in.chip.settings.chip_sn"]
    """
    if isinstance(h5_file, str):  # Also accepts a path to the file
        with tb.open_file(h5_file) as f:
            return get_config_dict(f)
    res = {}
    for cfg_path in ['configuration_in', 'configuration_out']:
        for node in h5_file.walk_nodes(f"/{cfg_path}"):
            if isinstance(node, tb.Table):
                directory = node._v_pathname.strip("/").replace("/", ".")
                try:
                    for a, b in node[:]:
                        res[f"{directory}.{str(a, encoding='utf8')}"] = str(b, encoding='utf8')
                except Exception:
                    pass  # print("Could not read node", node._v_pathname)
    return res


def _split_long_text(lns, max_chars):
    # Handle splitting multiple lines
    if not isinstance(lns, str) and len(lns) > 1:
        return sum((_split_long_text(x, max_chars) for x in lns), [])
    if not isinstance(lns, str):
        ln = lns[0]
    else:
        ln = lns
    # Check if single line is already short enough
    if len(ln) <= max_chars:
        return [ln]
    # Try to split on spaces
    ms = list(re.finditer(r'\s+', ln))
    ms.reverse()
    try:
        mm = next(m for m in ms if max_chars//2 < m.start() <= max_chars)
        return [ln[:mm.start()], *_split_long_text(ln[mm.end():], max_chars)]
    except StopIteration:
        pass
    # Try to split on word boundary
    ms = list(re.finditer(r'\W+', ln))
    ms.reverse()
    try:
        mm = next(m for m in ms if max_chars//2 < m.end() <= max_chars)
        return [ln[:mm.end()], *_split_long_text(ln[mm.end():], max_chars)]
    except StopIteration:
        pass
    # Split wherever necessary
    return [ln[:max_chars+1], *_split_long_text(ln[max_chars+1:], max_chars)]


def split_long_text(s, max_chars=80):
    """Splits a long text in multiple lines."""
    return "\n".join(_split_long_text(str(s).splitlines(), max_chars))


def get_commit():
    cwd = os.path.dirname(__file__)
    cp = subprocess.run(['git', 'log', '--pretty=format:%h', '-n', '1'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        encoding='utf8', cwd=cwd)
    return cp.stdout
