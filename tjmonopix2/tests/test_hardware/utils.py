#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import socketserver
import typing

import basil
import yaml
from basil.utils.sim.utils import cocotb_compile_and_run

import tjmonopix2
from tjmonopix2 import utils
from tjmonopix2.system.bdaq53 import BDAQ53
from tjmonopix2.system.tjmonopix2 import TJMonoPix2


def setup_cocotb(extra_defines: list = []) -> dict:
    if "SIM" not in os.environ.keys():
        os.environ["SIM"] = "verilator"

    tjmonopix2_path = os.path.dirname(tjmonopix2.__file__)  # tjmonopix2 package path
    top_dir = os.path.join(
        tjmonopix2_path, ".."
    )  # dir with firmware etc. that are not part of package
    basil_dir = os.path.dirname(basil.__file__)

    simulation_modules = {}
    simulation_modules["tjmonopix2.tests.test_hardware.drivers.Drive320Clock"] = {}
    os.environ["SIMULATION_MODULES"] = yaml.dump(simulation_modules)
    os.environ["SIMULATION_END_ON_DISCONNECT"] = "1"
    os.environ["COCOTB_REDUCED_LOG_FMT"] = "1"
    os.environ["SIMULATION_TRANSACTION_WAIT"] = str(25000 * 10)
    os.environ["SIMULATION_BUS_CLOCK"] = "0"

    # Find free port
    with socketserver.TCPServer(("localhost", 0), None) as s:
        free_port = s.server_address[1]

    os.environ["SIMULATION_PORT"] = str(free_port)

    version = utils.get_software_version().split(".")

    cocotb_compile_and_run(
        sim_files=[tjmonopix2_path + "/tests/test_hardware/hdl/tb.v"],
        top_level="tb",
        sim_bus="basil.utils.sim.BasilSbusDriver",
        include_dirs=(
            top_dir + "/firmware/src",
            top_dir + "/tjmonopix2/tests/test_hardware/hdl",
            basil_dir + "/firmware/modules",
            basil_dir + "/firmware/modules/utils",
        ),
        compile_args=[
            "-DVERSION_MAJOR={:s}".format(version[0]),
            "-DVERSION_MINOR={:s}".format(version[1]),
            "-DVERSION_PATCH={:s}".format(version[2]),
            "-LDFLAGS {:s}/tjmonopix2/tests/test_hardware/hdl/libmonopix2.a".format(top_dir),
            "--hierarchical",
            "-Wno-fatal",
            "-Wno-COMBDLY",
            "-Wno-PINMISSING",
            "-Wno-LATCH",
        ],
        extra_defines=extra_defines,
    )

    with open(os.path.join(tjmonopix2_path, "system", "bdaq53.yaml"), "r") as f:
        cnfg = yaml.full_load(f)

    cnfg["transfer_layer"][0]["type"] = "SiSim"
    cnfg["transfer_layer"][0]["init"]["host"] = "localhost"
    cnfg["transfer_layer"][0]["init"]["port"] = free_port
    cnfg["transfer_layer"][0]["init"]["timeout"] = 10000

    cnfg["hw_drivers"][0] = {
        "name": "FIFO",
        "type": "bram_fifo",
        "interface": "intf",
        "base_addr": 0x8000,
        "base_data_addr": 0x80000000,
    }
    for item in cnfg["hw_drivers"]:
        if "pulse_gen640" in item["type"]:
            cnfg["hw_drivers"].remove(item)
    os.environ["SiSim"] = "1"

    return cnfg


def wait_for_sim(dut: BDAQ53, repetitions=8) -> None:
    dut.write_command(dut.write_sync(write=False), repetitions=repetitions)


def init_device(sim_config: dict) -> typing.Tuple[BDAQ53, TJMonoPix2]:
    daq = BDAQ53(conf=sim_config)
    daq.init()

    device = TJMonoPix2(daq=daq)
    device.init()

    daq.rx_channels["rx0"].set_en(True)  # Enable rx module in FPGA
    return daq, device
