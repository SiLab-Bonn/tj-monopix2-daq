# ------------------------------------------------------------
#  Copyright (c) SILAB , Physics Institute of Bonn University
# ------------------------------------------------------------
#
#   Constraints for the BDAQ53 PCB with the Mercury KX1(160T-1) FPGA board
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
create_generated_clock -name I2C_CLK -source [get_pins PLLE2_BASE_inst_comm/CLKOUT0] -divide_by 1600 [get_pins i_clock_divisor_i2c/CLOCK_reg/Q]
create_generated_clock -name rgmii_txc -source [get_pins rgmii/ODDR_inst/C] -divide_by 1 [get_ports rgmii_txc]

# Exclude asynchronous clock domains from timing (handled by CDCs)
set_clock_groups -asynchronous -group {BUS_CLK_PLL} -group {I2C_CLK} -group {CLK125PLLTX CLK125PLLTX90} -group {CLK320_PLL CLK160_PLL CLK40_PLL CLK32_PLL CLK16_PLL} -group [get_clocks -include_generated_clocks CLK_MGT_REF] -group CLK_RGMII_RX

# SiTCP
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX] -to [get_ports {rgmii_txd[*]}] 4.000
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX] -to [get_ports rgmii_tx_ctl] 4.000
set_max_delay -datapath_only -from [get_clocks CLK125PLLTX90] -to [get_ports rgmii_txc] 4.000
set_property ASYNC_REG true [get_cells sitcp/SiTCP/GMII/GMII_TXCNT/irMacPauseExe_0]
set_property ASYNC_REG true [get_cells sitcp/SiTCP/GMII/GMII_TXCNT/irMacPauseExe_1]

# LED
# LED 0..3 are onboard LEDs: Bank 32, 33 running at 1.5 V)
set_property PACKAGE_PIN M17 [get_ports {LED[0]}]
set_property PACKAGE_PIN L18 [get_ports {LED[1]}]
set_property PACKAGE_PIN L17 [get_ports {LED[2]}]
set_property PACKAGE_PIN K18 [get_ports {LED[3]}]
# LED 4..7 are LEDs on the BDAQ53 base board. They have pull-ups to 1.8 V.
set_property PACKAGE_PIN P26 [get_ports {LED[4]}]
set_property PACKAGE_PIN M25 [get_ports {LED[5]}]
set_property PACKAGE_PIN L25 [get_ports {LED[6]}]
set_property PACKAGE_PIN P23 [get_ports {LED[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports {LED[*]}]
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
set_property PACKAGE_PIN AA25 [get_ports {PMOD[4]}]
set_property PACKAGE_PIN AB25 [get_ports {PMOD[5]}]
set_property PACKAGE_PIN V24 [get_ports {PMOD[6]}]
set_property PACKAGE_PIN V26 [get_ports {PMOD[7]}]
set_property IOSTANDARD LVCMOS25 [get_ports PMOD*]
# Pull down the PMOD pins which are used as inputs
set_property PULLDOWN true [get_ports {PMOD[0]}]
set_property PULLDOWN true [get_ports {PMOD[1]}]
set_property PULLDOWN true [get_ports {PMOD[2]}]
set_property PULLDOWN true [get_ports {PMOD[3]}]

# ------ Si570 / SMA input CLK
set_property PACKAGE_PIN D6 [get_ports MGT_REFCLK0_P]
set_property PACKAGE_PIN D5 [get_ports MGT_REFCLK0_N]
set_property PACKAGE_PIN F6 [get_ports MGT_REFCLK1_P]
set_property PACKAGE_PIN F5 [get_ports MGT_REFCLK1_N]

# ------ CLK Mux
set_property PACKAGE_PIN K25 [get_ports MGT_REF_SEL]
set_property IOSTANDARD LVCMOS25 [get_ports MGT_REF_SEL]
set_property PULLUP true [get_ports MGT_REF_SEL]

# ------ FCLK (100 MHz)
set_property PACKAGE_PIN AA3 [get_ports FCLK_IN]
set_property IOSTANDARD LVCMOS15 [get_ports FCLK_IN]

# ------ Button & Spare & more - omitted for now
#Reset push button
set_property PACKAGE_PIN C18 [get_ports RESET_BUTTON]
set_property IOSTANDARD LVCMOS25 [get_ports RESET_BUTTON]
set_property PULLUP true [get_ports RESET_BUTTON]

# I2C
set_property PACKAGE_PIN N24 [get_ports I2C_SCL]
set_property PACKAGE_PIN P24 [get_ports I2C_SDA]
set_property IOSTANDARD LVCMOS25 [get_ports I2C_*]
set_property SLEW SLOW [get_ports I2C_*]

# EEPROM (SPI for SiTCP)
set_property PACKAGE_PIN G14 [get_ports EEPROM_CS]
set_property PACKAGE_PIN H11 [get_ports EEPROM_SK]
set_property PACKAGE_PIN D8 [get_ports EEPROM_DI]
set_property PACKAGE_PIN A8 [get_ports EEPROM_DO]
set_property IOSTANDARD LVCMOS33 [get_ports EEPROM_*]

# LEMO
set_property PACKAGE_PIN AB21 [get_ports LEMO_TX0]
set_property PACKAGE_PIN V23 [get_ports LEMO_TX1]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_TX*]
set_property SLEW FAST [get_ports LEMO_TX*]
set_property PACKAGE_PIN U22 [get_ports LEMO_RX0]
set_property PACKAGE_PIN U26 [get_ports LEMO_RX1]
set_property IOSTANDARD LVCMOS25 [get_ports LEMO_RX*]

# TLU
set_property PACKAGE_PIN V21 [get_ports RJ45_TRIGGER]
set_property PACKAGE_PIN Y25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_RESET]
set_property IOSTANDARD LVCMOS25 [get_ports RJ45_TRIGGER]

