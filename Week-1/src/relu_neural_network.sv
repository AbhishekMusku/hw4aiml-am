// Sample modifications to network module to support alternative neuron models

// 1. For ReLU Network (Continuous-valued outputs instead of spikes)
module relu_neural_network #(
    parameter int WIDTH = 8,        // Bit width for values
    parameter int NUM_INPUTS = 3,   // Number of input neurons
    parameter int HIDDEN_SIZE = 3,  // Number of hidden neurons
    parameter int NUM_OUTPUTS = 3   // Number of output neurons
)(
    input  logic                                   clk,
    input  logic                                   rst_n,
    input  logic [WIDTH-1:0]                       inputs[NUM_INPUTS],
    input  logic [WIDTH-1:0]                       hidden_biases[HIDDEN_SIZE],
    input  logic [WIDTH-1:0]                       output_biases[NUM_OUTPUTS],
    input  logic [2:0]                             slope_shift,
    // Flattened weight arrays
    input  logic [WIDTH-1:0]                       input_to_hidden_weights[NUM_INPUTS*HIDDEN_SIZE],
    input  logic [WIDTH-1:0]                       hidden_to_output_weights[HIDDEN_SIZE*NUM_OUTPUTS],
    output logic [WIDTH-1:0]                       outputs[NUM_OUTPUTS]
);

    // Hidden layer outputs
    logic [WIDTH-1:0] hidden_outputs[HIDDEN_SIZE];
    // Input currents for hidden layer neurons
    logic [WIDTH-1:0] hidden_currents[HIDDEN_SIZE];
    // Input currents for output layer neurons
    logic [WIDTH-1:0] output_currents[NUM_OUTPUTS];
    
    // Calculate input currents for hidden layer neurons (weighted sum)
    always_comb begin
        // Initialize all currents to 0
        for (int i = 0; i < HIDDEN_SIZE; i++) begin
            hidden_currents[i] = '0;
        end
        
        // Weighted sum of inputs
        for (int i = 0; i < HIDDEN_SIZE; i++) begin
            for (int j = 0; j < NUM_INPUTS; j++) begin
                hidden_currents[i] = hidden_currents[i] + 
                    ((inputs[j] * input_to_hidden_weights[i*NUM_INPUTS + j]) >> (WIDTH/2));
            end
        end
    end
    
    // Hidden layer ReLU neurons
    genvar h;
    generate
        for (h = 0; h < HIDDEN_SIZE; h++) begin : hidden_neurons
            relu_neuron #(
                .WIDTH(WIDTH)
            ) hidden_neuron (
                .clk(clk),
                .rst_n(rst_n),
                .input_current(hidden_currents[h]),
                .bias(hidden_biases[h]),
                .slope_shift(slope_shift),
                .output_value(hidden_outputs[h])
            );
        end
    endgenerate
    
    // Calculate input currents for output layer neurons
    always_comb begin
        // Initialize all currents to 0
        for (int i = 0; i < NUM_OUTPUTS; i++) begin
            output_currents[i] = '0;
        end
        
        // Weighted sum of hidden layer outputs
        for (int i = 0; i < NUM_OUTPUTS; i++) begin
            for (int j = 0; j < HIDDEN_SIZE; j++) begin
                output_currents[i] = output_currents[i] + 
                    ((hidden_outputs[j] * hidden_to_output_weights[i*HIDDEN_SIZE + j]) >> (WIDTH/2));
            end
        end
    end
    
    // Output layer ReLU neurons
    genvar o;
    generate
        for (o = 0; o < NUM_OUTPUTS; o++) begin : output_neurons
            relu_neuron #(
                .WIDTH(WIDTH)
            ) output_neuron (
                .clk(clk),
                .rst_n(rst_n),
                .input_current(output_currents[o]),
                .bias(output_biases[o]),
                .slope_shift(slope_shift),
                .output_value(outputs[o])
            );
        end
    endgenerate
    
endmodule

