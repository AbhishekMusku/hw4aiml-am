set top_design matraptor_core 
source ../scripts/design_config.tcl
source ../scripts/dc-get-timlibs.tcl


# Analyzing the files for the design
analyze $rtl_list -autoread -define SYNTHESIS

# Elaborate the FIFO design
elaborate ${top_design} 



change_names -rules verilog -hierarchy

# Load the timing and design constraints
source ../../constraints/${top_design}.sdc

# any additional non-design specific constraints
set_max_transition 0.5 [current_design ]

# Duplicate any non-unique modules so details can be different inside for synthesis

uniquify

#compile with ultra features and with scan FFs
compile_ultra -no_autoungroup

# output reports
set stage dc
set stage dc
report_qor > ../reports/${top_design}.$stage.qor.rpt
report_timing -delay max -max_paths 10 > ../reports/${top_design}.$stage.timing.rpt
report_power -analysis_effort medium > ../reports/${top_design}.$stage.power.rpt
report_area -hierarchy > ../reports/${top_design}.$stage.area.rpt
report_constraint -all_viol > ../reports/${top_design}.$stage.constraints.rpt
check_design > ../reports/${top_design}.$stage.check_design.rpt
check_mv_design  > ../reports/${top_design}.$stage.mvrc.rpt
check_timing  > ../reports/${top_design}.$stage.check_timing.rpt


# Save netlists
write -hier -format verilog -output ../outputs/${top_design}.$stage.vg
write -hier -format ddc -output ../outputs/${top_design}.$stage.ddc
write -hier -format verilog -pg -output ../outputs/${top_design}.$stage.pg.vg
save_upf ../outputs/${top_design}.$stage.upf
