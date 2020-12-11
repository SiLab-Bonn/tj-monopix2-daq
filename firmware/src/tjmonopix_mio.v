
`timescale 1ns / 1ps
`default_nettype none

`include "clk_gen.v"

`include "utils/bus_to_ip.v"

`include "utils/cdc_syncfifo.v"
`include "utils/generic_fifo.v"
`include "utils/cdc_pulse_sync.v"

`include "utils/flag_domain_crossing.v"
`include "utils/ddr_des.v"
`include "utils/3_stage_synchronizer.v"

`include "utils/reset_gen.v"
`include "utils/pulse_gen_rising.v"
`include "utils/CG_MOD_pos.v"
 
`include "spi/spi_core.v"
`include "spi/spi.v"
`include "spi/blk_mem_gen_8_to_1_2k.v"

`include "gpio/gpio.v"

`include "tlu/tlu_controller.v"
`include "tlu/tlu_controller_core.v"
`include "tlu/tlu_controller_fsm.v"

`include "timestamp/timestamp.v"
`include "timestamp/timestamp_core.v"
`include "timestamp_div/timestamp_div.v"
`include "timestamp_div/timestamp_div_core.v"

//`include "utils/cdc_reset_sync.v"
`include "utils/fx2_to_bus.v"

`include "pulse_gen/pulse_gen.v"
`include "pulse_gen/pulse_gen_core.v"

`include "sram_fifo/sram_fifo_core.v"
`include "sram_fifo/sram_fifo.v"

`include "rrp_arbiter/rrp_arbiter.v"

`include "cmd/cmd.v"
`include "cmd/cmd_core.v"

`include "tjmono_data_rx/tjmono_data_rx.v"
`include "tjmono_data_rx/tjmono_data_rx_core.sv"
`include "utils/cdc_reset_sync.v"

`include "fei4_rx/fei4_rx_core.v"
`include "fei4_rx/receiver_logic.v"
`include "fei4_rx/sync_master.v"
`include "fei4_rx/rec_sync.v"
`include "fei4_rx/decode_8b10b.v"
`include "fei4_rx/fei4_rx.v"
`include "utils/flag_domain_crossing.v"


`ifdef COCOTB_SIM //for simulation
    `include "utils/ODDR_sim.v"
    `include "utils/IDDR_sim.v"
    `include "utils/DCM_sim.v"
    `include "utils/clock_multiplier.v"
    `include "utils/BUFG_sim.v"

    `include "utils/RAMB16_S1_S9_sim.v"
    //`include "utils/IBUFDS_sim.v"
    //`include "utils/IBUFGDS_sim.v"
    //`include "utils/OBUFDS_sim.v"
`else
    `include "utils/IDDR_s3.v"
    `include "utils/ODDR_s3.v"
`endif 



module tjmonopix_mio (

    input wire FCLK_IN, // 48MHz
    input wire TRIG_EXT,
    output wire TRIGGER,

    //full speed 
    inout wire [7:0] BUS_DATA,
    input wire [15:0] ADD,
    input wire RD_B,
    input wire WR_B,

    //high speed
    inout wire [7:0] FDATA,
    input wire FREAD,
    input wire FSTROBE,
    input wire FMODE,

    //LED
    output wire [4:0] LED,

    //SRAM
    output wire [19:0] SRAM_A,
    inout wire [15:0] SRAM_IO,
    output wire SRAM_BHE_B,
    output wire SRAM_BLE_B,
    output wire SRAM_CE1_B,
    output wire SRAM_OE_B,
    output wire SRAM_WE_B,

    input wire [2:0] LEMO_RX,
    output wire [2:0] LEMO_TX, 
    input wire RJ45_RESET,
    input wire RJ45_TRIGGER,

    input wire SO_CONF,
    output wire CLK_CONF,
    output wire DEF_CONF,
    output wire SI_CONF,
    output wire LD_CONF,
    output wire RST_N,

    output wire INJECTION,
	 output wire INJECTION_MON,

    output wire CLK_BX,
    output wire CLK_OUT,
    output wire CLK_CMD,
    output wire READ_A,
    output wire READ_B,
    output wire FREEZE_A,
    output wire FREEZE_B,
    output wire RESET_BCID,

    input wire TOK_A,
    input wire TOK_B,
    input wire OUT_A,
    input wire OUT_B,
    input wire HITOR_A, 
    input wire HITOR_B,
    output wire RX_READY,

    input wire RX_DATA,

    // I2C
    inout wire SDA,
    inout wire SCL,

    // CMD encoder
    input wire EXT_TRIGGER,
    output wire CMD_DATA, CMD_OUT, CMD_WRITING, CMD_OUTPUT_EN,
    output wire BYPASS_MODE,
    output wire CMD_LOOP_START_PULSE,

    //Encoded data
    input wire DUT_OUT_DATA
);

