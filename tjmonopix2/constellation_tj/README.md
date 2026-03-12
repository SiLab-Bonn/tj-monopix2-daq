---
title: "TJ-Monopix2"
description: "Satellite for controlling a TJ-Monopix2 using the BDAQ53 readout system"
category: "Readout Systems"
language: "Python"
parent_class: "TransmitterSatellite"
---

## Description

This satellite controls the TJ-Monopix2 using a [BDAQ53 readout board](https://doi.org/10.1016/j.nima.2020.164721). 
The satellite starts and stops expternal trigger scans, with various configuration parameters. 

Even though the satellite is designed for use with TJ-Monopix2 it can be easily changed for use with other BDAQ53 applications.

## Building

Clone the repository:

```sh
git clone https://github.com/SiLab-Bonn/tj-monopix2-daq
```

Install the [TJ-Monopix DAQ](https://github.com/SiLab-Bonn/tj-monopix2-daq) package:

```sh
cd tj-monopix2-daq
pip install ConstellationDAQ
pip install -e .
```

## Usage

Set the correct IP address in [tjmonopix2/system/bdaq53.yaml](https://github.com/SiLab-Bonn/tj-monopix2-daq/blob/development/tjmonopix2/system/bdaq53.yaml). Check the [README](https://github.com/SiLab-Bonn/tj-monopix2-daq/blob/development/README.md) for more information.

Start the satellite with:

```sh
python tjmonopix2/constellation/__main__.py -g testbeam -n chip0
```

## Parameters

| Configuration | Description | Type | Default Value |
|-----------|-------------|------| ------|
| `chip_sn` | (Required) Specify the serial number of chip. | String | None |
| `start_column` | (Required) Set the enabled start column. | Integer | None |
| `stop_column` | (Required) Set the enabled stop column. | Integer | None |
| `start_row` | (Required) Set the enabled start row. | Integer | None |
| `stop_row` | (Required) Set the enabled stop row. | Integer | None |
| `max_triggers` | (Required) Specify the maximum number of triggers for the external trigger scan| Integer | None |
| `scan_timeout` | (Optional) Set a timeout for the external scan. This is mutually exclusive to `max_triggers` | Float | None |
| `trigger_mode` | (Optional) Set triggering mode of the readout system. Available modes are `Aida` and `Eudet`. | String | `Eudet` |
| `output_directory` | (Optional) Set a specific output directory. If no directory is stated the default one is used. | String | None |
| `testbench_path` | (Optional) Use a specific testench yaml. If no directory is stated the default one is used. | String | None |
| `chip_config_file` | (Optional) Specify a chip configuration file. If no directory is stated the configuration from the last file is used. If the last file can not be found a default one is used. | String | None |
| `create_pdf` | (Optional) Generate a pdf with default plots from the scan. | Bool | True |
| `send_data` | (Optional) Send data to a `zmq` socket, for use with the [`online_monitor`](https://github.com/SiLab-Bonn/online_monitor). | String | `tcp://127.0.0.1:5500` |

The default testbench yaml can be found in [`tjmonopix2/testbench.yaml`](https://github.com/SiLab-Bonn/tj-monopix2-daq/blob/development/tjmonopix2/testbench.yaml).

### Configuration Example

An example configuration for the TJ-Monopix2 satellite which could be dropped into a Constellation configuration as a starting point:

```toml
[TJMonopix2.chip0]

chip_sn = 'W00R00'
start_column = 0
stop_column = 224
start_row = 0
stop_row = 512
max_triggers = 100000
create_pdf = false
```

## Metrics

The following metrics are distributed by this satellite and can be subscribed to. Timed metrics provide an interval in units of time, triggered metrics in number of calls.

| Metric | Description | Value Type | Interval |
|--------|-------------|------------|----------|
| `TRIGGER_NUMBER` | Number of recieved triggers | Int | 1s |

## Data

Data is saved in HDF5 format in the `output_directory`.
