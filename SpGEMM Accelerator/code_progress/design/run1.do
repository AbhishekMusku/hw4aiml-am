vlib work 
vdel -all
vlib work
vlog -sv Matraptor_Full_Final2.sv +acc
vlog -sv tb_matraptor_core.sv +acc
vsim work.tb_matraptor_core
add wave -r *
add wave /tb_matraptor_core/dut/PES[0]/U_PE/wr_ptr
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/wr_ptr[7]
add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_full_hit
add wave /tb_matraptor_core/dut/PES[0]/U_PE/PTR_W
add wave /tb_matraptor_core/dut/PES[0]/U_PE/tgt_q
add wave /tb_matraptor_core/dut/PES[0]/U_PE/vector_boundary
add wave /tb_matraptor_core/dut/PES[0]/U_PE/prev_col
add wave /tb_matraptor_core/dut/PES[0]/U_PE/current_queue
run -all
