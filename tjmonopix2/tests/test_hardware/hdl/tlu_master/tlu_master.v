/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved 
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps
`default_nettype none


module tlu_master #(
    parameter BASEADDR = 16'h0000,
    parameter HIGHADDR = 16'h0000,
    parameter ABUSWIDTH = 16
)(
    input wire BUS_CLK,
    input wire [ABUSWIDTH-1:0] BUS_ADD,
    inout wire [7:0] BUS_DATA,
    input wire BUS_RST,
    input wire BUS_WR,
    input wire BUS_RD,

    input wire CLK320,
    input wire CLK160,
    input wire CLK40,

    input wire TEST_PULSE,
    output wire DUT_TRIGGER, DUT_RESET, 
    input  wire DUT_BUSY, DUT_CLOCK,
    input  wire BEAM_TRIGGER,
    
    input wire FIFO_READ,
    output wire FIFO_EMPTY,
    output wire [15:0] FIFO_DATA
);

wire IP_RD, IP_WR;
wire [ABUSWIDTH-1:0] IP_ADD;
wire [7:0] IP_DATA_IN;
wire [7:0] IP_DATA_OUT;

bus_to_ip #(
    .BASEADDR(BASEADDR),
    .HIGHADDR(HIGHADDR),
    .ABUSWIDTH(ABUSWIDTH)
) i_bus_to_ip (
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),

    .IP_RD(IP_RD),
    .IP_WR(IP_WR),
    .IP_ADD(IP_ADD),
    .IP_DATA_IN(IP_DATA_IN),
    .IP_DATA_OUT(IP_DATA_OUT)
);
tlu_master_core #(
    .ABUSWIDTH(ABUSWIDTH)
) tlu_master_core (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(IP_ADD),
    .BUS_DATA_IN(IP_DATA_IN),
    .BUS_RD(IP_RD),
    .BUS_WR(IP_WR),
    .BUS_DATA_OUT(IP_DATA_OUT),

    .CLK320(CLK320),
    .CLK160(CLK160),
    .CLK40(CLK40),
    
    .TEST_PULSE(TEST_PULSE),
    .DUT_TRIGGER(DUT_TRIGGER), .DUT_RESET(DUT_RESET), 
    .DUT_BUSY(DUT_BUSY), .DUT_CLOCK(DUT_CLOCK),
    .BEAM_TRIGGER(BEAM_TRIGGER),
    
    .FIFO_READ(FIFO_READ),
    .FIFO_EMPTY(FIFO_EMPTY),
    .FIFO_DATA(FIFO_DATA)
    
);

endmodule
