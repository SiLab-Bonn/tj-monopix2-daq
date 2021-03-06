
`timescale 1ns / 1ps
`default_nettype none

module tjmonopix2_core (
    
    //local bus
    input wire BUS_CLK,
    inout wire [7:0] BUS_DATA,
    input wire [15:0] BUS_ADD,
    input wire BUS_RD,
    input wire BUS_WR,
    input wire BUS_RST,

    //clocks
    input wire CLK8,
    input wire CLK40,
    input wire CLK16,
    input wire CLK160,
    input wire CLK320,
    
    //fifo
    input wire ARB_READY_OUT,
    output wire ARB_WRITE_OUT,
    output wire [31:0] ARB_DATA_OUT,
    input wire FIFO_FULL,
    input wire FIFO_NEAR_FULL,
    
    // tlu, lemo, led
    output wire [4:0] LED,
    input wire [2:0] LEMO_RX,
    output wire [2:0] LEMO_TX,
    input wire RJ45_TRIGGER,
    input wire RJ45_RESET,

    // to chip
    output wire RESETB_EXT,
    output wire INPUT_SEL,
    
    output wire LVDS_CMD_CLK,
    output wire CMOS_CMD_CLK,    
    output wire LVDS_CMD,
    output wire CMOS_CMD,

    output wire LVDS_SER_CLK,
    output wire CMOS_SER_CLK,
    input wire DATA_OUT,

    output wire FREEZE_EXT,
    output wire READ_EXT,
    inout wire RO_RST_EXT,
    input wire TOKEN_OUT,
    input wire CMOS_DATA_OUT,

    output wire PULSE_EXT,
    output wire CMOS_PULSE_EXT,
    input wire HITOR_OUT,
    input wire CMOS_HITOR_OUT,
    input wire LVDS_CHSYNC_CLK_OUT,
    input wire LVDS_CHSYNC_LOCKED_OUT,
    inout wire [1:0] CHIP_ID
);

// -------  MODULE ADREESSES  ------- //
localparam GPIO_BASEADDR = 16'h0010;
localparam GPIO_HIGHADDR = 16'h0100-1;

localparam PULSE_INJ_BASEADDR = 16'h0100;
localparam PULSE_INJ_HIGHADDR = 16'h0200-1;

localparam RX_BASEADDR = 16'h0200;
localparam RX_HIGHADDR = 16'h0300-1; 

localparam PULSE_RST_BASEADDR = 16'h0400;
localparam PULSE_RST_HIGHADDR = 16'h0500-1;

localparam DIRECT_RX_BASEADDR = 16'h0500;
localparam DIRECT_RX_HIGHADDR = 16'h0600-1;

localparam TLU_BASEADDR = 16'h0600;
localparam TLU_HIGHADDR = 16'h0700-1;

localparam TS_INJ_BASEADDR = 16'h0700;
localparam TS_INJ_HIGHADDR = 16'h0800-1;
//localparam TS_CMOS_HIT_OR_BASEADDR = 16'h0800;
//localparam TS_CMOS_HIT_OR_HIGHADDR = 16'h0900-1;
localparam TS_HIT_OR_BASEADDR = 16'h0900;
localparam TS_HIT_OR_HIGHADDR = 16'h0A00-1;

localparam PULSE_TRIG_BASEADDR = 16'h0B00;
localparam PULSE_TRIG_HIGHADDR = 16'h0C00 - 1;

localparam PULSE_CMD_START_LOOP_BASEADDR = 16'h0C00;
localparam PULSE_CMD_START_LOOP_HIGHADDR = 16'h0D00 - 1;

localparam TS_RX0_BASEADDR = 16'h0D00;
localparam TS_RX0_HIGHADDR = 16'h0E00-1;

localparam CMD_BASEADDR = 16'h0E00;
localparam CMD_HIGHADDR = 16'h2E00 - 1;

