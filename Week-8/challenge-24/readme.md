# Matrix Multiplication on BrainScaleS-2 (Challenge #24)

## Overview
This repo documents my work for Challenge #24 (ECE 410/510, Week 8), where I ran matrix-vector multiplication using the EBRAINS BrainScaleS-2 neuromorphic hardware.

## Objective
Run a basic MAC (Multiply-Accumulate) simulation using spike-based input and neuron membrane voltage integration on BrainScaleS-2, as described in the official demo.

## Code Structure
tp_00-introduction.ipynb: Main notebook with the example configuration, results, and spike-response plots.

## What I Tried
Followed the official tutorial to implement the integrator neuron example.

**Ran a few additional scenarios beyond the base example:**

Equal spike counts with opposite weights (cancellation check)

Gradual staircase buildup using uniform spike timing


## Usage
Launch and run the notebook using the EBRAINS Jupyter Lab interface with the correct kernel (EBRAINS-25.02 or similar).

