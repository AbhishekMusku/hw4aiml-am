module lif_neuron #(
    parameter int WIDTH       = 8,     // Bit width of input current & membrane potential
    parameter int THRESHOLD   = 100,   // Spiking threshold
    parameter int LEAK        = 2,     // Leak per timestep
    parameter int REF_PERIOD  = 10     // Refractory period (in clock cycles)
)(
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic [WIDTH-1:0]     input_current,
    output logic                 spike
);

    // Internal state
    logic [WIDTH-1:0] membrane_potential;
    logic [$clog2(REF_PERIOD+1)-1:0] ref_counter;
    logic in_refractory;

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            membrane_potential <= 0;
            ref_counter        <= 0;
            in_refractory      <= 0;
            spike              <= 0;
        end else begin
            spike <= 0; // Default to no spike each cycle

            if (in_refractory) begin
                if (ref_counter == REF_PERIOD - 1) begin
                    in_refractory      <= 0;
                    ref_counter        <= 0;
                    membrane_potential <= 0;
                end else begin
                    ref_counter <= ref_counter + 1;
                end
            end else begin
                // Update membrane potential with leak and input
                if (membrane_potential > LEAK)
                    membrane_potential <= membrane_potential - LEAK + input_current;
                else
                    membrane_potential <= input_current;

                // Spike check
                if (membrane_potential >= THRESHOLD) begin
                    spike              <= 1;
                    in_refractory      <= 1;
                    ref_counter        <= 0;
                    membrane_potential <= 0;
                end
            end
        end
    end

endmodule
