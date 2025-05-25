//====================================================================
// Test‑bench for MatRaptor with Output Monitoring (Modified for S_MERGE_NEXT_Q)
// -------------------------------------------------------------------
//  * Reads triples <float>,<row>,<col> from "in.csv".
//  * Monitors output interface during merge phase
//  * Finishes simulation when design reaches S_MERGE_NEXT_Q state
//  * Captures and displays all output values
//====================================================================
`timescale 1ns/1ps

module tb_matraptor_core;
    //----------------------------------------------------------------
    // 1. Parameters
    //----------------------------------------------------------------
    localparam int DATA_W   = 32;
    localparam int IDX_W    = 16;
    localparam int NQ       = 8;
    localparam int Q_DEPTH  = 256;  // small for sim speed
    localparam int NUM_PES  = 1;   // debug with single PE

    //----------------------------------------------------------------
    // 2. Clock / reset
    //----------------------------------------------------------------
    logic clk = 0;
    always #2.5 clk = ~clk;  // 200 MHz

    logic rst_n = 0;
    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1;
    end

    //----------------------------------------------------------------
    // 3. DUT interface signals
    //----------------------------------------------------------------
    logic                 in_valid;
    logic                 in_ready;
    logic [DATA_W-1:0]    in_val;
    logic [IDX_W-1:0]     in_row;
    logic [IDX_W-1:0]     in_col;
    logic                 in_last;
    logic [NUM_PES-1:0]   pe_row_done;

    // ADDED: Output interface signals
    logic [NUM_PES-1:0]   out_valid;
    logic [NUM_PES-1:0]   out_ready;
    logic [DATA_W-1:0]    out_val[NUM_PES];
    logic [IDX_W-1:0]     out_col[NUM_PES];
    logic [NUM_PES-1:0]   out_last;

    //----------------------------------------------------------------
    // 4. Instantiate DUT
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
        
        // ADDED: Connect output interface
        .out_valid   (out_valid),
        .out_ready   (out_ready),
        .out_val     (out_val),
        .out_col     (out_col),
        .out_last    (out_last)
    );

    //----------------------------------------------------------------
    // 5. Output monitoring and ready signal generation
    //----------------------------------------------------------------
    
    // Always ready to accept outputs
    assign out_ready = '1;  // All PEs ready
    
    // Output capture storage
    typedef struct {
        logic [IDX_W-1:0] col;
        logic [DATA_W-1:0] val;
        real val_real;
    } output_entry_t;
    
    output_entry_t captured_outputs[$];  // Dynamic array for outputs
    
    // Monitor outputs from PE[0] (since NUM_PES = 1)
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            output_entry_t entry;
            entry.col = out_col[0];
            entry.val = out_val[0];
            entry.val_real = $itor(out_val[0]);
            captured_outputs.push_back(entry);
            
            $display("[TB OUTPUT] col=%0d, val=%f (raw=0x%08h)", 
                     out_col[0], $itor(out_val[0]), out_val[0]);
        end
    end

    //----------------------------------------------------------------
    // 6. State monitoring - detect S_MERGE_NEXT_Q
    //----------------------------------------------------------------
    logic [3:0] finish_counter;
	logic       merge_next_detected;
    // Monitor PE[0] state (since NUM_PES = 1)
    logic [2:0] current_state;
    assign current_state = dut.PES[0].U_PE.state;
    
    // State enum values (matching your design)
    localparam [2:0] S_RESET       = 3'd0;
    localparam [2:0] S_FILL        = 3'd1;
    localparam [2:0] S_ROW_FLUSH   = 3'd2;
    localparam [2:0] S_MERGE_START = 3'd3;
    localparam [2:0] S_MERGE_FIND  = 3'd4;
    localparam [2:0] S_MERGE_OUTPUT= 3'd5;
    localparam [2:0] S_MERGE_NEXT_Q= 3'd6;
    
    // Detect transition to S_MERGE_NEXT_Q
    always_ff @(posedge clk) begin
		if (!rst_n) begin
			finish_counter <= 0;
			merge_next_detected <= 0;
		end else if (current_state == S_MERGE_NEXT_Q && !merge_next_detected) begin
			merge_next_detected <= 1;        // First detection
			finish_counter <= 1;
        end else if (merge_next_detected && finish_counter > 0) begin
            finish_counter <= finish_counter + 1;  // Count cycles
            if (finish_counter == 5) begin
            
				$display("\n[TB] Reached S_MERGE_NEXT_Q - Merge Complete!");
				$display("[TB] Total outputs captured: %0d", captured_outputs.size());
				$display("\n[TB] Final Output Summary (sorted by column):");
				$display("----------------------------------------");
				
				// Display all captured outputs
				for (int i = 0; i < captured_outputs.size(); i++) begin
					$display("  col=%0d  val=%f", 
							 captured_outputs[i].col, 
							 captured_outputs[i].val_real);
				end
				
				$display("----------------------------------------");
				$display("[TB] Simulation Complete - Exiting");
				$finish;
			end
        end
    end

    //----------------------------------------------------------------
    // 7. CSV feeder FSM (same as before)
    //----------------------------------------------------------------
    int      fd;
    string   line;
    typedef enum logic [1:0] {
        F_OPEN = 2'b00,         // Opening file state
        F_SEND0 = 2'b01,        // Initial send state
        F_SEND = 2'b10,         // Sending data state
        F_DONE = 2'b11          // Completion state
    } fstate_t;
    fstate_t fstate;
    int      idle_cnt;

    // State variables and storage
    logic [DATA_W-1:0] current_val;     // Current value read from file
    logic [IDX_W-1:0]  current_row;     // Current row read from file  
    logic [IDX_W-1:0]  current_col;     // Current column read from file
    logic              file_eof;        // Flag for end of file
    logic              data_available;  // Flag that valid data is available
    fstate_t           next_state;      // Next state

    // State machine - sequential logic only
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            fstate         <= F_OPEN;
            idle_cnt       <= 0;
            current_val    <= '0;
            current_row    <= '0;
            current_col    <= '0;
            file_eof       <= 0;
            data_available <= 0;
        end else begin
            fstate <= next_state;
            
            case (fstate)
                F_OPEN: begin : open_file
                    fd = $fopen("in.csv", "r");
                    if (fd == 0) $fatal(1, "Cannot open in.csv");
                end
                
                F_SEND0: begin: SEND_VALID1_ROW
                    bit got_data;
                    got_data = 0;
                    while (!got_data && !$feof(fd)) begin
                        void'($fgets(line, fd));
                        if (line.len() == 0) continue;
                        if (line.substr(0,0) == "#") begin
                            // skip header/comment
                        end else if ($sscanf(line, "%f,%d,%d", current_val, current_row, current_col) == 3) begin
                            got_data = 1;
                            $display("[TB INPUT] Read: col=%0d, val=%f, row=%0d", 
                                     current_col, $itor(current_val), current_row);
                        end else begin
                            $display("[TB] Skip malformed line: %s", line);
                        end
                    end
                    if (!got_data) $fatal(1, "CSV contains no data lines");
                    
                    data_available <= 1;
                    file_eof       <= $feof(fd);
                end
                
                F_SEND: begin : send_line
                    if (in_valid && in_ready) begin
                        // Handshake completed, read next line
                        bit found_next;
                        found_next = 0;
                        while (!found_next && !$feof(fd)) begin
                            void'($fgets(line, fd));
                            if (line.len() == 0) continue;
                            if (line.substr(0,0) == "#") ;
                            else if ($sscanf(line, "%f,%d,%d", current_val, current_row, current_col) == 3) begin
                                found_next = 1;
                                $display("[TB INPUT] Read: col=%0d, val=%f, row=%0d", 
                                         current_col, $itor(current_val), current_row);
                            end else begin
                                $display("[TB] Skip malformed line: %s", line);
                            end
                        end
                        
                        data_available <= found_next;
                        file_eof       <= $feof(fd);
                    end
                end
                
                F_DONE: begin : done_state
                    // Input feeding is done, wait for design to finish processing
                    // The actual termination is handled by state monitoring above
                end
            endcase
        end
    end

    // Combinational logic for outputs and next state
    always_comb begin
        // Default values
        next_state = fstate;  // Stay in current state by default
        in_valid = 0;
        in_last = 0;
        in_val = current_val;
        in_row = current_row;
        in_col = current_col;
        
        case (fstate)
            F_OPEN: begin
                next_state = F_SEND0;
            end

            F_SEND0: begin
                if (data_available)
                    next_state = F_SEND;
                    
                // Drive outputs
                in_valid = data_available;
                in_last = file_eof;
            end
            
            F_SEND: begin
                // Drive outputs
                in_valid = data_available;
                in_last = file_eof;
                
                // State transition logic
                if (!data_available)
                    next_state = F_DONE;
            end
            
            F_DONE: begin
                // Stay in done state - termination handled by state monitor
            end
        endcase
    end

    //----------------------------------------------------------------
    // 8. Safety watchdog (extended for merge phase)
    //----------------------------------------------------------------
    initial begin
        #10_000_000;  // 10ms timeout (longer to allow merge completion)
        $display("[TB] Watchdog timeout - design may be stuck");
        $display("[TB] Current state: %0d", current_state);
        $display("[TB] Outputs captured so far: %0d", captured_outputs.size());
        $finish;
    end

    //----------------------------------------------------------------
    // 9. Debug state transitions
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
                S_MERGE_NEXT_Q:$display("[TB STATE] -> S_MERGE_NEXT_Q (FINAL)");
                default:       $display("[TB STATE] -> UNKNOWN(%0d)", dut.PES[0].U_PE.n_state);
            endcase
        end
    end
	
	
    // Only create output log file
    int output_log_fd;
    
    initial begin
        output_log_fd = $fopen("out.csv", "w");
        if (output_log_fd == 0) $fatal(1, "Cannot open sv_outputs.csv");
        
        $fwrite(output_log_fd, "# SystemVerilog DUT outputs\n");
        $fwrite(output_log_fd, "# Format: col,value\n");
    end
    
    // Log only outputs
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            $fwrite(output_log_fd, "%0d,%f\n", 
                    out_col[0], $itor(out_val[0]));
            $fflush(output_log_fd);
        end
    end
    
    final begin
        if (output_log_fd != 0) $fclose(output_log_fd);
    end

endmodule//====================================================================
// Test‑bench for MatRaptor with Output Monitoring (Modified for S_MERGE_NEXT_Q)
// -------------------------------------------------------------------
//  * Reads triples <float>,<row>,<col> from "in.csv".
//  * Monitors output interface during merge phase
//  * Finishes simulation when design reaches S_MERGE_NEXT_Q state
//  * Captures and displays all output values
//====================================================================
`timescale 1ns/1ps

