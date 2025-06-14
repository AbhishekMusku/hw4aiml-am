# Load configuration and check libraries
dc_shell> set top_design matraptor_core
dc_shell> source ../scripts/design_config.tcl
dc_shell> source ../scripts/dc-get-timlibs.tcl

# VERIFY LIBRARIES LOADED CORRECTLY
dc_shell> echo $target_library
dc_shell> echo $link_library

# Continue with synthesis
dc_shell> analyze $rtl_list -autoread -define SYNTHESIS
dc_shell> elaborate ${top_design}
dc_shell> change_names -rules verilog -hierarchy
dc_shell> source ../../constraints/${top_design}.sdc
dc_shell> set_max_transition 0.5 [current_design]
dc_shell> uniquify
dc_shell> compile_ultra -no_autoungroup

# Generate ALL reports
dc_shell> set stage dc
dc_shell> report_qor > ../reports/${top_design}.$stage.qor.rpt
dc_shell> report_timing -delay max -max_paths 10 > ../reports/${top_design}.$stage.timing.rpt
dc_shell> report_power -analysis_effort medium > ../reports/${top_design}.$stage.power.rpt
dc_shell> report_area -hierarchy > ../reports/${top_design}.$stage.area.rpt
dc_shell> report_constraint -all_viol > ../reports/${top_design}.$stage.constraints.rpt
dc_shell> check_design > ../reports/${top_design}.$stage.check_design.rpt
check_mv_design  > ../reports/${top_design}.$stage.mvrc.rpt
check_timing  > ../reports/${top_design}.$stage.check_timing.rpt

# Save netlists
dc_shell> write -hier -format verilog -output ../outputs/${top_design}.$stage.vg
dc_shell> write -hier -format ddc -output ../outputs/${top_design}.$stage.ddc
write -hier -format verilog -pg -output ../outputs/${top_design}.$stage.pg.vg
save_upf ../outputs/${top_design}.$stage.upf

# Exit
dc_shell> exit