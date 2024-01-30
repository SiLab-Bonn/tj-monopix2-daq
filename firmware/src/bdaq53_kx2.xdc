# ------------------------------------------------------------
#  Copyright (c) SILAB , Physics Institute of Bonn University
# ------------------------------------------------------------
#
#   Constraints for the BDAQ53 PCB with the Mercury+ KX2(160T-2) FPGA board
#

# Clock domains
# CLK_SYS: 100 MHz, from xtal oscillator
# -> PLL2: CLK8_PLL
#          CLK16_PLL: RX
#          CLK32_PLL: RX
#          CLK40_PLL: PULSER, TDC, TLU
#          CLK160_PLL: TLU, TDC
#          CLK320_PLL: TLU, TDC
# -> PLL1: BUS_CLK_PLL: 142.86 MHz, main system clock (7 ns)
#          CLK125PLLTX, Ethernet
#          CLK125PLLTX90: Ethernet
# CLK_MGT_REF: 160 MHz, from Si570 programmable oscilaltor
# ->       CMDCLK: 160 MHz, command encoder
# CLK_RGMII_RX: 125 MHz, from Ethernet chip

# Clock inputs
create_clock -period 10.000 -name CLK_SYS -add [get_ports FCLK_IN]
create_clock -period 8.000 -name CLK_RGMII_RX -add [get_ports rgmii_rxc]
create_clock -period 6.250 -name CLK_MGT_REF -add [get_ports MGT_REFCLK0_P]

# Derived clocks
create_generated_clock -name I2C_CLK -source [get_pins PLLE2_BASE_inst_comm/CLKOUT0] -divide_by 1600 [get_pins i_tjmonopix2_core/i_clock_divisor_i2c/CLOCK_reg/Q]
create_generated_clock -name rgmii_txc -source [get_pins rgmii/ODDR_inst/C] -divide_by 1 [get_ports rgmii_txc]

# Exclude asynchronous clock domains from timing (handled by CDCs)
set_clock_groups -asynchronous -group BUS_CLK_PLL -group I2C_CLK -group {CLK125PLLTX CLK125PLLTX90} -group {CLK320_PLL CLK160_PLL CLK40_PLL CLK32_PLL CLK16_PLL} -group [get_clocks -include_generated_clocks CLK_MGT_REF] -group CLK_RGMII_RX

# SiTCP
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX] -to [get_ports {rgmii_txd[*]}] 4.000
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX] -to [get_ports rgmii_tx_ctl] 4.000
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX90] -to [get_ports rgmii_txc] 4.000
set_property ASYNC_REG true [get_cells sitcp/SiTCP/GMII/GMII_TXCNT/irMacPauseExe_0]
set_property ASYNC_REG true [get_cells sitcp/SiTCP/GMII/GMII_TXCNT/irMacPauseExe_1]

