`timescale 1ns / 1ps
`default_nettype none

`include "xadc.v"

// Basil modules
`include "i2c/i2c.v"
`include "i2c/i2c_core.v"

`include "spi/spi_core.v"
`include "spi/spi.v"
`include "spi/blk_mem_gen_8_to_1_2k.v"

`include "gpio/gpio.v"
`include "gpio/gpio_core.v"

`include "rrp_arbiter/rrp_arbiter.v"

`include "tlu/tlu_controller.v"
`include "tlu/tlu_controller_core.v"
`include "tlu/tlu_controller_fsm.v"

`include "tdc_s3/tdc_s3.v"
`include "tdc_s3/tdc_s3_core.v"

`include "timestamp/timestamp.v"
`include "timestamp/timestamp_core.v"

`include "pulse_gen/pulse_gen.v"
`include "pulse_gen/pulse_gen_core.v"
`include "pulse_gen_rising.v"

`include "utils/3_stage_synchronizer.v"
`include "utils/clock_divider.v"

// Custom modules
`include "cmd/cmd.v"
`include "cmd/cmd_core.v"

`include "tjmono2_rx/tjmono2_rx.v"
`include "tjmono2_rx/tjmono2_rx_core.v"
`include "tjmono2_rx/receiver_logic.v"
`include "tjmono2_rx/rec_sync.v"
`include "tjmono2_rx/decode_8b10b.v"

`include "gray_dec.v"

// `include "tjmono_direct_rx/tjmono_direct_rx.v"
// `include "tjmono_direct_rx/tjmono_direct_rx_core.v"

module tjmonopix2_core #(
    // FIRMWARE VERSION
    parameter VERSION_MAJOR = 8'd0,
    parameter VERSION_MINOR = 8'd0,
    parameter VERSION_PATCH = 8'd0
)(
    // local bus
    input wire BUS_CLK,
    inout wire [7:0] BUS_DATA,
    input wire [31:0] BUS_ADD,
    input wire BUS_RD,
    input wire BUS_WR,
    input wire BUS_RST,

    // clocks
    input wire CLK16,
    input wire CLK32,
    input wire CLK40,
    input wire CLK160,
    input wire CLK320,
    input wire CLKCMD,
    output wire MGT_REF_SEL,

    // i2c
    inout wire I2C_SCL,
    inout wire I2C_SDA,

    //cmd
    output wire CMD_LOOP_START_PULSE,

    // Displayport control signals
    input wire [3:0] GPIO_SENSE,

    // Fifo
    input wire ARB_READY_OUT,
    output wire ARB_WRITE_OUT,
    output wire [31:0] ARB_DATA_OUT,
    input wire FIFO_FULL,
    input wire FIFO_NEAR_FULL,

    // tlu, lemo, led
    output wire [4:0] LED,
    input wire [1:0] LEMO_RX,
    output wire [7:0] LEMO_MUX,
    output wire RJ45_BUSY,
    output wire RJ45_CLK,
    input wire RJ45_TRIGGER,
    input wire RJ45_RESET,

    output wire RESETB_EXT,

    // LVDS IO
    output wire LVDS_CMD,
    output wire LVDS_CMD_CLK,
    output wire LVDS_SER_CLK,
    input wire LVDS_DATA,
    input wire LVDS_HITOR,
    output wire LVDS_PULSE_EXT,

    // NTC
    output wire [2:0] NTC_MUX,

    `ifdef MIO3
        // CHSYNC output only connected on MIO3 compatible PCBs
        input wire LVDS_CHSYNC_LOCKED_OUT,
        input wire LVDS_CHSYNC_CLK_OUT,
        // CHIP CONF
        output wire INPUT_SEL,

        // CMOS IO
        output wire CMOS_CMD,
        output wire CMOS_CMD_CLK,    
        output wire CMOS_SER_CLK,
        input wire CMOS_DATA,
        input wire CMOS_HITOR,
        output wire CMOS_PULSE_EXT,

        // CMOS RO
        output wire FREEZE_EXT,
        output wire READ_EXT,
        inout wire RO_RST_EXT,
        input wire TOKEN_OUT,
    `endif

    inout wire [1:0] CHIP_ID
);

// BOARD ID
localparam SIM = 8'd0;
localparam BDAQ53 = 8'd1;
localparam MIO3 = 8'd2;

