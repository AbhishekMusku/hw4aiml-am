#!/usr/bin/env python3
"""
MatRaptor-style Item Similarity Partial Products Generator
========================================================

• Loads user-item matrix A from CSV (complete matrix with all positions including zeros)
• Performs Step 2a: Normalize item vectors for similarity calculation
• Generates partial products for normalized_item_user @ normalized_item_user.T
• Outputs only non-zero products to CSV files for MatRaptor processing.

Pipeline:
1. Load user-item matrix A (users × items)
2. Transpose to get item_user matrix (items × users) 
3. Normalize item vectors: normalized_item_user = inv_norms @ item_user
4. Generate partial products for item similarity: normalized_item_user @ normalized_item_user.T
5. Output partial products as CSV
"""

import time, csv
import numpy as np
import pandas as pd
from scipy import sparse

def load_matrix_from_csv(filename):
    """Load complete matrix from CSV and convert to sparse CSR format."""
    print(f"Loading user-item matrix from {filename}...")
    
    df = pd.read_csv(filename)
    
    # Find column names (flexible naming)
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
    
    if user_col is None or item_col is None or rating_col is None:
        raise ValueError(f"Could not find required columns. Available: {list(df.columns)}")
    
    # Get dimensions and create sparse matrix
    n_users = df[user_col].max() + 1
    n_items = df[item_col].max() + 1
    
    print(f"Matrix dimensions: {n_users} users × {n_items} items")
    
    user_item_matrix = sparse.csr_matrix(
        (df[rating_col].values, (df[user_col].values, df[item_col].values)),
        shape=(n_users, n_items),
        dtype=np.float32
    )
    
    print(f"User-item matrix loaded:")
    print(f"  Shape: {user_item_matrix.shape}")
    print(f"  Non-zero entries: {user_item_matrix.nnz:,}")
    print(f"  Density: {user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]):.4f}")
    
    return user_item_matrix

def normalize_item_vectors(user_item_matrix_csr):
    """
    Perform Step 2a: Normalize item vectors for similarity calculation.
    
    Parameters:
    - user_item_matrix_csr: Sparse CSR matrix (users × items)
    
    Returns:
    - normalized_item_user: Normalized sparse matrix (items × users)
    """
    print("\nStep 2a: Normalizing item vectors...")
    
    # Transpose to get item-user matrix (items × users)
    item_user = user_item_matrix_csr.T.tocsr()
    print(f"Item-user matrix shape: {item_user.shape}")
    
    # Calculate L2 norm for each item (row)
    print("Calculating L2 norms for each item...")
    norms = sparse.linalg.norm(item_user, axis=1)
    print(f"Calculated norms for {len(norms)} items")
    
    # Avoid division by zero
    norms[norms == 0] = 1.0
    
    # Create diagonal matrix of inverse norms
    print("Creating diagonal inverse norms matrix...")
    inv_norms = sparse.diags(1.0 / norms, format='csr')
    
    # Normalize each item vector: normalized_item_user = inv_norms @ item_user
    print("Performing normalization: inv_norms @ item_user...")
    normalized_item_user = inv_norms @ item_user
    normalized_item_user = normalized_item_user.tocsr()
    
    print(f"Normalized item-user matrix:")
    print(f"  Shape: {normalized_item_user.shape}")
    print(f"  Non-zero entries: {normalized_item_user.nnz:,}")
    print(f"  Density: {normalized_item_user.nnz / (normalized_item_user.shape[0] * normalized_item_user.shape[1]):.4f}")
    
    return normalized_item_user

def estimate_products(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix) -> int:
    """Calculate the exact total number of a_ik * a_jk products."""
    nnz_per_AT_row = np.diff(AT_csr.indptr).astype(np.int64, copy=False)
    
    if A_csr.nnz == 0:
        return 0
    
    valid_indices_k = A_csr.indices[A_csr.indices < len(nnz_per_AT_row)]
    total = int(nnz_per_AT_row[valid_indices_k].sum(dtype=np.int64))
    return total