assign SDA = 1'bz;
assign SCL = 1'bz;


// ------- RESET / CLOCK  ------- //

wire BUS_RST;

(* KEEP = "{TRUE}" *) 
wire CLK320;  
(* KEEP = "{TRUE}" *) 
wire CLK160;
(* KEEP = "{TRUE}" *) 
wire CLK40;
//(* KEEP = "{TRUE}" *) 
wire CLK16;
(* KEEP = "{TRUE}" *) 
wire BUS_CLK;
(* KEEP = "{TRUE}" *) 
wire CLK8;

reset_gen reset_gen(.CLK(BUS_CLK), .RST(BUS_RST));

wire CLK_LOCKED;

clk_gen clk_gen(
    .CLKIN(FCLK_IN),
    .BUS_CLK(BUS_CLK),
    .U1_CLK8(CLK8),
    .U2_CLK40(CLK40),
    .U2_CLK16(CLK16),
    .U2_CLK160(CLK160),
    .U2_CLK320(CLK320),
    .U2_LOCKED(CLK_LOCKED)
);

wire [1:0] CHIP_TYPE;

// -------  MODULE ADREESSES  ------- //
localparam GPIO_BASEADDR = 16'h0000;
localparam GPIO_HIGHADDR = 16'h0100-1;

localparam PULSE_INJ_BASEADDR = 16'h0100;
localparam PULSE_INJ_HIGHADDR = 16'h0200-1;
	
localparam PULSE_TRIG_BASEADDR = 16'h0200;
localparam PULSE_TRIG_HIGHADDR = 16'h0300-1;

localparam DATA_RX_BASEADDR = 16'h0500;
localparam DATA_RX_HIGHADDR = 16'h0600-1;

localparam SPI_BASEADDR = 16'h5000;
localparam SPI_HIGHADDR = 16'h6000-1;

localparam PULSE_GATE_TDC_BASEADDR = 16'h0400;
localparam PULSE_GATE_TDC_HIGHADDR = 16'h0500-1;

localparam TLU_BASEADDR = 16'h0600;
localparam TLU_HIGHADDR = 16'h0700-1;

localparam TS_BASEADDR = 16'h0700;
localparam TS_HIGHADDR = 16'h0800-1;

localparam FIFO_BASEADDR = 16'h8000;
localparam FIFO_HIGHADDR = 16'h9000-1;

localparam TS_TDC_BASEADDR = 16'h0900;
localparam TS_TDC_HIGHADDR = 16'h0A00-1;

localparam TS_TLU_BASEADDR = 16'h0A00;
localparam TS_TLU_HIGHADDR = 16'h0B00-1;

localparam PULSER_TRIG_BASEADDR = 16'h0B00;
localparam PULSER_TRIG_HIGHADDR = 16'h0C00 - 1;

localparam PULSE_CMD_START_LOOP_BASEADDR = 16'h0C00;
localparam PULSE_CMD_START_LOOP_HIGHADDR =  16'h0D00 - 1;

localparam CMD_BASEADDR = 16'h0D00;
localparam CMD_HIGHADDR = 16'h2D00 - 1;

localparam FERX_BASEADDR = 32'h6000;
localparam FERX_HIGHADDR = 32'h7000-1;  

// -------  BUS SYGNALING  ------- //
wire [15:0] BUS_ADD;
wire BUS_RD, BUS_WR;