// -------  USER MODULES  ------- //
localparam VERSION = 8'h01;
reg RD_VERSION;
always@(posedge BUS_CLK)
    if(BUS_ADD == 16'h0000 && BUS_RD)
        RD_VERSION <= 1;
    else
        RD_VERSION <= 0;
assign BUS_DATA = (RD_VERSION) ? VERSION : 8'bz;
reg CLK32;
reg [4:0] clk32_cnt;
always@(negedge CLK320) begin
    if (BUS_RST == 1'b1 | clk32_cnt == 4'd9)
        clk32_cnt <= 4'd0;
    else
       clk32_cnt <= clk32_cnt +1;
end
always@(negedge CLK320) begin
    if (BUS_RST == 1'b1 | clk32_cnt == 4'd8)
        CLK32 <= 1'b0;
    else if (clk32_cnt == 4'd3)
       CLK32 <= 1'b1;
end

wire [23:0] IO;
gpio 
#( 
    .BASEADDR(GPIO_BASEADDR), 
    .HIGHADDR(GPIO_HIGHADDR),
    .IO_WIDTH(24),
    .IO_DIRECTION(24'hfff0ff)
) gpio_i
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(IO)
);    
wire EN_LVDS_IN, EN_CMOS_IN, EN_CMOS_OUT, SEL_DIRECT, SEL_SER_CLK;
wire [2:0] GPIO_MODE;
//assign RESETB_EXT = ~IO[0];
assign INPUT_SEL = IO[1];
assign EN_CMOS_IN = IO[2];
assign EN_CMOS_OUT = IO[6];
assign EN_LVDS_IN = IO[7];

assign IO[8] = LVDS_CHSYNC_LOCKED_OUT;
assign IO[9] = LVDS_CHSYNC_CLK_OUT;
assign IO[11:10] = {RO_RST_EXT, CHIP_ID};
assign GPIO_MODE = IO[14:12];
assign SEL_SER_CLK = IO[15];
assign SEL_DIRECT = IO[16]; 

assign CHIP_ID[0] = GPIO_MODE[0] ? 1'bz : IO[3];
assign CHIP_ID[1] = GPIO_MODE[1] ? 1'bz : IO[4];
assign RO_RST_EXT = GPIO_MODE[2] ? 1'bz : IO[5];

wire SER_CLK;
assign SER_CLK = SEL_SER_CLK ? CLK320 : CLK160;
assign LVDS_SER_CLK = EN_LVDS_IN ? ~SER_CLK : 1'b0;
assign CMOS_SER_CLK = EN_CMOS_IN ? SER_CLK : 1'b0;
wire CMD_CLK;
assign CMD_CLK = CLK160;
assign LVDS_CMD_CLK = EN_LVDS_IN ? ~CMD_CLK : 1'b0;
assign CMOS_CMD_CLK = EN_CMOS_IN ? CMD_CLK : 1'b0;
wire HITOR;
`ifdef COCOTB_SIM
    assign HITOR = EN_CMOS_OUT ? CMOS_HITOR_OUT : HITOR_OUT;
`else
    assign HITOR = HITOR_OUT;  //TODO change code here to use CMOS HITOR
    //assign HITOR = CMOS_HITOR_OUT;
`endif

// -----Reset Pulser ---- //
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
    .HIGHADDR(PULSE_RST_HIGHADDR)
) pulse_gen_rst
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .PULSE_CLK(CLK320),
    .EXT_START(~IO[0]),
    .PULSE(RST_PULSE)
);
assign RESETB_EXT = ~(IO_FF[1] | RST_PULSE);

//************************************************
// external INJECTION
wire EXT_TRIGGER;
`ifdef CODE_FOR_MIO3
pulse_gen640 #( 
    .BASEADDR(PULSE_INJ_BASEADDR), 
    .HIGHADDR(PULSE_INJ_HIGHADDR),
    .ABUSWIDTH(16),
    .CLKDV(4),
    .OUTPUT_SIZE(3)
) pulse_gen_inj (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK320(CLK320),
    .PULSE_CLK160(CLK160),
    .PULSE_CLK(CLK40),
    .EXT_START(EXT_TRIGGER),
    .PULSE({LEMO_TX[2],CMOS_PULSE_EXT,PULSE_EXT}),
    .DEBUG()
);
`else
wire PULSE;
pulse_gen
#( 
    .BASEADDR(PULSE_INJ_BASEADDR), 
    .HIGHADDR(PULSE_INJ_HIGHADDR)
) pulse_gen_inj
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40),
    .EXT_START(EXT_TRIGGER), //TODO maybe not needed?
    .PULSE(PULSE)
);
assign CMOS_PULSE_EXT = EN_CMOS_IN ? PULSE : 1'b0;
assign PULSE_EXT = EN_LVDS_IN ? ~PULSE : 1'b0;

assign LEMO_TX[2] = PULSE;
`endif

