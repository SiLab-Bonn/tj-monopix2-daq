/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */

`timescale 1ps / 1ps

module tlu_model (
    input wire SYS_CLK, SYS_RST, TLU_CLOCK, TLU_BUSY, ENABLE, START_TRIGGER,
    output wire TLU_TRIGGER, TLU_RESET
);

reg [14:0] TRIG_ID;
reg TRIG;
wire VETO;
integer seed;

initial
    seed = 0;

always @(posedge SYS_CLK) begin
    if(SYS_RST)
        TRIG <= 0;
    // else if($random(seed) % 100 == 10 && !VETO && ENABLE)
    //     TRIG <= 1;
    else if(START_TRIGGER && !VETO && ENABLE)
        TRIG <= 1;
    else
        TRIG <= 0;
end

always @(posedge SYS_CLK) begin
    if(SYS_RST)
        TRIG_ID <= 0;
    else if(TRIG)
        TRIG_ID <= TRIG_ID + 1;
end

localparam WAIT_STATE = 0, TRIG_STATE = 1, READ_ID_STATE = 2;

reg [1:0] state, state_next;
always @(posedge SYS_CLK)
    if(SYS_RST)
        state <= WAIT_STATE;
    else
        state <= state_next;

always @(*) begin
    state_next = state;

    case(state)
        WAIT_STATE:
            if(TRIG)
                state_next = TRIG_STATE;
        TRIG_STATE:
            if(TLU_BUSY)
                state_next = READ_ID_STATE;
        READ_ID_STATE:
            if(!TLU_BUSY)
                state_next = WAIT_STATE;
        default : state_next = WAIT_STATE;
    endcase
end

assign VETO = (state != WAIT_STATE) || (state == WAIT_STATE && TLU_CLOCK == 1'b1);

reg [15:0] TRIG_ID_SR;
initial TRIG_ID_SR = 0;
always @(posedge TLU_CLOCK or posedge TRIG)
    if(TRIG)
        TRIG_ID_SR <= {TRIG_ID, 1'b0};
    else
        TRIG_ID_SR <= {1'b0, TRIG_ID_SR[15:1]};

assign TLU_TRIGGER = (state == TRIG_STATE) | (TRIG_ID_SR[0] & TLU_BUSY);

assign TLU_RESET = 0;

endmodule
