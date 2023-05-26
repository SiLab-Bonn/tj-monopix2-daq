`timescale 1ns / 1ps
`default_nettype none

`include "utils/bus_to_ip.v"

`include "utils/cdc_syncfifo.v"
`include "utils/generic_fifo.v"
`include "utils/cdc_pulse_sync.v"

`include "utils/CG_MOD_pos.v"

`include "utils/ddr_des.v"
`include "utils/flag_domain_crossing.v"

`include "utils/cdc_reset_sync.v"

`include "utils/fifo_32_to_8.v"

`include "utils/rgmii_io.v"
`include "utils/rbcp_to_bus.v"

// SiTCP
`include "WRAP_SiTCP_GMII_XC7K_32K.V"
`include "SiTCP_XC7K_32K_BBT_V110.V"
`include "TIMER.v"

// User core and its modules
`include "tjmonopix2_core.v"

module tjmonopix2 #(
    // FIRMWARE VERSION
    parameter VERSION_MAJOR = 8'd0,
    parameter VERSION_MINOR = 8'd0,
    parameter VERSION_PATCH = 8'd0
)(
    output wire MGT_REF_SEL,                    // switch between Si570 and external reference clock
    input wire MGT_REFCLK0_P, MGT_REFCLK0_N,    // programmable clock from Si570 oscillator or SMA
    input wire MGT_REFCLK1_P, MGT_REFCLK1_N,    // programmable clock from Si570 oscillator
    input wire FCLK_IN, // 100MHz

    //LED
    output wire [7:0] LED,
      
    input wire LEMO_RX0, LEMO_RX1,
    output wire LEMO_TX0, LEMO_TX1,
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,

    `ifdef BDAQ53
        output wire [3:0] DP_GPIO_P, DP_GPIO_N,  // {CMD, CMD_CLK, SER_CLK, PULSE_EXT}
        input wire DP_GPIO_AUX_P, DP_GPIO_AUX_N, // DATA

        // output wire [3:0] mDP_GPIO_P, mDP_GPIO_N,  // {CMD, CMD_CLK, SER_CLK, PULSE_EXT}
        // input wire mDP_GPIO_AUX_P, mDP_GPIO_AUX_N, // DATA

        input wire HITOR_P, HITOR_N,             // HITOR

        // NTC
        output wire [2:0] NTC_MUX,

        // SiTCP EEPROM
        output wire EEPROM_CS, EEPROM_SK, EEPROM_DI,
        input wire EEPROM_DO,
    `elsif MIO3
        output wire RESETB_EXT,
        // LVDS signals single ended to TX/RX on GPAC
        output wire LVDS_CMD,     //LVDS DOUT3(DOUT16)
        output wire LVDS_CMD_CLK, //LVDS DOUT2(DOUT1)
        output wire LVDS_SER_CLK,     //LVDS DOUT1(DOUT18)
        input wire LVDS_DATA,      //LVDS DIN3(DIN11)
        input wire LVDS_HITOR,             //LVDS DIN2(DIN9)
        output wire LVDS_PULSE_EXT,   //LVDS DOUT0(DOUT19)
        input wire LVDS_CHSYNC_LOCKED_OUT, //LVDS DIN1(DIN10)
        input wire LVDS_CHSYNC_CLK_OUT,    //LVDS DIN0(DIN8)

        output wire INPUT_SEL,      //DOUT14
        output wire CMOS_CMD,       //DOUT4
        output wire CMOS_CMD_CLK,   //DOUT2
        output wire CMOS_SER_CLK,   //DOUT0
        input wire CMOS_DATA,   //DIN2
        input wire CMOS_HITOR,  //DIN4
        output wire CMOS_PULSE_EXT, //DOUT12
    
        // RO
        input wire FREEZE_EXT,      //DOUT10
        output wire READ_EXT,       //DOUT8
        output wire RO_RST_EXT,     //DOUT9
        input wire TOKEN_OUT,       //DIN0
    `endif

    // 2-row PMOD header for general purpose IOs
    inout wire [7:0] PMOD,

    // I2C
    inout wire I2C_SDA,
    inout wire I2C_SCL,

    // User buttons
    input wire RESET_BUTTON,    

    // Ethernet
    output wire [3:0] rgmii_txd,
    output wire rgmii_tx_ctl,
    output wire rgmii_txc,
    input wire [3:0] rgmii_rxd,
    input wire rgmii_rx_ctl,
    input wire rgmii_rxc,
    output wire mdio_phy_mdc,
    inout wire mdio_phy_mdio,
    output wire phy_rst_n
);

 // ------- RESET/CLOCK  ------- //
 (* KEEP = "{TRUE}" *) wire BUS_CLK;

