#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

from scan_threshold import ThresholdScan


scan_configuration = {
    'start_column': 482,
    'stop_column': 483,
    'start_row': 0,
    'stop_row': 512,

    'n_injections': 100,
    'VCAL_HIGH': 150,
    'VCAL_LOW_start': 130,
    'VCAL_LOW_stop': 90,
    'VCAL_LOW_step': -2
}

default_register_overrides = {
    "ITHR": 30,
    "IBIAS": 60,
    "ICASN": 8,
    "VCASP": 40,
    "VRESET": 100,
    "VCASC": 150,
}

sweeps = {  # REGISTER: (START, STOP, STEP)
    'ITHR': (25, 75, 5),
    'VRESET': (70, 255, 20),
    'IBIAS': (20, 60, 5),
    'VCASP': (100, 140, 5),
    'ICASN': (0, 16, 1)
}

if __name__ == "__main__":
    with open("output_data/scan_threshold_sweep.txt", "a") as ofs:
        for reg, sweep_range in sweeps.items():
            print(f"!!! Sweeping over {reg} in range {sweep_range}")
            for i in range(*sweep_range):
                print(f"!!! Sweeping over {reg}: {i}")
                register_overrides = default_register_overrides.copy()
                register_overrides[reg] = i
                with ThresholdScan(scan_config=scan_configuration, register_overrides=register_overrides) as scan:
                    scan.start()
                    print(f"{scan.output_filename} {reg}={i}", file=ofs)
