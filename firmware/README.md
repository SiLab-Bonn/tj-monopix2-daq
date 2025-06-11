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

todo