// -------  BUS SYGNALING  ------- //
fx2_to_bus fx2_to_bus (
    .ADD(ADD),
    .RD_B(RD_B),
    .WR_B(WR_B),

    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .CS_FPGA()
);

// -------  USER MODULES  ------- //
wire [15:0] GPIO_OUT;
gpio #( 
    .BASEADDR(GPIO_BASEADDR), 
    .HIGHADDR(GPIO_HIGHADDR),
    .IO_WIDTH(16),
    .IO_DIRECTION(16'hffff)
) gpio
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    .IO(GPIO_OUT)
    );    

wire RESET_CONF, RESET_BCID_CONF;
wire EN_BX_CLK_CONF, EN_OUT_CLK_CONF, SELECTAB;
wire READ_AB, FREEZE_AB, OUT_AB, TOK_AB;
wire EN_HITOR_TX;

assign RESET_CONF = GPIO_OUT[0];
assign RESET_BCID_CONF = GPIO_OUT[1];
assign EN_BX_CLK_CONF = GPIO_OUT[2];
assign EN_OUT_CLK_CONF = GPIO_OUT[3];
assign DEF_CONF = GPIO_OUT[4];
assign SELECTAB = GPIO_OUT[5];
assign EN_HITOR_TX = GPIO_OUT[5];

wire CONF_CLK;
assign CONF_CLK = CLK8;
    
wire SCLK, SDI, SDO, SEN, SLD;
spi #( 
    .BASEADDR(SPI_BASEADDR), 
    .HIGHADDR(SPI_HIGHADDR),
    .MEM_BYTES(4096) 
    )  spi_conf
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .SPI_CLK(CONF_CLK),

    .SCLK(SCLK),
    .SDI(SDI),
    .SDO(SDO),
    .SEN(SEN),
    .SLD(SLD)
);

assign CLK_CONF = SCLK;
assign SI_CONF = SDI;
assign SDO = SO_CONF;    
assign LD_CONF = SLD;

wire GATE_TDC;

pulse_gen #( 
    .BASEADDR(PULSE_TRIG_BASEADDR), 
    .HIGHADDR(PULSE_TRIG_HIGHADDR)
	) pulse_gen_trig
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40), //~CLK40),
    .EXT_START(TRIG_EXT || INJECTION),
    .PULSE(TRIGGER)
);

pulse_gen #( 
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

    .PULSE_CLK(CLK40), //~CLK40),
    .EXT_START(GATE_TDC),
    .PULSE(INJECTION)
);

pulse_gen #( 
    .BASEADDR(PULSE_GATE_TDC_BASEADDR), 
    .HIGHADDR(PULSE_GATE_TDC_HIGHADDR)
    ) pulse_gen_gate_tdc
(
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA[7:0]),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK40),
    .EXT_START(1'b0),
    .PULSE(GATE_TDC) 
);

// ----- Pulser for trigger command----- //
wire EXT_TRIGGER_PULSE;
wire EXT_START_VETO;
wire EXT_START_PULSE_TRIG;

pulse_gen #(
    .BASEADDR(PULSER_TRIG_BASEADDR),
    .HIGHADDR(PULSER_TRIG_HIGHADDR)
) i_pulse_gen_trig (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .PULSE_CLK(CLK_CMD),
    .EXT_START(EXT_START_PULSE_TRIG  & ~EXT_START_VETO),   // don't send triggers during the az phase (for sync fe)
    .PULSE(EXT_TRIGGER_PULSE)
);

// ----- Command encoder ----- //
wire EXT_START_PIN;
wire CMD_EXT_START_ENABLED;
wire AZ_VETO_FLAG, AZ_VETO_TLU_PULSE;
assign EXT_START_VETO = AZ_VETO_FLAG;   // don't send triggers during the az phase (for sync fe)
wire CMD_LOOP_START;

