//====================================================================
// MatRaptor ‑ fill‑only sandbox  (v3b, May 2025)
// -------------------------------------------------------------------
// * Single queue‑set per PE.
// * No drain/merge stage – we flush queues on row change, CSV end, or
//   queue‑full back‑pressure.
// * `row_done` pulses 1 cycle for real row boundaries (not for queue
//   full).  Core simply surfaces each PE’s pulse.
//====================================================================

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
// Processing element – p1_merge_only (fill‑only)
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

    typedef enum logic [1:0] {S_RESET, S_FILL, S_ROW_FLUSH} state_t;

    //-----------------------------------------------------------
    // State & storage
    //-----------------------------------------------------------
    state_t             state, n_state;
    logic [IDX_W-1:0]   cur_row, n_cur_row;

    entry_t queue_mem   [NQ][Q_DEPTH];
    logic  [PTR_W:0]    wr_ptr     [NQ];      // extra bit for full
    logic  [PTR_W:0]    rd_ptr     [NQ];
    logic  [PTR_W:0]    n_wr_ptr   [NQ];
    logic  [PTR_W:0]    n_rd_ptr   [NQ];

    // helper
	function automatic logic is_full(input int q_idx);
		return ((wr_ptr[q_idx][PTR_W-1:0] == rd_ptr[q_idx][PTR_W-1:0]) && 
				(wr_ptr[q_idx][PTR_W] != rd_ptr[q_idx][PTR_W]));
	endfunction

    logic               flush_row_done, n_flush_row_done;

    //-----------------------------------------------------------
    // Sequential
    //-----------------------------------------------------------
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state           <= S_RESET;
            cur_row         <= '0;
            flush_row_done  <= 1'b0;
            for (int q=0; q<NQ; q++) begin
                wr_ptr[q] <= '0;
                rd_ptr[q] <= '0;
            end
        end else begin
            state           <= n_state;
            cur_row         <= n_cur_row;
            flush_row_done  <= n_flush_row_done;
            for (int q=0; q<NQ; q++) begin
                wr_ptr[q] <= n_wr_ptr[q];
                rd_ptr[q] <= n_rd_ptr[q];
            end
        end
    end

    //-----------------------------------------------------------
    // Combinational next‑state
    //-----------------------------------------------------------
        // helper decls before statements
        int   tgt_q;
        logic row_boundary;
        logic queue_full_hit;

    always_comb begin

        // defaults
        n_state          = state;
        in_ready         = 1'b0;
        row_done         = 1'b0;
        n_cur_row        = cur_row;
        n_flush_row_done = 1'b0;
        for (int q=0; q<NQ; q++) begin
            n_wr_ptr[q] = wr_ptr[q];
            n_rd_ptr[q] = rd_ptr[q];
        end

        // helpers
        tgt_q          = in_col % NQ;
        queue_full_hit = in_valid && is_full(tgt_q);
        row_boundary   = in_valid && (in_row != cur_row || in_last) || queue_full_hit;

        unique case (state)
            //---------------------------------------------------
            S_RESET: begin
                n_state = S_FILL;
            end
            //---------------------------------------------------
            S_FILL: begin
                // drive ready when no stall condition
                in_ready = in_valid && !queue_full_hit && !row_boundary;

                if (row_boundary || queue_full_hit) begin
                    n_state          = S_ROW_FLUSH;
                    n_flush_row_done = row_boundary; // pulse for real row change
                    if (row_boundary)
                        n_cur_row = in_row;          // capture new row ID
                end else if (in_valid) begin
                    // normal queue write
                    queue_mem[tgt_q][wr_ptr[tgt_q][PTR_W-1:0]] = '{val: in_val, col: in_col};
                    n_wr_ptr[tgt_q] = wr_ptr[tgt_q] + 1;
                    n_cur_row       = in_row;
                end
            end
            //---------------------------------------------------
            S_ROW_FLUSH: begin
                in_ready = 1'b0;          // hold upstream one cycle
                row_done = flush_row_done;
                // clear pointers
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
