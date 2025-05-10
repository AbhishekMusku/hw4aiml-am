module tb;
    
    // Parameters and signals
    localparam int WIDTH = 16;
    localparam int FRAC_BITS = 8;
    localparam logic [WIDTH-1:0] THRESHOLD = 16'h0400;  // Threshold of 4 (4.0 × 2^8 = 1024)
    localparam logic [WIDTH-1:0] RESET_VAL = 16'h0000;
    
    // Testbench signals
    logic clk;
    logic rst_n;
    logic input_spike;
    logic [WIDTH-1:0] leak_factor;
    logic output_spike;
    logic [WIDTH-1:0] potential;
    
    // Fixed-point values for leak factors
    localparam logic [WIDTH-1:0] LAMBDA_08 = 16'h00CC;  // 0.8 (204/256)
    localparam logic [WIDTH-1:0] LAMBDA_05 = 16'h0080;  // 0.5 (128/256)
    
    // Instantiate the neuron
    binary_lif_neuron #(
        .WIDTH(WIDTH),
        .FRAC_BITS(FRAC_BITS),
        .THRESHOLD(THRESHOLD),
        .RESET_VAL(RESET_VAL)
    ) uut (
        .clk(clk),
        .rst_n(rst_n),
        .input_spike(input_spike),
        .leak_factor(leak_factor),
        .output_spike(output_spike),
        .potential(potential)
    );
    
    // Clock generation - 10ns period (100MHz)
    always begin
        #5 clk = ~clk;
    end
    
    // Task to display the potential in decimal format
    function real fixed_to_real(logic [WIDTH-1:0] fixed_val);
        return real'(fixed_val) / real'(2**FRAC_BITS);
    endfunction
    
    // Monitoring the neuron's behavior with clearer spike indication
    always @(posedge clk) begin
        string spike_status;
        
        if (output_spike)
            spike_status = "SPIKE=1 [NEURON FIRED!]";
        else
            spike_status = "SPIKE=0";
            
        $display("Time=%0t: Input=%b, Potential=%f, Lambda=%f, %s", 
                $time, input_spike, fixed_to_real(potential), 
                fixed_to_real(leak_factor), spike_status);
    end
    
    // Main test sequence
    initial begin
        // Initialize signals
        clk = 0;
        rst_n = 0;
        input_spike = 0;
        leak_factor = LAMBDA_05;  // Start with lambda=0.5 for Test Case 1
        
        // Release reset
        #20 rst_n = 1;
        
        // Test Case 1: Constant input below threshold (with lambda=0.5)
        $display("\n=== Test Case 1: Constant input below threshold (lambda=0.5) ===");
        repeat(10) begin
            @(posedge clk) input_spike = 1;
        end
        @(posedge clk) input_spike = 0;
        repeat(5) @(posedge clk); // Observe leakage for a few cycles
        
        // Reset for next test
        rst_n = 0;
        #20 rst_n = 1;
        
        // Test Case 2: Input that accumulates until reaching threshold (with lambda=0.8)
        leak_factor = LAMBDA_08;  // Change to lambda=0.8
        $display("\n=== Test Case 2: Input that accumulates until reaching threshold (lambda=0.8) ===");
        repeat(25) begin  // Should reach threshold sooner with lower threshold
            @(posedge clk) input_spike = 1;
        end
        @(posedge clk) input_spike = 0;
        repeat(5) @(posedge clk); // Observe behavior after
        
        // Reset for next test
        rst_n = 0;
        #20 rst_n = 1;
        
        // Test Case 3: Leakage with no input (with lambda=0.8)
        $display("\n=== Test Case 3: Leakage with no input (lambda=0.8) ===");
        // First charge up the neuron (but below threshold)
        repeat(12) begin  // Fewer iterations to stay safely below threshold
            @(posedge clk) input_spike = 1;
        end
        
        // Then observe leakage
        $display("--- Leakage starts now ---");
        @(posedge clk) input_spike = 0;
        repeat(15) @(posedge clk);
        
        // Reset for next test
        rst_n = 0;
        #20 rst_n = 1;
        
		// Test Case 4: Strong input causing immediate spiking (with lambda=0.8)
		$display("\n=== Test Case 4: Strong input causing immediate spiking (lambda=0.8) ===");
		// Instead of trying to directly set the potential, we'll use a very strong input
		@(posedge clk);
		input_spike = 1;
		force uut.potential = 16'h0390; // Force to ~3.56 (close to threshold)
		@(posedge clk);
		release uut.potential;
		input_spike = 1; // This should push it over threshold
		@(posedge clk);
		input_spike = 0;
        
        // End simulation
        repeat(5) @(posedge clk);
        $display("Simulation complete");
        $finish;
    end
    
endmodule