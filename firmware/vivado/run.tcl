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
if {[info exists ::env(PYTHONPATH)]} {
    unset ::env(PYTHONPATH)
}
if {[info exists ::env(PYTHONHOME)]} {
    unset ::env(PYTHONHOME)
}
# Get rid of Vivado python (since Vivado 2021) in PATH and use python from calling shell
set env(PATH) [join [lsearch -inline -all -not -regexp [split $::env(PATH) ":"] (.*)lnx64\/python(.*)] ":"]

set vivado_dir [exec pwd]
set basil_dir [exec python -c "import basil, os; print(str(os.path.dirname(os.path.dirname(basil.__file__))))"]
set include_dirs [list $vivado_dir/../src $vivado_dir/../SiTCP $basil_dir/basil/firmware/modules $basil_dir/basil/firmware/modules/utils]

file mkdir ../bit reports


proc run_bit {part xdc_file size {suffix ""}} {
    global vivado_dir
    set src_dir $vivado_dir/../src
    
    set board_name [lindex [split [lindex [split $xdc_file '.'] 0] '_'] 0]
    set fpga_name [lindex [split [lindex [split $xdc_file '.'] 0] '_'] 1]
    set option [lindex [split [lindex [split $xdc_file '.'] 0] '_'] 2]
    if {$option != ""} {set option \_$option}
    if {$suffix != ""} {set suffix \_$suffix}
    set identifier $board_name\_$fpga_name$suffix

    set version [exec python -c "import pkg_resources; print(pkg_resources.get_distribution('tjmonopix2').version)"]
    set version_major [lindex [split $version '.'] 0]
    set version_minor [lindex [split $version '.'] 1]
    set version_patch [lindex [split $version '.'] 2]

    create_project -force -part $part $identifier designs

    read_verilog $src_dir/tjmonopix2.v
    read_verilog $src_dir/tjmonopix2_core.v
    read_edif $vivado_dir/../SiTCP/SiTCP_XC7K_32K_BBT_V110.ngc
    read_xdc $src_dir/$xdc_file
    read_xdc $src_dir/SiTCP.xdc
    global include_dirs

    synth_design -top tjmonopix2 -include_dirs $include_dirs -verilog_define [string toupper $board_name]=1 -verilog_define "SYNTHESIS=1" -generic VERSION_MAJOR=8'd$version_major -generic VERSION_MINOR=8'd$version_minor -generic VERSION_PATCH=8'd$version_patch
    opt_design
    place_design
    phys_opt_design
    route_design
    report_utilization -file "reports/report_utilization_$identifier.log"
    report_timing -file "reports/report_timing_$identifier.log"

    write_bitstream -force -bin_file -file $vivado_dir/../bit/tjmonopix2_$identifier
    write_cfgmem -format mcs -size 64 -interface SPIx4 -loadbit "up 0x0 $vivado_dir/../bit/tjmonopix2_$identifier.bit" -force -file $vivado_dir/../bit/tjmonopix2_$identifier
    close_project
}

#
# Create projects and bitfiles
#

if {$argc == 0} {
    # Standalone mode, directly calling tcl file
    #          FPGA model          constraints file    flash size  suffix
    #run_bit    xc7k160tfbg676-1    mio3_kx1.xdc        64          ""
    run_bit    xc7k160tffg676-2    bdaq53_kx2.xdc      64          ""
    #run_bit    xc7k160tfbg676-1    bdaq53_kx1.xdc      64          ""
    #run_bit    xc7k325tffg676-2    bdaq53_kx1.xdc      64          325
} else {
    # Build specific firmware by passing arguments
    # Suffix argument is not required, and default "" can not be read from command line arguments 
    if {($argc == 3) || ($argc == 4)} {
        run_bit {*}$argv
    } else {
        puts "ERROR: Invalid args"
    }
}

exit
