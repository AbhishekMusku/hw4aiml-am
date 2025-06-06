#!/usr/bin/env python3
"""
MatRaptor-style sparse GEMM simulator with CSV input
===================================================

• Loads matrix A from CSV (complete matrix with all positions including zeros)
• Sets B = A.T (shape K×M) in CSR form
• Emits the elementary-product list [ prod = a_ik * a_jk ,  i ,  j ]
• Outputs only non-zero products to CSV files.
"""

import time, csv
import numpy as np
import pandas as pd
from scipy import sparse

def load_matrix_from_csv(filename):
    """Load complete matrix from CSV and convert to sparse CSR format."""
    df = pd.read_csv(filename)
    
    # Find column names
    user_col = None
    item_col = None
    rating_col = None
    
    for col in df.columns:
        if col in ['user_id', 'user', 'row']:
            user_col = col
        elif col in ['item_id', 'movie_id', 'item', 'col']:
            item_col = col
        elif col in ['rating', 'value', 'val']:
            rating_col = col
    
    # Get dimensions and create sparse matrix
    n_users = df[user_col].max() + 1
    n_items = df[item_col].max() + 1
    
    csr_matrix = sparse.csr_matrix(
        (df[rating_col].values, (df[user_col].values, df[item_col].values)),
        shape=(n_users, n_items),
        dtype=np.float32
    )
    
    return csr_matrix

def estimate_products(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix) -> int:
    """Calculate the exact total number of a_ik * a_jk products."""
    nnz_per_AT_row = np.diff(AT_csr.indptr).astype(np.int64, copy=False)
    
    if A_csr.nnz == 0:
        return 0
    
    valid_indices_k = A_csr.indices[A_csr.indices < len(nnz_per_AT_row)]
    total = int(nnz_per_AT_row[valid_indices_k].sum(dtype=np.int64))
    return total

def produce_products_scipy_optimized(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix):
    """SciPy-optimized product generation using efficient CSR operations."""
    # Use SciPy's efficient CSR data access
    A_indptr, A_indices, A_data = A_csr.indptr, A_csr.indices, A_csr.data
    AT_indptr, AT_indices, AT_data = AT_csr.indptr, AT_csr.indices, AT_csr.data
    
    # Pre-allocate result arrays
    total_products = estimate_products(A_csr, AT_csr)
    products = np.empty(total_products, dtype=np.float32)
    i_indices = np.empty(total_products, dtype=np.int32)
    j_indices = np.empty(total_products, dtype=np.int32)
    
    write_pos = 0
    
    # Efficient row-by-row processing using SciPy's CSR structure
    for i in range(A_csr.shape[0]):
        row_start, row_end = A_indptr[i], A_indptr[i + 1]
        if row_start == row_end:
            continue
            
        row_cols = A_indices[row_start:row_end]
        row_vals = A_data[row_start:row_end]
        
        for local_idx in range(len(row_cols)):
            k = row_cols[local_idx]
            a_ik = row_vals[local_idx]
            
            at_row_start, at_row_end = AT_indptr[k], AT_indptr[k + 1]
            if at_row_start == at_row_end:
                continue
                
            at_row_cols = AT_indices[at_row_start:at_row_end]
            at_row_vals = AT_data[at_row_start:at_row_end]
            
            num_products = len(at_row_vals)
            end_pos = write_pos + num_products
            
            # Compute all products vectorized
            products[write_pos:end_pos] = a_ik * at_row_vals
            i_indices[write_pos:end_pos] = i
            j_indices[write_pos:end_pos] = at_row_cols
            
            write_pos = end_pos
    
    # Trim arrays to actual size
    if write_pos < total_products:
        products = products[:write_pos]
        i_indices = i_indices[:write_pos]
        j_indices = j_indices[:write_pos]
    
    # Filter out any zero products (safety check)
    non_zero_mask = products != 0
    if not np.all(non_zero_mask):
        products = products[non_zero_mask]
        i_indices = i_indices[non_zero_mask]
        j_indices = j_indices[non_zero_mask]
    
    return np.column_stack((products, i_indices, j_indices))

