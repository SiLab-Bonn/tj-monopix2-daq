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

    create_project -force -part $part $board designs

    read_verilog $vivado_dir/../src/tjmonopix2_$board.v
    read_verilog $vivado_dir/../src/tjmonopix2_core.v
    read_edif $vivado_dir/../SiTCP/SiTCP_XC7K_32K_BBT_V110.ngc
    read_xdc $xdc_file
    read_xdc $vivado_dir/../SiTCP/SiTCP.xdc

    global include_dirs
    generate_target -verbose -force all [get_ips]

    synth_design -top tjmonopix2_mio3 -include_dirs $include_dirs -verilog_define "SYNTHESIS=1"
    opt_design
    place_design
    phys_opt_design
    route_design
    report_utilization
    report_timing -file "reports/report_timing.$board.log"
    write_bitstream -force -bin_file -file $vivado_dir/../bit/tjmonopix2_$board

    write_cfgmem -format mcs -size 64 -interface SPIx1 -loadbit "up 0x0 $vivado_dir/../bit/tjmonopix2_$board.bit" -force -file $vivado_dir/../bit/tjmonopix2_$board
    close_project
}


#########
#
# Create projects and bitfiles
#

#       FPGA type           board name	  constraints file                          flash size
run_bit xc7k160tfbg676-1    mio3          $vivado_dir/../src/tjmonopix2_mio3.xdc    64

exit
