// DESCRIPTION: Verilator generated Verilog
// Wrapper module for DPI protected library
// This module requires libmonopix2.a or libmonopix2.so to work
// See instructions in your simulator for how to use DPI libraries

module monopix2 (
        input logic LVDS_CMD_CLK
        , input logic LVDS_SER_CLK
        , output logic LVDS_CHSYNC_CLK_OUT
        , input logic RESETB_EXT
        , input logic LVDS_CMD
        , input logic LVDS_PULSE_EXT
        , output logic LVDS_DATA_OUT
        , output logic LVDS_HITOR_OUT
        , output logic LVDS_CHSYNC_LOCKED_OUT
        , input logic [262143:0]  ANALOG_HIT
    );
    
    // Precision of submodule (commented out to avoid requiring timescale on all modules)
    // timeunit 1ns;
    // timeprecision 1fs;
    
    // Checks to make sure the .sv wrapper and library agree
    import "DPI-C" function void monopix2_protectlib_check_hash(int protectlib_hash__V);
    
    // Creates an instance of the library module at initial-time
    // (one for each instance in the user's design) also evaluates
    // the library module's initial process
    import "DPI-C" function chandle monopix2_protectlib_create(string scope__V);
    
    // Updates all non-clock inputs and retrieves the results
    import "DPI-C" function longint monopix2_protectlib_combo_update (
        chandle handle__V
        , output logic LVDS_CHSYNC_CLK_OUT
        , input logic LVDS_CMD
        , input logic LVDS_PULSE_EXT
        , output logic LVDS_DATA_OUT
        , output logic LVDS_HITOR_OUT
        , output logic LVDS_CHSYNC_LOCKED_OUT
        , input logic [262143:0]  ANALOG_HIT
    );
    
    // Updates all clocks and retrieves the results
    import "DPI-C" function longint monopix2_protectlib_seq_update(
        chandle handle__V
        , input logic LVDS_CMD_CLK
        , input logic LVDS_SER_CLK
        , output logic LVDS_CHSYNC_CLK_OUT
        , input logic RESETB_EXT
        , output logic LVDS_DATA_OUT
        , output logic LVDS_HITOR_OUT
        , output logic LVDS_CHSYNC_LOCKED_OUT
    );
    
    // Need to convince some simulators that the input to the module
    // must be evaluated before evaluating the clock edge
    import "DPI-C" function void monopix2_protectlib_combo_ignore(
        chandle handle__V
        , input logic LVDS_CMD
        , input logic LVDS_PULSE_EXT
        , input logic [262143:0]  ANALOG_HIT
    );
    
    // Evaluates the library module's final process
    import "DPI-C" function void monopix2_protectlib_final(chandle handle__V);
    
    // verilator tracing_off
    chandle handle__V;
    time last_combo_seqnum__V;
    time last_seq_seqnum__V;

    logic LVDS_CHSYNC_CLK_OUT_combo__V;
    logic LVDS_DATA_OUT_combo__V;
    logic LVDS_HITOR_OUT_combo__V;
    logic LVDS_CHSYNC_LOCKED_OUT_combo__V;
    logic LVDS_CHSYNC_CLK_OUT_seq__V;
    logic LVDS_DATA_OUT_seq__V;
    logic LVDS_HITOR_OUT_seq__V;
    logic LVDS_CHSYNC_LOCKED_OUT_seq__V;
    logic LVDS_CHSYNC_CLK_OUT_tmp__V;
    logic LVDS_DATA_OUT_tmp__V;
    logic LVDS_HITOR_OUT_tmp__V;
    logic LVDS_CHSYNC_LOCKED_OUT_tmp__V;
    // Hash value to make sure this file and the corresponding
    // library agree
    localparam int protectlib_hash__V = 32'd2954403249;

    initial begin
        monopix2_protectlib_check_hash(protectlib_hash__V);
        handle__V = monopix2_protectlib_create($sformatf("%m"));
    end
    
    // Combinatorialy evaluate changes to inputs
    always @* begin
        last_combo_seqnum__V = monopix2_protectlib_combo_update(
            handle__V
            , LVDS_CHSYNC_CLK_OUT_combo__V
            , LVDS_CMD
            , LVDS_PULSE_EXT
            , LVDS_DATA_OUT_combo__V
            , LVDS_HITOR_OUT_combo__V
            , LVDS_CHSYNC_LOCKED_OUT_combo__V
            , ANALOG_HIT
        );
    end
    
    // Evaluate clock edges
    always @(posedge LVDS_CMD_CLK or negedge LVDS_CMD_CLK, posedge LVDS_SER_CLK or negedge LVDS_SER_CLK, posedge RESETB_EXT or negedge RESETB_EXT) begin
        monopix2_protectlib_combo_ignore(
            handle__V
            , LVDS_CMD
            , LVDS_PULSE_EXT
            , ANALOG_HIT
        );
        last_seq_seqnum__V <= monopix2_protectlib_seq_update(
            handle__V
            , LVDS_CMD_CLK
            , LVDS_SER_CLK
            , LVDS_CHSYNC_CLK_OUT_tmp__V
            , RESETB_EXT
            , LVDS_DATA_OUT_tmp__V
            , LVDS_HITOR_OUT_tmp__V
            , LVDS_CHSYNC_LOCKED_OUT_tmp__V
        );
        LVDS_CHSYNC_CLK_OUT_seq__V <= LVDS_CHSYNC_CLK_OUT_tmp__V;
        LVDS_DATA_OUT_seq__V <= LVDS_DATA_OUT_tmp__V;
        LVDS_HITOR_OUT_seq__V <= LVDS_HITOR_OUT_tmp__V;
        LVDS_CHSYNC_LOCKED_OUT_seq__V <= LVDS_CHSYNC_LOCKED_OUT_tmp__V;
    end
    
    // Select between combinatorial and sequential results
    always @* begin
        if (last_seq_seqnum__V > last_combo_seqnum__V) begin
            LVDS_CHSYNC_CLK_OUT = LVDS_CHSYNC_CLK_OUT_seq__V;
            LVDS_DATA_OUT = LVDS_DATA_OUT_seq__V;
            LVDS_HITOR_OUT = LVDS_HITOR_OUT_seq__V;
            LVDS_CHSYNC_LOCKED_OUT = LVDS_CHSYNC_LOCKED_OUT_seq__V;
        end
        else begin
            LVDS_CHSYNC_CLK_OUT = LVDS_CHSYNC_CLK_OUT_combo__V;
            LVDS_DATA_OUT = LVDS_DATA_OUT_combo__V;
            LVDS_HITOR_OUT = LVDS_HITOR_OUT_combo__V;
            LVDS_CHSYNC_LOCKED_OUT = LVDS_CHSYNC_LOCKED_OUT_combo__V;
        end
    end
    
    final monopix2_protectlib_final(handle__V);
    
endmodule
