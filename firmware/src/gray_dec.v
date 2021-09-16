
module bin2gray #(parameter N = 27)( 
    input [N-1:0] bin, 
    output [N-1:0] gray
);

    assign gray[N-1] = bin[N-1];

    for(genvar i=N-2;i>=0;i=i-1) begin
        xor(gray[i],bin[i+1],bin[i]);
    end

endmodule

module gray2bin #(parameter N = 27)( 
    input [N-1:0] gray,
    output [N-1:0] bin
);

    assign bin[N-1] = gray[N-1];

    for(genvar i=N-2;i>=0;i=i-1) begin
        xor(bin[i],gray[i],bin[i+1]);
    end

endmodule
