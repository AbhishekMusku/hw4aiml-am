//====================================================================
// Test‑bench for MatRaptor fill‑only sandbox (final TB v4)
// -------------------------------------------------------------------
//  * Reads triples <float>,<row>,<col> from "in.csv".
//  * Skips header lines starting with '#'.
//  * Drives DUT via ready/valid; asserts `in_last` on last line.
//  * Dumps queue contents on first `row_done` and exits.
//  * Safety watchdog: 1 ms timeout.
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
        .pe_row_done (pe_row_done)
    );

    //----------------------------------------------------------------
    // 5. CSV feeder FSM
    //----------------------------------------------------------------
    int      fd;
    string   line;
    typedef enum logic [2:0] {
    F_OPEN = 2'b00,         // Opening file state
    F_SEND0 = 2'b01,         // Sending data state
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
						end else begin
							$display("[TB] Skip malformed line: %s", line);
						end
					end
					if (!got_data) $fatal(1, "CSV contains no data lines");
					
					data_available <= 1;
					file_eof       <= $feof(fd);
					// State transition happens in combinational block
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
							end else begin
								$display("[TB] Skip malformed line: %s", line);
							end
						end
						
						data_available <= found_next;
						file_eof       <= $feof(fd);
						// State transition happens in combinational block
					end
				end
				
				F_DONE: begin : done_state
					if (out_idle()) begin
						idle_cnt <= idle_cnt + 1;
					end else begin
						idle_cnt <= 0;
					end
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
				// Move to F_SEND if we have data
					next_state = F_SEND0;
				
			end

			F_SEND0: begin
				// Move to F_SEND if we have data
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
				if (!data_available && in_valid && in_ready)
					next_state = F_DONE;
			end
			
			F_DONE: begin
				// Simulation termination logic
				if (idle_cnt >= 99 && out_idle())
					next_state = F_DONE; // Stay in DONE, but idle_cnt will increment to 100 and terminate
			end
		endcase
	end

	// Fix the out_idle function to actually check design idle state
	function logic out_idle;
		// Placeholder - replace with meaningful idle detection
		// For example, check if all queues are stable, no handshaking active, etc.
		out_idle = 1; // Currently always returns 1, which is problematic
	endfunction

	// Add this to your original debug/watchdog blocks
	always @(posedge clk) begin
		if (idle_cnt == 100) begin
			$display("[TB] Done. simulation ends");
			$finish;
		end
	end


    //----------------------------------------------------------------
    // 6. Debug prints + queue dump on first row_done
    //----------------------------------------------------------------
    always_ff @(posedge clk) begin : dbg_dump
        int q;
        int depth;
        int j;
        real val_real;
        int col_idx;
        if (pe_row_done[0]) begin
            $display("%0t ns : PE0 row_done - dumping queue contents", $time);
            for (q = 0; q < NQ; q++) begin
                // static reference since NUM_PES==1
                depth = dut.PES[0].U_PE.wr_ptr[q];
                $display("Queue %0d depth=%0d:", q, depth);
                for (j = 0; j < depth; j++) begin
                    val_real = $itor(dut.PES[0].U_PE.queue_mem[q][j].val);
                    col_idx  = dut.PES[0].U_PE.queue_mem[q][j].col;
                    $display("  [%0d] val=%f, col=%0d", j, val_real, col_idx);
                end
            end
            $finish;
        end
    end

    //----------------------------------------------------------------
    // 7. Safety watchdog (1 ms)
    //----------------------------------------------------------------
    initial begin
        #1_000_000;
        $display("[TB] Watchdog timeout");
        $finish;
    end
endmodule
