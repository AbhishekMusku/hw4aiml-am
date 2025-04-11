vlib work 
vdel -all
vlib work
vlog lif.sv +acc
vlog spiking_nn_2layer.sv +acc
vlog spi_interface.sv +acc
vlog snn_top.sv +acc
vlog snn_top_tb.sv +acc
vsim work.snn_top_tb
add wave -r *
run -all
