# CUDA Fibonacci Sequence (Challenge #14)

## Overview

This repository contains the implementation for **Challenge #14** from the *hw4aiml-am* course. The challenge involved implementing the Fibonacci sequence calculation using CUDA, benchmarking its performance for various input sizes (N up to $2^{20}$), and comparing it against a sequential CPU implementation. Different approaches were explored, including handling large number calculations and analyzing performance trade-offs.

---

## Project Structure

* `fib_cpu_gmp.cpp`: C++ source code for the sequential CPU Fibonacci calculation using the GMP library for large number support.
* `fib_cuda_matrix.cu`: CUDA source code for the Fibonacci calculation using the matrix exponentiation method.
* `fib_cuda_seq.cu`: CUDA source code for the Fibonacci calculation using a single-threaded sequential approach with modulo arithmetic for benchmarking purposes.
* `challenge14.ipynb`: Jupyter Notebook containing code generation, compilation commands, benchmarking execution, data analysis, and plot generation.
* `README.md`: This documentation file.

---

## Documentation

All implementation details, benchmarking results, performance graphs, observations, and analysis are documented primarily within the Jupyter Notebook (`challenge14.ipynb`). 
Key aspects covered include:

* Implementation of a sequential CPU Fibonacci algorithm using GMP to handle large numbers.
* Acknowledgment of AI (Gemini) assistance in generating the GMP-based CPU code.
* Implementation of two CUDA approaches:
    * Matrix exponentiation method (focusing on algorithmic efficiency, acknowledging overflow limits with standard types).
    * Single-threaded sequential method with modulo (for analyzing basic kernel execution performance without large number complexity).
* Benchmarking using `cudaEvent_t` for detailed timing breakdowns (Allocation, H2D, Kernel, D2H, Total).
* Performance comparison plots (log-log scale) visualizing runtime vs. problem size N for all three approaches.
* Analysis of results, including performance scaling, crossover points between CPU and GPU implementations, discussion of overflow issues, and insights into architectural/library overheads.
* Final conclusions on the effectiveness of different approaches for this problem on CPU vs. GPU.

---

## Usage

All necessary steps to compile the C++/CUDA code, run the benchmarks, perform the analysis are contained within the Jupyter Notebook:

```bash
jupyter notebook challenge14.ipynb