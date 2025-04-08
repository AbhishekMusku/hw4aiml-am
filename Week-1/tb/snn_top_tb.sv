`timescale 1ns/1ps

module snn_top_tb;
    // Parameters
    parameter int CLK_PERIOD = 10;  // 10ns (100MHz) clock period
    parameter int SPI_CLK_PERIOD = 40; // 40ns (25MHz) SPI clock
    
    // Signals
    logic        clk;
    logic        rst_n;
    logic        spi_clk;
    logic        spi_cs_n;
    logic        spi_mosi;
    logic        spi_miso;
    logic [3:0]  input_spikes;
    logic [2:0]  output_spikes;
    
    // Instance of DUT (Design Under Test)
    snn_top dut (
        .clk(clk),
        .rst_n(rst_n),
        .spi_clk(spi_clk),
        .spi_cs_n(spi_cs_n),
        .spi_mosi(spi_mosi),
        .spi_miso(spi_miso),
        .input_spikes(input_spikes),
        .output_spikes(output_spikes)
    );
    
    // Clock generation
    initial begin
        clk = 0;
        forever #(CLK_PERIOD/2) clk = ~clk;
    end
    
    // SPI clock generation (when needed)
    initial begin
        spi_clk = 0;
    end
    
    // SPI task to send a byte
    task send_spi_byte(input [7:0] data);
        for (int i = 7; i >= 0; i--) begin
            // Set MOSI to the bit value
            spi_mosi = data[i];
            // Toggle SPI clock
            #(SPI_CLK_PERIOD/2);
            spi_clk = 1;
            #(SPI_CLK_PERIOD/2);
            spi_clk = 0;
        end
    endtask
    
    // SPI task to send address and data
    task send_spi_command(input [7:0] addr, input [7:0] data);
        // Start SPI transaction
        spi_cs_n = 0;
        #(SPI_CLK_PERIOD);
        
        // Send address byte
        send_spi_byte(addr);
        
        // Send data byte
        send_spi_byte(data);
        
        // End SPI transaction
        #(SPI_CLK_PERIOD);
        spi_cs_n = 1;
        #(SPI_CLK_PERIOD);
    endtask
    
    // Test stimulus
    initial begin
        // Initialize signals
        rst_n = 0;
        spi_cs_n = 1;
        spi_mosi = 0;
        input_spikes = 4'b0000;
        
        // Apply reset
        #(CLK_PERIOD*5);
        rst_n = 1;
        #(CLK_PERIOD*5);
        
        // Test Case 1: Configure neuron parameters
        $display("Test Case 1: Configuring neuron parameters");
        send_spi_command(8'h00, 8'd50);  // Set threshold to 50
        #(CLK_PERIOD*5);
        send_spi_command(8'h01, 8'd5);   // Set leak rate to 5
        #(CLK_PERIOD*5);
        send_spi_command(8'h02, 8'd10);  // Set refractory period to 10
        #(CLK_PERIOD*10);
        
        // Test Case 2: Configure synapse weights
        // Configure first row of weights (input 0 to all outputs)
        $display("Test Case 2: Configuring weights");
        send_spi_command(8'h10, 8'd30);  // Input 0 -> Output 0 weight = 30
        #(CLK_PERIOD*2);
        send_spi_command(8'h11, 8'd20);  // Input 0 -> Output 1 weight = 20
        #(CLK_PERIOD*2);
        send_spi_command(8'h12, 8'd10);  // Input 0 -> Output 2 weight = 10
        #(CLK_PERIOD*2);
        
        // Configure second row of weights (input 1 to all outputs)
        send_spi_command(8'h13, 8'd15);  // Input 1 -> Output 0 weight = 15
        #(CLK_PERIOD*2);
        send_spi_command(8'h14, 8'd25);  // Input 1 -> Output 1 weight = 25
        #(CLK_PERIOD*2);
        send_spi_command(8'h15, 8'd35);  // Input 1 -> Output 2 weight = 35
        #(CLK_PERIOD*10);
        
        // Test Case 3: Test single input spike
        $display("Test Case 3: Single input spike");
        input_spikes = 4'b0001;  // Input 0 spike
        #(CLK_PERIOD*20);
        input_spikes = 4'b0000;  // Clear input spikes
        #(CLK_PERIOD*50);
        
        // Test Case 4: Test multiple input spikes
        $display("Test Case 4: Multiple input spikes");
        input_spikes = 4'b0011;  // Input 0 and 1 spikes
        #(CLK_PERIOD*20);
        input_spikes = 4'b0000;  // Clear input spikes
        #(CLK_PERIOD*50);
        
        // Test Case 5: Test repeated input patterns
        $display("Test Case 5: Repeated input patterns");
        repeat (5) begin
            input_spikes = 4'b0001;  // Input 0 spike
            #(CLK_PERIOD*2);
            input_spikes = 4'b0010;  // Input 1 spike
            #(CLK_PERIOD*2);
            input_spikes = 4'b0100;  // Input 2 spike
            #(CLK_PERIOD*2);
            input_spikes = 4'b1000;  // Input 3 spike
            #(CLK_PERIOD*2);
            input_spikes = 4'b0000;  // Clear all inputs
            #(CLK_PERIOD*7);
        end
        #(CLK_PERIOD*50);
        
        // End simulation
        $display("Simulation completed successfully");
        $finish;
    end
    
    // Monitor network activity
    always @(posedge clk) begin
        if (rst_n) begin
            if (|input_spikes) begin
                $display("Time=%0t: Input spikes=%b", $time, input_spikes);
            end
            if (|output_spikes) begin
                $display("Time=%0t: Output spikes=%b", $time, output_spikes);
            end
        end
    end

endmodule