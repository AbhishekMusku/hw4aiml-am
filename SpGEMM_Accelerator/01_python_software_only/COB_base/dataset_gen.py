"""
Synthetic Dataset Generator for Collaborative Filtering Testing

Generates sparse user-item matrices with configurable density and saves complete 
CSV/NPY files (including zeros) for benchmarking MatRaptor SpGEMM acceleration.
"""

import numpy as np
from scipy import sparse
import pandas as pd
import time

def generate_with_sparse_random(M, N, density, val_low, val_high, dtype, seed):
    """
    Generate a sparse matrix using scipy.sparse.random
    
    Parameters:
    - M, N: Matrix dimensions (M rows, N columns)
    - density: Fraction of non-zero elements
    - val_low, val_high: Range for random values
    - dtype: Data type for matrix elements
    - seed: Random seed for reproducibility
    
    Returns:
    - Sparse CSR matrix
    """
    np.random.seed(seed)
    
    # Generate sparse random matrix with values in [0,1]
    matrix = sparse.random(M, N, density=density, format='csr', 
                          random_state=seed, dtype=dtype)
    
    # Scale values to desired range [val_low, val_high]
    matrix.data = matrix.data * (val_high - val_low) + val_low
    
    # Round to integers if working with rating-like data
    matrix.data = np.round(matrix.data).astype(dtype)
    
    return matrix

def save_dense_matrix_to_npy(matrix, filename):
    """
    Save dense matrix (including all zeros) to .npy format
    
    Parameters:
    - matrix: Sparse matrix to save
    - filename: Output .npy filename
    """
    print(f"Converting sparse matrix to dense format...")
    
    # Convert to dense array - preserves ALL zeros
    dense_matrix = matrix.toarray().astype(np.float32)
    M, N = dense_matrix.shape
    
    print(f"Saving dense matrix with ALL {M*N:,} entries to {filename}...")
    
    # Save as binary .npy file
    np.save(filename, dense_matrix)
    
    # Calculate statistics
    non_zero_count = matrix.nnz
    zero_count = (M * N) - non_zero_count
    
    print(f"Dense matrix saved to {filename}:")
    print(f"  Total entries: {M*N:,}")
    print(f"  Non-zero entries: {non_zero_count:,}")
    print(f"  Zero entries: {zero_count:,}")
    print(f"  Matrix shape: {dense_matrix.shape}")
    print(f"  Data type: {dense_matrix.dtype}")

def main():
    # —— USER CONFIG ————————————————————————————————————————————————
    M, N           = 750, 750           # Matrix dimensions: M users × N items
    DENSITY        = 0.05               # Fraction of non-zero elements (sparsity)
    VAL_LOW, VAL_HIGH = 10, 100         # Value range for ratings
    SEED           = 123                # Random seed for reproducibility
    DTYPE          = np.float32         # Data type for matrix elements
    OUT_NPY        = "user_item_matrix_dense.npy"    # Output filename
    # ————————————————————————————————————————————————————————————————

    print("\n=== Complete Matrix Generator (ALL VALUES) ===")
    print(f"Generating {M}×{N} matrix with {DENSITY:.1%} density...")
    print(f"Output will contain ALL {M*N:,} matrix positions (including zeros)")
    
    # Size warning for very large matrices
    total_entries = M * N
    estimated_size_mb = total_entries * 4 / (1024 * 1024)  # 4 bytes per float32
    
    if total_entries > 100000:
        print(f"\nWARNING: Large matrix detected!")
        print(f"  Total entries: {total_entries:,}")
        print(f"  Estimated file size: ~{estimated_size_mb:.1f} MB")
        response = input("Continue? (y/n): ")
        if response.lower() != 'y':
            print("Aborted.")
            return
    
    t_start = time.time()
    
    try:
        # Generate the sparse matrix
        print("\nGenerating sparse matrix...")
        matrix = generate_with_sparse_random(M, N, DENSITY, 
                                            VAL_LOW, VAL_HIGH, 
                                            DTYPE, SEED)
        
        if matrix is None:
            raise RuntimeError("Matrix generation returned None.")
        
        t_gen = time.time() - t_start
        
        print(f"Sparse matrix generated successfully!")
        print(f"  Shape: {matrix.shape}")
        print(f"  Non-zero entries: {matrix.nnz:,}")
        print(f"  Zero entries: {(M*N) - matrix.nnz:,}")
        print(f"  Actual density: {matrix.nnz / (M*N):.4f}")
        print(f"  Generation time: {t_gen:.4f} seconds")
        
        # Save complete matrix to NPY using dense format
        print(f"\nSaving complete matrix to NPY...")
        t_save_start = time.time()
        
        save_dense_matrix_to_npy(matrix, OUT_NPY)
        
        t_save = time.time() - t_save_start
        print(f"Save completed in {t_save:.4f} seconds")
        
        # Show sample data
        print(f"\nSample data from {OUT_NPY}:")
        loaded_matrix = np.load(OUT_NPY)
        print(f"First 5x5 corner of matrix:")
        print(loaded_matrix[:5, :5])
        
        # Show file statistics
        import os
        file_size_mb = os.path.getsize(OUT_NPY) / (1024 * 1024)
        total_entries = M * N
        
        print(f"\nFile Statistics:")
        print(f"  File size: {file_size_mb:.1f} MB")
        print(f"  Total matrix entries: {total_entries:,}")
        print(f"  Zero entries: {total_entries - matrix.nnz:,}")
        print(f"  Non-zero entries: {matrix.nnz:,}")
        
        total_time = time.time() - t_start
        print(f"\nTotal execution time: {total_time:.4f} seconds")
        
    except Exception as e:
        print(f"Error during matrix generation: {e}")
        return

if __name__ == "__main__":
    main()