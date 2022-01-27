# tj-monopix2-daq
[![Hardware tests](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/tests.yml/badge.svg)](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/tests.yml)

Data acquisition system for the TJ-Monopix2 pixel detector.

## Installation
Clone the repository and install the required dependencies with
```bash
pip install basil-daq coloredlogs GitPython numba numpy matplotlib tables tqdm scipy basil-daq PyYAML pyzmq
```
Afterwards install the package (editable) by running
```bash
pip install -e .
```
from the root folder.

## Firmware compilation
Clone [basil](https://github.com/SiLab-Bonn/basil) to any location and install it by running `pip install -e .` from its root folder.
<details>
  <summary>If you want to download SiTCP and patch it for yourself, click here</summary>

  Grab a copy of [SiTCP](https://github.com/BeeBeansTechnologies/SiTCP_Netlist_for_Kintex7) and move the `*.V` and `*.ngc` files to a newly created `firmware/SiTCP` folder in the cloned `tj-monopix2-daq` repository. Add a line `` `default_nettype wire`` in all of the `*.V` files right below the copyright notice in the beginning and before the first module declaration. This ensures compatibility with the rest of the verilog code.
</details>

### Using firmware manager
This is the recommended method to compile firmware. Simply run
```bash
python manage_firmware.py --compile <platform>
```
where `<platform>` is either `BDAQ53`, `BDAQ53_KX1` or `MIO3`. Make sure to have a Vivado binary in the current PATH.

### Using Vivado CLI
Run
```
vivado -mode batch -source run.tcl
```
from the `firmware/vivado` folder. The resulting bit files will be written to `firmware/bit`. This will build the firmware for multiple supported hardware platforms. If you want to build it for only one, pass the arguments that you can find in `run.tcl` as command line arguments, e.g.
```
vivado -mode batch -source run.tcl -tclargs xc7k160tffg676-2 bdaq53_kx2.xdc 64
```

## Firmware flashing
The easiest way to flash the firmware to the FPGA is again the firmware manager.
Run
```bash
python manage_firmware.py --firmware <path-to-bit-or-mcs-file>
```
and specify the path to the firmware file. The file type determines if it is written to FPGA (`.bit`) or persistent flash memory (`.mcs`). 

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