`ifdef SIM
    localparam BOARD = SIM;
`elsif BDAQ53
    localparam BOARD = BDAQ53;
`elsif MIO3
    localparam BOARD = MIO3;
`endif

// BOARD CONFIGURATION
reg SI570_IS_CONFIGURED = 1'b0;

// VERSION/BOARD READBACK
localparam VERSION = 1; // Module version

// -------  MODULE ADREESSES  ------- //
localparam GPIO_BASEADDR = 32'h0010;
localparam GPIO_HIGHADDR = 32'h0100 - 1;

localparam PULSE_INJ_BASEADDR = 32'h0100;
localparam PULSE_INJ_HIGHADDR = 32'h0200 - 1;

localparam RX_BASEADDR = 32'h0200;
localparam RX_HIGHADDR = 32'h0300 - 1; 

localparam DAQ_SYSTEM_BASEADDR = 32'h0300;
localparam DAQ_SYSTEM_HIGHADDR = 32'h0400 - 1;

localparam PULSE_RST_BASEADDR = 32'h0400;
localparam PULSE_RST_HIGHADDR = 32'h0500 - 1;

localparam GPIO_DAQ_CONTROL_BASEADDR = 32'h0500;
localparam GPIO_DAQ_CONTROL_HIGHADDR = 32'h0600 - 1;

localparam TLU_BASEADDR = 32'h0600;
localparam TLU_HIGHADDR = 32'h0700 - 1;

localparam TDC_LVDS_BASEADDR = 32'h0700;
localparam TDC_LVDS_HIGHADDR = 32'h0800 - 1;

localparam PULSER_VETO_BASEADDR = 32'h0800;
localparam PULSER_VETO_HIGHADDR = 32'h0900-1;

// Temperature measurements with XADC in FPGA
`ifdef BDAQ53
    localparam GPIO_XADC_VPVN_BASEADDR = 32'h0900;
    localparam GPIO_XADC_VPVN_HIGHADDR = 32'h0A00-1;

    localparam GPIO_XADC_FPGA_TEMP_BASEADDR = 32'h0A00;
    localparam GPIO_XADC_FPGA_TEMP_HIGHADDR = 32'h0B00-1;
`endif

localparam PULSE_CMD_START_LOOP_BASEADDR = 32'h0C00;
localparam PULSE_CMD_START_LOOP_HIGHADDR = 32'h0D00 - 1;

localparam TDC_CMOS_BASEADDR = 32'h0D00;
localparam TDC_CMOS_HIGHADDR = 32'h0E00 - 1;

localparam I2C_BASEADDR = 32'h3000;
localparam I2C_HIGHADDR = 32'h4000 - 1;

localparam CMD_BASEADDR = 32'h1000;
localparam CMD_HIGHADDR = 32'h3000 - 1;

localparam ABUSWIDTH = 32;

// SYSTEM CONFIG
wire DAQ_SYSTEM_RD, DAQ_SYSTEM_WR;
wire [ABUSWIDTH-1:0] DAQ_SYSTEM_ADD;
wire [7:0] DAQ_SYSTEM_DATA_IN;
reg [7:0] DAQ_SYSTEM_DATA_OUT;

bus_to_ip #( .BASEADDR(DAQ_SYSTEM_BASEADDR), .HIGHADDR(DAQ_SYSTEM_HIGHADDR), .ABUSWIDTH(ABUSWIDTH) ) i_bus_to_ip_daq
(
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),

    .IP_RD(DAQ_SYSTEM_RD),
    .IP_WR(DAQ_SYSTEM_WR),
    .IP_ADD(DAQ_SYSTEM_ADD),
    .IP_DATA_IN(DAQ_SYSTEM_DATA_IN),
    .IP_DATA_OUT(DAQ_SYSTEM_DATA_OUT)
);

reg [31:0] BUS_DATA_OUT_REG;
always @ (posedge BUS_CLK) begin
    if(DAQ_SYSTEM_RD) begin
        case (DAQ_SYSTEM_ADD)
            0:       DAQ_SYSTEM_DATA_OUT <= VERSION;
            1:       DAQ_SYSTEM_DATA_OUT <= VERSION_MINOR;
            2:       DAQ_SYSTEM_DATA_OUT <= VERSION_MAJOR;
            3:       DAQ_SYSTEM_DATA_OUT <= BOARD;
            4:       DAQ_SYSTEM_DATA_OUT <= SI570_IS_CONFIGURED;
            default: DAQ_SYSTEM_DATA_OUT <= 0;
        endcase
    end
