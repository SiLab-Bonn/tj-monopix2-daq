#
# ------------------------------------------------------------
# Copyright (c) All rights reserved
# SiLab, Institute of Physics, University of Bonn
# ------------------------------------------------------------
#

import os
import cocotb


def patch_cocotb_makefile():
    makefile_path = os.path.join(
        os.path.dirname(cocotb.__file__), "share/makefiles/simulators"
    )
    with open(os.path.join(makefile_path, "Makefile.verilator"), "r+") as makefile:
        content = makefile.read()
        makefile.seek(0)
        makefile.truncate()
        makefile.write(content.replace("--public-flat-rw ", ""))


def wait_for_sim(dut, repetitions=8):
    dut.write_command(dut.write_sync(write=False), repetitions=repetitions)
