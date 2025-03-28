"""Utilities for plotting scripts."""
import re
import os
import subprocess
import matplotlib.pyplot as plt
import matplotlib as mpl
import matplotlib.cm
import matplotlib.colors
from matplotlib.ticker import MaxNLocator
import numpy as np
import tables as tb

__all__ = [
    'FRONTENDS', 'TDAC_CMAP', 'get_config_dict', 'split_long_text',
    'get_commit', 'draw_summary', 'set_integer_ticks',
    'integer_ticks_colorbar', 'frontend_names_on_top', 'groupwise',
    'is_single_hit_event']

FRONTENDS = [
    # First col (included), last col (included), name
    (0, 223, 'Normal'),
    (224, 447, 'Cascode'),
    (448, 479, 'HV Casc.'),
    (480, 511, 'HV')]

TDAC_CMAP = mpl.colors.ListedColormap([mpl.cm.viridis(x/7) for x in range(8)])


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
        try:
            for node in h5_file.walk_nodes(f"/{cfg_path}"):
                if isinstance(node, tb.Table):
                    directory = node._v_pathname.strip("/").replace("/", ".")
                    try:
                        for a, b in node[:]:
                            res[f"{directory}.{str(a, encoding='utf8')}"] = str(b, encoding='utf8')
                    except Exception:
                        pass  # print("Could not read node", node._v_pathname)
        except tb.NoSuchNodeError:
            print("WARNING Input file does not have", cfg_path, "(incomplete acquisition?)")
        except Exception:
            print("WARNING Could not read", cfg_path, "from input file (incomplete acquisition?)")
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
    """Returns the hash of the current commit of the tj-monopix2-daq repo."""
    cwd = os.path.dirname(__file__)
    cp = subprocess.run(['git', 'log', '--pretty=format:%h', '-n', '1'],
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        encoding='utf8', cwd=cwd)
    return cp.stdout


def draw_summary(input_file_path, cfg):
    """Draws the summary 'plot' with the scan and chip info."""
    plt.annotate(
        split_long_text(
            f"{os.path.abspath(input_file_path)}\n"
            f"Chip =  {cfg.get('configuration_in.chip.settings.chip_sn')}\n"
            f"Script version = {get_commit()}\n\n"
            + ", ".join(
                f"{r} = {cfg.get(f'configuration_out.chip.registers.{r}')}"
                for r in [
                    "IBIAS", "ITHR", "ICASN", "IDB", "ITUNE", "VRESET", "VCASP",
                    "VCASC", "VCLIP", "VL", "VH", "ICOMP", "IDEL", "IRAM",
                    "FREEZE_START_CONF", "READ_START_CONF", "READ_STOP_CONF",
                    "LOAD_CONF", "FREEZE_STOP_CONF", "STOP_CONF"])
            + f"\n\n{cfg.get('configuration_in.scan.run_config.scan_id')}\n"
            + ", ".join(
                f"{x.split('.')[-1]} = {cfg[x]}" for x in cfg.keys()
                if x.startswith("configuration_in.scan.scan_config."))
        ), (0.5, 0.5), ha='center', va='center')
    plt.gca().set_axis_off()


def set_integer_ticks(*axis):
    """Makes an axis only use integer numbers for ticks.

    Examples:
        set_integer_ticks(plt.gca().xaxis)
        set_integer_ticks(plt.gca().xaxis, plt.gca().yaxis)
    """
    for a in axis:
        a.set_major_locator(MaxNLocator(integer=True))


def integer_ticks_colorbar(*args, **kwargs):
    """Like plt.colorbar(), but ensures the ticks are integers."""
    return plt.colorbar(*args, ticks=MaxNLocator(integer=True), **kwargs)


def frontend_names_on_top(ax=None):
    """Writes the names of the frontends on the top of the plot."""
    if ax is None:
        ax = plt.gca()
    ax2 = ax.twiny()
    xl, xh = ax.get_xlim()
    ax2.set_xlim(xl, xh)
    ax2.set_xticks([x for x in [0, 224, 448, 480, 512] if xl <= x <= xh])
    ax2.set_xticklabels('')
    lx, lt = [], []
    for fc, lc, name in FRONTENDS:
        if fc > xh or lc < xl:
            continue
        fc = max(xl, fc)
        lc = min(xh, lc + 1)
        lx.append((fc + lc) / 2)
        lt.append(name.replace(" Casc.", "$_C$"))
    ax2.set_xticks(lx, minor=True)
    ax2.set_xticklabels(lt, minor=True)


def groupwise(iterable, n):
    """Returns items from the iterable in groups of n, i.e. groupwise('abcdef', 3) -> 'abc', 'def'."""
    i = iter(iterable)
    def get():
        items = []
        for _ in range(n):
            try:
                items.append(next(i))
            except StopIteration:
                break
        return items
    r = get()
    while len(r):
        yield r
        r = get()


def is_single_hit_event(timestamps, window_us=3.2):
    """Returns a mask that selects hits from single-hit events only.

    An event here is defined as a series of hits happening within a
    window of window_us microseconds. The timestamp is used to
    determine the arrival time of the hit, which is very approximate
    and only works if the hit rate is low (i.e. no noisy pixels!).

    Example usage:
        f = tb.open_file("..._interpreted.h5")
        hits = f.root.Dut[:]
        mask = is_single_hit_event(hits["timestamp"])
        single_hits = hits[mask]
    """
    window = int(window_us * 40)
    diff = np.diff(np.concatenate(((-2**63,), timestamps, (2**63-1,))))
    diff_from_previous = diff[:-1]
    diff_from_next = diff[1:]
    min_diff = np.minimum(diff_from_next, diff_from_previous)
    return min_diff > window