end

always @ (posedge BUS_CLK)
    if(DAQ_SYSTEM_WR) begin
        case (DAQ_SYSTEM_ADD)
            5:       SI570_IS_CONFIGURED <= DAQ_SYSTEM_DATA_IN[0];
            default: begin end
        endcase
    end

// -------  USER MODULES  ------- //
wire [23:0] IO;
gpio 
#( 
    .BASEADDR(GPIO_BASEADDR), 
    .HIGHADDR(GPIO_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .IO_WIDTH(24),
    .IO_DIRECTION(24'hfff0ff)
) gpio_i
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(IO)
);
wire EN_LVDS_IN, EN_CMOS_IN, EN_CMOS_OUT, SEL_DIRECT;
wire [2:0] GPIO_MODE;

assign GPIO_MODE = IO[14:12];

`ifdef MIO3
    assign INPUT_SEL = IO[1];
    assign EN_CMOS_IN = IO[2];
    assign EN_CMOS_OUT = IO[6];
    assign EN_LVDS_IN = IO[7];
    assign IO[8] = LVDS_CHSYNC_LOCKED_OUT;
    assign IO[9] = LVDS_CHSYNC_CLK_OUT;
    assign IO[11] = RO_RST_EXT;
    assign RO_RST_EXT = GPIO_MODE[2] ? 1'bz : IO[5];
    assign SEL_DIRECT = IO[16]; 
`endif

// GPIO module to access general base-board features
wire [15:0] IO_CONTROL;
assign MGT_REF_SEL = ~IO_CONTROL[15];   // invert, because the default value '0' should correspond to the internal clock
assign LEMO_MUX = IO_CONTROL[14:7];
assign NTC_MUX = IO_CONTROL[6:4];
assign IO_CONTROL[3:0] = GPIO_SENSE;

gpio #(
    .BASEADDR(GPIO_DAQ_CONTROL_BASEADDR),
    .HIGHADDR(GPIO_DAQ_CONTROL_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .IO_WIDTH(16),
    .IO_DIRECTION(16'hfff0)
) i_gpio_control (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(IO_CONTROL)
);

`ifdef BDAQ53
    `ifndef SIM
        wire [15:0] MEASURED_FPGA_TEMP;

        gpio #(
            .BASEADDR(GPIO_XADC_FPGA_TEMP_BASEADDR),
            .HIGHADDR(GPIO_XADC_FPGA_TEMP_HIGHADDR),
            .ABUSWIDTH(32),
            .IO_WIDTH(16),
            .IO_DIRECTION(16'h0000)
        ) i_gpio_xadc_fpga_temp (
            .BUS_CLK(BUS_CLK),
            .BUS_RST(BUS_RST),
            .BUS_ADD(BUS_ADD),
            .BUS_DATA(BUS_DATA),
            .BUS_RD(BUS_RD),
            .BUS_WR(BUS_WR),
            .IO(MEASURED_FPGA_TEMP)
        );

        wire [15:0] MEASURED_VPVN;

        gpio #(
            .BASEADDR(GPIO_XADC_VPVN_BASEADDR),
            .HIGHADDR(GPIO_XADC_VPVN_HIGHADDR),
            .ABUSWIDTH(32),
            .IO_WIDTH(16),
            .IO_DIRECTION(16'h0000)
        ) i_gpio_xadc_vpvn (
            .BUS_CLK(BUS_CLK),
            .BUS_RST(BUS_RST),
            .BUS_ADD(BUS_ADD),
            .BUS_DATA(BUS_DATA),
            .BUS_RD(BUS_RD),
            .BUS_WR(BUS_WR),
            .IO(MEASURED_VPVN)
        );

        // ------ XADC module for NTC (and FPGA-internal) temperature measurements ------ //
        xadc_ug480 i_xadc_ug480(
            .VAUXP(),
            .VAUXN(),
            .RESET(BUS_RST),
            .ALM(),
            .DCLK(BUS_CLK),
            .MEASURED_TEMP(MEASURED_FPGA_TEMP),
            .MEASURED_VPVN(MEASURED_VPVN),
            .MEASURED_VCCINT(),
            .MEASURED_VCCAUX(),
            .MEASURED_VCCBRAM(),
            .MEASURED_AUX0(),
            .MEASURED_AUX1(),
            .MEASURED_AUX2(),
            .MEASURED_AUX3()
        );
    `endif
`endif

// ----- Reset pulser ----- //
wire RST_PULSE;
reg [2:0] IO_FF;
always @(posedge CLK40) begin
    if (BUS_RST == 1'b1)
        IO_FF <= 3'b0;
    else
        IO_FF <= {IO_FF[2:0],IO[0]};
end

pulse_gen
#( 
    .BASEADDR(PULSE_RST_BASEADDR), 
    .HIGHADDR(PULSE_RST_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH)
) pulse_gen_rst
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .PULSE_CLK(CLK40),
    .EXT_START(~IO[0]),
    .PULSE(RST_PULSE)
);
assign RESETB_EXT = ~(IO_FF[1] | RST_PULSE);

