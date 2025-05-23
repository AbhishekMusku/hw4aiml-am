//CLAUDE 5 Direct Column Mapping with Accumulation - WORKING DESIGN MODIFIED
//---------------------------------------------------------------
// Processing element – p1_merge_only (modified for direct column addressing + accumulation)
// * Maps column directly to memory location: queue[col>>8][col[7:0]]
// * Supports columns 0-2047 (8 queues × 256 entries)
// * Automatic accumulation when same column appears multiple times
//---------------------------------------------------------------
module p1_merge_only #(
    parameter int DATA_W  = 32,
    parameter int IDX_W   = 16,
    parameter int NQ      = 8,
    parameter int Q_DEPTH = 256
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

    typedef enum logic [1:0] {S_RESET, S_FILL, S_ROW_FLUSH} state_t;

    //-----------------------------------------------------------
    // State & storage
    //-----------------------------------------------------------
    state_t             state, n_state;
    logic [IDX_W-1:0]   cur_row, n_cur_row;
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

    // MODIFIED: Direct column-to-address mapping
	assign qsel = in_col[10:8];        // Upper 3 bits select queue (supports up to col 2047)
	assign tgt_q = qsel;
    assign tgt_addr = in_col[7:0];     // Lower 8 bits select address in queue
    assign addr_valid = (in_col < 2048); // Only support columns 0-2047
    assign accumulate_mode = queue_mem[tgt_q][tgt_addr].valid && addr_valid;

    //-----------------------------------------------------------
    // Sequential
    //-----------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= S_RESET;
			cur_row         <= '0;
            first_element   <= 1'b1;
            flush_row_done  <= 1'b0;
            // ADDED: Clear all valid bits
            for (int q=0; q<NQ; q++) begin
                for (int addr=0; addr<Q_DEPTH; addr++) begin
                    queue_mem[q][addr].valid <= 1'b0;
                end
            end
        end else begin
            state           <= n_state;     
			cur_row         <= n_cur_row;
            first_element   <= n_first_element;
            flush_row_done  <= n_flush_row_done;
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
                $display("Time: %0t - INSERT QUEUE[%0d][%0d] col=%0d val=%0d", 
                         $time, tgt_q, tgt_addr, in_col, in_val);
            end
		end
        
        // ADDED: Clear valid bits when starting new row
        if (state == S_ROW_FLUSH && flush_row_done) begin
            for (int q=0; q<NQ; q++) begin
                for (int addr=0; addr<Q_DEPTH; addr++) begin
                    queue_mem[q][addr].valid <= 1'b0;
                end
            end
            $display("Time: %0t - CLEARED all queue valid bits for new row", $time);
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
					$display("Inside SFILL time = %d row_boundary = %d	in_row = %d	cur_row = %d", 
                             $time, row_boundary, in_row, cur_row);
                    n_state          = S_ROW_FLUSH;
                    n_flush_row_done = row_boundary; // pulse for row change
                    n_cur_row = in_row;      // capture new row ID
                end else if (in_valid && addr_valid) begin
                    // MODIFIED: Direct addressing - always ready if address valid
                    in_ready = 1'b1;
                    n_cur_row       = in_row;
                    n_first_element = 1'b0;
                end else if (in_valid && !addr_valid) begin
                    // Column out of range - reject
                    in_ready = 1'b0;
                    $display("Time: %0t - REJECTED col=%0d (out of range 0-2047)", $time, in_col);
                end else begin
                    // No valid input
                    in_ready = 1'b0;
                end
            end
            //---------------------------------------------------
            S_ROW_FLUSH: begin
                in_ready = 1'b0;          // hold upstream one cycle
                row_done = flush_row_done;
                n_first_element = 1'b1;
                n_state = S_ROW_FLUSH;
            end
            //---------------------------------------------------
        endcase
    end
endmodule


//---------------------------------------------------------------
// Top‑level core – routes a flat input stream into NUM_PES PEs
// (UNCHANGED from original)
//---------------------------------------------------------------
module matraptor_core #(
    parameter int DATA_W   = 32,
    parameter int IDX_W    = 16,
    parameter int NQ       = 8,
    parameter int Q_DEPTH  = 256,
    parameter int NUM_PES  = 1
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
            .row_done (pe_row_done[p])
        );
    end
endmodule
