vlib work 
vdel -all
vlib work
vlog -sv Matraptor_Full_Final1.sv 
vlog -sv tb_matraptor_core.sv
vsim work.tb_matraptor_core
#add wave -r *
run -all
