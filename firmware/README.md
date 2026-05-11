# TJ-Monopix2 Firmware

Firmware files for the DAQ system on a [BDAQ53 base board](https://gitlab.cern.ch/silab/bdaq53/-/wikis/Hardware/Readout-Hardware#bdaq53) with the commercial [Mercury+ KX2](https://www.enclustra.com/en/products/fpga-modules/mercury-kx2/) FPGA module.
 
## Features

- Simultaneous readout of
  - one chip (via DisplayPort on the base board) **or**
  - four chips (via RJ45 on the base board) at a time
- 640 MHz sampling TDC for the `HitOr` signal provided over a second DisplayPort cable 
- Communication with the EUDET and AIDA2020 trigger logic units
- 1 Gbps TCP/UDP connection to readout computer via [SiTCP](https://github.com/BeeBeansTechnologies/SiTCP_Netlist_for_Kintex7)

## Description

The firmware supports the differential communication mode of TJ-Monopix2 with a 160 MHz output data stream.
The FPGA pin configuration is compatible with all single-chip-boards.
Two variants of the firmware are provided within this codebase:
- Single-chip firmware that connects to the chip board over the DisplayPort connector DP5 / DP ML on the base board
- Quad-chip firmware that connects to up to four chips over the four RJ45 connectors

Careful: in the latter case, no connection is possible via the DisplayPort connector.
The distinction has to be made when compiling the firmware (see below), by default both versions are compiled when running `run.tcl` 

## Content

```
firmware/
│ src/
│ │ cmd/            Command encoder module
│ │ tjmono2_rx/     Data receiver (incl 8b10b decoder)
│ vivado/           TCL file for batch firmware compilation and generated projects
```


## Compilation

Clone [basil](https://github.com/SiLab-Bonn/basil) to any location and install it by running `pip install -e .` from its root folder.
<details>
  <summary>If you want to download SiTCP and patch it for yourself, click here</summary>

  Grab a copy of [SiTCP](https://github.com/BeeBeansTechnologies/SiTCP_Netlist_for_Kintex7) and move the `*.V` and `*.ngc` files to a newly created `firmware/SiTCP` folder in the cloned `tj-monopix2-daq` repository.
  Add a line `` `default_nettype wire`` in all `*.V` files right below the copyright notice in the beginning and before the first module declaration.
  This ensures compatibility with the rest of the verilog code.
</details>

### Using firmware manager
This is the easiest method to compile the firmware. Simply run
```bash
python manage_firmware.py --compile <platform>
```
where `<platform>` is usually `BDAQ53`. Make sure to have a Vivado binary in the current `PATH`.

### Using Vivado CLI or GUI
Use this method, if you are developing or debugging to check the output and see the logs.
You have to have SiTCP properly set up and patched (as explained above).
Run
```
vivado -mode batch -source run.tcl
```
from the `firmware/vivado` folder. The resulting bit files will be written to `firmware/bit`. This will build the firmware for multiple supported hardware platforms. If you want to build it for only one, pass the arguments that you can find in `run.tcl` as command line arguments, e.g.
```
vivado -mode batch -source run.tcl -tclargs xc7k160tffg676-2 bdaq53_kx2.xdc 64 _1RX
```