# SITCP
set_property SLEW FAST [get_ports mdio_phy_mdc]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdc]
set_property PACKAGE_PIN N16 [get_ports mdio_phy_mdc]

set_property SLEW FAST [get_ports mdio_phy_mdio]
set_property IOSTANDARD LVCMOS25 [get_ports mdio_phy_mdio]
set_property PACKAGE_PIN U16 [get_ports mdio_phy_mdio]

set_property SLEW FAST [get_ports phy_rst_n]
set_property IOSTANDARD LVCMOS25 [get_ports phy_rst_n]
set_property PACKAGE_PIN M20 [get_ports phy_rst_n]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rxc]
set_property PACKAGE_PIN R21 [get_ports rgmii_rxc]

set_property IOSTANDARD LVCMOS25 [get_ports rgmii_rx_ctl]
set_property PACKAGE_PIN P21 [get_ports rgmii_rx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[0]}]
set_property PACKAGE_PIN P16 [get_ports {rgmii_rxd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[1]}]
set_property PACKAGE_PIN N17 [get_ports {rgmii_rxd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[2]}]
set_property PACKAGE_PIN R16 [get_ports {rgmii_rxd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_rxd[3]}]
set_property PACKAGE_PIN R17 [get_ports {rgmii_rxd[3]}]

set_property SLEW FAST [get_ports rgmii_txc]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_txc]
set_property PACKAGE_PIN R18 [get_ports rgmii_txc]

set_property SLEW FAST [get_ports rgmii_tx_ctl]
set_property IOSTANDARD LVCMOS25 [get_ports rgmii_tx_ctl]
set_property PACKAGE_PIN P18 [get_ports rgmii_tx_ctl]

set_property SLEW FAST [get_ports {rgmii_txd[0]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[0]}]
set_property PACKAGE_PIN N18 [get_ports {rgmii_txd[0]}]
set_property SLEW FAST [get_ports {rgmii_txd[1]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[1]}]
set_property PACKAGE_PIN M19 [get_ports {rgmii_txd[1]}]
set_property SLEW FAST [get_ports {rgmii_txd[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[2]}]
set_property PACKAGE_PIN U17 [get_ports {rgmii_txd[2]}]
set_property SLEW FAST [get_ports {rgmii_txd[3]}]
set_property IOSTANDARD LVCMOS25 [get_ports {rgmii_txd[3]}]
set_property PACKAGE_PIN T17 [get_ports {rgmii_txd[3]}]

# DP_ML ("DP2") connected to SelectIOs
set_property PACKAGE_PIN K16 [get_ports DP_GPIO_P[0]]
set_property PACKAGE_PIN K17 [get_ports DP_GPIO_N[0]]
set_property PACKAGE_PIN L19 [get_ports DP_GPIO_P[1]]
set_property PACKAGE_PIN L20 [get_ports DP_GPIO_N[1]]
set_property PACKAGE_PIN H17 [get_ports DP_GPIO_P[2]]
set_property PACKAGE_PIN H18 [get_ports DP_GPIO_N[2]]
set_property PACKAGE_PIN G19 [get_ports DP_GPIO_P[3]]
set_property PACKAGE_PIN F20 [get_ports DP_GPIO_N[3]]
set_property IOSTANDARD LVDS_25 [get_ports DP_GPIO*]
set_property PACKAGE_PIN H19 [get_ports DP_GPIO_AUX_P]
set_property PACKAGE_PIN G20 [get_ports DP_GPIO_AUX_N]
set_property IOSTANDARD LVDS_25 [get_ports DP_GPIO_AUX*]

# # mDP_ML ("mini DP") connected to SelectIOs
#set_property PACKAGE_PIN K20 [get_ports {mDP_GPIO_P[0]}]
#set_property PACKAGE_PIN J20 [get_ports {mDP_GPIO_N[0]}]
#set_property PACKAGE_PIN E18 [get_ports {mDP_GPIO_P[1]}]
#set_property PACKAGE_PIN D18 [get_ports {mDP_GPIO_N[1]}]
#set_property PACKAGE_PIN D19 [get_ports {mDP_GPIO_P[2]}]
#set_property PACKAGE_PIN D20 [get_ports {mDP_GPIO_N[2]}]
#set_property PACKAGE_PIN F19 [get_ports {mDP_GPIO_P[3]}]
#set_property PACKAGE_PIN E20 [get_ports {mDP_GPIO_N[3]}]
#set_property IOSTANDARD LVDS_25 [get_ports mDP_GPIO*]

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
set_property PACKAGE_PIN M26 [get_ports {NTC_MUX[0]}]
set_property PACKAGE_PIN R25 [get_ports {NTC_MUX[1]}]
set_property PACKAGE_PIN P25 [get_ports {NTC_MUX[2]}]
set_property IOSTANDARD LVCMOS25 [get_ports {NTC_MUX*}]
set_property SLEW SLOW [get_ports NTC*]

# SPI configuration flash
set_property CONFIG_MODE SPIx4 [current_design]
set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property BITSTREAM.CONFIG.CONFIGRATE 33 [current_design]