wire RST;
wire BUS_CLK_PLL, CLK250PLL, CLK125PLLTX, CLK125PLLTX90, CLK125PLLRX;
wire PLL_FEEDBACK, LOCKED;

// -------  PLL for communication with FPGA  ------- //
wire CLK200_PLL, CLK200;
IDELAYCTRL IDELAYCTRL_inst (
    .RDY   (         ), // 1-bit Ready output
    .REFCLK( CLK200  ), // 1-bit Reference clock input
    .RST   ( ~LOCKED )  // 1-bit Reset input
);

PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(10),       // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(10.000),   // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).
    .DIVCLK_DIVIDE(1),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE"),   // Delay DONE until PLL Locks, ("TRUE"/"FALSE")
    
    .CLKOUT0_DIVIDE(7),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT0_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT0_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT1_DIVIDE(4),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT1_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT1_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT2_DIVIDE(8),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT2_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT2_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT3_DIVIDE(8),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT3_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT3_PHASE(90.0),     // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT4_DIVIDE(8),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT4_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT4_PHASE(-5.625),   // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT5_DIVIDE(5),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT5_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT5_PHASE(0)         // Phase offset for CLKOUT0 (-360.000-360.000).
) PLLE2_BASE_inst_comm (
    .CLKOUT0(BUS_CLK_PLL),
    .CLKOUT1(CLK250PLL),
    .CLKOUT2(CLK125PLLTX),
    .CLKOUT3(CLK125PLLTX90),
    .CLKOUT4(CLK125PLLRX),
    .CLKOUT5(CLK200_PLL),

    .CLKFBOUT(PLL_FEEDBACK),

    .LOCKED(LOCKED),          // 1-bit output: LOCK

    // Input 100 MHz clock
    .CLKIN1(FCLK_IN),

    // Control Ports
    .PWRDWN(0),
    .RST(!RESET_BUTTON),

    // Feedback
    .CLKFBIN(PLL_FEEDBACK)
);

wire CLK125TX, CLK125TX90, CLK125RX;
BUFG BUFG_inst_CLK125TX (  .O(CLK125TX),  .I(CLK125PLLTX) );
BUFG BUFG_inst_CLK125TX90 (  .O(CLK125TX90),  .I(CLK125PLLTX90) );
BUFG BUFG_inst_CLK125RX (  .O(CLK125RX),  .I(rgmii_rxc) );
BUFG BUFG_inst_CLK200 (  .O(CLK200),  .I(CLK200_PLL) );

// -------  PLL for clk synthesis  ------- //
(* KEEP = "{TRUE}" *) wire CLK320;  
(* KEEP = "{TRUE}" *) wire CLK160;
(* KEEP = "{TRUE}" *) wire CLK32;
(* KEEP = "{TRUE}" *) wire CLK40;
(* KEEP = "{TRUE}" *) wire CLK16;

wire PLL_FEEDBACK2, LOCKED2;
wire CLK16_PLL, CLK32_PLL, CLK40_PLL, CLK160_PLL, CLK320_PLL;

