module snn_top (
    // System signals
    input  logic        clk,         // System Clock
    input  logic        rst_n,       // Active low reset
    
    // SPI Interface
    input  logic        spi_clk,     // SPI Clock
    input  logic        spi_cs_n,    // SPI Chip Select (Active Low)
    input  logic        spi_mosi,    // SPI Master Out Slave In
    output logic        spi_miso,    // SPI Master In Slave Out (tied to 0)
    
    // Neural Network Interface
    input  logic [3:0]  input_spikes, // Input spikes
    output logic [2:0]  output_spikes // Output spikes
);

    // Internal connections between SPI and neural network
    logic [7:0] addr;
    logic [7:0] data;
    logic       write_en;
    
    // SPI Interface instance
    spi_interface spi_if (
        .clk(clk),
        .rst_n(rst_n),
        .spi_clk(spi_clk),
        .spi_cs_n(spi_cs_n),
        .spi_mosi(spi_mosi),
        .spi_miso(spi_miso),
        .addr(addr),
        .data_out(data),
        .write_en(write_en)
    );
    
    // Spiking Neural Network instance
    spiking_nn_2layer #(
        .N_INPUT(4),
        .N_OUTPUT(3),
        .WIDTH(8)
    ) neural_net (
        .clk(clk),
        .rst_n(rst_n),
        .addr(addr),
        .data(data),
        .write_en(write_en),
        .input_spikes(input_spikes),
        .output_spikes(output_spikes)
    );

endmodule