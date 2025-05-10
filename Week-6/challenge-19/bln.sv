module binary_lif_neuron #(
    parameter int WIDTH = 16,           // Bit width for fixed-point representation
    parameter int FRAC_BITS = 8,        // Number of fractional bits
    parameter logic [WIDTH-1:0] THRESHOLD = 16'h0400,  // Threshold value of 4 in fixed-point (1024)
    parameter logic [WIDTH-1:0] RESET_VAL = 16'h0000   // Reset potential value
)(
    input  logic clk,                   // Clock signal
    input  logic rst_n,                 // Active-low reset signal
    input  logic input_spike,           // Binary input I(t)
    input  logic [WIDTH-1:0] leak_factor, // Lambda value (fixed-point)
    output logic output_spike,          // Binary output S(t)
    output logic [WIDTH-1:0] potential  // Current potential value (for monitoring)
);

    // LIF neuron dynamics
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Reset condition
            potential <= '0;
            output_spike <= 1'b0;
        end else begin
            // Update potential: P(t) = λP(t-1) + I(t)
            potential <= ((potential * leak_factor) >> FRAC_BITS) + 
                         (input_spike ? (1 << FRAC_BITS) : '0);
            
            // Check threshold and generate output spike
            if (potential >= THRESHOLD) begin
                output_spike <= 1'b1;
                potential <= RESET_VAL; // Reset when threshold reached
            end else begin
                output_spike <= 1'b0;
            end
        end
    end

endmodule