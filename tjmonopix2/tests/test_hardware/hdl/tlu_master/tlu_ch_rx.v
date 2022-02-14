/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved 
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps
`default_nettype none

module tlu_ch_rx
#(
    parameter CLKDV = 4

)(
    input wire RST,
    input wire CLK320,
    input wire CLK160,
    input wire CLK40,
    
    input wire [3:0] TIME_STAMP,
    input wire [4:0] DIG_TH,
    input wire EN_INVERT,
    input wire EN,
    
    input wire TLU_IN,
    
    output reg VALID,
    output reg [7:0] LAST_RISING, LAST_FALLING,
    output wire [7:0] LAST_TOT,
    output reg [7:0] LAST_RISING_REL
    
);



// de-serialize
wire [CLKDV*4-1:0] TDC, TDC_DES;
reg  [CLKDV*4-1:0] TDC_DES_PREV;


ddr_des #(.CLKDV(CLKDV)) iddr_des_tdc(.CLK2X(CLK320), .CLK(CLK160), .WCLK(CLK40), .IN(TLU_IN), .OUT(TDC), .OUT_FAST());

assign TDC_DES = EN_INVERT ? ~TDC : TDC;

always @ (posedge CLK40)
    TDC_DES_PREV <= TDC_DES;
    
wire  [CLKDV*4:0] TDC_TO_COUNT;
assign TDC_TO_COUNT[CLKDV*4] = TDC_DES_PREV[0];
assign TDC_TO_COUNT[CLKDV*4-1:0] = TDC_DES;

reg [3:0] RISING_EDGES_CNT, FALLING_EDGES_CNT;
reg [3:0] RISING_POS, FALLING_POS;

integer i;
always @ (*) begin
    RISING_EDGES_CNT = 0;
    FALLING_EDGES_CNT = 0;
    RISING_POS = 0;
    FALLING_POS = 0;
    for (i=0; i<16; i=i+1) begin
        if ((TDC_TO_COUNT[16-i-1] == 1) && (TDC_TO_COUNT[16-i]==0)) begin
            if (RISING_EDGES_CNT == 0)
                RISING_POS = i;
                
            RISING_EDGES_CNT = RISING_EDGES_CNT + 1;
        end
        
        if ((TDC_TO_COUNT[i] == 0) && (TDC_TO_COUNT[i+1]==1)) begin
            if (FALLING_EDGES_CNT == 0)
                FALLING_POS = 15 - i;
            
            FALLING_EDGES_CNT = FALLING_EDGES_CNT + 1;
        end
    end
end

reg WAITING_FOR_TRAILING;
always@(posedge CLK40)
    if(RST)
        WAITING_FOR_TRAILING <= 0;
    else if(RISING_EDGES_CNT < FALLING_EDGES_CNT)
        WAITING_FOR_TRAILING <= 0;
    else if(RISING_EDGES_CNT > FALLING_EDGES_CNT)
        WAITING_FOR_TRAILING <= 1;


always@(posedge CLK40)
    if(RST)
        LAST_RISING <= 0;
    else if (RISING_EDGES_CNT > 0)
        LAST_RISING <= {TIME_STAMP, RISING_POS};
    
always@(posedge CLK40)
    if(RST)
        LAST_FALLING <= 0;
    else if (FALLING_EDGES_CNT > 0)
        LAST_FALLING <= {TIME_STAMP, FALLING_POS};


assign LAST_TOT = WAITING_FOR_TRAILING ? 8'hff: LAST_FALLING - LAST_RISING;//(LAST_FALLING > 0 && LAST_RISING < 0)? LAST_RISING - RISING_POS : LAST_FALLING - LAST_RISING; //TODO

wire RISING;
assign RISING = (RISING_EDGES_CNT > 0);
    
wire [7:0] CURRENT_TIME;
assign CURRENT_TIME = {TIME_STAMP[3:0], 4'b0};

wire [7:0] LAST_RISING_RELATIVE;
assign LAST_RISING_RELATIVE = CURRENT_TIME - LAST_RISING;
reg IS_LE;
always@(posedge CLK40)
    if(RST)
        IS_LE <= 0;
    else if (RISING) 
        IS_LE <= 1;
    else if (LAST_RISING_RELATIVE > 16*5)
        IS_LE <= 0;
    
always@(posedge CLK40)
    VALID <= (EN & IS_LE & (LAST_TOT > DIG_TH) & (LAST_RISING_RELATIVE > 2*16));

always@(posedge CLK40)
    LAST_RISING_REL <= LAST_RISING_RELATIVE;


endmodule