def produce_products_stream_scipy_optimized(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix,
                                          csv_path: str, chunk_size: int = 2_000_000):
    """SciPy-optimized streaming version."""
    A_indptr, A_indices, A_data = A_csr.indptr, A_csr.indices, A_csr.data
    AT_indptr, AT_indices, AT_data = AT_csr.indptr, AT_csr.indices, AT_csr.data
    
    # Streaming buffers
    buf_products = np.empty(chunk_size, dtype=np.float32)
    buf_i = np.empty(chunk_size, dtype=np.int32)
    buf_j = np.empty(chunk_size, dtype=np.int32)
    
    total_written = 0
    buf_pos = 0
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f)
        wr.writerow(['prod', 'row_idx_i', 'col_idx_j'])
        
        for i in range(A_csr.shape[0]):
            row_start, row_end = A_indptr[i], A_indptr[i + 1]
            if row_start == row_end:
                continue
                
            row_cols = A_indices[row_start:row_end]
            row_vals = A_data[row_start:row_end]
            
            for local_idx in range(len(row_cols)):
                k = row_cols[local_idx]
                a_ik = row_vals[local_idx]
                
                at_row_start, at_row_end = AT_indptr[k], AT_indptr[k + 1]
                if at_row_start == at_row_end:
                    continue
                    
                at_row_cols = AT_indices[at_row_start:at_row_end]
                at_row_vals = AT_data[at_row_start:at_row_end]
                
                num_products = len(at_row_vals)
                remaining_products = num_products
                at_offset = 0
                
                while remaining_products > 0:
                    space_left = chunk_size - buf_pos
                    write_count = min(remaining_products, space_left)
                    
                    end_pos = buf_pos + write_count
                    at_end = at_offset + write_count
                    
                    # Vectorized assignment to buffer
                    products = a_ik * at_row_vals[at_offset:at_end]
                    # Filter zeros during streaming
                    non_zero_mask = products != 0
                    if np.any(non_zero_mask):
                        valid_products = products[non_zero_mask]
                        valid_i = np.full(len(valid_products), i, dtype=np.int32)
                        valid_j = at_row_cols[at_offset:at_end][non_zero_mask]
                        
                        valid_count = len(valid_products)
                        if buf_pos + valid_count <= chunk_size:
                            buf_products[buf_pos:buf_pos+valid_count] = valid_products
                            buf_i[buf_pos:buf_pos+valid_count] = valid_i
                            buf_j[buf_pos:buf_pos+valid_count] = valid_j
                            buf_pos += valid_count
                    
                    at_offset = at_end
                    remaining_products -= write_count
                    
                    # Flush buffer if full
                    if buf_pos >= chunk_size * 0.9:  # Flush at 90% to avoid overflow
                        wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
                        total_written += buf_pos
                        buf_pos = 0
        
        # Flush remaining buffer
        if buf_pos > 0:
            wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
            total_written += buf_pos
    
    return total_written

def main():
    # Configuration
    INPUT_CSV = "user_item_matrix_complete.csv"
    OUT_CSV = "in.csv"
    MAX_RAM_GiB = 4
    CHUNK_SZ = 2_000_000

    # Load matrix
    A = load_matrix_from_csv(INPUT_CSV)
    AT = A.transpose().tocsr()

    # Decide mode based on memory usage
    products = estimate_products(A, AT)
    bytes_per_triple = 12  # 4 bytes float + 4 bytes int + 4 bytes int
    est_mem_GiB = (products * bytes_per_triple) / (1024**3)
    
    mode = "prealloc" if est_mem_GiB <= MAX_RAM_GiB else "stream"

    # Generate products
    if mode == "prealloc":
        triples = produce_products_scipy_optimized(A, AT)
        df_prod = pd.DataFrame(triples, columns=['prod', 'row_idx_i', 'col_idx_j'])
        df_prod['row_idx_i'] = df_prod['row_idx_i'].astype(np.int32)
        df_prod['col_idx_j'] = df_prod['col_idx_j'].astype(np.int32)
        df_prod.to_csv(OUT_CSV, index=False, float_format='%.6g')
    else:
        produce_products_stream_scipy_optimized(A, AT, OUT_CSV, CHUNK_SZ)

if __name__ == "__main__":
    main()