def produce_similarity_products_scipy_optimized(normalized_item_user_csr: sparse.csr_matrix):
    """
    Generate partial products for item similarity calculation.
    Products: normalized_item_user[i,k] * normalized_item_user[j,k]
    For matrix multiplication: normalized_item_user @ normalized_item_user.T
    """
    print("\nGenerating item similarity partial products...")
    
    A_csr = normalized_item_user_csr  # Items × Users
    AT_csr = normalized_item_user_csr.T.tocsr()  # Users × Items → transposed back
    
    # Use SciPy's efficient CSR data access
    A_indptr, A_indices, A_data = A_csr.indptr, A_csr.indices, A_csr.data
    AT_indptr, AT_indices, AT_data = AT_csr.indptr, AT_csr.indices, AT_csr.data
    
    # Pre-allocate result arrays
    total_products = estimate_products(A_csr, AT_csr)
    print(f"Estimated total products: {total_products:,}")
    
    products = np.empty(total_products, dtype=np.float32)
    i_indices = np.empty(total_products, dtype=np.int32)
    j_indices = np.empty(total_products, dtype=np.int32)
    
    write_pos = 0
    
    # Efficient row-by-row processing using SciPy's CSR structure
    print("Processing rows for partial products...")
    for i in range(A_csr.shape[0]):
        if i % 10 == 0:
            print(f"  Processing item {i}/{A_csr.shape[0]}...")
            
        row_start, row_end = A_indptr[i], A_indptr[i + 1]
        if row_start == row_end:
            continue
            
        row_cols = A_indices[row_start:row_end]  # User indices
        row_vals = A_data[row_start:row_end]     # Normalized ratings
        
        for local_idx in range(len(row_cols)):
            k = row_cols[local_idx]  # User k
            a_ik = row_vals[local_idx]  # normalized_item_user[i,k]
            
            # Get all items that user k has rated (AT_csr row k)
            at_row_start, at_row_end = AT_indptr[k], AT_indptr[k + 1]
            if at_row_start == at_row_end:
                continue
                
            at_row_cols = AT_indices[at_row_start:at_row_end]  # Item indices
            at_row_vals = AT_data[at_row_start:at_row_end]     # Normalized ratings
            
            num_products = len(at_row_vals)
            end_pos = write_pos + num_products
            
            # Compute all products vectorized: a_ik * a_jk for all j
            products[write_pos:end_pos] = a_ik * at_row_vals
            i_indices[write_pos:end_pos] = i  # Item i
            j_indices[write_pos:end_pos] = at_row_cols  # Item j
            
            write_pos = end_pos
    
    # Trim arrays to actual size
    if write_pos < total_products:
        products = products[:write_pos]
        i_indices = i_indices[:write_pos]
        j_indices = j_indices[:write_pos]
    
    # Filter out any zero products (safety check)
    non_zero_mask = products != 0
    if not np.all(non_zero_mask):
        print(f"Filtering out {np.sum(~non_zero_mask)} zero products...")
        products = products[non_zero_mask]
        i_indices = i_indices[non_zero_mask]
        j_indices = j_indices[non_zero_mask]
    
    print(f"Generated {len(products):,} non-zero partial products")
    return np.column_stack((products, i_indices, j_indices))

def produce_similarity_products_stream(normalized_item_user_csr: sparse.csr_matrix,
                                     csv_path: str, chunk_size: int = 2_000_000):
    """
    Streaming version for large matrices.
    Generates partial products for item similarity and writes directly to CSV.
    """
    print(f"\nGenerating item similarity partial products (streaming to {csv_path})...")
    
    A_csr = normalized_item_user_csr
    AT_csr = normalized_item_user_csr.T.tocsr()
    
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
        
        print("Processing items for partial products...")
        for i in range(A_csr.shape[0]):
            if i % 50 == 0:
                print(f"  Processing item {i}/{A_csr.shape[0]}, written: {total_written:,}")
                
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
                
                # Compute products and filter zeros
                products = a_ik * at_row_vals
                non_zero_mask = products != 0
                
                if np.any(non_zero_mask):
                    valid_products = products[non_zero_mask]
                    valid_i = np.full(len(valid_products), i, dtype=np.int32)
                    valid_j = at_row_cols[non_zero_mask]
                    
                    valid_count = len(valid_products)
                    
                    # Check if buffer has space
                    if buf_pos + valid_count > chunk_size:
                        # Flush current buffer
                        if buf_pos > 0:
                            wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
                            total_written += buf_pos
                            buf_pos = 0
                    
                    # Add to buffer
                    if valid_count <= chunk_size:  # Safety check
                        buf_products[buf_pos:buf_pos+valid_count] = valid_products
                        buf_i[buf_pos:buf_pos+valid_count] = valid_i
                        buf_j[buf_pos:buf_pos+valid_count] = valid_j
                        buf_pos += valid_count
        
        # Flush remaining buffer
        if buf_pos > 0:
            wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
            total_written += buf_pos
    
    print(f"Completed! Total partial products written: {total_written:,}")
    return total_written

