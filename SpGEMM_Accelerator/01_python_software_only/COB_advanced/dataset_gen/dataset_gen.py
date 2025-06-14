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

def save_matrix_to_coo_csv(matrix, filename, val_col='value', row_col='row', col_col='col'):
    """
    Save sparse matrix to CSV in COO (coordinate) format
    
    Parameters:
    - matrix: Sparse matrix to save
    - filename: Output CSV filename
    - val_col, row_col, col_col: Column names for value, row index, column index
    """
    # Convert to COO format if not already
    if not sparse.isspmatrix_coo(matrix):
        coo_matrix = matrix.tocoo()
    else:
        coo_matrix = matrix
    
    # Create DataFrame with COO data
    df = pd.DataFrame({
        row_col: coo_matrix.row,
        col_col: coo_matrix.col,
        val_col: coo_matrix.data
    })
    
    # Save to CSV
    df.to_csv(filename, index=False)
    print(f"Matrix saved to {filename} with {len(df)} non-zero entries")

def main():
    # —— USER CONFIG ————————————————————————————————————————————————
    M, N           = 750, 750         # Matrix dimensions: M users × N items
    DENSITY        = 0.05               # Fraction of non-zero elements (sparsity)
    VAL_LOW, VAL_HIGH = 10, 100           # Value range for ratings (1-5 scale)
    SEED           = 123                # Random seed for reproducibility
    DTYPE          = np.float32         # Data type for matrix elements
    OUT_CSV        = "user_item_matrix.csv"  # Output filename
    # ————————————————————————————————————————————————————————————————

    print("\n=== User-Item Matrix Generator ===")
    print(f"Generating {M}×{N} matrix with {DENSITY:.1%} density...")
    
    t_start = time.time()
    
    try:
        # Generate the sparse matrix
        matrix = generate_with_sparse_random(M, N, DENSITY, 
                                            VAL_LOW, VAL_HIGH, 
                                            DTYPE, SEED)
        
        if matrix is None:
            raise RuntimeError("Matrix generation returned None.")
        
        t_gen = time.time() - t_start
        
        print(f"Matrix generated successfully!")
        print(f"  Shape: {matrix.shape}")
        print(f"  Non-zero entries: {matrix.nnz:,}")
        print(f"  Actual density: {matrix.nnz / (matrix.shape[0] * matrix.shape[1]):.4f}")
        print(f"  Generation time: {t_gen:.4f} seconds")
        
        # Save to CSV
        print(f"\nSaving matrix to {OUT_CSV}...")
        t_save_start = time.time()
        
        save_matrix_to_coo_csv(matrix, OUT_CSV, 
                              val_col='rating', 
                              row_col='user_id', 
                              col_col='movie_id')
        
        t_save = time.time() - t_save_start
        print(f"Save completed in {t_save:.4f} seconds")
        
        # Show sample data
        print(f"\nSample of generated data:")
        df_sample = pd.read_csv(OUT_CSV).head(10)
        print(df_sample)
        
        total_time = time.time() - t_start
        print(f"\nTotal execution time: {total_time:.4f} seconds")
        
    except Exception as e:
        print(f"Error during matrix generation: {e}")
        return

if __name__ == "__main__":
    main()