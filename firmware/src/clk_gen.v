/**
 * ------------------------------------------------------------
 * Copyright (c) All rights reserved 
 * SiLab, Institute of Physics, University of Bonn
 * ------------------------------------------------------------
 */
 


`ifndef DV1
	`define DV1 6
	`define FX1_d 3
	`define FX1_m 10
	`define FX2_d 8
	`define FX2_m 2
	`define prd 6.25
`endif	 

`timescale 1ns / 1ps
 
module clk_gen(
    input wire CLKIN,
    output wire BUS_CLK,
    output wire U1_CLK8,
    output wire U2_CLK16,
    output wire U2_CLK40,
    output wire U2_CLK160,
    output wire U2_CLK320,
    output wire U2_LOCKED
    );

    wire U1_CLK0, U1_CLK0_BUF, U1_CLKDV, U1_CLKDV_BUF;
    wire U2_CLKDV_BUF, U2_CLK0_BUF, U2_CLK2X_BUF, U2_CLKFX_BUF;

    assign BUS_CLK = U1_CLK0_BUF;
    assign U2_CLK40 = U2_CLKFX_BUF;
    assign U2_CLK16 = U2_CLKDV_BUF;
    assign U2_CLK160 = U2_CLK0_BUF;
    assign U2_CLK320 = U2_CLK2X_BUF;
    assign U1_CLK8 = U1_CLKDV_BUF;
    
    BUFG CLKFB_BUFG_INST (.I(U1_CLK0), .O(U1_CLK0_BUF));
    BUFG CLKDV_BUFG_INST (.I(U1_CLKDV), .O(U1_CLKDV_BUF));

    wire U1_CLKFX;
    wire U1_LOCKED;

   DCM #(
         .CLKDV_DIVIDE(`DV1), // Divide by: 1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,6.5
         // 7.0,7.5,8.0,9.0,10.0,11.0,12.0,13.0,14.0,15.0 or 16.0
         .CLKFX_DIVIDE(`FX1_d), // Can be any Integer from 1 to 32
         .CLKFX_MULTIPLY(`FX1_m), // Can be any Integer from 2 to 32
         .CLKIN_DIVIDE_BY_2("FALSE"), // TRUE/FALSE to enable CLKIN divide by two feature
         .CLKIN_PERIOD(20.833), // Specify period of input clock
         .CLKOUT_PHASE_SHIFT("NONE"), // Specify phase shift of NONE, FIXED or VARIABLE
         .CLK_FEEDBACK("1X"), // Specify clock feedback of NONE, 1X or 2X
         .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), // SOURCE_SYNCHRONOUS, SYSTEM_SYNCHRONOUS or
         // an Integer from 0 to 15
         .DFS_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for frequency synthesis
         .DLL_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for DLL
         .DUTY_CYCLE_CORRECTION("TRUE"), // Duty cycle correction, TRUE or FALSE
         .FACTORY_JF(16'hC080), // FACTORY JF values
         .PHASE_SHIFT(0), // Amount of fixed phase shift from -255 to 255
         .STARTUP_WAIT("TRUE") // Delay configuration DONE until DCM_SP LOCK, TRUE/FALSE
         ) DCM_BUS (
         .CLKFB(U1_CLK0_BUF), 
         .CLKIN(CLKIN), 
         .DSSEN(1'b0), 
         .PSCLK(1'b0), 
         .PSEN(1'b0), 
         .PSINCDEC(1'b0), 
         .RST(1'b0),
         .CLKDV(U1_CLKDV),
         .CLKFX(U1_CLKFX), 
         .CLKFX180(), 
         .CLK0(U1_CLK0), 
         .CLK2X(), 
         .CLK2X180(), 
         .CLK90(), 
         .CLK180(), 
         .CLK270(), 
         .LOCKED(U1_LOCKED), 
         .PSDONE(), 
         .STATUS());
  
   wire U1_CLKFX_BUF, U2_CLKDV;
   wire U2_CLK0, U2_CLKFX, U2_CLK2X;
   BUFG CLKFX_2_BUFG_INST (.I(U1_CLKFX), .O(U1_CLKFX_BUF));
   BUFG CLKDV_2_BUFG_INST (.I(U2_CLKDV), .O(U2_CLKDV_BUF));
   BUFG CLKFB_2_BUFG_INST (.I(U2_CLK0), .O(U2_CLK0_BUF));
   BUFG CLKFX2_2_BUFG_INST (.I(U2_CLKFX), .O(U2_CLKFX_BUF));
   BUFG U2_CLK2X_INST (.I(U2_CLK2X), .O(U2_CLK2X_BUF));
   
   DCM #(
         .CLKDV_DIVIDE(10), // Divide by: 1.5,2.0,2.5,3.0,3.5,4.0,4.5,5.0,5.5,6.0,6.5
         // 7.0,7.5,8.0,9.0,10.0,11.0,12.0,13.0,14.0,15.0 or 16.0
         .CLKFX_DIVIDE(`FX2_d), // Can be any Integer from 1 to 32
         .CLKFX_MULTIPLY(`FX2_m), // Can be any Integer from 2 to 32
         .CLKIN_DIVIDE_BY_2("FALSE"), // TRUE/FALSE to enable CLKIN divide by two feature
         .CLKIN_PERIOD(`prd), // Specify period of input clock
         .CLKOUT_PHASE_SHIFT("NONE"), // Specify phase shift of NONE, FIXED or VARIABLE
         .CLK_FEEDBACK("1X"), // Specify clock feedback of NONE, 1X or 2X
         .DESKEW_ADJUST("SYSTEM_SYNCHRONOUS"), // SOURCE_SYNCHRONOUS, SYSTEM_SYNCHRONOUS or
         // an Integer from 0 to 15
         .DFS_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for frequency synthesis
         .DLL_FREQUENCY_MODE("LOW"), // HIGH or LOW frequency mode for DLL
         .DUTY_CYCLE_CORRECTION("TRUE"), // Duty cycle correction, TRUE or FALSE
         .FACTORY_JF(16'hC080), // FACTORY JF values
         .PHASE_SHIFT(0), // Amount of fixed phase shift from -255 to 255
         .STARTUP_WAIT("TRUE") // Delay configuration DONE until DCM_SP LOCK, TRUE/FALSE
     ) DCM_U2 (
         .DSSEN(1'b0), 
         .CLK0(U2_CLK0), // 0 degree DCM_SP CLK output
         .CLK180(), // 180 degree DCM_SP CLK output
         .CLK270(), // 270 degree DCM_SP CLK output
         .CLK2X(U2_CLK2X), // 2X DCM_SP CLK output
         .CLK2X180(), // 2X, 180 degree DCM_SP CLK out
         .CLK90(), // 90 degree DCM_SP CLK output
         .CLKDV(U2_CLKDV), //  DCM_SP CLK out (CLKDV_DIVIDE)
         .CLKFX(U2_CLKFX), // DCM_SP CLK synthesis out (M/D)
         .CLKFX180(), // 180 degree CLK synthesis out
         .LOCKED(U2_LOCKED), // DCM_SP LOCK status output
         .PSDONE(), // Dynamic phase adjust done output
         .STATUS(), // 8-bit DCM_SP status bits output
         .CLKFB(U2_CLK0_BUF), // DCM_SP clock feedback
         .CLKIN(U1_CLKFX_BUF), // Clock input (from IBUFG, BUFG or DCM_SP)
         .PSCLK(1'b0), // Dynamic phase adjust clock input
         .PSEN(1'b0), // Dynamic phase adjust enable input
         .PSINCDEC(1'b0), // Dynamic phase adjust increment/decrement
         .RST(!U1_LOCKED)// // DCM_SP asynchronous reset input
     );
    

endmodule