cmd #(
    .BASEADDR(CMD_BASEADDR),
    .HIGHADDR(CMD_HIGHADDR),
    .ABUSWIDTH(16)
) i_cmd (
    .CHIP_TYPE(CHIP_TYPE),
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),

    .EXT_START_PIN(EXT_START_PIN),
    .EXT_START_ENABLED(CMD_EXT_START_ENABLED),
    .EXT_TRIGGER(EXT_TRIGGER_PULSE), // length of EXT_TRIGGER_PULSE determines how many frames will be read out

    .AZ_PULSE(1'b0),
    .AZ_VETO_TLU_PULSE(AZ_VETO_TLU_PULSE),
    .AZ_VETO_FLAG(AZ_VETO_FLAG),

    .CMD_WRITING(CMD_WRITING),
    .CMD_LOOP_START(CMD_LOOP_START),
    .CMD_CLK(CLK_CMD),
    .CMD_OUTPUT_EN(CMD_OUTPUT_EN),
    .CMD_SERIAL_OUT(CMD_DATA),
    .CMD_OUT(CMD_OUT),

    .BYPASS_MODE(BYPASS_MODE)
);

// ----- CMD_START_LOOP -> TDC pulse generator ----- //
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

    .PULSE_CLK(CLK_CMD),
    .EXT_START(CMD_LOOP_START),
    .PULSE(CMD_LOOP_START_PULSE)
    );


wire ARB_READY_OUT, ARB_WRITE_OUT;
wire [31:0] ARB_DATA_OUT;


wire FE_FIFO_READ, TS_FIFO_READ, TLU_FIFO_READ, TS_TDC_FIFO_READ,TS_TLU_FIFO_READ, FE_DIRECT_READ;
wire FE_FIFO_EMPTY, TS_FIFO_EMPTY, TLU_FIFO_EMPTY,TS_TDC_FIFO_EMPTY, TS_TLU_FIFO_EMPTY, FE_DIRECT_EMPTY;
wire [31:0] FE_FIFO_DATA;
wire [31:0] TS_FIFO_DATA;
wire [31:0] TLU_FIFO_DATA;
wire [31:0] TS_TDC_FIFO_DATA;
wire [31:0] TS_TLU_FIFO_DATA;
wire [31:0] FE_DIRECT_FIFO_DATA;
wire TLU_FIFO_PEEMPT_REQ;

wire FIFO_FULL;

