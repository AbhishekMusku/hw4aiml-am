set lib_dir /pkgs/synopsys/2020/32_28nm/SAED32_EDK/lib
set hack_lef_dir /u/bcruik2/hacked_lefs

# MatRaptor design configuration
set top_design matraptor_core
set add_ios 0
set pad_design 0
set design_size { 580 580 }
set design_io_border 310
set dc_floorplanning 0
set enable_dft 0
set innovus_enable_manual_macro_placement 0

set rtl_list [list ../rtl/MATRAPTOR_CORE_128.sv]
set slow_corner "ss0p95v125c_2p25v ss0p95v125c"
set fast_corner "ff0p95vn40c ff1p16vn40c_2p75v ff1p16vn40c"
set synth_corners $slow_corner
set synth_corners_target "ss0p95v125c"
set synth_corners_slow $slow_corner
set synth_corners_fast $fast_corner
set slow_metal Cmax_125
set fast_metal Cmax_125

set lib_types "$lib_dir/stdcell_rvt/db_nldm $lib_dir/stdcell_hvt/db_nldm $lib_dir/io_std/db_nldm $lib_dir/sram/db_nldm $lib_dir/pll/db_nldm"
set ndm_types "$lib_dir/stdcell_rvt/ndm $lib_dir/stdcell_hvt/ndm $lib_dir/sram/ndm $lib_dir/io_std/ndm $lib_dir/pll/ndm"
set lib_types_target "$lib_dir/stdcell_rvt/db_nldm"

set sub_lib_type "saed32?vt_ saed32sram_ saed32io_wb_ saed32pll_"
set sub_lib_type_target "saed32rvt_"
set tech_lef ${hack_lef_dir}/tech.lef

set lef_types [list $hack_lef_dir $lib_dir/sram/lef/ $lib_dir/io_std/lef $lib_dir/pll/lef]
set sub_lef_type "saed32nm_?vt_*.lef saed32sram.lef saed32_io_wb_all.lef saed32_PLL.lef"
set mwlib_types [list $lib_dir/stdcell_hvt/milkyway $lib_dir/stdcell_rvt/milkyway $lib_dir/stdcell_lvt/milkyway $lib_dir/io_std/milkyway $lib_dir/sram/milkyway $lib_dir/pll/milkyway]
set sub_mwlib_type "saed32nm_?vt_* SRAM32NM saed32io_wb_* SAED32_PLL_FR*"

set topdir [ lindex [ regexp -inline "(.*)\(syn\|pt\|apr\)" [pwd] ] 1 ]
set FCL 0
set split_constraints 0