// 2. For Hodgkin-Huxley Network (similar structure to LIF network but with more parameters)
module hh_neural_network #(
    parameter int WIDTH = 16,       // Bit width for values
    parameter int FRAC_BITS = 8,    // Fractional bits for fixed-point
    parameter int NUM_INPUTS = 3,   // Number of input neurons
    parameter int HIDDEN_SIZE = 3,  // Number of hidden neurons
    parameter int NUM_OUTPUTS = 3   // Number of output neurons
)(
    input  logic                                   clk,
    input  logic                                   rst_n,
    input  logic                                   spikes_in[NUM_INPUTS],
    // Neuron parameters (shared across all neurons for simplicity)
    input  logic [WIDTH-1:0]                       g_na_max,
    input  logic [WIDTH-1:0]                       g_k_max,
    input  logic [WIDTH-1:0]                       g_leak,
    input  logic [WIDTH-1:0]                       e_na,
    input  logic [WIDTH-1:0]                       e_k,
    input  logic [WIDTH-1:0]                       e_leak,
    input  logic [WIDTH-1:0]                       alpha_scale,
    input  logic [WIDTH-1:0]                       beta_scale,
    // Flattened weight arrays
    input  logic [WIDTH-1:0]                       input_to_hidden_weights[NUM_INPUTS*HIDDEN_SIZE],
    input  logic [WIDTH-1:0]                       hidden_to_output_weights[HIDDEN_SIZE*NUM_OUTPUTS],
    output logic                                   spikes_out[NUM_OUTPUTS],
    output logic [WIDTH-1:0]                       output_potentials[NUM_OUTPUTS]
);

    // Hidden layer spikes and potentials
    logic hidden_spikes[HIDDEN_SIZE];
    logic [WIDTH-1:0] hidden_potentials[HIDDEN_SIZE];
    
    // Input currents for hidden layer neurons
    logic [WIDTH-1:0] hidden_currents[HIDDEN_SIZE];
    // Input currents for output layer neurons
    logic [WIDTH-1:0] output_currents[NUM_OUTPUTS];
    
    // Calculate weighted input currents for hidden layer based on input spikes
    always_comb begin
        // Initialize all currents to 0
        for (int i = 0; i < HIDDEN_SIZE; i++) begin
            hidden_currents[i] = '0;
        end
        
        // For each hidden neuron, sum the input weights for input spikes that are active
        for (int i = 0; i < HIDDEN_SIZE; i++) begin
            for (int j = 0; j < NUM_INPUTS; j++) begin
                if (spikes_in[j]) begin
                    hidden_currents[i] = hidden_currents[i] + input_to_hidden_weights[i*NUM_INPUTS + j];
                end
            end
        end
    end
    
    // Hidden layer Hodgkin-Huxley neurons
    genvar h;
    generate
        for (h = 0; h < HIDDEN_SIZE; h++) begin : hidden_neurons
            hodgkin_huxley_neuron #(
                .WIDTH(WIDTH),
                .FRAC_BITS(FRAC_BITS)
            ) hidden_neuron (
                .clk(clk),
                .rst_n(rst_n),
                .input_current(hidden_currents[h]),
                .g_na_max(g_na_max),
                .g_k_max(g_k_max),
                .g_leak(g_leak),
                .e_na(e_na),
                .e_k(e_k),
                .e_leak(e_leak),
                .alpha_scale(alpha_scale),
                .beta_scale(beta_scale),
                .spike(hidden_spikes[h]),
                .membrane_potential(hidden_potentials[h])
            );
        end
    endgenerate
    
    // Calculate input currents for output layer based on hidden layer spikes
    always_comb begin
        // Initialize all currents to 0
        for (int i = 0; i < NUM_OUTPUTS; i++) begin
            output_currents[i] = '0;
        end
        
        // For each output neuron, sum the hidden weights for hidden spikes that are active
        for (int i = 0; i < NUM_OUTPUTS; i++) begin
            for (int j = 0; j < HIDDEN_SIZE; j++) begin
                if (hidden_spikes[j]) begin
                    output_currents[i] = output_currents[i] + hidden_to_output_weights[i*HIDDEN_SIZE + j];
                end
            end
        end
    end
    
    // Output layer Hodgkin-Huxley neurons
    genvar o;
    generate
        for (o = 0; o < NUM_OUTPUTS; o++) begin : output_neurons
            hodgkin_huxley_neuron #(
                .WIDTH(WIDTH),
                .FRAC_BITS(FRAC_BITS)
            ) output_neuron (
                .clk(clk),
                .rst_n(rst_n),
                .input_current(output_currents[o]),
                .g_na_max(g_na_max),
                .g_k_max(g_k_max),
                .g_leak(g_leak),
                .e_na(e_na),
                .e_k(e_k),
                .e_leak(e_leak),
                .alpha_scale(alpha_scale),
                .beta_scale(beta_scale),
                .spike(spikes_out[o]),
                .membrane_potential(output_potentials[o])
            );
        end
    endgenerate
    
endmodule