PLLE2_BASE #(
    .BANDWIDTH("OPTIMIZED"),  // OPTIMIZED, HIGH, LOW
    .CLKFBOUT_MULT(16),       // Multiply value for all CLKOUT, (2-64)
    .CLKFBOUT_PHASE(0.0),     // Phase offset in degrees of CLKFB, (-360.000-360.000).
    .CLKIN1_PERIOD(10.000),   // Input clock period in ns to ps resolution (i.e. 33.333 is 30 MHz).
    .DIVCLK_DIVIDE(1),        // Master division value, (1-56)
    .REF_JITTER1(0.0),        // Reference input jitter in UI, (0.000-0.999).
    .STARTUP_WAIT("FALSE"),   // Delay DONE until PLL Locks, ("TRUE"/"FALSE")

    .CLKOUT0_DIVIDE(100),     // Divide amount for CLKOUT0 (1-128)
    .CLKOUT0_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT0_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT1_DIVIDE(50),      // Divide amount for CLKOUT0 (1-128)
    .CLKOUT1_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT1_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT2_DIVIDE(40),      // Divide amount for CLKOUT0 (1-128)
    .CLKOUT2_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT2_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT3_DIVIDE(10),      // Divide amount for CLKOUT0 (1-128)
    .CLKOUT3_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT3_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).

    .CLKOUT4_DIVIDE(5),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT4_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT4_PHASE(0.0),      // Phase offset for CLKOUT0 (-360.000-360.000).
    
    .CLKOUT5_DIVIDE(7),       // Divide amount for CLKOUT0 (1-128)
    .CLKOUT5_DUTY_CYCLE(0.5), // Duty cycle for CLKOUT0 (0.001-0.999).
    .CLKOUT5_PHASE(0.0)       // Phase offset for CLKOUT0 (-360.000-360.000).
) PLLE2_BASE_inst_clk (
    .CLKOUT0(CLK16_PLL),
    .CLKOUT1(CLK32_PLL),
    .CLKOUT2(CLK40_PLL),
    .CLKOUT3(CLK160_PLL),
    .CLKOUT4(CLK320_PLL),
    .CLKOUT5(),

    .CLKFBOUT(PLL_FEEDBACK2),
    
    .LOCKED(LOCKED2),         // 1-bit output: LOCK
    
    // Input 100 MHz clock
    .CLKIN1(FCLK_IN),
    
    // Control Ports
    .PWRDWN(0),
    .RST(!RESET_BUTTON),
    
    // Feedback
    .CLKFBIN(PLL_FEEDBACK2)
);

BUFG BUFG_inst_BUS_CKL (.O(BUS_CLK), .I(BUS_CLK_PLL));
BUFG BUFG_inst_CLK16   (.O(CLK16),   .I(CLK16_PLL));
BUFG BUFG_inst_CLK32   (.O(CLK32),   .I(CLK32_PLL));
BUFG BUFG_inst_CLK40   (.O(CLK40),   .I(CLK40_PLL));
BUFG BUFG_inst_CLK160  (.O(CLK160),  .I(CLK160_PLL));
BUFG BUFG_inst_CLK320  (.O(CLK320),  .I(CLK320_PLL));

// MGT CLK (from Si570 or SMA input)
wire CLKCMD, EXT_TRIGGER_CLK;

