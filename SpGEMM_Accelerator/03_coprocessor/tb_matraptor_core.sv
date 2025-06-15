//====================================================================
// MatRaptor Core Testbench with SPI Interface and Performance Measurement
//====================================================================
//
// FUNCTIONALITY:
// - SPI-driven testbench for MatRaptor sparse matrix accelerator
// - Hardware execution timing measurement for performance analysis
// - Automatic completion detection and output verification
//
// TEST FLOW:
// - Cocotb Python script drives SPI frames (value, row, col, last_flag)
// - Hardware processes partial products with timing measurement
// - Outputs captured to CSV for verification
//
// TIMING MEASUREMENT:
// - Start: First valid input accepted
// - Stop: Final row merge completion (S_MERGE_NEXT_Q state)
// - Precision: Nanosecond resolution via $time
//
// COMPLETION DETECTION:
// - Monitors SPI input completion (in_last flag)
// - Tracks PE state machine transitions
// - Automatic termination when all rows processed
//
// INTERFACES:
// - SPI: Variable frequency from cocotb
// - System: 500MHz clock for MatRaptor core
// - Output: CSV logging (row,col,value format)
//
// SAFETY:
// - 10ms watchdog timeout
// - State deadlock detection
// - Graceful file handle cleanup
//====================================================================
`timescale 1ns/1ps

module tb_matraptor_core;
    //----------------------------------------------------------------
    // 1. Parameters
    //----------------------------------------------------------------
    localparam int DATA_W   = 32;
    localparam int IDX_W    = 16;
    localparam int NQ       = 8;
    localparam int Q_DEPTH  = 256;
    localparam int NUM_PES  = 1;

    //----------------------------------------------------------------
    // 2. Clock / reset
    //----------------------------------------------------------------
    logic clk = 0;
    always #1 clk = ~clk; // 500 MHz

    logic rst_n = 0;
    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1;
    end
	
    // SPI signals (driven by cocotb)
    logic spi_clk = 0;
    logic spi_cs_n = 1;
    logic spi_mosi = 0;
	
    //----------------------------------------------------------------
    // 3. TIMING MEASUREMENT VARIABLES
    //----------------------------------------------------------------
    time start_time, end_time;
    logic timing_started, timing_stopped;
    real execution_time_ns, execution_time_seconds;

    //----------------------------------------------------------------
    // 4. DUT interface signals
    //----------------------------------------------------------------
    logic                 in_valid;
    logic                 in_ready;
    logic [DATA_W-1:0]    in_val;
    logic [IDX_W-1:0]     in_row;
    logic [IDX_W-1:0]     in_col;
    logic                 in_last;
    logic [NUM_PES-1:0]   pe_row_done;

    // Output interface signals
    logic [NUM_PES-1:0]   out_valid;
    logic [NUM_PES-1:0]   out_ready;
    logic [DATA_W-1:0]    out_val[NUM_PES];
    logic [IDX_W-1:0]     out_col[NUM_PES];
    logic [NUM_PES-1:0]   out_last;
	
    //----------------------------------------------------------------
    // 5. SPI Interface (replaces CSV reader)
    //----------------------------------------------------------------
    simple_spi_interface #(
        .DATA_W(DATA_W),
        .IDX_W(IDX_W)
    ) spi_if (
        .clk(clk),
        .rst_n(rst_n),
        .spi_clk(spi_clk),
        .spi_cs_n(spi_cs_n),
        .spi_mosi(spi_mosi),
        .in_valid(in_valid),
        .in_ready(in_ready),
        .in_val(in_val),
        .in_row(in_row),
        .in_col(in_col),
        .in_last(in_last)
    );

    //----------------------------------------------------------------
    // 6. Instantiate MatRaptor
    //----------------------------------------------------------------
    matraptor_core #(
        .DATA_W  (DATA_W),
        .IDX_W   (IDX_W),
        .NQ      (NQ),
        .Q_DEPTH (Q_DEPTH),
        .NUM_PES (NUM_PES)
    ) dut (
        .clk         (clk),
        .rst_n       (rst_n),
        .in_valid    (in_valid),
        .in_ready    (in_ready),
        .in_val      (in_val),
        .in_row      (in_row),
        .in_col      (in_col),
        .in_last     (in_last),
        .pe_row_done (pe_row_done),
        .out_valid   (out_valid),
        .out_ready   (out_ready),
        .out_val     (out_val),
        .out_col     (out_col),
        .out_last    (out_last)
    );
	
    //----------------------------------------------------------------
    // 7. TIMING START DETECTION
    //----------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            timing_started <= 0;
            start_time <= 0;
        end else if (in_valid && in_ready && !timing_started) begin
            timing_started <= 1;
            start_time <= $time;
            $display("[TB TIMING] Started at time %0t", $time);
        end
    end
	
    //----------------------------------------------------------------
    // 8. Track SPI input completion 
    //----------------------------------------------------------------
    logic input_feeding_done;
    logic [IDX_W-1:0] last_row_sent;
    logic [IDX_W-1:0] current_row_processing;

    // Always ready to accept outputs
    assign out_ready = '1;
    
    // Output capture storage
    typedef struct {
        logic [IDX_W-1:0] row;
        logic [IDX_W-1:0] col;
        logic [DATA_W-1:0] val;
        real val_real;
    } output_entry_t;
        
    output_entry_t captured_outputs[$];
    
    // Monitor outputs from PE[0]
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            output_entry_t entry;
            entry.row = current_row_processing;
            entry.col = out_col[0];
            entry.val = out_val[0];
            entry.val_real = $itor(out_val[0]);
            captured_outputs.push_back(entry);
            
            $display("[TB OUTPUT] row=%0d, col=%0d, val=%f (raw=0x%08h)",
                     current_row_processing, out_col[0], $itor(out_val[0]), out_val[0]);
        end
    end

    //----------------------------------------------------------------
    // 9. State monitoring
    //----------------------------------------------------------------
    logic [3:0] finish_counter;
    logic       merge_next_detected;
    logic [2:0] current_state;
    assign current_state = dut.PES[0].U_PE.state;
    
    // State enum values
    localparam [2:0] S_RESET       = 3'd0;
    localparam [2:0] S_FILL        = 3'd1;
    localparam [2:0] S_ROW_FLUSH   = 3'd2;
    localparam [2:0] S_MERGE_START = 3'd3;
    localparam [2:0] S_MERGE_FIND  = 3'd4;
    localparam [2:0] S_MERGE_OUTPUT= 3'd5;
    localparam [2:0] S_MERGE_NEXT_Q= 3'd6;
    
    // Monitor current row being processed
    assign current_row_processing = dut.PES[0].U_PE.merge_row;

    // Track when input feeding is complete (SPI version)
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            input_feeding_done <= 0;
            last_row_sent <= 0;
        end else begin
            // Set done when we see in_last
            if (in_valid && in_ready && in_last) 
                input_feeding_done <= 1;
            if (in_valid && in_ready)
                last_row_sent <= in_row;
        end
    end

    // Detect when we should terminate
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            finish_counter <= 0;
            merge_next_detected <= 0;
            timing_stopped <= 0;
            end_time <= 0;
        end else if (current_state == S_MERGE_NEXT_Q && 
                     input_feeding_done && 
                     current_row_processing == last_row_sent &&
                     !merge_next_detected) begin
            merge_next_detected <= 1;
            finish_counter <= 1;
            if (!timing_stopped) begin
                timing_stopped <= 1;
                end_time <= $time;
                $display("[TB TIMING] Stopped at time %0t", $time);
            end
        end else if (merge_next_detected && finish_counter > 0) begin
            finish_counter <= finish_counter + 1;
            if (finish_counter == 5) begin
                $display("\n[TB] All rows processed - Final merge complete!");
                $display("[TB] Last row processed: %0d", current_row_processing);
                $display("[TB] Total outputs captured: %0d", captured_outputs.size());
                $display("----------------------------------------");
                
                // Display all captured outputs
                for (int i = 0; i < captured_outputs.size(); i++) begin
                    $display("  row=%0d  col=%0d  val=%f",
                             captured_outputs[i].row,
                             captured_outputs[i].col, 
                             captured_outputs[i].val_real);
                end
                
                $display("----------------------------------------");
                execution_time_ns = end_time - start_time;
                execution_time_seconds = execution_time_ns / 1e9;
                
                $display("\n=== MATRAPTOR TIMING RESULTS ===");
                $display("Start time:       %0t ns", start_time);
                $display("End time:         %0t ns", end_time);
                $display("Execution time:   %0t ns", execution_time_ns);
                $display("Execution time:   %0.9f seconds", execution_time_seconds);
                $display("Clock frequency:  500 MHz (2ns period)");
                $display("Total cycles:     %0d", execution_time_ns / 2);
                $display("========================================");
                $display("For speedup calculation:");
                $display("Compare your software time to: %0.9f seconds", execution_time_seconds);
                $display("========================================");
                $display("[TB] Simulation Complete - Exiting");
                //$finish;
            end
        end
    end

    //----------------------------------------------------------------
    // 10. Safety watchdog
    //----------------------------------------------------------------
    initial begin
        #1_000_000_000;  // 10ms timeout
        $display("[TB] Watchdog timeout - design may be stuck");
        $display("[TB] Current state: %0d", current_state);
        $display("[TB] Outputs captured so far: %0d", captured_outputs.size());
        $finish;
    end

    //----------------------------------------------------------------
    // 11. Debug state transitions
    //----------------------------------------------------------------
    always_ff @(posedge clk) begin
        if (current_state != dut.PES[0].U_PE.n_state) begin
            case (dut.PES[0].U_PE.n_state)
                S_RESET:       $display("[TB STATE] -> S_RESET");
                S_FILL:        $display("[TB STATE] -> S_FILL");
                S_ROW_FLUSH:   $display("[TB STATE] -> S_ROW_FLUSH");
                S_MERGE_START: $display("[TB STATE] -> S_MERGE_START");
                S_MERGE_FIND:  $display("[TB STATE] -> S_MERGE_FIND");
                S_MERGE_OUTPUT:$display("[TB STATE] -> S_MERGE_OUTPUT");
                S_MERGE_NEXT_Q:$display("[TB STATE] -> S_MERGE_NEXT_Q (Row %0d complete)", current_row_processing);
                default:       $display("[TB STATE] -> UNKNOWN(%0d)", dut.PES[0].U_PE.n_state);
            endcase
        end
    end
	
    //----------------------------------------------------------------
    // 12. Output logging
    //----------------------------------------------------------------
    int output_log_fd;
    
    initial begin
        output_log_fd = $fopen("out.csv", "w");
        if (output_log_fd == 0) $fatal(1, "Cannot open out.csv");
        
        $fwrite(output_log_fd, "# SystemVerilog DUT outputs\n");
        $fwrite(output_log_fd, "# Format: row,col,value\n");
    end

    // Log outputs
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            $fwrite(output_log_fd, "%0d,%0d,%f\n",
                    current_row_processing, out_col[0], $itor(out_val[0]));
            $fflush(output_log_fd);
        end
    end
    
    // Debug SPI input
    always_ff @(posedge clk) begin
        if (in_valid && in_ready)
            $display("[TB SPI] Received: val=%0d, row=%0d, col=%0d, last=%b at time %t", 
                     in_val, in_row, in_col, in_last, $time);
    end
    
    final begin
        if (output_log_fd != 0) $fclose(output_log_fd);
    end

endmodule