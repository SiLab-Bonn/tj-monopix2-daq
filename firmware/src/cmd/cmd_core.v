/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps

module cmd_core
#(
    parameter                   ABUSWIDTH = 16
) (
    output wire [1:0]           CHIP_TYPE,
    input wire                  BUS_CLK,
    input wire                  BUS_RST,
    input wire [ABUSWIDTH-1:0]  BUS_ADD,
    input wire [7:0]            BUS_DATA_IN,
    input wire                  BUS_RD,
    input wire                  BUS_WR,
    output reg [7:0]            BUS_DATA_OUT,

    input wire                  EXT_START_PIN,
    output wire                 EXT_START_ENABLED,
    input wire                  EXT_TRIGGER,

    input wire                  AZ_PULSE,
    input wire                  AZ_VETO_TLU_PULSE,
    output reg                  AZ_VETO_FLAG,

    output reg                  CMD_WRITING,
    output reg                  CMD_LOOP_START,
    input wire                  CMD_CLK,
    output wire                 CMD_EN,
    output reg                  CMD_SERIAL_OUT,
    output wire                 CMD_OUTPUT_EN,

    output wire                 BYPASS_MODE
);

localparam VERSION = 2;
localparam REGSIZE = 16;
localparam BRAM_ABUSWIDTH = 12;
localparam CMD_MEM_SIZE = 2**BRAM_ABUSWIDTH;
localparam TAG_PATTERN = 8'b01101010;
localparam SYNC_PATTERN_UNSYMETRIC = 16'b1000000101111110;
reg [15:0] SYNC_PATTERN;// = 16'b0101010101010101; //RD53A is default sync pattern

reg [7:0] sync_halfpattern = 8'h00;
reg [7:0] sync_cycle_cnt = 8'h00;
reg [5:0] sync_cnt = 6'h00;
reg [15:0] repeat_cnt = 16'h0000;
reg data_written = 1'b0;
reg data_pending = 1'b0;
reg SYNCING = 1'b0;
reg serializer_next_byte = 1'b0;
reg [7:0] CMD_DATA_OUT_SR = 8'h00;
wire serializer_next_doublebyte;
wire serializer_next_halfbyte;

reg [2:0] EN_delay = 2'b00;
assign CMD_EN = EN_delay[2];

// flags
wire SOFT_RST;
assign SOFT_RST = (BUS_ADD==0 && BUS_WR);
wire RST;
assign RST = BUS_RST || SOFT_RST;
wire START;
assign START = (BUS_ADD==1 && BUS_WR);
reg CONF_DONE;

// Auto zero
reg AZ_START;

// CDC
wire RST_SYNC;
cdc_reset_sync rst_reset_sync (.clk_in(BUS_CLK), .pulse_in(RST), .clk_out(CMD_CLK), .pulse_out(RST_SYNC));
wire START_SYNC;
cdc_pulse_sync start_pulse_sync (.clk_in(BUS_CLK), .pulse_in(START), .clk_out(CMD_CLK), .pulse_out(START_SYNC));
wire EXT_START_SYNC;
cdc_pulse_sync ext_start_pulse_sync (.clk_in(BUS_CLK), .pulse_in(EXT_START_PIN), .clk_out(CMD_CLK), .pulse_out(EXT_START_SYNC));


// Trigger SR and LUT
reg trigger_request, trigger_pending = 1'b0;
reg [3:0] trigger_index, trigger_index_sr;
reg [7:0] trigger_pattern, trigger_pattern_temp, trigger_pattern_sr;
reg [7:0] tag_pattern_temp = TAG_PATTERN;
always @(posedge CMD_CLK) begin
    if (serializer_next_halfbyte)
        trigger_index_sr <= {EXT_TRIGGER, trigger_index_sr[3:1]};
end
always @(posedge CMD_CLK) begin
    if (serializer_next_doublebyte)
        trigger_index <= trigger_index_sr;