# LED
# LED 0..3 are onboard LEDs: Bank 32, 33 running at 1.5 V)
set_property PACKAGE_PIN U9 [get_ports {LED[0]}]
set_property IOSTANDARD LVCMOS15 [get_ports {LED[0]}]
set_property PACKAGE_PIN V12 [get_ports {LED[1]}]
set_property IOSTANDARD LVCMOS15 [get_ports {LED[1]}]
set_property PACKAGE_PIN V13 [get_ports {LED[2]}]
set_property IOSTANDARD LVCMOS15 [get_ports {LED[2]}]
set_property PACKAGE_PIN W13 [get_ports {LED[3]}]
set_property IOSTANDARD LVCMOS15 [get_ports {LED[3]}]
# LED 4..7 are LEDs on the BDAQ53 base board. They have pull-ups to 1.8 V.
set_property PACKAGE_PIN E21 [get_ports {LED[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {LED[4]}]
set_property PACKAGE_PIN E22 [get_ports {LED[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {LED[5]}]
set_property PACKAGE_PIN D21 [get_ports {LED[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {LED[6]}]
set_property PACKAGE_PIN C22 [get_ports {LED[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {LED[7]}]
set_property SLEW SLOW [get_ports LED*]

# PMOD
#  ____________
# |1 2 3 4  G +|  First PMOD channel (4 signal lines, ground and vcc)
# |7_8_9_10_G_+|  Second PMOD channel ("")
#
# PMOD connector Pin10-->PMOD0; Pin9-->PMOD1; Pin8-->PMOD2; Pin7-->PMOD3;
set_property PACKAGE_PIN AC23 [get_ports {PMOD[0]}]
set_property PACKAGE_PIN AC24 [get_ports {PMOD[1]}]
set_property PACKAGE_PIN W25 [get_ports {PMOD[2]}]
set_property PACKAGE_PIN W26 [get_ports {PMOD[3]}]
# PMOD connector Pin4-->PMOD4; Pin3-->PMOD5; Pin2-->PMOD6; Pin1-->PMOD7;
set_property PACKAGE_PIN U26 [get_ports {PMOD[4]}]
set_property PACKAGE_PIN V26 [get_ports {PMOD[5]}]
set_property PACKAGE_PIN AE25 [get_ports {PMOD[6]}]
set_property PACKAGE_PIN AD24 [get_ports {PMOD[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports PMOD*]
# Pull down the PMOD pins which are used as inputs
set_property PULLDOWN true [get_ports {PMOD[0]}]
set_property PULLDOWN true [get_ports {PMOD[1]}]
set_property PULLDOWN true [get_ports {PMOD[2]}]
set_property PULLDOWN true [get_ports {PMOD[3]}]

# ------ Si570 / SMA input CLK
set_property PACKAGE_PIN H6 [get_ports MGT_REFCLK0_P]
set_property PACKAGE_PIN H5 [get_ports MGT_REFCLK0_N]
set_property PACKAGE_PIN K6 [get_ports MGT_REFCLK1_P]
set_property PACKAGE_PIN K5 [get_ports MGT_REFCLK1_N]

# ------ CLK Mux
set_property PACKAGE_PIN D23 [get_ports MGT_REF_SEL]
set_property IOSTANDARD LVCMOS33 [get_ports MGT_REF_SEL]
set_property PULLUP true [get_ports MGT_REF_SEL]

# ------ FCLK (100 MHz)
set_property PACKAGE_PIN AA4 [get_ports FCLK_IN]
set_property IOSTANDARD LVCMOS15 [get_ports FCLK_IN]

# ------ Button & Spare & more - omitted for now
#Reset push button
set_property PACKAGE_PIN G9 [get_ports RESET_BUTTON]
set_property IOSTANDARD LVCMOS25 [get_ports RESET_BUTTON]
set_property PULLUP true [get_ports RESET_BUTTON]

# I2C
set_property PACKAGE_PIN L23 [get_ports I2C_SCL]
set_property PACKAGE_PIN C24 [get_ports I2C_SDA]
set_property IOSTANDARD LVCMOS33 [get_ports I2C_*]
set_property SLEW SLOW [get_ports I2C_*]

# EEPROM (SPI for SiTCP)
set_property PACKAGE_PIN A20 [get_ports EEPROM_CS]
set_property PACKAGE_PIN B20 [get_ports EEPROM_SK]
set_property PACKAGE_PIN A24 [get_ports EEPROM_DI]
set_property PACKAGE_PIN A23 [get_ports EEPROM_DO]
set_property IOSTANDARD LVCMOS33 [get_ports EEPROM_*]

# LEMO
set_property PACKAGE_PIN AB21 [get_ports LEMO_TX0]
set_property PACKAGE_PIN AD25 [get_ports LEMO_TX1]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_TX*]
set_property SLEW FAST [get_ports LEMO_TX*]
set_property PACKAGE_PIN AB22 [get_ports LEMO_RX0]
set_property PACKAGE_PIN AD23 [get_ports LEMO_RX1]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_RX*]

# TLU
set_property PACKAGE_PIN AE23 [get_ports RJ45_TRIGGER]
set_property PACKAGE_PIN U22 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_TRIGGER]

# SITCP
set_property SLEW FAST [get_ports mdio_phy_mdc]
set_property IOSTANDARD LVCMOS33 [get_ports mdio_phy_mdc]
set_property PACKAGE_PIN B25 [get_ports mdio_phy_mdc]

set_property SLEW FAST [get_ports mdio_phy_mdio]
set_property IOSTANDARD LVCMOS33 [get_ports mdio_phy_mdio]
set_property PACKAGE_PIN B26 [get_ports mdio_phy_mdio]

set_property SLEW FAST [get_ports phy_rst_n]
set_property IOSTANDARD LVCMOS33 [get_ports phy_rst_n]
#M20 is routed to Connector C. The Ethernet PHY on th KX2 board has NO reset connection to an FPGA pin
set_property PACKAGE_PIN M20 [get_ports phy_rst_n]

set_property IOSTANDARD LVCMOS33 [get_ports rgmii_rxc]
set_property PACKAGE_PIN G22 [get_ports rgmii_rxc]

set_property IOSTANDARD LVCMOS33 [get_ports rgmii_rx_ctl]
set_property PACKAGE_PIN F23 [get_ports rgmii_rx_ctl]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_rxd[0]}]
set_property PACKAGE_PIN H23 [get_ports {rgmii_rxd[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_rxd[1]}]
set_property PACKAGE_PIN H24 [get_ports {rgmii_rxd[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_rxd[2]}]
set_property PACKAGE_PIN J21 [get_ports {rgmii_rxd[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_rxd[3]}]
set_property PACKAGE_PIN H22 [get_ports {rgmii_rxd[3]}]

set_property SLEW FAST [get_ports rgmii_txc]
set_property IOSTANDARD LVCMOS33 [get_ports rgmii_txc]
set_property PACKAGE_PIN K23 [get_ports rgmii_txc]

set_property SLEW FAST [get_ports rgmii_tx_ctl]
set_property IOSTANDARD LVCMOS33 [get_ports rgmii_tx_ctl]
set_property PACKAGE_PIN J23 [get_ports rgmii_tx_ctl]

set_property SLEW FAST [get_ports {rgmii_txd[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_txd[0]}]
set_property PACKAGE_PIN J24 [get_ports {rgmii_txd[0]}]
set_property SLEW FAST [get_ports {rgmii_txd[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_txd[1]}]
set_property PACKAGE_PIN J25 [get_ports {rgmii_txd[1]}]
set_property SLEW FAST [get_ports {rgmii_txd[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_txd[2]}]
set_property PACKAGE_PIN L22 [get_ports {rgmii_txd[2]}]
set_property SLEW FAST [get_ports {rgmii_txd[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {rgmii_txd[3]}]
set_property PACKAGE_PIN K22 [get_ports {rgmii_txd[3]}]

# DP_ML ("DP5") connected to SelectIOs
set_property PACKAGE_PIN A18 [get_ports {DP5_GPIO_P[0]}]
set_property PACKAGE_PIN A19 [get_ports {DP5_GPIO_N[0]}]
set_property PACKAGE_PIN C19 [get_ports {DP5_GPIO_P[1]}]
set_property PACKAGE_PIN B19 [get_ports {DP5_GPIO_N[1]}]
set_property PACKAGE_PIN E18 [get_ports {DP5_GPIO_P[2]}]
set_property PACKAGE_PIN D18 [get_ports {DP5_GPIO_N[2]}]
set_property PACKAGE_PIN B17 [get_ports {DP5_GPIO_P[3]}]
set_property PACKAGE_PIN A17 [get_ports {DP5_GPIO_N[3]}]
set_property IOSTANDARD LVDS_25 [get_ports DP5_GPIO*]
set_property PACKAGE_PIN C16 [get_ports DP5_GPIO_AUX_P]
set_property PACKAGE_PIN B16 [get_ports DP5_GPIO_AUX_N]
set_property IOSTANDARD LVDS_25 [get_ports DP5_GPIO_AUX*]

# DP_ML ("DP1") connected to SelectIOs
# set_property PACKAGE_PIN J4 [get_ports {DP1_GPIO_P[0]}]
# set_property PACKAGE_PIN J3 [get_ports {DP1_GPIO_N[0]}]
# set_property PACKAGE_PIN L4 [get_ports {DP1_GPIO_P[1]}]
# set_property PACKAGE_PIN L3 [get_ports {DP1_GPIO_N[1]}]
# set_property PACKAGE_PIN N4 [get_ports {DP1_GPIO_P[2]}]
# set_property PACKAGE_PIN N3 [get_ports {DP1_GPIO_N[2]}]
# set_property PACKAGE_PIN R4 [get_ports {DP1_GPIO_P[3]}]
# set_property PACKAGE_PIN R3 [get_ports {DP1_GPIO_N[3]}]
# set_property IOSTANDARD LVDS_25 [get_ports DP1_GPIO*]
# set_property PACKAGE_PIN C16 [get_ports DP1_GPIO_AUX_P]
# set_property PACKAGE_PIN B16 [get_ports DP1_GPIO_AUX_N]
# set_property IOSTANDARD LVDS_25 [get_ports DP1_GPIO_AUX*]

# mDP_ML ("mini DP") connected to SelectIOs
# the lanes (indices) correspond to the DP-side of a DP-mDP-cable
set_property PACKAGE_PIN B14 [get_ports {mDP_GPIO_P[0]}]
set_property PACKAGE_PIN A14 [get_ports {mDP_GPIO_N[0]}]
set_property PACKAGE_PIN C12 [get_ports {mDP_GPIO_P[3]}]
set_property PACKAGE_PIN C11 [get_ports {mDP_GPIO_N[3]}]
set_property PACKAGE_PIN H14 [get_ports {mDP_GPIO_P[2]}]
set_property PACKAGE_PIN G14 [get_ports {mDP_GPIO_N[2]}]
set_property PACKAGE_PIN B12 [get_ports {mDP_GPIO_P[1]}]
set_property PACKAGE_PIN B11 [get_ports {mDP_GPIO_N[1]}]
set_property IOSTANDARD LVDS_25 [get_ports mDP_GPIO*]
set_property PACKAGE_PIN B15 [get_ports mDP_GPIO_AUX_P]
set_property PACKAGE_PIN A15 [get_ports mDP_GPIO_AUX_N]
set_property IOSTANDARD LVDS_25 [get_ports mDP_GPIO_AUX*]

# J1C ("RJ45") connected to SelectIOs
set_property PACKAGE_PIN D14 [get_ports {J1C_GPIO_P[3]}]
set_property PACKAGE_PIN D13 [get_ports {J1C_GPIO_N[3]}]
set_property PACKAGE_PIN C14 [get_ports {J1C_GPIO_P[2]}]
set_property PACKAGE_PIN C13 [get_ports {J1C_GPIO_N[2]}]
set_property PACKAGE_PIN G11 [get_ports {J1C_GPIO_P[1]}]
set_property PACKAGE_PIN F10 [get_ports {J1C_GPIO_N[1]}]
set_property PACKAGE_PIN J13 [get_ports J1C_GPIO_AUX_P]
set_property PACKAGE_PIN H13 [get_ports J1C_GPIO_AUX_N]

# J1D ("RJ45") connected to SelectIOs
set_property PACKAGE_PIN G12 [get_ports {J1D_GPIO_P[3]}]
set_property PACKAGE_PIN F12 [get_ports {J1D_GPIO_N[3]}]
set_property PACKAGE_PIN E13 [get_ports {J1D_GPIO_P[2]}]
set_property PACKAGE_PIN E12 [get_ports {J1D_GPIO_N[2]}]
set_property PACKAGE_PIN F14 [get_ports {J1D_GPIO_P[1]}]
set_property PACKAGE_PIN F13 [get_ports {J1D_GPIO_N[1]}]
set_property PACKAGE_PIN J11 [get_ports J1D_GPIO_AUX_P]
set_property PACKAGE_PIN J10 [get_ports J1D_GPIO_AUX_N]


# DP2 (SL)
set_property PACKAGE_PIN D19 [get_ports HITOR_P]
set_property PACKAGE_PIN D20 [get_ports HITOR_N]
set_property IOSTANDARD LVDS_25 [get_ports HITOR_*]

# Displayport RESET signals 0:DP1, 1:DP3, 2:DP4, 3:DP5, 4:mDP
# set_property PACKAGE_PIN G10 [get_ports RESETB_EXT]
# set_property PACKAGE_PIN K18 [get_ports {GPIO_RESET[3]}]
# set_property PACKAGE_PIN L17 [get_ports {GPIO_RESET[2]}]
# set_property PACKAGE_PIN H11 [get_ports {GPIO_RESET[1]}]
# set_property PACKAGE_PIN H12 [get_ports {GPIO_RESET[0]}]
# set_property IOSTANDARD LVCMOS25 [get_ports RESETB_EXT]
# set_property PULLUP TRUE [get_ports RESETB_EXT]

# NTC_MUX
set_property PACKAGE_PIN B21 [get_ports {NTC_MUX[0]}]
set_property PACKAGE_PIN D26 [get_ports {NTC_MUX[1]}]
set_property PACKAGE_PIN C26 [get_ports {NTC_MUX[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {NTC_MUX*}]
set_property SLEW SLOW [get_ports NTC*]

# SPI configuration flash
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
