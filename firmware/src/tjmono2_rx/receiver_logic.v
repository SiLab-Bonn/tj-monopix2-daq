/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved 
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
`timescale 1ps/1ps
`default_nettype none

module receiver_logic
(
    input wire              RESET,
    input wire              WCLK,
    input wire              FCLK,
    input wire              FCLK2X,
    input wire              BUS_CLK,
    input wire              RX_DATA,
    input wire              read,
    output wire  [27:0]     data,
    output wire             empty,
    output wire             full,
    output wire             rec_sync_ready,
    output reg  [7:0]       lost_err_cnt,
    output reg  [7:0]       decoder_err_cnt,
    output reg [15:0]       fifo_size,
    input wire              invert_rx_data,
    input wire              enable_rx,
    input wire              no_8b10b_mode,
    input wire [3:0]        load_rawcnt,
    input wire [7:0]        empty_record,
    input wire              FIFO_CLK,
    input wire [26:0]       TIMESTAMP
);

wire RESET_WCLK;
cdc_reset_sync rst_pulse_sync (.clk_in(BUS_CLK), .pulse_in(RESET), .clk_out(WCLK), .pulse_out(RESET_WCLK));

reg enable_rx_buf, enable_rx_buf2, enable_rx_wclk;
always @ (posedge WCLK)
begin
    enable_rx_buf <= enable_rx;
    enable_rx_buf2 <= enable_rx_buf;
    enable_rx_wclk <= enable_rx_buf2;
end

// 8b/10b record sync
wire [9:0] data_8b10b;
reg decoder_err;
rec_sync rec_sync_inst (
    .reset(RESET_WCLK),
    .datain(invert_rx_data ? ~RX_DATA : RX_DATA),
    .data(data_8b10b),
    .WCLK(WCLK),
    .FCLK(FCLK),
    .rec_sync_ready(rec_sync_ready),
    .decoder_err(decoder_err)
);

reg [9:0] raw10bdata;
always @(posedge FCLK) begin
    if (RESET_WCLK)
        raw10bdata <= 10'b0;
    else
        raw10bdata <= {raw10bdata[9:0], RX_DATA};
end