end

always @(posedge CMD_CLK) begin
    if (CHIP_TYPE == 2'b00) begin //RD53A
        SYNC_PATTERN <= 16'b0101010101010101;
        end
    else if (CHIP_TYPE == 2'b01) begin //ITkPixV1
        SYNC_PATTERN <= 16'b1010101010101010;
        end
end

always @(trigger_index) begin
    case(trigger_index)
        4'd1: begin trigger_pattern=8'b00101011; trigger_request = 1'b1; end    //T1  2B
        4'd2: begin trigger_pattern=8'b00101101; trigger_request = 1'b1; end    //T2  2D
        4'd3: begin trigger_pattern=8'b00101110; trigger_request = 1'b1; end    //T3  2E
        4'd4: begin trigger_pattern=8'b00110011; trigger_request = 1'b1; end    //T4  33
        4'd5: begin trigger_pattern=8'b00110101; trigger_request = 1'b1; end    //T5  35
        4'd6: begin trigger_pattern=8'b00110110; trigger_request = 1'b1; end    //T6  36
        4'd7: begin trigger_pattern=8'b00111001; trigger_request = 1'b1; end    //T7  39
        4'd8: begin trigger_pattern=8'b00111010; trigger_request = 1'b1; end    //T8  3A
        4'd9: begin trigger_pattern=8'b00111100; trigger_request = 1'b1; end    //T9  3C
        4'd10: begin trigger_pattern=8'b01001011; trigger_request = 1'b1; end   //T10 4B
        4'd11: begin trigger_pattern=8'b01001101; trigger_request = 1'b1; end   //T11 4D
        4'd12: begin trigger_pattern=8'b01001110; trigger_request = 1'b1; end   //T12 4E
        4'd13: begin trigger_pattern=8'b01010011; trigger_request = 1'b1; end   //T13 53
        4'd14: begin trigger_pattern=8'b01010101; trigger_request = 1'b1; end   //T14 55
        4'd15: begin trigger_pattern=8'b01010110; trigger_request = 1'b1; end   //T15 56
        default: begin trigger_pattern = 8'b0; trigger_request = 1'b0; end
    endcase
end

//Registers
reg [7:0] status_regs [15:0];
initial status_regs[2] = 0;
always @(posedge BUS_CLK) begin
    if(RST) begin
        status_regs[0] <= 0;
        status_regs[1] <= 0;
        status_regs[2] <= 8'b00010000 | (BYPASS_MODE<<5);    // general flags and cmds {CHIP_TYPE[1:0], BYPASS_MODE, CMD_OUTPUT_EN, EXT_TRIGGER_EN, EXT_START_EN, SYNCING, CONF_DONE}. Default: Output enabled
        status_regs[3] <= 0;    // CMD size [7:0]
        status_regs[4] <= 0;    // CMD size [15:8]
        status_regs[5] <= 8'd1; // CONF_REPEAT_COUNT [7:0], repeat once by default
        status_regs[6] <= 0;    // CONF_REPEAT_COUNT [15:8]
        status_regs[7] <= 0;    // CMD_MEM_SIZE[7:0]
        status_regs[8] <= 0;    // CMD_MEM_SIZE[15:8]
        status_regs[9] <= 0;    // AZ: veto wait cycles [7:0]
        status_regs[10] <= 0;   // AZ: veto wait cycles [15:8]
        status_regs[11] <= 0;
        status_regs[12] <= 0;
        status_regs[13] <= 0;
        status_regs[14] <= 0;
        status_regs[15] <= 0;
    end
    else if(BUS_WR && BUS_ADD < 16)
        status_regs[BUS_ADD[3:0]] <= BUS_DATA_IN;
end
assign CHIP_TYPE = status_regs[2][7:6];
wire [15:0] CONF_CMD_SIZE;
assign CONF_CMD_SIZE = {status_regs[4], status_regs[3]};
wire [15:0] CONF_REPEAT_COUNT;
assign CONF_REPEAT_COUNT = {status_regs[6], status_regs[5]};
wire [15:0] CONF_AZ_VETO_CYLCES;
assign CONF_AZ_VETO_CYLCES = {status_regs[10], status_regs[9]};
wire [7:0] BUS_STATUS_OUT;
assign BUS_STATUS_OUT = status_regs[BUS_ADD[3:0]];

wire EXT_START_EN;
assign EXT_START_EN = status_regs[2][2];
wire EXT_TRIGGER_EN;
assign EXT_TRIGGER_EN = status_regs[2][3];
assign CMD_OUTPUT_EN = status_regs[2][4];
assign BYPASS_MODE = status_regs[2][5];

wire EXT_TRIGGER_EN_SYNC;
three_stage_synchronizer ext_trigger_en_sync (
    .CLK(CMD_CLK),
    .IN(EXT_TRIGGER_EN),
    .OUT(EXT_TRIGGER_EN_SYNC)
);

assign EXT_START_ENABLED = EXT_TRIGGER_EN_SYNC;

//External Trigger
reg trigger_start=1'b0;
reg trigger_sent =1'b0;


// Map address space
reg [7:0] BUS_DATA_OUT_REG;
always @ (posedge BUS_CLK) begin
    if(BUS_RD) begin
        if(BUS_ADD == 0)
            BUS_DATA_OUT_REG <= VERSION;
        else if(BUS_ADD == 2)
            BUS_DATA_OUT_REG <= {CHIP_TYPE, BYPASS_MODE, CMD_OUTPUT_EN, EXT_TRIGGER_EN, EXT_START_EN, SYNCING, CONF_DONE};
        else if(BUS_ADD == 3)
            BUS_DATA_OUT_REG <= CONF_CMD_SIZE[7:0];
        else if(BUS_ADD == 4)
            BUS_DATA_OUT_REG <= CONF_CMD_SIZE[15:8];
        else if(BUS_ADD == 5)
            BUS_DATA_OUT_REG <= CONF_REPEAT_COUNT[7:0];
        else if(BUS_ADD == 6)
            BUS_DATA_OUT_REG <= CONF_REPEAT_COUNT[15:8];
        else if(BUS_ADD == 7)
            BUS_DATA_OUT_REG <= CMD_MEM_SIZE[7:0];
        else if(BUS_ADD == 8)
            BUS_DATA_OUT_REG <= CMD_MEM_SIZE[15:8];
        else if(BUS_ADD == 9)
            BUS_DATA_OUT_REG <= CONF_AZ_VETO_CYLCES[7:0];
        else if(BUS_ADD == 10)
            BUS_DATA_OUT_REG <= CONF_AZ_VETO_CYLCES[15:8];
        else if(BUS_ADD < 16)
            BUS_DATA_OUT_REG <= BUS_STATUS_OUT;
    end
else
    BUS_DATA_OUT_REG <= 8'h00;
end

// wait cycle for bram ???
reg [ABUSWIDTH-1:0] PREV_BUS_ADD = 16'h0000;
always @ (posedge BUS_CLK) begin
    if(BUS_RD)
        PREV_BUS_ADD <= BUS_ADD;
    else
        PREV_BUS_ADD <= 16'h0000;
end


// Mux: RAM, registers
reg [7:0] OUT_MEM;
reg OUT_SR;
always @(*) begin
    if(PREV_BUS_ADD < REGSIZE)
        BUS_DATA_OUT = BUS_DATA_OUT_REG;
    else if(PREV_BUS_ADD < REGSIZE + CMD_MEM_SIZE)
        BUS_DATA_OUT = OUT_MEM;
    else
        BUS_DATA_OUT = 8'hxx;
end

// BRAM
wire BUS_MEM_EN;
wire [ABUSWIDTH-1:0] BUS_MEM_ADD;

assign BUS_MEM_EN = (BUS_WR | BUS_RD) & BUS_ADD >= REGSIZE;
assign BUS_MEM_ADD = BUS_ADD - REGSIZE;

(* RAM_STYLE="{BLOCK_POWER2}" *)
reg [7:0] mem [CMD_MEM_SIZE-1:0];

reg [BRAM_ABUSWIDTH-1:0] read_address = 0;

always @(posedge BUS_CLK)
    if (BUS_MEM_EN) begin
        if (BUS_WR)
            mem[BUS_MEM_ADD] <= BUS_DATA_IN;
        OUT_MEM <= mem[BUS_MEM_ADD];
    end


// FSM
reg START_FSM;
localparam STATE_INIT = 0, STATE_IDLE = 1, STATE_SYNC = 2, STATE_DATA_WRITE = 3, STATE_TRIGGER = 4;

reg [3:0] state=STATE_INIT, next_state=STATE_INIT;

always @ (posedge CMD_CLK) begin
    if (RST_SYNC)
        START_FSM <= 0;
    else if(START_SYNC)
        START_FSM <= 1;
    else if(START_FSM)
        START_FSM <= 0;
end

reg wait_for_start;
always @(posedge CMD_CLK)
    if(RST_SYNC)
        wait_for_start <= 0;
    else if(START_SYNC || EXT_START_SYNC || AZ_START || trigger_start)
        wait_for_start <= 1;
    else if(data_pending==0 && serializer_next_byte && wait_for_start)
        wait_for_start <= 0;

wire wait_for_start_pulse;
pulse_gen_rising i_pulse_gen_rising_wait_for_start(.clk_in(CMD_CLK), .in(~wait_for_start), .out(wait_for_start_pulse));

wire CMD_READY;
assign CMD_READY = wait_for_start_pulse & (state == STATE_SYNC | state == STATE_TRIGGER);

wire DONE_SYNC;
cdc_pulse_sync done_pulse_sync(.clk_in(CMD_CLK), .pulse_in(CMD_READY), .clk_out(BUS_CLK), .pulse_out(DONE_SYNC));


always @(posedge BUS_CLK)
    if(RST || DONE_SYNC)
        CONF_DONE <= 1;
    else if(START || EXT_START_PIN)
        CONF_DONE <= 0;


always @ (*) begin
    next_state = state;
    case(state)
        STATE_INIT:     // fixed output pattern to assist the pll locking
            if(START_FSM)
                next_state = STATE_SYNC;
/*
        STATE_IDLE:
            if(data_pending)
                next_state = STATE_DATA_WRITE;
            else
                next_state = STATE_SYNC;
*/
        STATE_SYNC:
            if(trigger_start && serializer_next_doublebyte) begin
                next_state = STATE_TRIGGER;
            end
            else begin
                if(data_pending && serializer_next_doublebyte)
                    next_state = STATE_DATA_WRITE;
            end

        STATE_DATA_WRITE: begin
            if(data_written)
                next_state = STATE_SYNC;
            if(trigger_start && serializer_next_doublebyte) begin
                next_state = STATE_TRIGGER;
            end
        end

        STATE_TRIGGER: begin
            if(trigger_sent == 1)
                if(data_pending)
                    next_state = STATE_DATA_WRITE;
                else
                    next_state = STATE_SYNC;
        end
    endcase
end


always @ (posedge CMD_CLK) begin
    if (RST_SYNC)
        state <= STATE_INIT;
    else
        state <= next_state;

    if(trigger_request && !AZ_VETO_TLU_PULSE && EXT_TRIGGER_EN && !trigger_start) begin     // do not trigger while in AZ procedure
        trigger_start <= 1;
        trigger_pattern_sr <= trigger_pattern;
    end
    if(trigger_sent) begin
        trigger_start <= 0;
        //trigger_pattern_sr <= 8'b0;
    end

    case(state)
        STATE_SYNC: begin
            if (sync_cnt==0 | sync_cnt==2)
                sync_halfpattern <= SYNC_PATTERN_UNSYMETRIC[15:8];
            else if (sync_cnt==1 | sync_cnt==3)
                sync_halfpattern <= SYNC_PATTERN_UNSYMETRIC[7:0];
            else
                sync_halfpattern <= SYNC_PATTERN[15:8];
        end

        STATE_DATA_WRITE: begin
            if(serializer_next_byte) begin
                if((CONF_REPEAT_COUNT != 16'd1) && read_address == 0)
                    CMD_LOOP_START <= 1;
                else
                    CMD_LOOP_START <= 0;

                if(read_address < CONF_CMD_SIZE-1)      //loop over command bytes
                    read_address <= read_address + 1;
                else begin
                    read_address <= 10'b0;
                    if(repeat_cnt < CONF_REPEAT_COUNT-1)    //loop over repetitions
                        repeat_cnt <= repeat_cnt + 1;
                    else begin
                        repeat_cnt <= 16'd0;
                        data_written <= 1;
                    end
                end
            end
        end

        STATE_TRIGGER: begin
            if(trigger_request) begin
                trigger_pending <= 1;
                trigger_pattern_temp <= trigger_pattern;
            end
            if(serializer_next_doublebyte && serializer_next_byte) begin
                if(!trigger_request) begin
                    trigger_pending <= 0;
                    trigger_sent <= 1;
                end
                if(trigger_pending)
                    trigger_pattern_sr <= trigger_pattern_temp;
                else
                    trigger_sent <= 1;
            end
            else begin
                if(!serializer_next_doublebyte && serializer_next_byte)
                    trigger_pattern_sr <= tag_pattern_temp;
            end
        end
    endcase

    //resets
    if(state!=STATE_TRIGGER)
        trigger_sent <= 0;
    if(state!=STATE_DATA_WRITE)
        data_written <= 0;
    if(state==STATE_INIT)
        EN_delay <= { EN_delay[1:0], 1'b0 };
    else
        EN_delay <= { EN_delay[1:0], 1'b1 };
end


//MUX
always @ (negedge CMD_CLK) begin
    if (RST_SYNC) begin
        CMD_DATA_OUT_SR <= 16'h0000;
        CMD_SERIAL_OUT <= 1'b0;
    end
    else if(state==STATE_SYNC) begin
        CMD_DATA_OUT_SR <= sync_halfpattern;
        CMD_SERIAL_OUT <= OUT_SR;
    end
    else if(state==STATE_DATA_WRITE) begin
        CMD_DATA_OUT_SR <= mem[read_address];
        CMD_SERIAL_OUT <= OUT_SR;
    end
//    else if(state==STATE_IDLE) begin
//        CMD_DATA_OUT_SR <= 8'h00;
//        CMD_SERIAL_OUT <= OUT_SR;
//        end
    else if(state==STATE_INIT)
        CMD_SERIAL_OUT <= ~CMD_SERIAL_OUT;  // write a 010101... pattern
    else if(state==STATE_TRIGGER) begin
        CMD_DATA_OUT_SR <= trigger_pattern_sr;
        CMD_SERIAL_OUT <= OUT_SR;
    end
end


//data_pending flag
always @ (posedge CMD_CLK) begin
    if( (START_SYNC || EXT_START_SYNC || AZ_START) && CONF_CMD_SIZE) // && EXT_START_EN
        data_pending <= 1;
    else if( (state==STATE_DATA_WRITE || state==STATE_TRIGGER ) && next_state==STATE_SYNC )
        data_pending <= 0;

    if(state==STATE_DATA_WRITE)
        CMD_WRITING <= 1;
    else
        CMD_WRITING <= 0;
end


//SERIALIZER (MSB first)
reg [7:0] serializer_shift_register = 8'd0;
reg [2:0] serializer_cnt = 3'b000;

assign serializer_next_doublebyte = (!sync_cycle_cnt[0] && serializer_next_byte) ? 1'b1 : 1'b0;
assign serializer_next_halfbyte   = (!serializer_cnt[0] && !serializer_cnt[1])   ? 1'b1 : 1'b0;

always @ (posedge CMD_CLK) begin
    if(EN_delay[0]) begin
        serializer_shift_register <= {serializer_shift_register [6:0], 1'b0};
        if(serializer_cnt == 3'b111) begin
            serializer_next_byte <= 1;
            sync_cycle_cnt <= sync_cycle_cnt + 1;
            sync_cnt <= sync_cnt + 1;
            serializer_shift_register <= CMD_DATA_OUT_SR;
            serializer_cnt <= 3'b000;
        end
        else begin
            serializer_cnt <= serializer_cnt + 1;
            serializer_next_byte <= 0;
        end

        OUT_SR <= serializer_shift_register[7];
    end
    else
        serializer_cnt <= 3'b000;
end



// ----- Auro-zeroing state machine ----- //
localparam AZ_STATE_IDLE = 0, AZ_STATE_WAIT_FOR_TLU = 1, AZ_WAIT_BEFORE_START = 2, AZ_STATE_START = 3, AZ_STATE_WAIT_AFTER_AZ = 4, AZ_STATE_WAIT_CMD_END = 5;
localparam AZ_WAIT_FOR_TLU_DELAY = 6'd3;
reg [2:0] az_state, az_next_state = AZ_STATE_IDLE;
reg [15:0] az_wait_cnt;

wire AZ_PULSE_SYNC;
cdc_pulse_sync i_pulse_sync_az(.clk_in(BUS_CLK), .pulse_in(AZ_PULSE), .clk_out(CMD_CLK), .pulse_out(AZ_PULSE_SYNC));

always @ (posedge CMD_CLK)
begin
    case(az_state)
        AZ_STATE_IDLE: begin                // wait for the next az pulse
            if(AZ_PULSE_SYNC) begin
                az_next_state <= AZ_STATE_WAIT_FOR_TLU;
            end
            az_wait_cnt <= 16'd0;
            AZ_VETO_FLAG <= 0;
        end

        AZ_STATE_WAIT_FOR_TLU: begin        // check, if the veto signal is high (=data taking), proceed if veto is low
            AZ_VETO_FLAG <= 1;
            if(!AZ_VETO_TLU_PULSE) begin
                az_next_state <= AZ_WAIT_BEFORE_START;
            end
        end

        AZ_WAIT_BEFORE_START: begin
            if(az_wait_cnt < AZ_WAIT_FOR_TLU_DELAY)
                az_wait_cnt <= az_wait_cnt + 1;
            else begin
                az_wait_cnt <= 16'd0;
                az_next_state <= AZ_STATE_START;
            end
        end

        AZ_STATE_START: begin               // stat the az procedure and return to idle
            if(!AZ_VETO_TLU_PULSE) begin    // check again for veto
                AZ_START <= 1;
                AZ_VETO_FLAG <= 1;
                az_next_state <= AZ_STATE_WAIT_AFTER_AZ;
            end
        end

        AZ_STATE_WAIT_AFTER_AZ: begin
            AZ_START <= 0;
            if(az_wait_cnt < CONF_AZ_VETO_CYLCES)
                az_wait_cnt <= az_wait_cnt + 1;
            else begin
                az_wait_cnt <= 16'd0;
                az_next_state <= AZ_STATE_WAIT_CMD_END;
            end
        end

        AZ_STATE_WAIT_CMD_END: begin
            if(!CMD_WRITING) begin   // wait for the cmd encoder to finish
                AZ_VETO_FLAG <= 0;
                az_next_state <= AZ_STATE_IDLE;
            end
        end

    endcase
    az_state <= az_next_state;
end

endmodule
