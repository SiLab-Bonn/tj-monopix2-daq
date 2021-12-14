# -----------------------------------------------------------
# Copyright (c) SILAB , Physics Institute, University of Bonn
# -----------------------------------------------------------
#
#   This script creates Vivado projects and bitfiles for the supported hardware platforms
#
#   Start vivado in tcl mode by typing:
#       vivado -mode tcl -source run.tcl
#

# Use current environment python instead of vivado included python
unset ::env(PYTHONPATH)
unset ::env(PYTHONHOME)

set vivado_dir [exec pwd]
set basil_dir [exec python -c "import basil, os; print(str(os.path.dirname(os.path.dirname(basil.__file__))))"]
set include_dirs [list $vivado_dir/../src $vivado_dir/../SiTCP $basil_dir/basil/firmware/modules $basil_dir/basil/firmware/modules/utils]

file mkdir ../bit reports


proc run_bit { part board xdc_file size} {
    global vivado_dir
    set board_name [string tolower $board]
    set version [exec python -c "import pkg_resources; print(pkg_resources.get_distribution('tjmonopix2').version)"]
    set version_major [lindex [split $version '.'] 0]
    set version_minor [lindex [split $version '.'] 1]
    set version_patch [lindex [split $version '.'] 2]

    create_project -force -part $part $board designs

    read_verilog $vivado_dir/../src/tjmonopix2.v
    read_verilog $vivado_dir/../src/tjmonopix2_core.v
    read_edif $vivado_dir/../SiTCP/SiTCP_XC7K_32K_BBT_V110.ngc
    read_xdc $xdc_file
    read_xdc $vivado_dir/../src/SiTCP.xdc
    global include_dirs

    synth_design -top tjmonopix2 -include_dirs $include_dirs -verilog_define "$board=1" -verilog_define "SYNTHESIS=1" -generic VERSION_MAJOR=8'd$version_major -generic VERSION_MINOR=8'd$version_minor -generic VERSION_PATCH=8'd$version_patch
    opt_design
    place_design
    phys_opt_design
    route_design
    report_utilization -file "reports/report_utilization_$board_name.log"
    report_timing -file "reports/report_timing_$board_name.log"

    write_bitstream -force -bin_file -file $vivado_dir/../bit/tjmonopix2_$board_name
    write_cfgmem -format mcs -size 64 -interface SPIx4 -loadbit "up 0x0 $vivado_dir/../bit/tjmonopix2_$board_name.bit" -force -file $vivado_dir/../bit/tjmonopix2_$board_name
    close_project
}

#
# Create projects and bitfiles
#

if {$argc == 0} {
    # Standalone mode, directly calling tcl file
    #       FPGA type           board name	  constraints file               flash size
    # run_bit xc7k160tfbg676-1    MIO3          $vivado_dir/../src/mio3.xdc      64
    run_bit xc7k160tffg676-2    BDAQ53        $vivado_dir/../src/bdaq53.xdc      64
    run_bit xc7k160tfbg676-1    BDAQ53        $vivado_dir/../src/bdaq53_kx1.xdc  64
    # run_bit xc7k325tffg676-2    BDAQ53        $vivado_dir/../src/bdaq53_kx1.xdc  64
} else {
    # Build specific firmware by passing arguments
    if {$argc == 4} {
        run_bit {*}$argv
    } else {
        puts "ERROR: Invalid args"
    }
}

exit