// ----- Pulser for trigger command----- //
wire EXT_START_VETO;
pulse_gen #(
    .BASEADDR(PULSE_TRIG_BASEADDR),
    .HIGHADDR(PULSE_TRIG_HIGHADDR)
) i_pulse_gen_trig (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK160),
    .EXT_START(RJ45_TRIGGER & ~EXT_START_VETO),   // don't send triggers during the az phase (for sync fe)
    .PULSE(EXT_TRIGGER)
);

// ----- Command encoder ----- //
wire CMD;
wire CMD_OUT, CMD_WRITING, CMD_OUTPUT_EN; //TODO they were output wire but connected to nowhere
wire BYPASS_MODE;                         //TODO it was output wire...
wire CMD_LOOP_START_PULSE;                //TODO it was output wire...
wire CMD_LOOP_START;

wire EXT_START_PIN;
wire CMD_EXT_START_ENABLED;
wire AZ_VETO_FLAG, AZ_VETO_TLU_PULSE;
assign EXT_START_VETO = AZ_VETO_FLAG;   // don't send triggers during the az phase (for sync fe)
assign AZ_VETO_TLU_PULSE = 1'b0;
cmd #(
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(16)
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
    .CMD_CLK(CMD_CLK),
    .CMD_OUTPUT_EN(CMD_OUTPUT_EN),
    .CMD_SERIAL_OUT(CMD),
    .CMD_OUT(CMD_OUT),

    .BYPASS_MODE(BYPASS_MODE)
);
assign LVDS_CMD = EN_LVDS_IN ? ~CMD : 1'b0;
assign CMOS_CMD = EN_CMOS_IN ? CMD : 1'b0;

// ----- CMD_START_LOOP -> TDC pulse generator ----- // TODO delete??
pulse_gen #(
    .BASEADDR(PULSE_CMD_START_LOOP_BASEADDR),
    .HIGHADDR(PULSE_CMD_START_LOOP_HIGHADDR)
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

wire RX_FIFO_READ, RX_FIFO_EMPTY;
wire [31:0] RX_FIFO_DATA;
wire DIRECT_RX_FIFO_READ, DIRECT_RX_FIFO_EMPTY;
wire [31:0] DIRECT_RX_FIFO_DATA;
wire TS_HIT_OR_FIFO_READ,TS_HIT_OR_FIFO_EMPTY;
wire [31:0] TS_HIT_OR_FIFO_DATA;
wire TS_HIT_OR_TRAILING_FIFO_READ,TS_HIT_OR_TRAILING_FIFO_EMPTY;
wire [31:0] TS_HIT_OR_TRAILING_FIFO_DATA;

wire  TLU_FIFO_READ, TLU_FIFO_EMPTY;
wire [31:0] TLU_FIFO_DATA;
wire TS_RX0_FIFO_READ,TS_RX0_FIFO_EMPTY;
wire [31:0] TS_RX0_FIFO_DATA;
wire TS_INJ_FIFO_READ,TS_INJ_FIFO_EMPTY;
wire [31:0] TS_INJ_FIFO_DATA;

