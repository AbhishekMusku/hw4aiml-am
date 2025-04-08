`timescale 1ns/1ps

module lif_neuron_tb;
    // Parameters
    parameter int CLK_PERIOD = 10;  // 10ns (100MHz) clock period
    parameter int WIDTH = 8;
    parameter int THRESHOLD = 100;
    parameter int LEAK = 2;
    parameter int REF_PERIOD = 10;
    
    // Signals
    logic                clk;
    logic                rst_n;
    logic [WIDTH-1:0]    input_current;
    logic                spike;
    
    // Instance of DUT (Design Under Test)
    lif_neuron #(
        .WIDTH(WIDTH),
        .THRESHOLD(THRESHOLD),
        .LEAK(LEAK),
        .REF_PERIOD(REF_PERIOD)
    ) dut (
        .clk(clk),
        .rst_n(rst_n),
        .input_current(input_current),
        .spike(spike)
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
        input_current = 0;
        
        // Apply reset
        #(CLK_PERIOD*2);
        rst_n = 1;
        #CLK_PERIOD;
        
        // Test Case 1: Sub-threshold stimulation
        // Apply constant current below threshold to test leak mechanism
        $display("Test Case 1: Sub-threshold stimulation - Testing leak mechanism");
        input_current = 20;  // Current less than leak + threshold
        repeat(15) @(posedge clk);
        
        // Test Case 2: Threshold crossing
        // Apply current that will eventually cause threshold crossing
        $display("Test Case 2: Threshold crossing - Testing spike generation");
        input_current = 30;  // Should eventually cross threshold
        
        // Wait for spike or timeout
        fork
            begin
                repeat(15) begin
                    @(posedge clk);
                    if (spike) begin
                        $display("Spike detected at time %t", $time);
                        break;
                    end
                end
            end
        join
        
        // Test Case 3: Refractory period
        $display("Test Case 3: Refractory period - Testing neuron doesn't spike during refractory period");
        input_current = 255;  // High current
        
        // Wait through refractory period
        repeat(REF_PERIOD+5) @(posedge clk);
        
        // Test Case 4: Spike again after refractory period
        $display("Test Case 4: Post-refractory spiking - Verify neuron can spike again");
        repeat(10) @(posedge clk);
        
        // Finish simulation
        input_current = 0;
        #(CLK_PERIOD*5);
        $display("Simulation completed successfully");
        $finish;
    end
    
    // Monitor membrane potential and spikes
    always @(posedge clk) begin
        if (rst_n) begin
            $display("Time=%t, Current=%d, Membrane=%d, Spike=%b, Refractory=%b, RefCounter=%d", 
                $time, input_current, dut.membrane_potential, spike, 
                dut.in_refractory, dut.ref_counter);
        end
    end

endmodule