`timescale 1ns/1ps

module spiking_nn_2layer_tb;
    // Parameters
    parameter int CLK_PERIOD = 10;  // 10ns (100MHz) clock period
    parameter int N_INPUT  = 4;
    parameter int N_OUTPUT = 3;
    parameter int WIDTH    = 8;
    
    // Signals
    logic                clk;
    logic                rst_n;
    logic [N_INPUT-1:0]  input_spikes;
    logic [N_OUTPUT-1:0] output_spikes;
    
    // Instance of DUT (Design Under Test)
    spiking_nn_2layer #(
        .N_INPUT(N_INPUT),
        .N_OUTPUT(N_OUTPUT),
        .WIDTH(WIDTH)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .input_spikes(input_spikes),
        .output_spikes(output_spikes)
    );
    
    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end
    
    // Test stimulus
    initial begin
        // Initialize signals
        rst_n = 0;
        input_spikes = '0;
        
        // Initialize synapse weights for testing
        // We'll set specific patterns to test different neural pathways
        for (int i = 0; i < N_INPUT; i++) begin
            for (int j = 0; j < N_OUTPUT; j++) begin
                // Simple pattern: weight = (i+1)*10 + j
                // Input 0 has smaller weights, Input 3 has larger weights
                dut.synapse_weights[i][j] = (i+1)*10 + j;
            end
        end
        
        // Display initial weights
        $display("Synapse Weights:");
        for (int i = 0; i < N_INPUT; i++) begin
            for (int j = 0; j < N_OUTPUT; j++) begin
                $display("  Weight[%0d][%0d] = %0d", i, j, dut.synapse_weights[i][j]);
            end
        end
        
        // Apply reset
        #(CLK_PERIOD*2);
        rst_n = 1;
        #CLK_PERIOD;
        
        // Test Case 1: Single input spike
        $display("\nTest Case 1: Single input spike");
        input_spikes = 4'b0001; // Only input 0 spikes
        repeat(5) @(posedge clk);
        input_spikes = 4'b0000;
        repeat(5) @(posedge clk);
        
        // Test Case 2: Multiple input spikes
        $display("\nTest Case 2: Multiple input spikes");
        input_spikes = 4'b1010; // Inputs 1 and 3 spike
        repeat(5) @(posedge clk);
        input_spikes = 4'b0000;
        repeat(10) @(posedge clk);
        
        // Test Case 3: All inputs spike
        $display("\nTest Case 3: All inputs spike");
        input_spikes = 4'b1111; // All inputs spike
        repeat(5) @(posedge clk);
        input_spikes = 4'b0000;
        repeat(20) @(posedge clk);
        
        // Test Case 4: Repeated spike pattern
        $display("\nTest Case 4: Repeated spike pattern");
        for (int i = 0; i < 5; i++) begin
            input_spikes = 4'b0001;
            @(posedge clk);
            input_spikes = 4'b0010;
            @(posedge clk);
            input_spikes = 4'b0100;
            @(posedge clk);
            input_spikes = 4'b1000;
            @(posedge clk);
            input_spikes = 4'b0000;
            repeat(2) @(posedge clk);
        end
        
        // Finish simulation
        input_spikes = '0;
        #(CLK_PERIOD*10);
        $display("Simulation completed successfully");
        $finish;
    end
    
    // Monitor network activity
    always @(posedge clk) begin
        if (rst_n) begin
            // Display input and output spikes
            $display("Time=%t, InputSpikes=%b, OutputSpikes=%b", $time, input_spikes, output_spikes);
            
            // Display output layer neuron states when there's activity
            if (|input_spikes || |output_spikes) begin
                $display("  Output Currents: [%0d, %0d, %0d]", dut.output_currents[0], dut.output_currents[1], dut.output_currents[2]);
                
                // We cannot directly index the output_layer array in this way
                // Instead, we will simply monitor the output spikes
                $display("  Output Spikes: %b", output_spikes);
            end
        end
    end

endmodule