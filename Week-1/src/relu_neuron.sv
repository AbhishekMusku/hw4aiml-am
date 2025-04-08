module relu_neuron #(
    parameter int WIDTH = 8     // Bit width of input current & output
)(
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic [WIDTH-1:0]     input_current,
    input  logic [WIDTH-1:0]     bias,         // Bias term (equivalent to threshold)
    input  logic [2:0]           slope_shift,  // For implementing leaky ReLU if desired
    output logic [WIDTH-1:0]     output_value  // Continuous output instead of spike
);

    // Internal signals
    logic signed [WIDTH:0] sum_with_bias; // Extra bit for sign
    logic [WIDTH-1:0] relu_out;
    
    // Add bias (can be negative) and compute ReLU
    assign sum_with_bias = $signed({1'b0, input_current}) + $signed({bias[WIDTH-1], bias});
    
    // ReLU function: max(0, sum_with_bias)
    // For standard ReLU
    assign relu_out = (sum_with_bias[WIDTH]) ? '0 : sum_with_bias[WIDTH-1:0];
    
    // Register the output
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            output_value <= '0;
        end else begin
            output_value <= relu_out;
        end
    end
    
    // Note: slope_shift input could be used to implement leaky ReLU
    // by returning sum_with_bias >> slope_shift when sum_with_bias < 0
    // Example: if (sum_with_bias[WIDTH]) 
    //             output_value <= sum_with_bias[WIDTH-1:0] >> slope_shift;
    //          else 
    //             output_value <= sum_with_bias[WIDTH-1:0];

endmodule
