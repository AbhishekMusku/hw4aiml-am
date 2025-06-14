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

def save_complete_matrix_to_csv(matrix, filename, val_col='rating', row_col='user_id', col_col='item_id'):
    """
    Save ALL matrix values (including zeros) to CSV using efficient vectorized operations
    
    Parameters:
    - matrix: Sparse matrix to save
    - filename: Output CSV filename
    - val_col, row_col, col_col: Column names for value, row index, column index
    """
    print(f"Converting to dense format and preparing CSV data...")
    
    # Convert to dense array
    dense_matrix = matrix.toarray()
    M, N = dense_matrix.shape
    
    print(f"Creating CSV with ALL {M*N:,} entries using vectorized operations...")
    
    # Create coordinate arrays using vectorized operations
    row_indices, col_indices = np.meshgrid(np.arange(M), np.arange(N), indexing='ij')
    
    # Create DataFrame using vectorized operations
    df = pd.DataFrame({
        row_col: row_indices.flatten(),
        col_col: col_indices.flatten(),
        val_col: dense_matrix.flatten()
    })
    
    print(f"Saving DataFrame to {filename}...")
    df.to_csv(filename, index=False)
    
    # Calculate statistics
    non_zero_count = matrix.nnz
    zero_count = len(df) - non_zero_count
    
    print(f"Complete matrix saved to {filename}:")
    print(f"  Total entries: {len(df):,}")
    print(f"  Non-zero entries: {non_zero_count:,}")
    print(f"  Zero entries: {zero_count:,}")

def main():
    # —— USER CONFIG ————————————————————————————————————————————————
    M, N           = 1000, 1000           # Matrix dimensions: M users × N items
    DENSITY        = 0.01               # Fraction of non-zero elements (sparsity)
    VAL_LOW, VAL_HIGH = 10, 100         # Value range for ratings
    SEED           = 123                # Random seed for reproducibility
    DTYPE          = np.float32         # Data type for matrix elements
    OUT_CSV        = "user_item_matrix_complete.csv"  # Output filename
    # ————————————————————————————————————————————————————————————————

    print("\n=== Complete Matrix Generator (ALL VALUES) ===")
    print(f"Generating {M}×{N} matrix with {DENSITY:.1%} density...")
    print(f"Output will contain ALL {M*N:,} matrix positions (including zeros)")
    
    # Size warning for very large matrices
    total_entries = M * N
    estimated_size_mb = total_entries * 20 / (1024 * 1024)  # Rough estimate: 20 bytes per CSV row
    
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
        
        # Save complete matrix to CSV using vectorized operations
        print(f"\nSaving complete matrix to CSV...")
        t_save_start = time.time()
        
        save_complete_matrix_to_csv(matrix, OUT_CSV, 
                                   val_col='rating', 
                                   row_col='user_id', 
                                   col_col='item_id')
        
        t_save = time.time() - t_save_start
        print(f"Save completed in {t_save:.4f} seconds")
        
        # Show sample data
        print(f"\nSample data from {OUT_CSV}:")
        df_sample = pd.read_csv(OUT_CSV).head(15)
        print(df_sample)
        
        # Show file statistics
        import os
        file_size_mb = os.path.getsize(OUT_CSV) / (1024 * 1024)
        total_rows = len(pd.read_csv(OUT_CSV))
        
        print(f"\nFile Statistics:")
        print(f"  File size: {file_size_mb:.1f} MB")
        print(f"  Total CSV rows: {total_rows:,}")
        print(f"  Rows with zeros: {total_rows - matrix.nnz:,}")
        print(f"  Rows with values: {matrix.nnz:,}")
        
        total_time = time.time() - t_start
        print(f"\nTotal execution time: {total_time:.4f} seconds")
        
    except Exception as e:
        print(f"Error during matrix generation: {e}")
        return

if __name__ == "__main__":
    main()