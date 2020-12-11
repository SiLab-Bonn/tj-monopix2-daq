/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps

module cmd
#(
    parameter BASEADDR = 32'h0000,
    parameter HIGHADDR = 32'h0000,
    parameter ABUSWIDTH = 16
) (
    output wire [1:0]           CHIP_TYPE,
    input wire                  BUS_CLK,
    input wire                  BUS_RST,
    input wire  [ABUSWIDTH-1:0] BUS_ADD,
    inout wire  [7:0]           BUS_DATA,
    input wire                  BUS_RD,
    input wire                  BUS_WR,

    input wire                  EXT_START_PIN,
    output wire                 EXT_START_ENABLED,
    input wire                  EXT_TRIGGER,

    input wire                  AZ_PULSE,
    input wire                  AZ_VETO_TLU_PULSE,
    output wire                 AZ_VETO_FLAG,

    output wire                 CMD_WRITING,
    output wire                 CMD_LOOP_START,
    input wire                  CMD_CLK,
    output wire                 CMD_OUTPUT_EN,
    output wire                 CMD_SERIAL_OUT,
    output wire                 CMD_OUT,

    output wire                 BYPASS_MODE
);

wire IP_RD, IP_WR;
wire [ABUSWIDTH-1:0] IP_ADD;
wire [7:0] IP_DATA_IN;
wire [7:0] IP_DATA_OUT;

bus_to_ip #( .BASEADDR(BASEADDR), .HIGHADDR(HIGHADDR), .ABUSWIDTH(ABUSWIDTH) ) i_bus_to_ip
(
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


wire CMD_EN;

cmd_core
#(
    .ABUSWIDTH(ABUSWIDTH)
) i_cmd_core
(   
    .CHIP_TYPE(CHIP_TYPE),
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(IP_ADD),
    .BUS_DATA_IN(IP_DATA_IN),
    .BUS_RD(IP_RD),
    .BUS_WR(IP_WR),
    .BUS_DATA_OUT(IP_DATA_OUT),

    .EXT_START_PIN(EXT_START_PIN),
    .EXT_START_ENABLED(EXT_START_ENABLED),
    .EXT_TRIGGER(EXT_TRIGGER),

    .AZ_PULSE(AZ_PULSE),
    .AZ_VETO_TLU_PULSE(AZ_VETO_TLU_PULSE),
    .AZ_VETO_FLAG(AZ_VETO_FLAG),

    .CMD_WRITING(CMD_WRITING),
    .CMD_LOOP_START(CMD_LOOP_START),
    .CMD_CLK(CMD_CLK),
    .CMD_EN(CMD_EN),
    .CMD_SERIAL_OUT(CMD_SERIAL_OUT),
    .CMD_OUTPUT_EN(CMD_OUTPUT_EN),

    .BYPASS_MODE(BYPASS_MODE)
);

assign CMD_OUT = CMD_SERIAL_OUT & CMD_OUTPUT_EN;

endmodule
