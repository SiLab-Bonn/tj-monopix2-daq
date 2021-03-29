# tj-monopix2-daq

## Installation
TBD

## Firmware compilation
Grab a copy of [SiTCP](https://github.com/BeeBeansTechnologies/SiTCP_Netlist_for_Kintex7) and move the `*.V` and `*.ngc` files to a newly created `firmware/SiTCP` folder in the cloned `tj-monopix2-daq` repository. Add a line `` `default_nettype wire`` in all of the `*.V` files right below the copyright notice in the beginning and before the first module declaration. This ensures compatibility with the rest of the verilog code.

Next, clone the [basil](https://github.com/SiLab-Bonn/basil) directory to any location and install it by running `python setup.py develop` from its root folder.
Now everything should be set up for compiling the firmware. To do so, run
```
vivado -mode tcl -source run.tcl
```
from the `firmware/vivado` folder. The resulting bit file will be written to `firmware/bit`
