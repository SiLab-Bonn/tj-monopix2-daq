# ------------------------------------------------------------
# TJ-Monopix2: Simple hardware test
# Basic DAQ hardware and chip configuration
#
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import yaml
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2

# Initialization
with open(os.path.join('..', 'tjmonopix2', 'system', 'bdaq53.yaml'), 'r') as f:
    cnfg = yaml.full_load(f)

daq = BDAQ53(cnfg)
daq.init()

chip = TJMonoPix2(daq)
chip.init()

# Testing
chip.registers["ITHR"].write(50)  # Write registers using register object
chip._write_register(151, 25)  # Write registers directly

chip.masks["enable"][:2, :] = True  # Usage of masks as 2d-array with regular python indexing
chip.masks.update()

daq.rx_channels["rx0"].set_en(True)  # Enable RX module in firmware

daq.reset_fifo()  # Clear FIFO before reading data
raw_data = daq["FIFO"].get_data()  # Get FIFO contents
hit_data, reg_data = chip.interpret_data(raw_data)  # Interpret data

print(chip.registers["ITHR"].read())  # Read registers using register object
print(chip._get_register_value(151))  # Read registers (almost) directly

# Closing
daq.close()
