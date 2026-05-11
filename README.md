# tj-monopix2-daq
[![Hardware tests](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/tests.yml/badge.svg)](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/tests.yml)
[![Codestyle](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/codestyle.yml/badge.svg)](https://github.com/SiLab-Bonn/tj-monopix2-daq/actions/workflows/codestyle.yml)

Data acquisition system for the TJ-Monopix2 pixel detector.

# Installation
Clone the repository and install the required dependencies with
```bash
pip install basil-daq coloredlogs GitPython matplotlib numba numpy pyyaml pyzmq scipy tables tqdm 
```
Afterwards install the package (editable) by running
```bash
pip install -e .
```
from the root folder.

## Firmware compilation
See [here](firmware/README.md) for details about the firmware and how to compile it.

## Firmware flashing
The easiest way to flash the firmware to the FPGA is again the firmware manager.
Run
```bash
python manage_firmware.py --firmware <path-to-bit-or-mcs-file>
```
and specify the path to the firmware file. The file type determines if it is written to FPGA (`.bit`) or persistent flash memory (`.mcs`). 

## Hardware configuration
### Connecting a module
**BDAQ53 hardware platform:**
The DisplayPort cable has to be connected between the `DP1` (Data) plug on the carrier PCB and the `DP_ML` on the short side of the readout board.
The second DisplayPort plug on the carrier PCB is not required for operation and transmits only HitOr data. If needed, it has to be connected to the `DP_SL` close to the `DP_ML` on the long side of the readout board.

### Readout board IP address configuration
To support multiple readout boards on one PC, different IP addresses have to be used. The IP address can be changed using jumpers on the PMOD connector on both supported hardware platforms. The PMOD connector is located between the power connector and the USB port.

The default IP address (when using the firmware manager) is 192.168.10.**23**, but you can set the subnet in a range between 192.168.**10**.23 and 192.168.**25**.23.

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

# Usage
A `testbench.yaml` file containing information on the individual setup is required for operation. It is located in the `tjmonopix2` folder and contains an extensive list of configuration options that are documented there.

# Contributing
The `master` branch contains stable and well-tested code for reading out TJ-Monopix2. The `development` branch is not guaranteed to have stable and working code. If you want to contribute, create a feature branch off either of the mentioned branches and make a pull request against the respective branch when you have made progress on ongoing work or implemented a new feature.