rrp_arbiter 
#( 
    .WIDTH(7)
) rrp_arbiter (

    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TS_RX0_FIFO_EMPTY, ~TS_INJ_FIFO_EMPTY,
        ~TS_HIT_OR_TRAILING_FIFO_EMPTY,~TS_HIT_OR_FIFO_EMPTY, 
        ~DIRECT_RX_FIFO_EMPTY, ~RX_FIFO_EMPTY, ~TLU_FIFO_EMPTY}),
    .HOLD_REQ(5'b0),
    .DATA_IN({TS_RX0_FIFO_DATA,TS_INJ_FIFO_DATA,
        TS_HIT_OR_TRAILING_FIFO_DATA, TS_HIT_OR_FIFO_DATA,
        DIRECT_RX_FIFO_DATA, RX_FIFO_DATA,TLU_FIFO_DATA}),
    .READ_GRANT({TS_RX0_FIFO_READ,TS_INJ_FIFO_READ,
        TS_HIT_OR_TRAILING_FIFO_READ, TS_HIT_OR_FIFO_READ, 
        DIRECT_RX_FIFO_READ, RX_FIFO_READ,TLU_FIFO_READ}),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

//************************************************
// TLU
wire TRIGGER_ACKNOWLEDGE_FLAG,TRIGGER_ACCEPTED_FLAG;
assign TRIGGER_ACKNOWLEDGE_FLAG = TRIGGER_ACCEPTED_FLAG;
wire [63:0] TIMESTAMP;
wire TLU_BUSY, TLU_CLK, TLU_TRIGGER;
tlu_slave #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8)
) i_tlu_slave (
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
    .FIFO_PREEMPT_REQ(),
     
    .TRIGGER_ENABLED(),
    .TRIGGER_SELECTED(),
    .TLU_ENABLED(),
    .TRIGGER({8'b0}),
    .TRIGGER_VETO({7'b0,FIFO_FULL}),
    .TIMESTAMP_RESET(),
    .EXT_TRIGGER_ENABLE(),     //.EXT_TRIGGER_ENABLE(TLU_EXT_TRIGGER_ENABLE)
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),

    .TLU_TRIGGER(TLU_TRIGGER),
    .TLU_RESET(1'b0),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLK),
    .EXT_TIMESTAMP(),
    .TIMESTAMP(TIMESTAMP)
);
assign LEMO_TX[0] = TLU_CLK;
assign LEMO_TX[1] = TLU_BUSY;
assign TLU_TRIGGER = RJ45_TRIGGER;

timestamp640 #(
    .BASEADDR(TS_HIT_OR_BASEADDR),
    .HIGHADDR(TS_HIT_OR_HIGHADDR),
    .IDENTIFIER(4'b0110)
)i_timestamp640_hit_or(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK40(CLK40),
    .CLK160(CLK160),
    .CLK320(CLK320),
    .DI(HITOR),
    .EXT_ENABLE(),
    .EXT_TIMESTAMP(TIMESTAMP),
    .TIMESTAMP_OUT(),
    .FIFO_READ(TS_HIT_OR_FIFO_READ),
    .FIFO_EMPTY(TS_HIT_OR_FIFO_EMPTY),
    .FIFO_DATA(TS_HIT_OR_FIFO_DATA),
    .FIFO_READ_TRAILING(TS_HIT_OR_TRAILING_FIFO_READ),
    .FIFO_EMPTY_TRAILING(TS_HIT_OR_TRAILING_FIFO_EMPTY),
    .FIFO_DATA_TRAILING(TS_HIT_OR_TRAILING_FIFO_DATA)
);

timestamp640 #(
    .BASEADDR(TS_RX0_BASEADDR),
    .HIGHADDR(TS_RX0_HIGHADDR),
    .IDENTIFIER(4'b0110)
)i_timestamp640_rx0(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK40(CLK40),
    .CLK160(CLK160),
    .CLK320(CLK320),
    .DI(LEMO_RX[0]),
    .EXT_ENABLE(),
    .EXT_TIMESTAMP(TIMESTAMP),
    .TIMESTAMP_OUT(),
    .FIFO_READ(TS_RX0_FIFO_READ),
    .FIFO_EMPTY(TS_RX0_FIFO_EMPTY),
    .FIFO_DATA(TS_RX0_FIFO_DATA),
    .FIFO_READ_TRAILING(),
    .FIFO_EMPTY_TRAILING(),
    .FIFO_DATA_TRAILING()
);
// LEMO_RX0 or flatcable 5 is loop back of injection pulse
timestamp640 #(
    .BASEADDR(TS_INJ_BASEADDR),
    .HIGHADDR(TS_INJ_HIGHADDR),
    .IDENTIFIER(4'b0110)
)i_timestamp640_inj(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK40(CLK40),
    .CLK160(CLK160),
    .CLK320(CLK320),
    .DI(LEMO_RX[2]),
    .EXT_ENABLE(),
    .EXT_TIMESTAMP(TIMESTAMP),
    .TIMESTAMP_OUT(),
    .FIFO_READ(TS_INJ_FIFO_READ),
    .FIFO_EMPTY(TS_INJ_FIFO_EMPTY),
    .FIFO_DATA(TS_INJ_FIFO_DATA),
    .FIFO_READ_TRAILING(),
    .FIFO_EMPTY_TRAILING(),
    .FIFO_DATA_TRAILING()
);

//************************************************
// fast readout
wire  RX_CLKX2,RX_CLKW;
assign  RX_CLKX2 = SEL_SER_CLK ? CLK320 : CLK160;
assign  RX_CLKW = SEL_SER_CLK ? CLK32 : CLK16;
tjmono2_rx #(
        .BASEADDR(RX_BASEADDR),
        .HIGHADDR(RX_HIGHADDR),
        .DATA_IDENTIFIER(4'h4),
        .ABUSWIDTH(16),
        .USE_FIFO_CLK(0)
) tjmono2_rx (
        .RX_CLKX2(RX_CLKX2),
        .RX_CLKW(RX_CLKW),
        .RX_DATA(DATA_OUT),

        .RX_READY(),
        .RX_8B10B_DECODER_ERR(),
        .RX_FIFO_OVERFLOW_ERR(),

        .FIFO_CLK(),
        .FIFO_READ(RX_FIFO_READ),
        .FIFO_EMPTY(RX_FIFO_EMPTY),
        .FIFO_DATA(RX_FIFO_DATA),

        .RX_FIFO_FULL(),
        .RX_ENABLED(),

        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
        );

//************************************************
// direct readout
wire DIRECT_DATA,RX_CLK;
assign DIRECT_DATA = SEL_DIRECT ? CMOS_DATA_OUT : DATA_OUT;
assign RX_CLK = SEL_SER_CLK ? CLK32 : CLK16;
tjmono_direct_rx #(
    .BASEADDR(DIRECT_RX_BASEADDR),
    .HIGHADDR(DIRECT_RX_HIGHADDR),
    .ABUSWIDTH(16),
    .IDENTIFIER(2'b00)
)tjmono_direct_rx(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .TIMESTAMP(TIMESTAMP),

    .RX_TOKEN(TOKEN_OUT), 
    .RX_DATA(DIRECT_DATA), 
    .RX_CLK(RX_CLK),
    .RX_READ(READ_EXT), 
    .RX_FREEZE(FREEZE_EXT),

    .FIFO_READ(DIRECT_RX_FIFO_READ),
    .FIFO_EMPTY(DIRECT_RX_FIFO_EMPTY),
    .FIFO_DATA(DIRECT_RX_FIFO_DATA)
); 

endmodule
