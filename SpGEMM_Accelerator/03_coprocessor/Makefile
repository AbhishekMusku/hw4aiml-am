TOPLEVEL = tb_matraptor_core
MODULE = test_spi
VERILOG_SOURCES = tb_matraptor_core.sv Matraptor.sv simple_spi_interface.sv

TOPLEVEL_LANG = verilog
SIM = questa
SIM_ARGS += -l sim.log  # Add this line to log simulation output

COMPILE_ARGS += -sv +define+COCOTB_SIM=1

include $(shell cocotb-config --makefiles)/Makefile.sim