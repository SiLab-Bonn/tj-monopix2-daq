
module oddr_reg
(
    input wire CLK, 
    input wire [1:0] DATA,
    output wire OUT
);
    
reg [1:0] REG;
always@(posedge CLK)
    REG <= DATA;

ODDR oddr(
    .D1(REG[0]), .D2(REG[1]), 
    .C(CLK), .CE(1'b1), .R(1'b0), .S(1'b0),
    .Q(OUT)
);

    
endmodule

module tlu_tx 
#(
    parameter INV_OUT = 0
)( 
    input wire SYS_CLK, CLK320, CLK160, SYS_RST, ENABLE, TRIG,
    input wire [30:0] TRIG_ID,
	input wire [4:0] N_BITS_TRIGGER_ID,
    output wire READY,
    input wire [3:0] TRIG_LE,
    input wire [15:0] CONF_TIME_OUT,
    output wire TIME_OUT,
	 output wire [2:0]STATE_OUT,
    
    input wire TLU_CLOCK, TLU_BUSY,
    output wire TLU_TRIGGER, TLU_RESET
);


wire TIMEOUT_INT;
reg TRIG_FF;
localparam WAIT_STATE = 3'b001, TRIG_STATE =3'b010, READ_ID_STATE = 3'b100;

reg [2:0] state, state_next;
always@(posedge SYS_CLK)
    if(SYS_RST)
        state <= WAIT_STATE;
    else
        state <= state_next;

reg [1:0] BUSY_FF;
always@(posedge SYS_CLK)
    BUSY_FF <= {BUSY_FF[0], INV_OUT ? ~TLU_BUSY : TLU_BUSY};

wire BUSY_REAL;
assign BUSY_REAL = &BUSY_FF; //This should not be needed but ...

always@(*) begin
    state_next = state;
    
    case(state)
        WAIT_STATE: 
            if(TRIG)
                state_next = TRIG_STATE;
        TRIG_STATE:
            if(TIMEOUT_INT)
                state_next = WAIT_STATE;
            else if(BUSY_REAL)
                state_next = READ_ID_STATE;
        READ_ID_STATE:
            if(!BUSY_REAL)
                state_next = WAIT_STATE;
        default : state_next = WAIT_STATE;
    endcase
end

wire TLU_CLOCK_REAL;

reg [4:0] TLU_CLOCK_FF;
always@(posedge CLK160)
    TLU_CLOCK_FF <= {TLU_CLOCK_FF[3:0], INV_OUT ? ~TLU_CLOCK : TLU_CLOCK};

assign TLU_CLOCK_REAL = TLU_CLOCK_FF[4:3] == 2'b00 && TLU_CLOCK_FF[2:1] == 2'b11; //This is bad but seem to help for some cross-talk

wire TLU_CLOCK_HIGH;
assign TLU_CLOCK_HIGH = TLU_CLOCK_FF[4:1] == 4'b1111;

reg [31:0] TRIG_ID_SR;
initial TRIG_ID_SR = 0;
//always@(posedge TLU_CLOCK_REAL or posedge TRIG_FF)
integer n;
always@(posedge CLK160)
    if(TRIG_FF)
        TRIG_ID_SR <= {TRIG_ID, 1'b0};
    else if (TLU_CLOCK_REAL & BUSY_REAL)
		// This loop basically does: TRIG_ID_SR <= {(32 - N_BITS_TRIGGER_ID)'b0, TRIG_ID_SR[N_BITS_TRIGGER_ID:1]}
		for (n = 0; n < 31; n = n + 1)
			if (n < N_BITS_TRIGGER_ID)
				TRIG_ID_SR[n] <= TRIG_ID_SR[n+1];
			else
				TRIG_ID_SR[n] <= 1'b0;

reg [31:0] WAIT_CNT;
always@(posedge SYS_CLK) begin
    if(SYS_RST)
        WAIT_CNT <= 0;
    else if(state == READ_ID_STATE && state_next == WAIT_STATE)
        WAIT_CNT <= 4;
    else if(WAIT_CNT != 0)
        WAIT_CNT <= WAIT_CNT - 1;
end

reg TRIG_OUT;
always@(*) //posedge SYS_CLK)
    TRIG_OUT = (state == TRIG_STATE) || TRIG_ID_SR[0];

assign TLU_RESET = INV_OUT ? 1'b0 : 1'b0;

reg TLU_CLOCK_VETO;
always@(posedge SYS_CLK)
    TLU_CLOCK_VETO <= TLU_CLOCK_HIGH;
    
assign READY = (state == WAIT_STATE  && TLU_CLOCK_VETO == 0  && WAIT_CNT==0) | !ENABLE;
assign STATE_OUT = ENABLE? state: 3'b0;

reg [15:0] TIME_OUT_CNT;
always@(posedge SYS_CLK) begin
    if(SYS_RST)
        TIME_OUT_CNT <= 0;
    else if(TRIG)
        TIME_OUT_CNT <= CONF_TIME_OUT;
    else if(TIME_OUT_CNT != 0)
        TIME_OUT_CNT <= TIME_OUT_CNT -1;
end


assign TIMEOUT_INT = (TIME_OUT_CNT == 0) && (CONF_TIME_OUT != 0);
reg TIME_OUT_FF;
always@(posedge SYS_CLK)
    TIME_OUT_FF <= TIMEOUT_INT;

assign TIME_OUT = !TIME_OUT_FF && TIMEOUT_INT && ENABLE;

reg [7:0] TRIG_DES;
wire [3:0] TRIG_LE_CALC;
assign TRIG_LE_CALC = TRIG_LE -1;

integer i;
always@(posedge SYS_CLK)
    for(i = 7; i>=0; i = i - 1)
        TRIG_DES[i] <= (2*i <= TRIG_LE_CALC);


always@(posedge SYS_CLK)
    TRIG_FF <= TRIG;
    
reg [1:0] trig_des_sr;
always@(posedge CLK160)
    trig_des_sr[1:0] <= {trig_des_sr[0], TRIG_FF};

wire LOAD_DES;
assign LOAD_DES = (trig_des_sr[0] == 1 && trig_des_sr[1] == 0);

reg TRIG_OUT_DES; 
always@(posedge CLK160)
    TRIG_OUT_DES <= TRIG_OUT;
    
reg [7:0] TRIG_DES_OUT;
always@(posedge CLK160)
    if(LOAD_DES)
        TRIG_DES_OUT <= TRIG_DES;
    else if (trig_des_sr[1])
        TRIG_DES_OUT <= {TRIG_DES_OUT[5:0], 2'b11};
    else
        TRIG_DES_OUT[7:6] <= {2{TRIG_OUT_DES}};

wire [1:0] TO_ODDR ;
assign TO_ODDR = INV_OUT ? ~TRIG_DES_OUT[7:6] : TRIG_DES_OUT[7:6];
    
oddr_reg oddr_reg(
    .CLK(CLK160), 
    .DATA(TO_ODDR),
    .OUT(TLU_TRIGGER)
    );

endmodule