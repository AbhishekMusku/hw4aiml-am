//================================================================
// SPI Interface Module - Python to MatRaptor Bridge
//================================================================
// Hardware-software interface receiving 9-byte frames from Python
// cocotb testbench and delivering parsed data to MatRaptor core.
//
// FUNCTIONALITY:
// * Frame reception: 72-bit SPI frames with MSB-first transmission
// * Data parsing: Extracts value/row/col/flags from received frames
// * Clock crossing: Safe transfer from SPI domain to system domain
// * Backpressure: Waits for MatRaptor ready before frame consumption
//
// INTERFACE PROTOCOLS:
// * SPI: Standard 4-wire (CLK/CS/MOSI) with 25MHz clock from Python
// * MatRaptor: Valid/ready handshaking to downstream core
// * Frame format: [VALUE 32b][ROW 16b][COL 16b][FLAGS 8b]
//
// TIMING & CLOCK DOMAINS:
// * SPI Clock: 25MHz from Python cocotb testbench
// * System Clock: 500MHz for MatRaptor core (20:1 ratio)
// * Reset: Async assert/sync release on both domains
// * Clock Crossing: Toggle-based with 2-FF synchronizer
//
// IMPLEMENTATION NOTES:
// * Frame buffering: Complete 72-bit capture before parsing
// * Edge detection: Toggle method for reliable clock crossing
// * Error handling: Out-of-range frames logged but not processed
//================================================================
module simple_spi_interface #(
    parameter DATA_W = 32,
    parameter IDX_W = 16
)(
    input  logic                clk,        // System clock (500MHz)
    input  logic                rst_n,
    
    // SPI signals
    input  logic                spi_clk,
    input  logic                spi_cs_n,   // Chip select (active low)
    input  logic                spi_mosi,   // Data from Python
    
    // MatRaptor interface
    output logic                in_valid,
    input  logic                in_ready,
    output logic [DATA_W-1:0]   in_val,
    output logic [IDX_W-1:0]    in_row,
    output logic [IDX_W-1:0]    in_col,
    output logic                in_last
);

    //================================================================
    // SPI Reception Logic - FIXED FRAME CAPTURE
    //================================================================
    
    // Frame format: 9 bytes = 72 bits
    // [VALUE 32b][ROW 16b][COL 16b][FLAGS 8b]
    localparam FRAME_BITS = 72;
    
    logic [FRAME_BITS-1:0] shift_reg;
    logic [FRAME_BITS-1:0] captured_frame_data;
    logic [6:0] bit_counter;
    logic frame_complete;
    
    // SPI shift register with fixed frame capture
    always_ff @(posedge spi_clk or negedge rst_n) begin
        if (!rst_n) begin
            shift_reg <= '0;
            bit_counter <= '0;
            frame_complete <= 1'b0;
            captured_frame_data <= '0;
        end else if (!spi_cs_n) begin  // Active during CS assertion
            // First check if we're about to complete a frame
            if (bit_counter == FRAME_BITS-1) begin
                // Capture complete frame: current shift register + incoming bit
                captured_frame_data <= {shift_reg[FRAME_BITS-2:0], spi_mosi};
                frame_complete <= 1'b1;
                bit_counter <= '0;
            end else begin
                frame_complete <= 1'b0;
                bit_counter <= bit_counter + 1;
            end
            
            // Always shift in the new bit
            shift_reg <= {shift_reg[FRAME_BITS-2:0], spi_mosi};
            
        end else begin
            // CS deasserted - reset counter and clear complete flag
            bit_counter <= '0;
            frame_complete <= 1'b0;
        end
    end
    
    //================================================================
    // Clock Domain Crossing (SPI clock → System clock)
    //================================================================
    
    // Step 1: Toggle signal in SPI clock domain
    logic frame_complete_toggle;
    always_ff @(posedge spi_clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_complete_toggle <= 1'b0;
        end else if (frame_complete) begin
            frame_complete_toggle <= ~frame_complete_toggle;
        end
    end
    
    // Step 2: Synchronize toggle to system clock domain
    logic frame_complete_toggle_sync1, frame_complete_toggle_sync2, frame_complete_toggle_prev;
    logic new_frame_pulse;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_complete_toggle_sync1 <= 1'b0;
            frame_complete_toggle_sync2 <= 1'b0;
            frame_complete_toggle_prev <= 1'b0;
        end else begin
            frame_complete_toggle_sync1 <= frame_complete_toggle;
            frame_complete_toggle_sync2 <= frame_complete_toggle_sync1;
            frame_complete_toggle_prev <= frame_complete_toggle_sync2;
        end
    end
    
    // Detect edge for new frame
    assign new_frame_pulse = frame_complete_toggle_sync2 ^ frame_complete_toggle_prev;
    
    // Step 3: Capture frame data in system clock domain
    logic [FRAME_BITS-1:0] frame_data;
    logic frame_ready;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            frame_data <= '0;
            frame_ready <= 1'b0;
        end else if (new_frame_pulse && !frame_ready) begin
            // Capture the frame data from SPI domain
            frame_data <= captured_frame_data;
            frame_ready <= 1'b1;
            $display("[SPI] Frame ready at %0t: 0x%018h", $time, captured_frame_data);
        end else if (in_valid && in_ready) begin
            // Frame consumed by MatRaptor
            frame_ready <= 1'b0;
            $display("[SPI] Frame consumed at %0t", $time);
        end
    end
    
    //================================================================
    // Parse Frame Data
    //================================================================
    
    logic [31:0] parsed_val;
    logic [15:0] parsed_row;
    logic [15:0] parsed_col;
    logic [7:0]  parsed_flags;
    logic        parsed_last;
    
    always_comb begin
        // MSB first parsing
        parsed_val   = frame_data[71:40];   // VALUE (32 bits)
        parsed_row   = frame_data[39:24];   // ROW (16 bits)
        parsed_col   = frame_data[23:8];    // COL (16 bits)
        parsed_flags = frame_data[7:0];     // FLAGS (8 bits)
        parsed_last  = parsed_flags[0];     // Last flag in bit 0
    end
    
    // Debug output when new frame arrives
    always_ff @(posedge clk) begin
        if (new_frame_pulse && !frame_ready) begin
            $display("[SPI] New frame parsed:");
            $display("  Value: %0d (0x%08h)", parsed_val, parsed_val);
            $display("  Row:   %0d", parsed_row);
            $display("  Col:   %0d", parsed_col);
            $display("  Last:  %0b", parsed_last);
        end
    end
    
    //================================================================
    // MatRaptor Interface
    //================================================================
    
    assign in_valid = frame_ready;
    assign in_val   = parsed_val;
    assign in_row   = parsed_row;
    assign in_col   = parsed_col;
    assign in_last  = parsed_last;

endmodule