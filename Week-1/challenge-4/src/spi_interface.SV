module spi_interface #(
    parameter int ADDR_WIDTH = 8,
    parameter int DATA_WIDTH = 8
)(
    // System signals
    input  logic                    clk,        // System clock
    input  logic                    rst_n,      // Active low reset
    
    // SPI interface
    input  logic                    spi_clk,    // SPI clock from master
    input  logic                    spi_cs_n,   // Chip select (active low)
    input  logic                    spi_mosi,   // Master Out Slave In
    output logic                    spi_miso,   // Master In Slave Out (tied to 0)
    
    // Register interface
    output logic [ADDR_WIDTH-1:0]   addr,       // Register address
    output logic [DATA_WIDTH-1:0]   data_out,   // Data to write to registers
    output logic                    write_en    // Write enable signal
);

    // SPI state machine states
    localparam IDLE     = 2'b00;
    localparam RECEIVE  = 2'b01;
    localparam PROCESS  = 2'b10;
    
    // Internal registers
    logic [1:0]                     state, next_state;
    logic [ADDR_WIDTH+DATA_WIDTH-1:0] shift_reg;
    logic [4:0]                     bit_counter;  // Counts bits received (max 16 bits for 8+8)
    logic                           spi_clk_prev; // For edge detection
    logic                           spi_cs_n_prev; // For CS edge detection
    
    // MISO is tied to 0 since we're not sending data back
    assign spi_miso = 1'b0;
    
    // Detect edges of SPI clock and chip select
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            spi_clk_prev <= 1'b0;
            spi_cs_n_prev <= 1'b1;
        end else begin
            spi_clk_prev <= spi_clk;
            spi_cs_n_prev <= spi_cs_n;
        end
    end
    
    // Edge detection
    wire spi_clk_posedge = ~spi_clk_prev & spi_clk;
    wire spi_cs_n_posedge = ~spi_cs_n_prev & spi_cs_n;
    wire spi_cs_n_negedge = spi_cs_n_prev & ~spi_cs_n;
    
    // State machine - sequential part
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            bit_counter <= '0;
            shift_reg <= '0;
            write_en <= 1'b0;
            addr <= '0;
            data_out <= '0;
        end else begin
            state <= next_state;
            
            // Default write_en to 0
            write_en <= 1'b0;
            
            // Handle SPI transactions
            case (state)
                IDLE: begin
                    // Start receiving on CS falling edge
                    if (spi_cs_n_negedge) begin
                        bit_counter <= ADDR_WIDTH + DATA_WIDTH - 1;
                    end
                end
                
                RECEIVE: begin
                    // Shift in data on SPI clock rising edge
                    if (spi_clk_posedge && !spi_cs_n) begin
                        shift_reg <= {shift_reg[ADDR_WIDTH+DATA_WIDTH-2:0], spi_mosi};
                        if (bit_counter > 0)
                            bit_counter <= bit_counter - 1'b1;
                    end
                end
                
                PROCESS: begin
                    // Trigger write enable pulse for one clock cycle
                    write_en <= 1'b1;
                    
                    // Extract address and data from shift register
                    addr <= shift_reg[DATA_WIDTH +: ADDR_WIDTH];
                    data_out <= shift_reg[DATA_WIDTH-1:0];
                end
                
                default: begin
                    write_en <= 1'b0;
                end
            endcase
        end
    end
    
    // State machine - combinational part
    always_comb begin
        // Default: stay in current state
        next_state = state;
        
        case (state)
            IDLE: begin
                if (spi_cs_n_negedge)
                    next_state = RECEIVE;
            end
            
            RECEIVE: begin
                // If we've received all bits or CS went high
                if ((bit_counter == 0 && spi_clk_posedge) || spi_cs_n_posedge)
                    next_state = PROCESS;
            end
            
            PROCESS: begin
                // Go back to idle after processing
                next_state = IDLE;
            end
            
            default: next_state = IDLE;
        endcase
    end

endmodule