/**
 * ------------------------------------------------------------
 * Copyright (c) SILAB , Physics Institute of Bonn University
 * ------------------------------------------------------------
 */

`timescale 1ns / 1ps

`define BDAQ53
`define SIM

`include "tjmonopix2_core.v"
`include "tlu_model.v"
`include "utils/bus_to_ip.v"
`include "utils/generic_fifo.v"

// Use basil simulation modules instead of Xilinx IP
`include "utils/IDDR_sim.v"
`include "utils/ODDR_sim.v"
`include "utils/RAMB16_S1_S9_sim.v"

`include "bram_fifo/bram_fifo.v"
`include "bram_fifo/bram_fifo_core.v"

`include "tlu_master/tlu_ch_rx.v"
`include "tlu_master/tlu_master_core.v"
`include "tlu_master/tlu_master.v"
`include "tlu_master/tlu_tx.v"

// Chip RTL
`include "monopix2.sv"
// `include "MONOPIX_TOP.sv"

 module tb #(
    // FIRMWARE VERSION
    parameter VERSION_MAJOR = `VERSION_MAJOR,
    parameter VERSION_MINOR = `VERSION_MINOR,
    parameter VERSION_PATCH = `VERSION_PATCH
)(
    output wire        BUS_CLK /* verilator public_flat_rd */,
    input wire         BUS_RST /* verilator public_flat_rw */,
    input wire  [31:0] BUS_ADD /* verilator public_flat_rw */,
    input wire  [31:0] BUS_DATA_IN /* verilator public_flat_rw */,
    output wire [31:0] BUS_DATA_OUT /* verilator public_flat_rd */,
    input wire         BUS_RD /* verilator public_flat_rw */,
    input wire         BUS_WR /* verilator public_flat_rw */,
    output wire        BUS_BYTE_ACCESS /* verilator public_flat_rd */
 );

// Connect tb internal bus to external split bus
wire [31:0] BUS_DATA;
assign BUS_DATA = BUS_WR ? BUS_DATA_IN : 32'bz;
assign BUS_DATA_OUT = BUS_DATA;
assign BUS_BYTE_ACCESS = BUS_ADD < 32'h8000_0000 ? 1'b1 : 1'b0;

// CLOCK
wire CLK16;
wire CLK32;
wire CLK40 /* verilator public_flat_rd */;
wire CLK160;
reg CLK320 /* verilator public_flat_rw */;
wire CLKCMD;

clock_divider #(.DIVISOR(20) ) clock_divider3 ( .CLK(CLK320), .RESET(1'b0), .CE(), .CLOCK(CLK16) );
clock_divider #(.DIVISOR(10) ) clock_divider5 ( .CLK(CLK320), .RESET(1'b0), .CE(), .CLOCK(CLK32) );
clock_divider #(.DIVISOR(8) ) clock_divider2 ( .CLK(CLK320), .RESET(1'b0), .CE(), .CLOCK(CLK40) );
clock_divider #(.DIVISOR(2) ) clock_divider1 ( .CLK(CLK320), .RESET(1'b0), .CE(), .CLOCK(CLK160) );

assign BUS_CLK = CLK40;
assign CLKCMD = CLK160;

localparam FIFO_BASEADDR = 32'h8000;
localparam FIFO_HIGHADDR = 32'h9000-1;

localparam FIFO_BASEADDR_DATA = 32'h8000_0000;
localparam FIFO_HIGHADDR_DATA = 32'h9000_0000;

localparam TLU_MASTER_BASEADDR = 32'h7000;
localparam TLU_MASTER_HIGHADDR = 32'h8000 - 1;

// Verification
reg  [512*512-1:0] ANALOG_HIT /* verilator public_flat_rw */;
reg                BEAM_TRIGGER /* verilator public_flat_rw */;

// Firmware core
wire I2C_SDA, I2C_SCL;
wire CMD_LOOP_START_PULSE;
wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;
wire FIFO_FULL, FIFO_NEAR_FULL;
wire [4:0] LED;
wire LEMO_RX0, LEMO_RX1;
wire LEMO_MUX_TX1, LEMO_MUX_TX0, LEMO_MUX_RX1, LEMO_MUX_RX0;

wire RJ45_CLK, RJ45_BUSY, RJ45_RESET, RJ45_TRIGGER;
wire RESETB_EXT /* verilator public_flat_rd */;

wire LVDS_CMD, LVDS_CMD_CLK;
wire LVDS_SER_CLK;
wire LVDS_DATA;
wire LVDS_HITOR;
wire LVDS_PULSE_EXT;
wire LVDS_CHSYNC_LOCK;

wire [1:0] CHIP_ID;

tjmonopix2_core #(
    .VERSION_MAJOR(VERSION_MAJOR),
    .VERSION_MINOR(VERSION_MINOR),
    .VERSION_PATCH(VERSION_PATCH)
) fpga (
    //local bus
    .BUS_CLK(BUS_CLK),
    .BUS_DATA(BUS_DATA[7:0]),
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

    .RESETB_EXT(RESETB_EXT), 

    .LVDS_CMD(LVDS_CMD), 
    .LVDS_CMD_CLK(LVDS_CMD_CLK), 
    .LVDS_SER_CLK(LVDS_SER_CLK), 
    .LVDS_DATA(LVDS_DATA), 
    .LVDS_HITOR(LVDS_HITOR),
    .LVDS_PULSE_EXT(LVDS_PULSE_EXT),

    .CHIP_ID(CHIP_ID)
);

wire SELF_TRIGGER;
assign SELF_TRIGGER = 1'b0;

// tlu_model tlu (
//     .SYS_CLK(BUS_CLK),
//     .SYS_RST(BUS_RST),
//     .ENABLE(1'b1),

//     .START_TRIGGER(SELF_TRIGGER ? LVDS_HITOR : BEAM_TRIGGER),

//     .TLU_CLOCK(RJ45_CLK),
//     .TLU_BUSY(RJ45_BUSY),
//     .TLU_TRIGGER(RJ45_TRIGGER),
//     .TLU_RESET(RJ45_RESET)
// );

tlu_master #(
    .BASEADDR(TLU_MASTER_BASEADDR),
    .HIGHADDR(TLU_MASTER_HIGHADDR)
) tlu (
    .CLK320(CLK320),
    .CLK160(CLK160),
    .CLK40(CLK40),

    .TEST_PULSE(1'b0),
    .DUT_TRIGGER(RJ45_TRIGGER),
    .DUT_RESET(RJ45_RESET),
    .DUT_BUSY(RJ45_BUSY),
    .DUT_CLOCK(RJ45_CLK),
    .BEAM_TRIGGER(BEAM_TRIGGER),

    .FIFO_READ(1'b0),
    .FIFO_EMPTY(),
    .FIFO_DATA(),

    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR)
);

bram_fifo
#(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR),
    .BASEADDR_DATA(FIFO_BASEADDR_DATA),
    .HIGHADDR_DATA(FIFO_HIGHADDR_DATA),
    .ABUSWIDTH(32)
) i_out_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),

    .FIFO_NOT_EMPTY(),
    .FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_NEAR_FULL),
    .FIFO_READ_ERROR()
);

monopix2 dut (
    .RESETB_EXT(1'b1),  // No need to reset chip in tests
    .ANALOG_HIT(ANALOG_HIT),
    
    .LVDS_CMD(LVDS_CMD), 
    .LVDS_CMD_CLK(LVDS_CMD_CLK), 
    .LVDS_SER_CLK(LVDS_SER_CLK), 
    .LVDS_DATA_OUT(LVDS_DATA), 
    .LVDS_HITOR_OUT(LVDS_HITOR),
    .LVDS_PULSE_EXT(LVDS_PULSE_EXT),

    .LVDS_CHSYNC_LOCKED_OUT(LVDS_CHSYNC_LOCK),
    .LVDS_CHSYNC_CLK_OUT()
);

// MONOPIX_TOP dut (
//     .RESETB_EXT(1'b1),  // No need to reset chip in tests
//     .ANALOG_HIT(ANALOG_HIT),

//     .LVDS_CMD(LVDS_CMD), 
//     .LVDS_CMD_CLK(LVDS_CMD_CLK), 
//     .LVDS_SER_CLK(LVDS_SER_CLK), 
//     .LVDS_DATA_OUT(LVDS_DATA), 
//     .LVDS_HITOR_OUT(LVDS_HITOR),
//     .LVDS_PULSE_EXT(LVDS_PULSE_EXT),

//     .LVDS_CHSYNC_LOCKED_OUT(LVDS_CHSYNC_LOCK),
//     .LVDS_CHSYNC_CLK_OUT()
// );

endmodule