IBUFDS_GTE2 IBUFDS_refclk  
(
    .O               (CLKCMD),
    .ODIV2           (),
    .CEB             (1'b0),
    .I               (MGT_REFCLK1_P),
    .IB              (MGT_REFCLK1_N)
);

// SMA CLK input from AIDA2020 TLU
IBUFDS_GTE2 IBUFDS_aidatlu_clk  
(
    .O               (EXT_TRIGGER_CLK),
    .ODIV2           (),
    .CEB             (1'b0),
    .I               (MGT_REFCLK0_P),
    .IB              (MGT_REFCLK0_N)
);

// -------  LEMO TX ------- //
wire RJ45_CLK, RJ45_BUSY;
wire CMD_LOOP_START_PULSE;
wire [1:0] LEMO_MUX_TX1, LEMO_MUX_TX0, LEMO_MUX_RX1, LEMO_MUX_RX0;
assign LEMO_TX0 = LEMO_MUX_TX0[1] ? (LEMO_MUX_TX0[0] ? 1'b0 : 1'b0) : (LEMO_MUX_TX0[0] ? CMD_LOOP_START_PULSE : RJ45_CLK);
assign LEMO_TX1 = LEMO_MUX_TX1[1] ? (LEMO_MUX_TX1[0] ? 1'b0 : 1'b0) : (LEMO_MUX_TX1[0] ? EXT_TRIGGER_CLK : RJ45_BUSY);

// -------  Diff buffer for BDAQ  ------- //
`ifdef BDAQ53
    wire LVDS_CMD, LVDS_CMD_CLK, LVDS_SER_CLK, LVDS_PULSE_EXT;
    wire CMD_P, CMD_N, CMD_CLK_P, CMD_CLK_N, SER_CLK_P, SER_CLK_N, PULSE_EXT_P, PULSE_EXT_N;
    wire CMD_OUT_int, CMD_CLK_int, SER_CLK_int, PULSE_EXT_int;

    // CMD
    OBUFDS #(
        .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
        .SLEW("FAST")           // Specify the output slew rate
    ) i_OBUFDS_cmd (
        .O(CMD_P),              // Diff_p output (connect directly to top-level port)
        .OB(CMD_N),             // Diff_n output (connect directly to top-level port)
        .I(LVDS_CMD)            // Buffer input
    );
    assign DP_GPIO_N[3] = CMD_N;
    assign DP_GPIO_P[3] = CMD_P;

    // CMD CLK
    OBUFDS #(
        .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
        .SLEW("FAST")           // Specify the output slew rate
    ) i_OBUFDS_cmd_clk (
        .O(CMD_CLK_P),          // Diff_p output (connect directly to top-level port)
        .OB(CMD_CLK_N),         // Diff_n output (connect directly to top-level port)
        .I(LVDS_CMD_CLK)        // Buffer input
    );
    assign DP_GPIO_N[2] = CMD_CLK_N;
    assign DP_GPIO_P[2] = CMD_CLK_P;

    // SER CLK
    OBUFDS #(
        .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
        .SLEW("FAST")           // Specify the output slew rate
    ) i_OBUFDS_ser_clk (
        .O(SER_CLK_P),          // Diff_p output (connect directly to top-level port)
        .OB(SER_CLK_N),         // Diff_n output (connect directly to top-level port)
        .I(LVDS_SER_CLK)        // Buffer input
    );
    assign DP_GPIO_N[1] = SER_CLK_N;
    assign DP_GPIO_P[1] = SER_CLK_P;

    // PULSE
    OBUFDS #(
        .IOSTANDARD("LVDS_25"), // Specify the output I/O standard
        .SLEW("FAST")           // Specify the output slew rate
    ) i_OBUFDS_pulse_ext (
        .O(PULSE_EXT_P),        // Diff_p output (connect directly to top-level port)
        .OB(PULSE_EXT_N),       // Diff_n output (connect directly to top-level port)
        .I(LVDS_PULSE_EXT)      // Buffer input
    );
    assign DP_GPIO_N[0] = PULSE_EXT_N;
    assign DP_GPIO_P[0] = PULSE_EXT_P;

    wire LVDS_DATA, LVDS_DATA_int, LVDS_HITOR;
    IBUFDS #(
        .DIFF_TERM("TRUE"),     // Differential Termination
        .IBUF_LOW_PWR("FALSE"), // Low power="TRUE", Highest performance="FALSE"
        .IOSTANDARD("LVDS_25")  // Specify the input I/O standard
    ) i_IBUFDS_data (
        .O(LVDS_DATA_int),      // Buffer output
        .I(DP_GPIO_AUX_P),      // Diff_p buffer input (connect directly to top-level port)
        .IB(DP_GPIO_AUX_N)      // Diff_n buffer input (connect directly to top-level port)
    );

    assign LVDS_DATA = ~LVDS_DATA_int;

    IBUFDS #(
        .DIFF_TERM("TRUE"),     // Differential Termination
        .IBUF_LOW_PWR("FALSE"), // Low power="TRUE", Highest performance="FALSE"
        .IOSTANDARD("LVDS_25")  // Specify the input I/O standard
    ) i_IBUFDS_hitor (
        .O(LVDS_HITOR),         // Buffer output
        .I(HITOR_P),            // Diff_p buffer input (connect directly to top-level port)
        .IB(HITOR_N)            // Diff_n buffer input (connect directly to top-level port)
    );
`endif

assign RST = !RESET_BUTTON | !LOCKED;
wire   gmii_tx_clk;
wire   gmii_tx_en;
wire  [7:0] gmii_txd;
wire   gmii_tx_er;
wire   gmii_crs;
wire   gmii_col;
wire   gmii_rx_clk;
wire   gmii_rx_dv;
wire  [7:0] gmii_rxd;
wire   gmii_rx_er;
wire   mdio_gem_mdc;
wire   mdio_gem_i;
wire   mdio_gem_o;
wire   mdio_gem_t;
wire   link_status;
wire  [1:0] clock_speed;
wire   duplex_status;

rgmii_io rgmii
(
    .rgmii_txd(rgmii_txd),
    .rgmii_tx_ctl(rgmii_tx_ctl),
    .rgmii_txc(rgmii_txc),

    .rgmii_rxd(rgmii_rxd),
    .rgmii_rx_ctl(rgmii_rx_ctl),

    .gmii_txd_int(gmii_txd),            // Internal gmii_txd signal.
    .gmii_tx_en_int(gmii_tx_en),
    .gmii_tx_er_int(gmii_tx_er),
    .gmii_col_int(gmii_col),
    .gmii_crs_int(gmii_crs),
    .gmii_rxd_reg(gmii_rxd),            // RGMII double data rate data valid.
    .gmii_rx_dv_reg(gmii_rx_dv),        // gmii_rx_dv_ibuf registered in IOBs.
    .gmii_rx_er_reg(gmii_rx_er),        // gmii_rx_er_ibuf registered in IOBs.

    .eth_link_status(link_status),
    .eth_clock_speed(clock_speed),
    .eth_duplex_status(duplex_status),

    // FOllowing are generated by DCMs
    .tx_rgmii_clk_int(CLK125TX),        // Internal RGMII transmitter clock.
    .tx_rgmii_clk90_int(CLK125TX90),    // Internal RGMII transmitter clock w/ 90 deg phase
    .rx_rgmii_clk_int(CLK125RX),        // Internal RGMII receiver clock

    .reset(!phy_rst_n)
);

// -------  SITCP  ------- //
// Instantiate tri-state buffer for MDIO
IOBUF i_iobuf_mdio(
    .O(mdio_gem_i),
    .IO(mdio_phy_mdio),
    .I(mdio_gem_o),
    .T(mdio_gem_t)
);

wire EEPROM_CS_int, EEPROM_SK_int, EEPROM_DI_int, EEPROM_DO_int;
wire TCP_OPEN_ACK, TCP_CLOSE_REQ;
wire TCP_RX_WR, TCP_TX_WR;
wire TCP_TX_FULL, TCP_ERROR;
wire RBCP_ACT, RBCP_WE, RBCP_RE;
wire [7:0] RBCP_WD, RBCP_RD;
wire [31:0] RBCP_ADDR;
wire [7:0] TCP_RX_DATA;
wire RBCP_ACK;
wire SiTCP_RST;

wire [7:0] TCP_TX_DATA;

// connect the physical EEPROM pins only for the BDAQ53
`ifdef BDAQ53
    assign EEPROM_CS = EEPROM_CS_int;
    assign EEPROM_SK = EEPROM_SK_int;
    assign EEPROM_DI = EEPROM_DI_int;
    assign EEPROM_DO_int = EEPROM_DO;
`endif

// IP address subnet selection
wire [3:0] IP_ADDR_SEL;
assign PMOD[7:4] = 4'hf;
assign IP_ADDR_SEL = {PMOD[0], PMOD[1], PMOD[2], PMOD[3]};

WRAP_SiTCP_GMII_XC7K_32K sitcp(
    .CLK(BUS_CLK)                ,    // in     : System Clock >129MHz
    .RST(RST)                    ,    // in     : System reset
    // Configuration parameters
    .FORCE_DEFAULTn(1'b0)        ,    // in     : Load default parameters
    .EXT_IP_ADDR({8'd192, 8'd168, |{IP_ADDR_SEL} ? 8'd10 + IP_ADDR_SEL : 8'd10, 8'd23}),   // IP address[31:0] default: 192.168.10.23. If jumpers are set: 192.168.[11..25].23
    .EXT_TCP_PORT(16'd24)        ,    // in     : TCP port #[15:0]
    .EXT_RBCP_PORT(16'd4660)     ,    // in     : RBCP port #[15:0]
    .PHY_ADDR(5'd3)              ,    // in     : PHY-device MIF address[4:0]
    // EEPROM
    .EEPROM_CS(EEPROM_CS_int)    ,    // out    : Chip select
    .EEPROM_SK(EEPROM_SK_int)    ,    // out    : Serial data clock
    .EEPROM_DI(EEPROM_DI_int)    ,    // out    : Serial write data
    .EEPROM_DO(EEPROM_DO_int)    ,    // in     : Serial read data
    // User data, initial values are stored in the EEPROM, 0xFFFF_FC3C-3F
    .USR_REG_X3C()               ,    // out    : Stored at 0xFFFF_FF3C
    .USR_REG_X3D()               ,    // out    : Stored at 0xFFFF_FF3D
    .USR_REG_X3E()               ,    // out    : Stored at 0xFFFF_FF3E
    .USR_REG_X3F()               ,    // out    : Stored at 0xFFFF_FF3F
    // MII interface
    .GMII_RSTn(phy_rst_n)        ,    // out    : PHY reset
    .GMII_1000M(1'b1)            ,    // in     : GMII mode (0:MII, 1:GMII)
    // TX 
    .GMII_TX_CLK(CLK125TX)       ,    // in     : Tx clock
    .GMII_TX_EN(gmii_tx_en)      ,    // out    : Tx enable
    .GMII_TXD(gmii_txd)          ,    // out    : Tx data[7:0]
    .GMII_TX_ER(gmii_tx_er)      ,    // out    : TX error
    // RX
    .GMII_RX_CLK(CLK125RX)       ,    // in     : Rx clock
    .GMII_RX_DV(gmii_rx_dv)      ,    // in     : Rx data valid
    .GMII_RXD(gmii_rxd)          ,    // in     : Rx data[7:0]
    .GMII_RX_ER(gmii_rx_er)      ,    // in     : Rx error
    .GMII_CRS(gmii_crs)          ,    // in     : Carrier sense
    .GMII_COL(gmii_col)          ,    // in     : Collision detected
    // Management IF
    .GMII_MDC(mdio_phy_mdc)      ,    // out    : Clock for MDIO
    .GMII_MDIO_IN(mdio_gem_i)    ,    // in     : Data
    .GMII_MDIO_OUT(mdio_gem_o)   ,    // out    : Data
    .GMII_MDIO_OE(mdio_gem_t)    ,    // out    : MDIO output enable
    // User I/F
    .SiTCP_RST(SiTCP_RST)        ,    // out    : Reset for SiTCP and related circuits
    // TCP connection control
    .TCP_OPEN_REQ(1'b0)          ,    // in     : Reserved input, shoud be 0
    .TCP_OPEN_ACK(TCP_OPEN_ACK)  ,    // out    : Acknowledge for open (=Socket busy)
    .TCP_ERROR(TCP_ERROR)        ,    // out    : TCP error, its active period is equal to MSL
    .TCP_CLOSE_REQ(TCP_CLOSE_REQ),    // out    : Connection close request
    .TCP_CLOSE_ACK(TCP_CLOSE_REQ),    // in     : Acknowledge for closing
    // FIFO I/F
    .TCP_RX_WC(1'b1)             ,    // in     : Rx FIFO write count[15:0] (Unused bits should be set 1)
    .TCP_RX_WR(TCP_RX_WR)        ,    // out    : Write enable
    .TCP_RX_DATA(TCP_RX_DATA)    ,    // out    : Write data[7:0]
    .TCP_TX_FULL(TCP_TX_FULL)    ,    // out    : Almost full flag
    .TCP_TX_WR(TCP_TX_WR)        ,    // in     : Write enable
    .TCP_TX_DATA(TCP_TX_DATA)    ,    // in     : Write data[7:0]
    // RBCP
    .RBCP_ACT(RBCP_ACT)          ,    // out    : RBCP active
    .RBCP_ADDR(RBCP_ADDR)        ,    // out    : Address[31:0]
    .RBCP_WD(RBCP_WD)            ,    // out    : Data[7:0]
    .RBCP_WE(RBCP_WE)            ,    // out    : Write enable
    .RBCP_RE(RBCP_RE)            ,    // out    : Read enable
    .RBCP_ACK(RBCP_ACK)          ,    // in     : Access acknowledge
    .RBCP_RD(RBCP_RD)                 // in     : Read data[7:0]
);

// -------  BUS SIGNALING  ------- //
wire BUS_WR, BUS_RD, BUS_RST;
wire [31:0] BUS_ADD;
wire [7:0] BUS_DATA;
assign BUS_RST = SiTCP_RST;

rbcp_to_bus irbcp_to_bus(
    .BUS_RST(BUS_RST),
    .BUS_CLK(BUS_CLK),

    .RBCP_ACT(RBCP_ACT),
    .RBCP_ADDR(RBCP_ADDR),
    .RBCP_WD(RBCP_WD),
    .RBCP_WE(RBCP_WE),
    .RBCP_RE(RBCP_RE),
    .RBCP_ACK(RBCP_ACK),
    .RBCP_RD(RBCP_RD),

    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA)
); 

// -------  MODULES for fast data readout(FIFO) - cdc_fifo is for timing reasons
wire ARB_READY_OUT,ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire FIFO_FULL, FIFO_NEAR_FULL;
wire [31:0] cdc_data_out;
wire full_32to8, cdc_fifo_empty;
cdc_syncfifo #(.DSIZE(32), .ASIZE(3)) cdc_syncfifo_i
(
    .rdata(cdc_data_out),
    .wfull(FIFO_FULL),
    .rempty(cdc_fifo_empty),
    .wdata(ARB_DATA_OUT),
    .winc(ARB_WRITE_OUT), .wclk(BUS_CLK), .wrst(BUS_RST),
    .rinc(!full_32to8), .rclk(BUS_CLK), .rrst(BUS_RST)
);
assign ARB_READY_OUT = !FIFO_FULL;

wire FIFO_EMPTY;
fifo_32_to_8 #(.DEPTH(256*1024)) i_data_fifo (
    .RST(BUS_RST),
    .CLK(BUS_CLK),
    
    .WRITE(!cdc_fifo_empty),
    .READ(TCP_TX_WR),
    .DATA_IN(cdc_data_out),
    .FULL(full_32to8),
    .EMPTY(FIFO_EMPTY),
    .DATA_OUT(TCP_TX_DATA)
);

assign TCP_TX_WR = !TCP_TX_FULL && !FIFO_EMPTY;

// -------  USER CORE ------- //
assign LED[7]= 1'b0;
assign LED[6]= 1'b1;
assign LED[5]= 1'b1;
wire [1:0] CHIP_ID;

tjmonopix2_core #(
    .VERSION_MAJOR(VERSION_MAJOR),
    .VERSION_MINOR(VERSION_MINOR),
    .VERSION_PATCH(VERSION_PATCH)
) i_tjmonopix2_core (
    //local bus
    .BUS_CLK(BUS_CLK),
    .BUS_DATA(BUS_DATA),
    .BUS_ADD(BUS_ADD),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .BUS_RST(BUS_RST),
    //clocks
    .CLK16(CLK16),
    .CLK32(CLK32),
    .CLK40(CLK40),
    .CLK160(CLK160),
    .CLK320(CLK320),
    .CLKCMD(CLKCMD),
    .EXT_TRIGGER_CLK(EXT_TRIGGER_CLK),
    .MGT_REF_SEL(MGT_REF_SEL),

    .I2C_SDA(I2C_SDA),
    .I2C_SCL(I2C_SCL),

    //cmd
    .CMD_LOOP_START_PULSE(CMD_LOOP_START_PULSE),

    //fifo
    .ARB_READY_OUT(ARB_READY_OUT),
    .ARB_WRITE_OUT(ARB_WRITE_OUT),
    .ARB_DATA_OUT(ARB_DATA_OUT),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL),

    //LED
    .LED(LED[4:0]),
    .LEMO_RX({LEMO_RX1, LEMO_RX0}),
    .LEMO_MUX({LEMO_MUX_TX1, LEMO_MUX_TX0, LEMO_MUX_RX1, LEMO_MUX_RX0}),
    .RJ45_CLK(RJ45_CLK),
    .RJ45_BUSY(RJ45_BUSY),
    .RJ45_RESET(RJ45_RESET),
    .RJ45_TRIGGER(RJ45_TRIGGER),

    .LVDS_CMD(LVDS_CMD), 
    .LVDS_CMD_CLK(LVDS_CMD_CLK), 
    .LVDS_SER_CLK(LVDS_SER_CLK), 
    .LVDS_DATA(LVDS_DATA), 
    .LVDS_HITOR(LVDS_HITOR),
    .LVDS_PULSE_EXT(LVDS_PULSE_EXT),

    `ifdef MIO3
        .RESETB_EXT(RESETB_EXT), 

        .LVDS_CHSYNC_LOCKED_OUT(LVDS_CHSYNC_LOCKED_OUT),
        .LVDS_CHSYNC_CLK_OUT(LVDS_CHSYNC_CLK_OUT),
        .INPUT_SEL(INPUT_SEL), 

        .CMOS_CMD(CMOS_CMD), 
        .CMOS_CMD_CLK(CMOS_CMD_CLK), 
        .CMOS_SER_CLK(CMOS_SER_CLK),
        .CMOS_DATA(CMOS_DATA),
        .CMOS_HITOR(CMOS_HITOR),
        .CMOS_PULSE_EXT(CMOS_PULSE_EXT),

        .FREEZE_EXT(FREEZE_EXT), 
        .READ_EXT(READ_EXT), 
        .RO_RST_EXT(RO_RST_EXT), 
        .TOKEN_OUT(TOKEN_OUT),
    `elsif BDAQ53
        .NTC_MUX(NTC_MUX),
    `endif

    .CHIP_ID(CHIP_ID)
);

endmodule
