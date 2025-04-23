# LLM-Assisted Chip Design Project

## Overview
This repository contains my implementation of Challenge #4 from the hw4aiml-am course, which focuses on experimenting with LLM-assisted chip design. The project replicates the approach described in the Johns Hopkins paper ["Designing Silicon Brains using LLM: Leveraging ChatGPT for Automated Description of a Spiking Neuron Array"](https://arxiv.org/abs/2402.10920).

## Project Structure
- `LLM_transcripts/`: Contains transcripts of interactions with LLMs
- `output/`: Output files generated during the process
- `src/`: Source code files
  - `lif.sv`: Leaky Integrate and Fire neuron implementation
  - `relu_neuron.sv`: ReLU neuron implementation
  - `relu_neural_network.sv`: ReLU neural network implementation
  - `snn_top.sv`: Spiking Neural Network top module
  - `spi_interface.sv`: SPI interface for the neural network
  - `spiking_nn_2layer.sv`: Two-layer spiking neural network implementation
- `tb/`: Testbench files
  - `lif_neuron_tb.sv`: Testbench for LIF neuron
  - `run.do`: Simulation run script
  - `snn_top_tb.sv`: Testbench for SNN top module
  - `spiking_nn_2layer_tb.sv`: Testbench for two-layer spiking neural network
- `w1_codetest.pdf`: Week 1 code test documentation

## Implementation Details
This project explores various neuron models for silicon brain design:
1. Leaky Integrate and Fire (LIF) neuron implementation
2. ReLU neuron alternative implementation
3. Compared different neuron models including ReLU and Hodgkin–Huxley

## Usage
To run the testbenches and simulate the designs:

1. Navigate to the `tb` directory
2. Execute the simulation run script:
   ```bash
   cd tb
   do run.do
   ```