rrp_arbiter 
#( 
    .WIDTH(6)
) rrp_arbiter (

    .RST(BUS_RST),
    .CLK(BUS_CLK),

    .WRITE_REQ({~TS_TDC_FIFO_EMPTY,~TS_TLU_FIFO_EMPTY, ~TS_FIFO_EMPTY, ~FE_DIRECT_EMPTY, ~TLU_FIFO_EMPTY, ~FE_FIFO_EMPTY}),
    .HOLD_REQ({4'b0, TLU_FIFO_PEEMPT_REQ}),
    .DATA_IN({TS_TDC_FIFO_DATA, TS_TLU_FIFO_DATA, TS_FIFO_DATA, FE_DIRECT_FIFO_DATA, TLU_FIFO_DATA, FE_FIFO_DATA}),
    .READ_GRANT({TS_TDC_FIFO_READ,TS_TLU_FIFO_READ,TS_FIFO_READ, FE_DIRECT_READ, TLU_FIFO_READ, FE_FIFO_READ}),

    .READY_OUT(ARB_READY_OUT),
    .WRITE_OUT(ARB_WRITE_OUT),
    .DATA_OUT(ARB_DATA_OUT)
);

wire TDC_TDC_OUT, TDC_TRIG_OUT;
wire HITOR_AB;

wire [63:0] TIMESTAMP;
wire TLU_BUSY,TLU_CLOCK;
wire TRIGGER_ACKNOWLEDGE_FLAG,TRIGGER_ACCEPTED_FLAG;

//assign HITOR_AB = (SELECTAB)? HITOR_B : HITOR_A;

//// TLU

tlu_controller #(
    .BASEADDR(TLU_BASEADDR),
    .HIGHADDR(TLU_HIGHADDR),
    .DIVISOR(8),
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
    
    .FIFO_PREEMPT_REQ(TLU_FIFO_PEEMPT_REQ),
    
    .TRIGGER({7'b0,TDC_TRIG_OUT}),
    .TRIGGER_VETO({7'b0,FIFO_FULL}),
	 
    .TRIGGER_ACKNOWLEDGE(TRIGGER_ACKNOWLEDGE_FLAG),
    .TRIGGER_ACCEPTED_FLAG(TRIGGER_ACCEPTED_FLAG),
	 //.EXT_TRIGGER_ENABLE(TLU_EXT_TRIGGER_ENABLE)
	 
    .TLU_TRIGGER(RJ45_TRIGGER),
    .TLU_RESET(RJ45_RESET),
    .TLU_BUSY(TLU_BUSY),
    .TLU_CLOCK(TLU_CLOCK),
    
    .TIMESTAMP(TIMESTAMP)
);
assign TRIGGER_ACKNOWLEDGE_FLAG = TRIGGER_ACCEPTED_FLAG;

timestamp
#(
    .BASEADDR(TS_BASEADDR),
    .HIGHADDR(TS_HIGHADDR),
    .IDENTIFIER(4'b0101)
)i_timestamp(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK(CLK40),
	 .DI(LEMO_RX[2]),
	 .EXT_ENABLE(GATE_TDC),
	 .EXT_TIMESTAMP(TIMESTAMP),

    .FIFO_READ(TS_FIFO_READ),
    .FIFO_EMPTY(TS_FIFO_EMPTY),
    .FIFO_DATA(TS_FIFO_DATA)
    
);

timestamp_div
#(
    .BASEADDR(TS_TDC_BASEADDR),
    .HIGHADDR(TS_TDC_HIGHADDR),
    .IDENTIFIER(4'b0110)
)i_timestamp_div_tdc(
    .BUS_CLK(BUS_CLK),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RST(BUS_RST),
    .BUS_WR(BUS_WR),
    .BUS_RD(BUS_RD),
    
    .CLK40(CLK40),
    .CLK160(CLK160),
    .CLK320(CLK320),
	 .DI(HITOR_B),
	 //.DI(LEMO_RX[1]),
	 .EXT_ENABLE(GATE_TDC),
	 .EXT_TIMESTAMP(TIMESTAMP),

    .FIFO_READ(TS_TDC_FIFO_READ),
    .FIFO_EMPTY(TS_TDC_FIFO_EMPTY),
    .FIFO_DATA(TS_TDC_FIFO_DATA)
    
);

timestamp_div
#(
    .BASEADDR(TS_TLU_BASEADDR),
    .HIGHADDR(TS_TLU_HIGHADDR),
    .IDENTIFIER(4'b0111)
)i_timestamp_div_tlu(
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
	 .EXT_ENABLE(~TLU_BUSY),
	 .EXT_TIMESTAMP(TIMESTAMP),

    .FIFO_READ(TS_TLU_FIFO_READ),
    .FIFO_EMPTY(TS_TLU_FIFO_EMPTY),
    .FIFO_DATA(TS_TLU_FIFO_DATA)
    
);


tjmono_data_rx #(
   .BASEADDR(DATA_RX_BASEADDR),
   .HIGHADDR(DATA_RX_HIGHADDR),
   .IDENTIFIER(2'b00)
) tjmono_data_rx (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR),
    
    .CLK_BX(CLK40),
    .RX_TOKEN(TOK_AB), 
    .RX_DATA(OUT_AB),
    .RX_CLK(CLK40),
    .RX_READ(READ_AB), 
    .RX_FREEZE(FREEZE_AB), 
    .TIMESTAMP(TIMESTAMP),
    .READY(RX_READY),
    
    .FIFO_READ(FE_DIRECT_READ),
    .FIFO_EMPTY(FE_DIRECT_EMPTY),
    .FIFO_DATA(FE_DIRECT_FIFO_DATA),
    
    .LOST_ERROR()
    
);

assign OUT_AB = (SELECTAB)? OUT_B : OUT_A;
assign TOK_AB = (SELECTAB)? TOK_B : TOK_A;
assign READ_A = (SELECTAB)? 1'b0 : READ_AB;
assign FREEZE_A = (SELECTAB)? 1'b0 : FREEZE_AB;
assign READ_B = (SELECTAB)? READ_AB : 1'b0;
assign FREEZE_B = (SELECTAB)? FREEZE_AB : 1'b0;




wire USB_READ;
assign USB_READ = FREAD & FSTROBE;



//************************************************

  wire FIFO_READ_SPI_RX;
  wire FIFO_EMPTY_SPI_RX;
  wire [31:0] FIFO_DATA_SPI_RX;


//Receiver for the 8b10b encoder
fei4_rx # (
        .BASEADDR(FERX_BASEADDR),
        .HIGHADDR(FERX_HIGHADDR),
        .DSIZE(10),
        .DATA_IDENTIFIER(8'h40)
        ) 
rx (
        .RX_CLK(CLK160), //40
        .RX_CLK2X(CLK320), //80
        .DATA_CLK(CLK16), //4

        .RX_DATA(RX_DATA),

        .RX_READY(),
        .RX_8B10B_DECODER_ERR(),
        .RX_FIFO_OVERFLOW_ERR(),

        .FIFO_READ(FE_FIFO_READ),
        .FIFO_EMPTY(FE_FIFO_EMPTY),
        .FIFO_DATA(FE_FIFO_DATA),

        .RX_FIFO_FULL(),

        .BUS_CLK(BUS_CLK),
        .BUS_RST(BUS_RST),
        .BUS_ADD(BUS_ADD),
        .BUS_DATA(BUS_DATA),
        .BUS_RD(BUS_RD),
        .BUS_WR(BUS_WR)
        );

// //******************************************************/
    

sram_fifo #(
    .BASEADDR(FIFO_BASEADDR),
    .HIGHADDR(FIFO_HIGHADDR)
) sram_fifo (
    .BUS_CLK(BUS_CLK),
    .BUS_RST(BUS_RST),
    .BUS_ADD(BUS_ADD),
    .BUS_DATA(BUS_DATA),
    .BUS_RD(BUS_RD),
    .BUS_WR(BUS_WR), 

    .SRAM_A(SRAM_A),
    .SRAM_IO(SRAM_IO),
    .SRAM_BHE_B(SRAM_BHE_B),
    .SRAM_BLE_B(SRAM_BLE_B),
    .SRAM_CE1_B(SRAM_CE1_B),
    .SRAM_OE_B(SRAM_OE_B),
    .SRAM_WE_B(SRAM_WE_B),

    .USB_READ(USB_READ),
    .USB_DATA(FDATA),

    .FIFO_READ_NEXT_OUT(ARB_READY_OUT),
    .FIFO_EMPTY_IN(!ARB_WRITE_OUT),
    .FIFO_DATA(ARB_DATA_OUT),
	 
    .FIFO_NOT_EMPTY(),
    .FIFO_FULL(),
    //.FIFO_FULL(FIFO_FULL),
    .FIFO_NEAR_FULL(FIFO_FULL),
    .FIFO_READ_ERROR()
);

ODDR clk_bx_gate(.D1(EN_BX_CLK_CONF), .D2(1'b0), .C(CLK40), .CE(1'b1), .R(1'b0), .S(1'b0), .Q(CLK_BX) );
//ODDR clk_out_gate(.D1(EN_OUT_CLK_CONF), .D2(1'b0), .C(CLK40), .CE(1'b1), .R(1'b0), .S(1'b0), .Q(CLK_OUT) );
assign CLK_OUT = CLK160; //EN_OUT_CLK_CONF ? CLK160 : 1'b0;
assign CLK_CMD = CLK160;

reg nRST_reg;
assign RST_N = nRST_reg;
always@(negedge CLK40)
    nRST_reg <= !RESET_CONF;
   
reg RST_BCID_reg;
assign RESET_BCID = RST_BCID_reg;
always@(negedge CLK40)
    RST_BCID_reg <= RESET_BCID_CONF;


// LED assignments
assign LED[0] = 0;
assign LED[1] = 0;
assign LED[2] = 0;
assign LED[3] = 0;
assign LED[4] = 0;

assign LEMO_TX[0] = TLU_CLOCK; // trigger clock; also connected to RJ45 output
assign LEMO_TX[1] = TLU_BUSY;  // TLU_BUSY signal; also connected to RJ45 output. Asserted when TLU FSM has 
assign LEMO_TX[2] = INJECTION;

assign INJECTION_MON = INJECTION;
endmodule