def main():
    print("=" * 60)
    print("ITEM SIMILARITY PARTIAL PRODUCTS GENERATOR")
    print("=" * 60)
    
    # Configuration
    INPUT_CSV = "user_item_matrix_complete.csv"
    OUT_CSV = "in.csv"
    MAX_RAM_GiB = 4
    CHUNK_SZ = 2_000_000

    start_time = time.time()
    
    # Step 1: Load user-item matrix
    print("\n" + "="*40)
    print("STEP 1: LOADING USER-ITEM MATRIX")
    print("="*40)
    user_item_matrix = load_matrix_from_csv(INPUT_CSV)
    load_time = time.time() - start_time
    print(f"Loading completed in {load_time:.2f} seconds")

    # Step 2a: Normalize item vectors
    print("\n" + "="*40)
    print("STEP 2A: NORMALIZING ITEM VECTORS")
    print("="*40)
    norm_start = time.time()
    normalized_item_user = normalize_item_vectors(user_item_matrix)
    norm_time = time.time() - norm_start
    print(f"Normalization completed in {norm_time:.2f} seconds")

    # Estimate memory usage for partial products
    print("\n" + "="*40)
    print("MEMORY ESTIMATION")
    print("="*40)
    AT_for_estimation = normalized_item_user.T.tocsr()
    products = estimate_products(normalized_item_user, AT_for_estimation)
    bytes_per_triple = 12  # 4 bytes float + 4 bytes int + 4 bytes int
    est_mem_GiB = (products * bytes_per_triple) / (1024**3)
    
    print(f"Estimated partial products: {products:,}")
    print(f"Estimated memory usage: {est_mem_GiB:.2f} GiB")
    
    mode = "prealloc" if est_mem_GiB <= MAX_RAM_GiB else "stream"
    print(f"Selected mode: {mode}")

    # Generate partial products
    print("\n" + "="*40)
    print("PARTIAL PRODUCTS GENERATION")
    print("="*40)
    
    gen_start = time.time()
    
    if mode == "prealloc":
        print("Using in-memory generation...")
        triples = produce_similarity_products_scipy_optimized(normalized_item_user)
        
        print(f"Saving {len(triples):,} partial products to {OUT_CSV}...")
        df_prod = pd.DataFrame(triples, columns=['prod', 'row_idx_i', 'col_idx_j'])
        df_prod['row_idx_i'] = df_prod['row_idx_i'].astype(np.int32)
        df_prod['col_idx_j'] = df_prod['col_idx_j'].astype(np.int32)
        df_prod.to_csv(OUT_CSV, index=False, float_format='%.6g')
    else:
        print("Using streaming generation...")
        total_written = produce_similarity_products_stream(normalized_item_user, OUT_CSV, CHUNK_SZ)
        print(f"Streamed {total_written:,} partial products to {OUT_CSV}")
    
    gen_time = time.time() - gen_start
    total_time = time.time() - start_time
    
    print("\n" + "="*40)
    print("COMPLETION SUMMARY")
    print("="*40)
    print(f"Data loading time: {load_time:.2f} seconds")
    print(f"Normalization time: {norm_time:.2f} seconds") 
    print(f"Partial products generation: {gen_time:.2f} seconds")
    print(f"Total execution time: {total_time:.2f} seconds")
    print(f"Output file: {OUT_CSV}")
    print(f"Ready for MatRaptor processing!")

if __name__ == "__main__":
    main()