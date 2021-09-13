#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import yaml
import basil
import cocotb
import socketserver

import tjmonopix2

from basil.utils.sim.utils import cocotb_compile_and_run


def setup_cocotb(extra_defines=[]):
    if 'SIM' not in os.environ.keys():
        os.environ['SIM'] = 'verilator'

    if os.environ['SIM'] == 'verilator':
        patch_cocotb_makefile()

    # if hit_file is not None and len(hit_file) > 0:
    #     os.environ['SIMULATION_MODULES'] = yaml.dump({'tjmonopix2_daq.sim.HitDataFile': {
    #             'filename': hit_file
    #         }})
    tjmonopix2_path = os.path.dirname(tjmonopix2.__file__)  # tjmonopix2 package path
    top_dir = os.path.join(tjmonopix2_path, '..')  # dir with firmware etc. that are not part of package
    basil_dir = os.path.dirname(basil.__file__)

    simulation_modules = {}
    #simulation_modules["hit_drivers.HitDefault"] = {}
    simulation_modules['tjmonopix2.tests.Drive320Clock'] = {}
    os.environ["SIMULATION_MODULES"] = yaml.dump(simulation_modules)
    os.environ["SIMULATION_END_ON_DISCONNECT"] = "1"
    os.environ["COCOTB_REDUCED_LOG_FMT"] = "1"
    os.environ["SIMULATION_TRANSACTION_WAIT"] = str(25000 * 10)
    os.environ["SIMULATION_BUS_CLOCK"] = "0"

    # Find free port
    with socketserver.TCPServer(("localhost", 0), None) as s:
        free_port = s.server_address[1]

    os.environ["SIMULATION_PORT"] = str(free_port)

    cocotb_compile_and_run(
        sim_files=[tjmonopix2_path + "/tests/hdl/tb.v"],
        top_level='tb',
        sim_bus='basil.utils.sim.BasilSbusDriver',
        include_dirs=(
            top_dir,
            top_dir + "/firmware/src",
            top_dir + "/tjmonopix2/tests/hdl",
            basil_dir + "/firmware/modules",
            basil_dir + "/firmware/modules/utils",
        ),
        compile_args=[
            "-GVERSION_MAJOR=0",
            "-GVERSION_MINOR=1",
            "-GVERSION_PATCH=0",
            "-LDFLAGS {:s}/tjmonopix2/tests/hdl/libmonopix2.a".format(top_dir),
            "--hierarchical",
            "-Wno-COMBDLY",
            "-Wno-PINMISSING",
            "-Wno-fatal",
            "-j 4"],
        extra_defines=extra_defines,
        extra="EXTRA_ARGS = --trace-fst --trace-structs"
    )

    with open(os.path.join(tjmonopix2_path, 'system', 'bdaq53.yaml'), 'r') as f:
        cnfg = yaml.full_load(f)

    cnfg['transfer_layer'][0]['type'] = 'SiSim'
    cnfg['transfer_layer'][0]['init']['host'] = 'localhost'
    cnfg['transfer_layer'][0]['init']['port'] = free_port
    cnfg['transfer_layer'][0]['init']['timeout'] = 10000

    cnfg['hw_drivers'][0] = {'name': 'FIFO', 'type': 'bram_fifo', 'interface': 'intf', 'base_addr': 0x8000, 'base_data_addr': 0x80000000}
    for item in cnfg['hw_drivers']:
        if 'pulse_gen640' in item['type']:
            cnfg['hw_drivers'].remove(item)
    os.environ['SiSim'] = '1'

    return cnfg

def patch_cocotb_makefile():
    makefile_path = os.path.join(os.path.dirname(cocotb.__file__), 'share/makefiles/simulators')
    with open(os.path.join(makefile_path, 'Makefile.verilator'), 'r+') as makefile:
        content = makefile.read()
        makefile.seek(0)
        makefile.truncate()
        makefile.write(content.replace('--public-flat-rw ', ''))

def wait_for_sim(dut, repetitions=8):
    dut.write_command(dut.write_sync(write=False), repetitions=repetitions)
