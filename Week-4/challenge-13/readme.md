# GPU SAXPY Benchmarking (Challenge #13)

## Overview

This repository contains my implementation of **Challenge #13** from the *hw4aiml-am* course. The challenge benchmarks different SAXPY problem sizes on the GPU and visualizes how performance scales as input size increases.

---

## Project Structure

- `challenge13.ipynb` : Jupyter notebook with the complete implementation, benchmarking, and visual analysis

---

## Documentation

All implementation details, graphs, observations, and analysis are documented in the notebook (`challenge13.ipynb`). It includes:

- CUDA kernel execution benchmarking
- Time breakdown using `cudaEvent_t`
- Performance plots and throughput analysis
- Key observations on memory transfer vs compute
- Final conclusions and insights

---

## Usage

To run the notebook:

```bash
jupyter notebook challenge13.ipynb
