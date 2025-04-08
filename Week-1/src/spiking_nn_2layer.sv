module spiking_nn_2layer #(
    parameter int N_INPUT  = 4,
    parameter int N_OUTPUT = 3,
    parameter int WIDTH    = 8
)(
    input  logic                 clk,
    input  logic                 rst_n,
    
    // Configuration interface
    input  logic [7:0]           addr,        // Register address
    input  logic [7:0]           data,        // Register data
    input  logic                 write_en,    // Write enable
    
    // Neural network interface
    input  logic [N_INPUT-1:0]   input_spikes, // Input spikes
    output logic [N_OUTPUT-1:0]  output_spikes // Output spikes
);

    // Parameter registers
    logic [WIDTH-1:0] threshold;   // Neuron threshold
    logic [WIDTH-1:0] leak_rate;   // Leak rate
    logic [WIDTH-1:0] ref_period;  // Refractory period
    
    // Synapse weights
    logic [WIDTH-1:0] synapse_weights [N_INPUT*N_OUTPUT];
    
    // Address map
    localparam ADDR_THRESHOLD = 8'h00;    // Threshold value
    localparam ADDR_LEAK_RATE = 8'h01;    // Leak rate value
    localparam ADDR_REF_PERIOD = 8'h02;   // Refractory period
    localparam ADDR_WEIGHTS_BASE = 8'h10; // Weights start at addr 0x10
    
    // Configuration register file
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            // Default values
            threshold <= 8'd100;
            leak_rate <= 8'd2;
            ref_period <= 8'd5;
            
            // Initialize weights to 0
            for (int i = 0; i < N_INPUT*N_OUTPUT; i++) begin
                synapse_weights[i] <= 8'd0;
            end
        end
        else if (write_en) begin
            // Handle register writes
            case (addr)
                ADDR_THRESHOLD: threshold <= data;
                ADDR_LEAK_RATE: leak_rate <= data;
                ADDR_REF_PERIOD: ref_period <= data;
                default: begin
                    // Write to weight if address is in weight range
                    if (addr >= ADDR_WEIGHTS_BASE && 
                        addr < ADDR_WEIGHTS_BASE + N_INPUT*N_OUTPUT) begin
                        synapse_weights[addr - ADDR_WEIGHTS_BASE] <= data;
                    end
                end
            endcase
        end
    end
    
    // Calculate input currents for neurons
    logic [WIDTH-1:0] output_currents [N_OUTPUT];
    
    always_comb begin
        // Initialize all currents to 0
        for (int j = 0; j < N_OUTPUT; j++) begin
            output_currents[j] = 0;
        end
        
        // For each input spike, add corresponding weights
        for (int i = 0; i < N_INPUT; i++) begin
            if (input_spikes[i]) begin
                for (int j = 0; j < N_OUTPUT; j++) begin
                    output_currents[j] += synapse_weights[i*N_OUTPUT + j];
                end
            end
        end
    end
    
    // Output layer LIF neurons
    genvar n;
    generate
        for (n = 0; n < N_OUTPUT; n++) begin : output_neurons
            lif_neuron #(
                .WIDTH(WIDTH)
            ) neuron (
                .clk(clk),
                .rst_n(rst_n),
                .input_current(output_currents[n]),
                .THRESHOLD(threshold),
                .LEAK(leak_rate),
                .REF_PERIOD(ref_period),
                .spike(output_spikes[n])
            );
        end
    endgenerate

endmodule