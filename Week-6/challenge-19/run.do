vlib work 
vdel -all
vlib work
vlog bln.sv +acc
vlog tb.sv +acc
vsim work.tb
add wave -r *
run -all
