# Firmware/Hardware tests

To run the simulated firmware and hardware with cocotb you need verilator version [v4.106](https://github.com/verilator/verilator/tree/v4.106). At the moment, this is the latest supported version.
The compiled chip RTL library (`/hdl/libmonopix2.a`) includes the whole chip with two double columns (for performance reasons).

## For persons with access to the chip RTL source code
You can compile the source code to a static and dynamic library for various simulation tools with the following command from the respective source folder:
```bash
verilator -cc -DTEST_COL=2 -Wno-fatal --timescale-override /1fs -I./SYNC -I./MATRIX_DAC -I./GCR -I./DIGITAL -I./CMD --protect-lib monopix2 -Mdir protected MONOPIX_TOP.sv 
make -j 4 -C protected -f VMONOPIX_TOP.mk
```
Consult the verilator documentation for further information on how to customize the compiled library.
