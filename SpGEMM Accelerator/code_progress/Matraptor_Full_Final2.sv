//---------------------------------------------------------------
// Parameter helpers
//---------------------------------------------------------------
package matraptor_pkg;
    function automatic int clog2(int value);
        int v = value - 1;
        int c = 0;
        while (v > 0) begin
            v = v >> 1;
            c++;
        end
        return c;
    endfunction
endpackage
//---------------------------------------------------------------
// Processing element – p1_merge_only (modified for sequential vector filling)
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
        logic [DATA_W-1:0] val;
        logic [IDX_W-1:0]  col;
    } entry_t;

    localparam int PTR_W = matraptor_pkg::clog2(Q_DEPTH);
    localparam int QID_W = matraptor_pkg::clog2(NQ);

    typedef enum logic [1:0] {S_RESET, S_FILL, S_ROW_FLUSH} state_t;

    //-----------------------------------------------------------
    // State & storage
    //-----------------------------------------------------------
    state_t             state, n_state;
    logic [IDX_W-1:0]   cur_row, n_cur_row;
    
    // NEW: Vector boundary detection and queue tracking
    logic [IDX_W-1:0]   prev_col, n_prev_col;
    logic [QID_W-1:0]   current_queue, n_current_queue;
    logic               first_element, n_first_element;  // Track if this is first element ever
    logic               vector_boundary;

    entry_t queue_mem   [NQ][Q_DEPTH];
    logic  [PTR_W:0]    wr_ptr     [NQ];      // extra bit for full
    logic  [PTR_W:0]    rd_ptr     [NQ];
    logic  [PTR_W:0]    n_wr_ptr   [NQ];
    logic  [PTR_W:0]    n_rd_ptr   [NQ];

        int   tgt_q;
        logic row_boundary;
        logic queue_full_hit;
        logic final_queue_reached;

    // helper functions
    function automatic logic is_full(input int q_idx);
        return ((wr_ptr[q_idx][PTR_W-1:0] == rd_ptr[q_idx][PTR_W-1:0]) && 
                (wr_ptr[q_idx][PTR_W] != rd_ptr[q_idx][PTR_W]));
    endfunction

    logic               flush_row_done, n_flush_row_done;


    //-----------------------------------------------------------
    // NEW: Vector boundary detection logic
    //-----------------------------------------------------------
    always_comb begin
        vector_boundary = 1'b0;
        if (in_valid && !first_element) begin
            // Vector boundary: current col < previous col
            vector_boundary = (in_col < prev_col);
        end
    end

    //-----------------------------------------------------------
    // Sequential
    //-----------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= S_RESET;
            cur_row         <= '0;
            prev_col        <= '0;
            current_queue   <= '0;
            first_element   <= 1'b1;
            flush_row_done  <= 1'b0;
            for (int q=0; q<NQ; q++) begin
                wr_ptr[q] <= '0;
                rd_ptr[q] <= '0;
            end
        end else begin
            state           <= n_state;
            cur_row         <= n_cur_row;
            prev_col        <= n_prev_col;
            current_queue   <= n_current_queue;
            first_element   <= n_first_element;
            flush_row_done  <= n_flush_row_done;
            for (int q=0; q<NQ; q++) begin
				if(!final_queue_reached) begin
                wr_ptr[q] <= n_wr_ptr[q];
				end
                rd_ptr[q] <= n_rd_ptr[q];
            end
        end
    end
	
	
	
	// In always_ff: Actually write to memory
	always_ff @(posedge clk) begin
		if (in_valid && vector_boundary || in_valid) begin
			queue_mem[tgt_q][wr_ptr[tgt_q][PTR_W-1:0]] = '{val: in_val, col: in_col};
			$display("Time : %d		QUEUE[%d][%d] = %d", $time, tgt_q, wr_ptr[tgt_q][PTR_W-1:0], queue_mem[tgt_q][wr_ptr[tgt_q][PTR_W-1:0]].col, queue_mem[tgt_q][wr_ptr[tgt_q][PTR_W-1:0]].val);
		end
	end

    //-----------------------------------------------------------
    // Combinational next‑state
    //-----------------------------------------------------------
        // MODIFIED: Target queue is now the current_queue, not col % NQ
    always_comb begin
        // defaults
        n_state          = state;
        in_ready         = 1'b0;
        row_done         = 1'b0;
        n_cur_row        = cur_row;
        n_prev_col       = prev_col;
        n_current_queue  = current_queue;
        n_first_element  = first_element;
        n_flush_row_done = 1'b0;
		tgt_q = n_current_queue;
        for (int q=0; q<NQ; q++) begin
            n_wr_ptr[q] = wr_ptr[q];
            n_rd_ptr[q] = rd_ptr[q];
        end

        // Keep existing logic for row boundary and queue full
        queue_full_hit = in_valid && is_full(tgt_q);
        row_boundary   = in_valid && (in_row != cur_row || in_last) || queue_full_hit;
        // NEW: Stop if reached final queue (helper queue at index NQ-1)
		final_queue_reached = (n_current_queue >= (NQ-1));

        unique case (state)
            //---------------------------------------------------
            S_RESET: begin
                n_state = S_FILL;
                n_current_queue = 0;    // Start with queue 0
                n_first_element = 1'b1; // Reset first element flag
            end
            //---------------------------------------------------
            S_FILL: begin
                // MODIFIED: Don't accept input if final queue reached
                if (final_queue_reached) begin
                    // Stop processing - reached helper queue
                    in_ready = 1'b0;
                    n_state = S_ROW_FLUSH;
                    n_flush_row_done = 1'b1;  // Trigger flush
                end else if (row_boundary || queue_full_hit) begin
                    // Keep existing row boundary and queue full logic
                    n_state          = S_ROW_FLUSH;
                    n_flush_row_done = row_boundary; // pulse for real row change
                    if (row_boundary)
                        n_cur_row = in_row;          // capture new row ID
                end else if (in_valid && vector_boundary) begin
                    // NEW: Vector boundary detected - advance to next queue
                    n_current_queue = current_queue + 1;
					final_queue_reached = (n_current_queue >= (NQ-1));
					tgt_q = n_current_queue;
                    n_prev_col = in_col;
                    n_first_element = 1'b0;
					in_ready = 1'b1;
                    n_wr_ptr[tgt_q] = wr_ptr[tgt_q] + 1;
                    n_cur_row       = in_row;
                    n_prev_col      = in_col;      // NEW: Track previous column
                    n_first_element = 1'b0;        // NEW: No longer first element
                end else if (in_valid) begin
                    // MODIFIED: Normal queue write to current_queue instead of col % NQ
                    in_ready = 1'b1;
                    n_wr_ptr[tgt_q] = wr_ptr[tgt_q] + 1;
                    n_cur_row       = in_row;
                    n_prev_col      = in_col;      // NEW: Track previous column
                    n_first_element = 1'b0;        // NEW: No longer first element
                end else begin
                    // No valid input
                    in_ready = 1'b0;
                end
            end
            //---------------------------------------------------
            S_ROW_FLUSH: begin
                in_ready = 1'b0;          // hold upstream one cycle
                row_done = flush_row_done;
                // MODIFIED: Reset current_queue and first_element on flush
                n_current_queue = 0;
                n_first_element = 1'b1;
                n_prev_col = '0;
                // clear pointers (kept commented as in original)
                for (int q=0; q<NQ; q++) begin
                    //n_wr_ptr[q] = '0;
                    //n_rd_ptr[q] = '0;
                end
                n_state = S_FILL;
            end
            //---------------------------------------------------
        endcase
    end
endmodule


//---------------------------------------------------------------
// Top‑level core – routes a flat input stream into NUM_PES PEs
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