reg [3:0] rawcnt;
always @(posedge FCLK) begin
    if (RESET_WCLK || rawcnt==4'd9)
        rawcnt <= 4'b0;
    else
        rawcnt <= rawcnt+1;
end

reg raw_k, raw_eof;
reg [7:0] raw_data;
wire load_raw;
assign load_raw = (rawcnt == load_rawcnt);
always @(posedge FCLK) begin
    if (RESET_WCLK)
        {raw_k,raw_eof, raw_data} <= {1'b1, 1'b0, 8'b001_11100};
    else if (load_raw) begin            // parameterize
        if ((raw10bdata[9] == 1'b1) && (raw10bdata[7:0] == empty_record))
            {raw_k, raw_eof, raw_data} <= {1'b1, raw10bdata[8], 8'b001_11100};
        else
            {raw_k, raw_eof, raw_data} <= raw10bdata;
    end
end

//wire write_8b10b;
//assign write_8b10b = rec_sync_ready & enable_rx_wclk;
wire write_en;
assign write_en = (rec_sync_ready | no_8b10b_mode) & enable_rx_wclk;

reg [9:0] data_to_dec;
integer i;
always @ (*) begin
    for (i=0; i<10; i=i+1)
        data_to_dec[(10-1)-i] = data_8b10b[i];
end

reg dispin;
wire dispout;
always@(posedge WCLK) begin
    if(RESET_WCLK)
        dispin <= 1'b0;
    else
        dispin <= dispout;
end

wire dec_k0, dec_k;
wire [7:0] dec_data0, dec_data;
wire code_err, disp_err;
decode_8b10b decode_8b10b_inst (
    .datain(data_to_dec),
    .dispin(dispin),
    .dataout({dec_k0,dec_data0}), // control character, data out
    .dispout(dispout),
    .code_err(code_err),
    .disp_err(disp_err)
);

assign dec_k = no_8b10b_mode? raw_k:dec_k0;
assign dec_data = no_8b10b_mode? raw_data:dec_data0;

always@(negedge WCLK) begin // avoid glitches from code_err or disp_err
    if(RESET_WCLK)
        decoder_err <= 1'b0;
    else
        decoder_err <= code_err | disp_err;
end
// Invalid symbols may or may not cause
// disparity errors depending on the symbol
// itself and the disparities of the previous and
// subsequent symbols. For this reason,
// DISP_ERR should always be combined
// with CODE_ERR to detect all errors.

always@(posedge WCLK) begin
    if(RESET_WCLK)
        decoder_err_cnt <= 0;
    else
        if(decoder_err && write_en && decoder_err_cnt != 8'hff)
            decoder_err_cnt <= decoder_err_cnt + 1;
        else 
            decoder_err_cnt <= decoder_err_cnt;
end

wire sof;
assign sof = write_en && dec_k && (dec_data==8'b111_11100 || dec_data==8'b101_11100);
wire eof;
assign eof = write_en && dec_k && (dec_data==8'b010_11100 || dec_data==8'b011_11100);
wire idle;
assign idle = write_en && dec_k && dec_data==8'b001_11100;
wire busy;
assign busy = write_en && !dec_k;

reg [2:0] byte_sel;
always@(posedge WCLK) begin
    if(RESET_WCLK) 
        byte_sel <= 0;
    else if (busy || sof || eof ) begin
        if ( byte_sel == 2 )
            byte_sel <= 0;
        else
            byte_sel <= byte_sel + 1;
    end
    else
        byte_sel <= 0;
end

reg [8:0] data_dec_in [2:0];
always@(posedge WCLK) begin
    if(RESET_WCLK) 
        for (i=0; i<3; i=i+1)
            data_dec_in[i] <= 8'b0;
    else if ((write_en &&  dec_k==1'b0) || sof || eof ) 
         data_dec_in[byte_sel] <= {dec_k, dec_data};
    else if (idle && byte_sel==2)
        data_dec_in[2] <= {1'b1, 8'b001_11100};    
    else if (idle && byte_sel==1) begin
        data_dec_in[1] <= {1'b1, 8'b001_11100};        //{dec_k, dec_data};
        data_dec_in[2] <= {1'b1, 8'b001_11100};
    end
end

reg busy_ff;
always@(posedge WCLK) begin
    busy_ff <= busy && (byte_sel==1 || byte_sel==0);
end

reg write_dec_in;
always@(posedge WCLK) begin
    if(RESET_WCLK) 
        write_dec_in <= 1'b0;
    else if (byte_sel==2)
        write_dec_in <= 1'b1;
    else if (idle && busy_ff)
        write_dec_in <= 1'b1;
    else
        write_dec_in <= 1'b0;

end

wire cdc_fifo_full, cdc_fifo_empty;
always@(posedge WCLK) begin
    if(RESET_WCLK)
        lost_err_cnt <= 0;
    else
        if(cdc_fifo_full && write_dec_in && lost_err_cnt != 8'hff)
            lost_err_cnt <= lost_err_cnt + 1;
        else
            lost_err_cnt <= lost_err_cnt;
end

wire [27:0] cdc_data_out;
wire [27:0] wdata;
assign wdata =  sof ? {1'b1, TIMESTAMP} : {1'b0, data_dec_in[0],data_dec_in[1],data_dec_in[2]};

// generate delayed and long reset
reg [5:0] rst_cnt;
always@(posedge BUS_CLK) begin
    if(RESET)
        rst_cnt <= 5'd8;
    else if(rst_cnt != 5'd7)
        rst_cnt <= rst_cnt +1;
end
wire rst_long = rst_cnt[5];
reg cdc_sync_ff;
always @(posedge WCLK) begin
    cdc_sync_ff <= rst_long;
end

wire RESET_FIFO;
cdc_reset_sync rst_fifo_pulse_sync (.clk_in(WCLK), .pulse_in(RESET_WCLK), .clk_out(FIFO_CLK), .pulse_out(RESET_FIFO));

cdc_syncfifo #(
    .DSIZE(28),
    .ASIZE(3)
) cdc_syncfifo_i (
    .rdata(cdc_data_out),
    .wfull(cdc_fifo_full),
    .rempty(cdc_fifo_empty),
    .wdata(wdata),
    .winc((sof | write_dec_in) & !cdc_fifo_full),
    .wclk(WCLK),
    .wrst(RESET_WCLK),
    .rinc(!full),
    .rclk(FIFO_CLK),
    .rrst(RESET_FIFO)
);

wire [12:0] fifo_size_int;

gerneric_fifo #(
    .DATA_SIZE(28),
    .DEPTH(1024*8)
) fifo_i (
    .clk(FIFO_CLK),
    .reset(RESET_FIFO),
    .write(!cdc_fifo_empty),
    .read(read),
    .data_in(cdc_data_out),
    .full(full),
    .empty(empty),
    .data_out(data), 
    .size(fifo_size_int)
);

always @(posedge FIFO_CLK) begin
    fifo_size <= {3'b0, fifo_size_int};
end

endmodule
