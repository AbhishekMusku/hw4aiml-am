//---------------------------------------------------------------
// Single PE MatRaptor - Phase 1 Fill + Phase 2 Merge (Sequential, No Double Buffer)
//---------------------------------------------------------------
// Implements row-wise product SpGEMM with continuous multi-row support
// Based on "MatRaptor: A Sparse-Sparse Matrix Multiplication Accelerator"
//
// Features:
// * Direct column mapping: queue[col>>8][col[7:0]] 
// * Supports columns 0-2047 (8 queues × 256 entries)
// * Automatic accumulation for repeated column indices
// * Continuous row processing with automatic boundary detection
// * Phase 1: Fill queues with accumulation
// * Phase 2: Bitmap-based merge with sorted output
// * Processes multiple rows sequentially without external control
//---------------------------------------------------------------
module p1_merge_only #(
    parameter int DATA_W  = 32,
    parameter int IDX_W   = 16,
    parameter int NQ      = 4,
    parameter int Q_DEPTH = 128
)(
    input  logic                 clk,
    input  logic                 rst_n,

    // input stream
    input  logic                 in_valid,
    output logic                 in_ready,
    input  logic  [DATA_W-1:0]   in_val,
    input  logic  [IDX_W-1:0]    in_row,
    input  logic  [IDX_W-1:0]    in_col,
    input  logic                 in_last,

    // PHASE 2 ADDITION: output stream
    output logic                 out_valid,
    input  logic                 out_ready,
    output logic [DATA_W-1:0]    out_val,
    output logic [IDX_W-1:0]     out_col,
    output logic                 out_last,

    // debug pulse
    output logic                 row_done
);
    //-----------------------------------------------------------
    // Local types / constants
    //-----------------------------------------------------------
    typedef struct packed {
        logic                valid;    // ADDED: Position has valid data
        logic [DATA_W-1:0]   val;      // Data value (accumulated)
        logic [IDX_W-1:0]    col;      // Column index (for verification)
    } entry_t;

    localparam int PTR_W = $clog2(Q_DEPTH);
    localparam int QID_W = $clog2(NQ);

    // PHASE 2 MODIFICATION: Extended state enum
    typedef enum logic [2:0] {
        S_RESET, 
        S_FILL, 
        S_ROW_FLUSH,
        S_MERGE_START,      // Initialize merge
        S_MERGE_FIND,       // Find next valid in queue
        S_MERGE_OUTPUT,     // Output found entry
        S_MERGE_NEXT_Q      // Move to next queue (unused but kept for completeness)
    } state_t;

    //-----------------------------------------------------------
    // State & storage
    //-----------------------------------------------------------
    state_t             state, n_state;
    logic [IDX_W-1:0]   cur_row, n_cur_row;
	logic [IDX_W-1:0]   merge_row, n_merge_row;  // ADD THIS LINE
    logic               first_element, n_first_element;  // Track if this is first element ever
    
    entry_t queue_mem   [NQ][Q_DEPTH];
    
    // MODIFIED: Direct addressing variables (replacing pointer management)
    logic [QID_W-1:0]   tgt_q, qsel;
    logic [PTR_W-1:0]   tgt_addr;              // Direct address in queue
    logic               addr_valid;            // Address within supported range
    logic               accumulate_mode;       // Location already has data
    
    logic               row_boundary;
    logic               queue_full_hit;        // Keep for compatibility, but won't be used

    logic               flush_row_done, n_flush_row_done;

    // PHASE 2 ADDITIONS: Bitmap structures for merge
    logic [127:0] queue_bitmap[NQ];        // 8 bitmaps, one per queue
    logic [1:0]   merge_queue, n_merge_queue;              // Current queue being processed in merge
    logic [6:0]   merge_pos, n_merge_pos;                // Position within current queue
    logic         merge_active, n_merge_active;             // Phase 2 merge is active
	// Find current position (first entry or when we need next position)
	logic [6:0] current_pos;

    // MODIFIED: Direct column-to-address mapping
    assign qsel = in_col[8:7];        // Upper 3 bits select queue (supports up to col 2047)
    assign tgt_q = qsel;
    assign tgt_addr = in_col[7:0];     // Lower 8 bits select address in queue
    assign addr_valid = (in_col < 512); // Only support columns 0-2047
    assign accumulate_mode = queue_mem[tgt_q][tgt_addr].valid && addr_valid;
	
	
	
	// Check if this is last element (same logic as before)
	logic queue_will_be_empty;
	assign queue_will_be_empty  = (queue_bitmap[merge_queue] == (128'b1 << current_pos));

    //-----------------------------------------------------------
    // Functions
    //-----------------------------------------------------------
    // 256-bit priority encoder function
    function automatic logic [6:0] priority_encode_128(input logic [127:0] bitmap);
        for (int i = 0; i < 128; i++) begin
            if (bitmap[i]) return i[6:0];
        end
        return 7'h7F; // No bit set
    endfunction

    // Check if any queue has valid data
    function automatic logic queues_have_data();
        for (int q = 0; q < NQ; q++) begin
            if (queue_bitmap[q] != '0) return 1'b1;
        end
        return 1'b0;
    endfunction

    //-----------------------------------------------------------
    // Sequential
    //-----------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= S_RESET;
            cur_row         <= '0;
			merge_row       <= '0; 
            first_element   <= 1'b1;
            flush_row_done  <= 1'b0;
            // PHASE 2 ADDITIONS
            merge_queue     <= '0;
            merge_pos       <= '0;
            merge_active    <= 1'b0;
        end else begin
            state           <= n_state;     
            cur_row         <= n_cur_row;
			merge_row       <= n_merge_row; 
            first_element   <= n_first_element;
            flush_row_done  <= n_flush_row_done;
            // PHASE 2 ADDITIONS
            merge_queue     <= n_merge_queue;
            merge_pos       <= n_merge_pos;
            merge_active    <= n_merge_active;
        end
    end
    
    // MODIFIED: Direct addressing with accumulation
    always_ff @(posedge clk) begin
        if (in_valid && addr_valid && !row_boundary && in_ready) begin
            if (accumulate_mode) begin
                // ACCUMULATE: Add to existing value
                queue_mem[tgt_q][tgt_addr].val <= queue_mem[tgt_q][tgt_addr].val + in_val;
                $display("Time: %0t - ACCUMULATE QUEUE[%0d][%0d] col=%0d: %0d + %0d = %0d", 
                         $time, tgt_q, tgt_addr, in_col,
                         queue_mem[tgt_q][tgt_addr].val, in_val,
                         queue_mem[tgt_q][tgt_addr].val + in_val);
            end else begin
                // INSERT: New entry at direct address
                queue_mem[tgt_q][tgt_addr] <= '{valid: 1'b1, val: in_val, col: in_col};
                // PHASE 2 ADDITION: Set bitmap bit
                queue_bitmap[tgt_q][tgt_addr] <= 1'b1;
                $display("Time: %0t - INSERT QUEUE[%0d][%0d] col=%0d val=%0d", 
                         $time, tgt_q, tgt_addr, in_col, in_val);
            end
        end

        if (state == S_MERGE_OUTPUT && out_valid && out_ready) begin
            queue_bitmap[merge_queue][current_pos] <= 1'b0;
            queue_mem[merge_queue][current_pos].valid <= 1'b0;
            $display("Time: %0t - MERGE OUTPUT col=%0d val=%0d, cleared bitmap[%0d][%0d]", 
                     $time, out_col, out_val, merge_queue, merge_pos);
        end
		
    end



    //-----------------------------------------------------------
    // Combinational next‑state
    //-----------------------------------------------------------
    always_comb begin
        // defaults
        n_state          = state;
        in_ready         = 1'b0;
        row_done         = 1'b0;
        n_cur_row        = cur_row;
        n_first_element  = first_element;
        n_flush_row_done = 1'b0;
        
        // PHASE 2 ADDITIONS: defaults
		n_merge_row      = merge_row;
        n_merge_queue    = merge_queue;
        n_merge_pos      = merge_pos;
        n_merge_active   = merge_active;
        out_valid        = 1'b0;
        out_val          = '0;
        out_col          = '0;
        out_last         = 1'b0;
		current_pos = priority_encode_128(queue_bitmap[merge_queue]);

        // MODIFIED: No queue full condition with direct addressing
        queue_full_hit = 1'b0;  // Never full with direct addressing
        row_boundary   = (!first_element) && in_valid && (in_row != cur_row);
        $display("time = %d row_boundary = %d	in_valid = %d	in_row = %d	cur_row = %d	addr_valid = %d", 
                 $time, row_boundary, in_valid, in_row, cur_row, addr_valid);

        unique case (state)
            //---------------------------------------------------
            S_RESET: begin
                n_state = S_FILL;
                n_first_element = 1'b1; // Reset first element flag
            end
            //---------------------------------------------------
			S_FILL: begin
				if (row_boundary) begin
					// Normal row boundary - process previous row
					$display("Inside SFILL time = %d row_boundary = %d	in_row = %d	cur_row = %d", 
							 $time, row_boundary, in_row, cur_row);
					n_state          = S_ROW_FLUSH;
					n_flush_row_done = row_boundary;
					n_merge_row = cur_row; 
					n_cur_row = in_row;
				end else if (in_valid && addr_valid) begin
					// Accept ALL valid elements first (including last)
					in_ready = 1'b1;
					n_cur_row = in_row;
					n_first_element = 1'b0;
					
					// AFTER accepting, check if it was the last element
					if (in_last) begin
						// Next cycle, trigger flush for this final row
						n_state = S_ROW_FLUSH;
						n_flush_row_done = 1'b1;
						n_merge_row = in_row;
						$display("Time: %0t - LAST ELEMENT ACCEPTED, will flush row %0d next cycle", 
								 $time, in_row);
					end
				end else if (in_valid && !addr_valid) begin
					in_ready = 1'b0;
					$display("Time: %0t - REJECTED col=%0d (out of range 0-2047)", $time, in_col);
				end else begin
					in_ready = 1'b0;
				end
			end
            //---------------------------------------------------
            S_ROW_FLUSH: begin
                in_ready = 1'b0;          // hold upstream one cycle
                row_done = flush_row_done;
                n_first_element = 1'b1;
                // PHASE 2 ADDITION: Start merge after flush
                n_state = S_MERGE_START;
                n_merge_active = 1'b1;
            end
            //---------------------------------------------------
            // PHASE 2 ADDITIONS: New merge states
            //---------------------------------------------------
            S_MERGE_START: begin
                n_merge_queue = 2'd0;
                n_state = S_MERGE_FIND;
                $display("Time: %0t - MERGE START", $time);
            end
            //---------------------------------------------------
			//---------------------------------------------------
			// OPTIMIZED MERGE STATES
			//---------------------------------------------------
			S_MERGE_FIND: begin
				if (queue_bitmap[merge_queue] != '0) begin
					// Found non-empty queue - go directly to output (no position finding here)
					n_state = S_MERGE_OUTPUT;
					$display("Time: %0t - MERGE FIND: Queue[%0d] has data", $time, merge_queue);
				end else if (merge_queue < (NQ-1)) begin
					// Current queue empty, try next queue
					n_merge_queue = merge_queue + 1;
					n_state = S_MERGE_FIND;  // Stay in find state
					$display("Time: %0t - MERGE FIND: Queue[%0d] empty, moving to queue[%0d]", 
							 $time, merge_queue, merge_queue + 1);
				end else begin
					// All queues processed - done with merge
					n_merge_active = 1'b0;
					n_state = S_MERGE_NEXT_Q;
					$display("Time: %0t - MERGE COMPLETE: All queues processed", $time);
				end
			end

			//---------------------------------------------------
			S_MERGE_OUTPUT: begin
				
				// Output the found entry
				out_valid = 1'b1;
				out_col = {merge_queue, current_pos};
				out_val = queue_mem[merge_queue][current_pos].val;
				n_merge_pos = current_pos;  // Update merge_pos for bitmap clearing
				
				if (out_ready) begin
					// After output accepted, decide next state
					if (!queue_will_be_empty) begin
						// Current queue still has more data - stay and output next position
						n_state = S_MERGE_OUTPUT;
						$display("Time: %0t - OUTPUT col=%0d val=%0d, more data in queue[%0d]", 
								 $time, out_col, out_val, merge_queue);
					end else begin
						// Current queue will be empty - find next queue
						n_state = S_MERGE_FIND;
						$display("Time: %0t - OUTPUT col=%0d val=%0d, queue[%0d] now empty", 
								 $time, out_col, out_val, merge_queue);
					end
				end
			end
            //---------------------------------------------------
			S_MERGE_NEXT_Q: begin
				// Transition back to S_FILL for next row processing
				n_state = S_FILL;
				n_first_element = 1'b1;  // Ready for first element of next row
				n_merge_active = 1'b0;   // Clear merge active flag
				$display("Time: %0t - Row merge complete, ready for next row", $time);
			end
            //---------------------------------------------------
            default: n_state = S_RESET;
        endcase
    end
endmodule


//---------------------------------------------------------------
// Top‑level core – routes a flat input stream into NUM_PES PEs
// (UPDATED to include output streams)
//---------------------------------------------------------------
module matraptor_core #(
    parameter int DATA_W   = 32,
    parameter int IDX_W    = 16,
    parameter int NQ       = 4,
    parameter int Q_DEPTH  = 128,
    parameter int NUM_PES  = 8
)(
    input  logic                 clk,
    input  logic                 rst_n,

    // flat input stream (already partial‑products)
    input  logic                 in_valid,
    output logic                 in_ready,
    input  logic [DATA_W-1:0]    in_val,
    input  logic [IDX_W-1:0]     in_row,
    input  logic [IDX_W-1:0]     in_col,
    input  logic                 in_last,

    // PHASE 2 ADDITION: output streams from PEs
    output logic [NUM_PES-1:0]   out_valid,
    input  logic [NUM_PES-1:0]   out_ready,
    output logic [DATA_W-1:0]    out_val[NUM_PES],
    output logic [IDX_W-1:0]     out_col[NUM_PES],
    output logic [NUM_PES-1:0]   out_last,

    // debug
    output logic [NUM_PES-1:0]   pe_row_done
);
    //-----------------------------------------------------------
    // Demux input by column mod NUM_PES
    //-----------------------------------------------------------
    logic [NUM_PES-1:0] pe_in_valid;
    logic [NUM_PES-1:0] pe_in_ready;

    for (genvar p = 0; p < NUM_PES; p++) begin : GEN_PES
        assign pe_in_valid[p] = in_valid && (in_col % NUM_PES == p);
    end
    assign in_ready = pe_in_ready[in_col % NUM_PES];

    //-----------------------------------------------------------
    // Instantiate PEs
    //-----------------------------------------------------------
    for (genvar p = 0; p < NUM_PES; p++) begin : PES
        p1_merge_only #(
            .DATA_W (DATA_W),
            .IDX_W  (IDX_W),
            .NQ     (NQ),
            .Q_DEPTH(Q_DEPTH)
        ) U_PE (
            .clk      (clk),
            .rst_n    (rst_n),
            .in_valid (pe_in_valid[p]),
            .in_ready (pe_in_ready[p]),
            .in_val   (in_val),
            .in_row   (in_row),
            .in_col   (in_col),
            .in_last  (in_last),
            
            // PHASE 2 ADDITION: Connect output streams
            .out_valid(out_valid[p]),
            .out_ready(out_ready[p]),
            .out_val  (out_val[p]),
            .out_col  (out_col[p]),
            .out_last (out_last[p]),
            
            .row_done (pe_row_done[p])
        );
    end
endmodule