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

## Hardware configuration
### IP Address configuration
To support multiple readout boards on one PC, different IP addresses have to be used. The IP address can be changed using jumpers on the PMOD connector on both supported hardware platforms. The PMOD connector is located between the power connector and the USB port.

The default IP address is 192.168.10.**23**, but you can set the subnet in a range between 192.168.**10**.23 and 192.168.**25**.23.

**Procedure**:
1. Make sure, the readout system is not powered.
2. Locate PMOD Pin1 (indicated by a white dot on the PCB).
3. The IP is set by putting jumpers on the PMOD connector, which short pin 1+2, 3+4, 5+6 and 7+8. Standard binary counting is used:

      | PMOD_7+8 | PMOD_5+6 | PMOD_3+4 | PMOD_1+2 | IP_ADDRESS    |
      | -------- | -------- | -------- | -------- | ------------- |
      | 0        | 0        | 0        | 0        | 192.168.10.23 |
      | 0        | 0        | 0        | 1        | 192.168.11.23 |
      | ...      | ...      | ...      | ...      | ...           |
      | 1        | 1        | 1        | 0        | 192.168.24.23 |
      | 1        | 1        | 1        | 1        | 192.168.25.23 |

4. Double check, that you did not place the jumper in the wrong place!
5. Turn the readout system on and verify the setting by a ping to the new IP address.
