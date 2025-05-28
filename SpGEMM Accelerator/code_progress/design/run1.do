vlib work 
vdel -all
vlib work
vlog -sv claude_HASH_6.sv +acc
vlog -sv tb_matraptor_core_CLAUDE_6.sv +acc
vsim work.tb_matraptor_core
do wave.do
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_bitmap;
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/merge_queue;
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/n_merge_queue;
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/current_pos;
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/n_merge_pos;
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/merge_pos;
#add wave /tb_matraptor_core/out_valid;
#add wave /tb_matraptor_core/out_ready;
#add wave /tb_matraptor_core/out_val;
#add wave /tb_matraptor_core/out_col;     
#add wave /tb_matraptor_core/file_eof;        
add wave /tb_matraptor_core/data_available;  
#add wave /tb_matraptor_core/next_state;      
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/wr_ptr
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/wr_ptr[7]
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_full_hit
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/PTR_W
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/tgt_q
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/vector_boundary
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/prev_col
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/current_queue
add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_mem
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_mem.val
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_mem[1].col
#add wave /tb_matraptor_core/dut/PES[0]/U_PE/queue_mem[1].val
run -all