module tb_matraptor_core;
    //----------------------------------------------------------------
    // 1. Parameters
    //----------------------------------------------------------------
    localparam int DATA_W   = 32;
    localparam int IDX_W    = 16;
    localparam int NQ       = 8;
    localparam int Q_DEPTH  = 256;  // small for sim speed
    localparam int NUM_PES  = 1;   // debug with single PE

    //----------------------------------------------------------------
    // 2. Clock / reset
    //----------------------------------------------------------------
    logic clk = 0;
    always #2.5 clk = ~clk;  // 200 MHz

    logic rst_n = 0;
    initial begin
        repeat (5) @(posedge clk);
        rst_n = 1;
    end

    //----------------------------------------------------------------
    // 3. DUT interface signals
    //----------------------------------------------------------------
    logic                 in_valid;
    logic                 in_ready;
    logic [DATA_W-1:0]    in_val;
    logic [IDX_W-1:0]     in_row;
    logic [IDX_W-1:0]     in_col;
    logic                 in_last;
    logic [NUM_PES-1:0]   pe_row_done;

    // ADDED: Output interface signals
    logic [NUM_PES-1:0]   out_valid;
    logic [NUM_PES-1:0]   out_ready;
    logic [DATA_W-1:0]    out_val[NUM_PES];
    logic [IDX_W-1:0]     out_col[NUM_PES];
    logic [NUM_PES-1:0]   out_last;

    //----------------------------------------------------------------
    // 4. Instantiate DUT
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
        
        // ADDED: Connect output interface
        .out_valid   (out_valid),
        .out_ready   (out_ready),
        .out_val     (out_val),
        .out_col     (out_col),
        .out_last    (out_last)
    );

    //----------------------------------------------------------------
    // 5. Output monitoring and ready signal generation
    //----------------------------------------------------------------
    
    // Always ready to accept outputs
    assign out_ready = '1;  // All PEs ready
    
    // Output capture storage
    typedef struct {
        logic [IDX_W-1:0] col;
        logic [DATA_W-1:0] val;
        real val_real;
    } output_entry_t;
    
    output_entry_t captured_outputs[$];  // Dynamic array for outputs
    
    // Monitor outputs from PE[0] (since NUM_PES = 1)
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            output_entry_t entry;
            entry.col = out_col[0];
            entry.val = out_val[0];
            entry.val_real = $itor(out_val[0]);
            captured_outputs.push_back(entry);
            
            $display("[TB OUTPUT] col=%0d, val=%f (raw=0x%08h)", 
                     out_col[0], $itor(out_val[0]), out_val[0]);
        end
    end

    //----------------------------------------------------------------
    // 6. State monitoring - detect S_MERGE_NEXT_Q
    //----------------------------------------------------------------
    logic [3:0] finish_counter;
	logic       merge_next_detected;
    // Monitor PE[0] state (since NUM_PES = 1)
    logic [2:0] current_state;
    assign current_state = dut.PES[0].U_PE.state;
    
    // State enum values (matching your design)
    localparam [2:0] S_RESET       = 3'd0;
    localparam [2:0] S_FILL        = 3'd1;
    localparam [2:0] S_ROW_FLUSH   = 3'd2;
    localparam [2:0] S_MERGE_START = 3'd3;
    localparam [2:0] S_MERGE_FIND  = 3'd4;
    localparam [2:0] S_MERGE_OUTPUT= 3'd5;
    localparam [2:0] S_MERGE_NEXT_Q= 3'd6;
    
    // Detect transition to S_MERGE_NEXT_Q
    always_ff @(posedge clk) begin
		if (!rst_n) begin
			finish_counter <= 0;
			merge_next_detected <= 0;
		end else if (current_state == S_MERGE_NEXT_Q && !merge_next_detected) begin
			merge_next_detected <= 1;        // First detection
			finish_counter <= 1;
        end else if (merge_next_detected && finish_counter > 0) begin
            finish_counter <= finish_counter + 1;  // Count cycles
            if (finish_counter == 5) begin
            
				$display("\n[TB] Reached S_MERGE_NEXT_Q - Merge Complete!");
				$display("[TB] Total outputs captured: %0d", captured_outputs.size());
				$display("\n[TB] Final Output Summary (sorted by column):");
				$display("----------------------------------------");
				
				// Display all captured outputs
				for (int i = 0; i < captured_outputs.size(); i++) begin
					$display("  col=%0d  val=%f", 
							 captured_outputs[i].col, 
							 captured_outputs[i].val_real);
				end
				
				$display("----------------------------------------");
				$display("[TB] Simulation Complete - Exiting");
				$finish;
			end
        end
    end

    //----------------------------------------------------------------
    // 7. CSV feeder FSM (same as before)
    //----------------------------------------------------------------
    int      fd;
    string   line;
    typedef enum logic [1:0] {
        F_OPEN = 2'b00,         // Opening file state
        F_SEND0 = 2'b01,        // Initial send state
        F_SEND = 2'b10,         // Sending data state
        F_DONE = 2'b11          // Completion state
    } fstate_t;
    fstate_t fstate;
    int      idle_cnt;

    // State variables and storage
    logic [DATA_W-1:0] current_val;     // Current value read from file
    logic [IDX_W-1:0]  current_row;     // Current row read from file  
    logic [IDX_W-1:0]  current_col;     // Current column read from file
    logic              file_eof;        // Flag for end of file
    logic              data_available;  // Flag that valid data is available
    fstate_t           next_state;      // Next state

    // State machine - sequential logic only
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            fstate         <= F_OPEN;
            idle_cnt       <= 0;
            current_val    <= '0;
            current_row    <= '0;
            current_col    <= '0;
            file_eof       <= 0;
            data_available <= 0;
        end else begin
            fstate <= next_state;
            
            case (fstate)
                F_OPEN: begin : open_file
                    fd = $fopen("in.csv", "r");
                    if (fd == 0) $fatal(1, "Cannot open in.csv");
                end
                
                F_SEND0: begin: SEND_VALID1_ROW
                    bit got_data;
                    got_data = 0;
                    while (!got_data && !$feof(fd)) begin
                        void'($fgets(line, fd));
                        if (line.len() == 0) continue;
                        if (line.substr(0,0) == "#") begin
                            // skip header/comment
                        end else if ($sscanf(line, "%f,%d,%d", current_val, current_row, current_col) == 3) begin
                            got_data = 1;
                            $display("[TB INPUT] Read: col=%0d, val=%f, row=%0d", 
                                     current_col, $itor(current_val), current_row);
                        end else begin
                            $display("[TB] Skip malformed line: %s", line);
                        end
                    end
                    if (!got_data) $fatal(1, "CSV contains no data lines");
                    
                    data_available <= 1;
                    file_eof       <= $feof(fd);
                end
                
                F_SEND: begin : send_line
                    if (in_valid && in_ready) begin
                        // Handshake completed, read next line
                        bit found_next;
                        found_next = 0;
                        while (!found_next && !$feof(fd)) begin
                            void'($fgets(line, fd));
                            if (line.len() == 0) continue;
                            if (line.substr(0,0) == "#") ;
                            else if ($sscanf(line, "%f,%d,%d", current_val, current_row, current_col) == 3) begin
                                found_next = 1;
                                $display("[TB INPUT] Read: col=%0d, val=%f, row=%0d", 
                                         current_col, $itor(current_val), current_row);
                            end else begin
                                $display("[TB] Skip malformed line: %s", line);
                            end
                        end
                        
                        data_available <= found_next;
                        file_eof       <= $feof(fd);
                    end
                end
                
                F_DONE: begin : done_state
                    // Input feeding is done, wait for design to finish processing
                    // The actual termination is handled by state monitoring above
                end
            endcase
        end
    end

    // Combinational logic for outputs and next state
    always_comb begin
        // Default values
        next_state = fstate;  // Stay in current state by default
        in_valid = 0;
        in_last = 0;
        in_val = current_val;
        in_row = current_row;
        in_col = current_col;
        
        case (fstate)
            F_OPEN: begin
                next_state = F_SEND0;
            end

            F_SEND0: begin
                if (data_available)
                    next_state = F_SEND;
                    
                // Drive outputs
                in_valid = data_available;
                in_last = file_eof;
            end
            
            F_SEND: begin
                // Drive outputs
                in_valid = data_available;
                in_last = file_eof;
                
                // State transition logic
                if (!data_available)
                    next_state = F_DONE;
            end
            
            F_DONE: begin
                // Stay in done state - termination handled by state monitor
            end
        endcase
    end

    //----------------------------------------------------------------
    // 8. Safety watchdog (extended for merge phase)
    //----------------------------------------------------------------
    initial begin
        #10_000_000;  // 10ms timeout (longer to allow merge completion)
        $display("[TB] Watchdog timeout - design may be stuck");
        $display("[TB] Current state: %0d", current_state);
        $display("[TB] Outputs captured so far: %0d", captured_outputs.size());
        $finish;
    end

    //----------------------------------------------------------------
    // 9. Debug state transitions
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
                S_MERGE_NEXT_Q:$display("[TB STATE] -> S_MERGE_NEXT_Q (FINAL)");
                default:       $display("[TB STATE] -> UNKNOWN(%0d)", dut.PES[0].U_PE.n_state);
            endcase
        end
    end
	
	
    // Only create output log file
    int output_log_fd;
    
    initial begin
        output_log_fd = $fopen("out.csv", "w");
        if (output_log_fd == 0) $fatal(1, "Cannot open sv_outputs.csv");
        
        $fwrite(output_log_fd, "# SystemVerilog DUT outputs\n");
        $fwrite(output_log_fd, "# Format: col,value\n");
    end
    
    // Log only outputs
    always_ff @(posedge clk) begin
        if (out_valid[0] && out_ready[0]) begin
            $fwrite(output_log_fd, "%0d,%f\n", 
                    out_col[0], $itor(out_val[0]));
            $fflush(output_log_fd);
        end
    end
    
    final begin
        if (output_log_fd != 0) $fclose(output_log_fd);
    end

endmodule