`ifdef BDAQ53
    wire CMOS_PULSE_EXT;
`endif

// ------- I2C module ------- //
wire I2C_CLK;

clock_divider #(
.DIVISOR(1600)
) i_clock_divisor_i2c (
    .CLK(BUS_CLK),
    .RESET(1'b0),
    .CE(),
    .CLOCK(I2C_CLK)
);

i2c
#(
    .BASEADDR(I2C_BASEADDR),
    .HIGHADDR(I2C_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .MEM_BYTES(32)
)  i_i2c
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .I2C_CLK(I2C_CLK),
    .I2C_SDA(I2C_SDA),
    .I2C_SCL(I2C_SCL)
);

// ----- Pulser for injection ----- //
assign CMOS_PULSE_EXT = 1'b0;  // not connected for now
assign LVDS_PULSE_EXT = 1'b0;  // not connected for now

// ----- Command encoder ----- //
wire CMD;
wire CMD_OUT, CMD_OUTPUT_EN, CMD_WRITING;
wire CMD_LOOP_START;

wire EXT_START_PIN, EXT_TRIGGER;
wire CMD_EXT_START_ENABLED;
wire AZ_VETO_FLAG, AZ_VETO_TLU_PULSE;
assign AZ_VETO_TLU_PULSE = 1'b0;
cmd #(
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH)
) i_cmd (
    .CHIP_TYPE(),
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .EXT_START_PIN(EXT_START_PIN),
    .EXT_START_ENABLED(CMD_EXT_START_ENABLED),
    .EXT_TRIGGER(EXT_TRIGGER), // length of EXT_TRIGGER determines how many frames will be read out

    .AZ_PULSE(1'b0),
    .AZ_VETO_TLU_PULSE(AZ_VETO_TLU_PULSE),
    .AZ_VETO_FLAG(AZ_VETO_FLAG),

    .CMD_WRITING(CMD_WRITING),
    .CMD_LOOP_START(CMD_LOOP_START),
    .CMD_CLK(CLKCMD),
    .CMD_OUTPUT_EN(CMD_OUTPUT_EN),
    .CMD_SERIAL_OUT(CMD),
    .CMD_OUT(CMD_OUT)
);

`ifdef MIO3
    assign LVDS_SER_CLK = EN_LVDS_IN ? ~CLK160 : 1'b0;
    assign CMOS_SER_CLK = EN_CMOS_IN ? CLK160 : 1'b0;
    assign LVDS_CMD_CLK = EN_LVDS_IN ? ~CLKCMD : 1'b0;
    assign CMOS_CMD_CLK = EN_CMOS_IN ? CLKCMD : 1'b0;
    assign LVDS_CMD = EN_LVDS_IN ? ~CMD : 1'b0;
    assign CMOS_CMD = EN_CMOS_IN ? CMD : 1'b0;
`elsif BDAQ53
    ODDR ODDR_inst_SER_CLK (
        .Q(LVDS_SER_CLK), .C(CLK160), .CE(1'b1), .D1(1'b0), .D2(1'b1), .R(1'b0), .S(1'b0)
    );
    ODDR ODDR_inst_CMD_CLK (
        .Q(LVDS_CMD_CLK), .C(CLKCMD), .CE(1'b1), .D1(1'b0), .D2(1'b1), .R(1'b0), .S(1'b0)
    );
    ODDR ODDR_inst_CMD (
        .Q(LVDS_CMD), .C(CLKCMD), .CE(1'b1), .D1(~CMD_OUT), .D2(~CMD_OUT), .R(1'b0), .S(1'b0)
    );
`endif

pulse_gen #(
    .BASEADDR(PULSE_CMD_START_LOOP_BASEADDR),
    .HIGHADDR(PULSE_CMD_START_LOOP_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH)
) i_pulse_gen_cmd_start_loop (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK160),
    .EXT_START(CMD_LOOP_START),
    .PULSE(CMD_LOOP_START_PULSE)
);

// RX
wire RX_FIFO_READ, RX_FIFO_EMPTY;
wire [31:0] RX_FIFO_DATA;

// TLU
wire TLU_FIFO_READ, TLU_FIFO_EMPTY;
wire [31:0] TLU_FIFO_DATA;
wire TLU_FIFO_PREEMPT_REQ;

// TDC
wire TDC_LVDS_FIFO_READ, TDC_LVDS_FIFO_EMPTY, TDC_CMOS_FIFO_READ, TDC_CMOS_FIFO_EMPTY;
wire [31:0] TDC_LVDS_FIFO_DATA, TDC_CMOS_FIFO_DATA;

rrp_arbiter 
#( 
    .WIDTH(4)
) rrp_arbiter (
    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({
        ~RX_FIFO_EMPTY,
        ~TLU_FIFO_EMPTY,
        ~TDC_LVDS_FIFO_EMPTY,
        ~TDC_CMOS_FIFO_EMPTY
    }),
    .HOLD_REQ({1'b0, TLU_FIFO_PREEMPT_REQ, 1'b0, 1'b0}),
    .DATA_IN({
        RX_FIFO_DATA,
        TLU_FIFO_DATA,
        TDC_LVDS_FIFO_DATA,
        TDC_CMOS_FIFO_DATA
    }),
    .READ_GRANT({
        RX_FIFO_READ,
        TLU_FIFO_READ,
        TDC_LVDS_FIFO_READ,
        TDC_CMOS_FIFO_READ
    }),
    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

// ----- TLU ----- //
wire TRIGGER_ACKNOWLEDGE_FLAG,TRIGGER_ACCEPTED_FLAG;
wire [63:0] TIMESTAMP;
tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
    .ABUSWIDTH(ABUSWIDTH),
    .WIDTH(8),
    .TLU_TRIGGER_MAX_CLOCK_CYCLES(32),
    .TIMESTAMP_N_OF_BIT(64)
) i_tlu_controller (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TRIGGER_CLK(CLK40),

    .FIFO_READ(TLU_FIFO_READ),
    .FIFO_EMPTY(TLU_FIFO_EMPTY),
    .FIFO_DATA(TLU_FIFO_DATA),
    .FIFO_PREEMPT_REQ(TLU_FIFO_PREEMPT_REQ),

    .TRIGGER({8'b0}),
    .TRIGGER_VETO({7'b0, FIFO_FULL}),
    .TIMESTAMP_RESET(1'b0),
    .EXT_TRIGGER_ENABLE(1'b1),
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),

    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(RJ45_BUSY),
    .TLU_CLOCK(RJ45_CLK),
    .EXT_TIMESTAMP(),
    .TIMESTAMP(TIMESTAMP)
);

// ----- Pulser for TLU veto----- //
wire EXT_START_PULSE_VETO;
assign EXT_START_PULSE_VETO = TRIGGER_ACCEPTED_FLAG;
wire VETO_TLU_PULSE;

// set acknowledge when veto returns to low
pulse_gen_rising i_pulse_gen_rising_tlu_veto(.clk_in(CLK40), .in(~VETO_TLU_PULSE), .out(TRIGGER_ACKNOWLEDGE_FLAG));

pulse_gen #(
    .BASEADDR(PULSER_VETO_BASEADDR),
    .HIGHADDR(PULSER_VETO_HIGHADDR),
    .ABUSWIDTH(32)
) i_pulse_gen_veto (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40),
    .EXT_START(EXT_START_PULSE_VETO),
    .PULSE(VETO_TLU_PULSE)
);

// ----- TDC ----- //
localparam CLKDV = 4;  // division factor from 160 MHz clock to DV_CLK (here 40 MHz)
wire [CLKDV * 4 - 1:0] FAST_TRIGGER_OUT;
// wire LEMO_RX0_FROM_TDC;
// wire HITOR_FROM_TDC;

tdc_s3 #(
    .BASEADDR(TDC_LVDS_BASEADDR),
    .HIGHADDR(TDC_LVDS_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .CLKDV(CLKDV),
    .DATA_IDENTIFIER(4'b0010),
    .FAST_TDC(1),
    .FAST_TRIGGER(1),
    .BROADCAST(0)         // generate for LVDS TDC module the 640MHz sampled trigger signal and share it with other modules using TRIGGER input
) i_tdc_lvds (
    .CLK320(CLK320),      // 320 MHz
    .CLK160(CLK160),      // 160 MHz
    .DV_CLK(CLK40),       // 40 MHz
    .TDC_IN(LVDS_HITOR),  // LVDS HITOR (DP)
    .TDC_OUT(),
    .TRIG_IN(LEMO_RX[0]),
    .TRIG_OUT(),

    // input/output trigger signals for broadcasting mode
    .FAST_TRIGGER_IN(16'b0),
    .FAST_TRIGGER_OUT(FAST_TRIGGER_OUT),  // collect 640 MHz sampled trigger signal to pass it to other modules

    .FIFO_READ(TDC_LVDS_FIFO_READ),
    .FIFO_EMPTY(TDC_LVDS_FIFO_EMPTY),
    .FIFO_DATA(TDC_LVDS_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(1'b0),
    .EXT_EN(1'b0),

    .TIMESTAMP(TIMESTAMP[15:0])
);

tdc_s3 #(
    .BASEADDR(TDC_CMOS_BASEADDR),
    .HIGHADDR(TDC_CMOS_HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH),
    .CLKDV(CLKDV),
    .DATA_IDENTIFIER(4'b0001),
    .FAST_TDC(1),
    .FAST_TRIGGER(1),
    .BROADCAST(1)         // generate FAST_TRIGGER signal for LVDS TDC module and receive here
) i_tdc_cmos (
    .CLK320(CLK320),      // 320 MHz
    .CLK160(CLK160),      // 160 MHz
    .DV_CLK(CLK40),       // 40 MHz
    .TDC_IN(LEMO_RX[1]),  // CMOS HITOR (LEMO)
    .TDC_OUT(),
    .TRIG_IN(1'b0),
    .TRIG_OUT(),

    // input/output trigger signals for broadcasting mode
    .FAST_TRIGGER_IN(FAST_TRIGGER_OUT),  // looped through tdc_lvds instance
    .FAST_TRIGGER_OUT(),  // collect 640 MHz sampled trigger signal to pass it to other modules

    .FIFO_READ(TDC_CMOS_FIFO_READ),
    .FIFO_EMPTY(TDC_CMOS_FIFO_EMPTY),
    .FIFO_DATA(TDC_CMOS_FIFO_DATA),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .ARM_TDC(1'b0),
    .EXT_EN(1'b0),

    .TIMESTAMP(TIMESTAMP[15:0])
);

// fast readout
tjmono2_rx #(
    .BASEADDR(RX_BASEADDR),
    .HIGHADDR(RX_HIGHADDR),
    .DATA_IDENTIFIER(4'b0100),
    .ABUSWIDTH(ABUSWIDTH),
    .USE_FIFO_CLK(0)
) tjmono2_rx (
    .TS_CLK(CLK40),
    .FCLK(CLK160),
    .FCLK2X(CLK320),
    .RX_CLKW(CLK16),
    .RX_DATA(LVDS_DATA),

    .RX_READY(),
    .RX_8B10B_DECODER_ERR(),
    .RX_FIFO_OVERFLOW_ERR(),

    .FIFO_CLK(),
    .FIFO_READ(RX_FIFO_READ),
    .FIFO_EMPTY(RX_FIFO_EMPTY),
    .FIFO_DATA(RX_FIFO_DATA),

    .RX_FIFO_FULL(),
    .RX_ENABLED(),

    .TIMESTAMP(TIMESTAMP[51:0]),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR)
);

endmodule
