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
    """
    print("\nStep 2a: Normalizing item vectors...")
    
    item_user = user_item_matrix_csr.T.tocsr()
    print(f"Item-user matrix shape: {item_user.shape}")
    
    print("Calculating L2 norms for each item...")
    norms = np.sqrt(np.array(item_user.multiply(item_user).sum(axis=1)).flatten())
    print(f"Calculated norms for {len(norms)} items")
    
    norms[norms == 0] = 1.0
    
    print("Creating diagonal inverse norms matrix...")
    inv_norms = sparse.diags(1.0 / norms, format='csr')
    
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

def produce_similarity_products_scipy_optimized(normalized_item_user_csr: sparse.csr_matrix, scale_factor: int = 65536):
    """
    Generate partial products for item similarity calculation.
    """
    print("\nGenerating item similarity partial products...")
    
    A_csr = normalized_item_user_csr
    AT_csr = normalized_item_user_csr.T.tocsr()
    
    A_indptr, A_indices, A_data = A_csr.indptr, A_csr.indices, A_csr.data
    AT_indptr, AT_indices, AT_data = AT_csr.indptr, AT_csr.indices, AT_csr.data
    
    total_products = estimate_products(A_csr, AT_csr)
    print(f"Estimated total products: {total_products:,}")
    
    products = np.empty(total_products, dtype=np.float32)
    i_indices = np.empty(total_products, dtype=np.int32)
    j_indices = np.empty(total_products, dtype=np.int32)
    
    write_pos = 0
    
    print("Processing rows for partial products...")
    for i in range(A_csr.shape[0]):
        if i % 10 == 0:
            print(f"  Processing item {i}/{A_csr.shape[0]}...")
            
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
            
            products[write_pos:end_pos] = a_ik * at_row_vals
            i_indices[write_pos:end_pos] = i
            j_indices[write_pos:end_pos] = at_row_cols
            
            write_pos = end_pos
    
    if write_pos < total_products:
        products = products[:write_pos]
        i_indices = i_indices[:write_pos]
        j_indices = j_indices[:write_pos]
    
    non_zero_mask = products != 0
    if not np.all(non_zero_mask):
        print(f"Filtering out {np.sum(~non_zero_mask)} zero products...")
        products = products[non_zero_mask]
        i_indices = i_indices[non_zero_mask]
        j_indices = j_indices[non_zero_mask]
    
    products_scaled = (products * scale_factor).astype(np.int32)
    print(f"Generated {len(products_scaled):,} non-zero scaled partial products")
    return np.column_stack((products_scaled, i_indices, j_indices))

def produce_similarity_products_stream(normalized_item_user_csr: sparse.csr_matrix,
                                     csv_path: str, chunk_size: int = 2_000_000, scale_factor: int = 65536):
    """
    Streaming version for large matrices.
    """
    print(f"\nGenerating item similarity partial products (streaming to {csv_path})...")
    
    A_csr = normalized_item_user_csr
    AT_csr = normalized_item_user_csr.T.tocsr()
    
    A_indptr, A_indices, A_data = A_csr.indptr, A_csr.indices, A_csr.data
    AT_indptr, AT_indices, AT_data = AT_csr.indptr, AT_csr.indices, AT_csr.data
    
    buf_products = np.empty(chunk_size, dtype=np.int32)
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
                
                products = a_ik * at_row_vals
                products_scaled = (products * scale_factor).astype(np.int32)
                non_zero_mask = products_scaled != 0

                if np.any(non_zero_mask):
                    valid_products = products_scaled[non_zero_mask]
                    valid_i = np.full(len(valid_products), i, dtype=np.int32)
                    valid_j = at_row_cols[non_zero_mask]
                    
                    valid_count = len(valid_products)
                    
                    if buf_pos + valid_count > chunk_size:
                        if buf_pos > 0:
                            wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
                            total_written += buf_pos
                            buf_pos = 0
                    
                    if valid_count <= chunk_size:
                        buf_products[buf_pos:buf_pos+valid_count] = valid_products
                        buf_i[buf_pos:buf_pos+valid_count] = valid_i
                        buf_j[buf_pos:buf_pos+valid_count] = valid_j
                        buf_pos += valid_count
        
        if buf_pos > 0:
            wr.writerows(zip(buf_products[:buf_pos], buf_i[:buf_pos], buf_j[:buf_pos]))
            total_written += buf_pos
    
    print(f"Completed! Total partial products written: {total_written:,}")
    return total_written

# --- NEW FUNCTION TO SAVE TIMING STATS ---
def save_timing_stats_to_csv(stats, filename="cob1_timing_stats.csv"):
    """
    Save timing statistics to a CSV file.
    """
    print(f"\nSaving timing statistics to {filename}...")
    try:
        df = pd.DataFrame([stats]) # Create DataFrame from a list with one dictionary
        df.to_csv(filename, index=False)
        print(f"Timing stats saved successfully.")
    except Exception as e:
        print(f"Error saving timing stats: {e}")

def main():
    print("=" * 60)
    print("ITEM SIMILARITY PARTIAL PRODUCTS GENERATOR")
    print("=" * 60)
    
    # Configuration
    INPUT_CSV = "user_item_matrix_complete.csv"
    OUT_CSV = "in.csv"
    MAX_RAM_GiB = 4
    CHUNK_SZ = 2_000_000
    SCALE_FACTOR = 65536

    start_time = time.time()
    
    # Step 1: Load user-item matrix
    print("\n" + "="*40)
    print("STEP 1: LOADING USER-ITEM MATRIX")
    print("="*40)
    user_item_matrix = load_matrix_from_csv(INPUT_CSV)
    load_time = time.time() - start_time
    print(f"Loading completed in {load_time:.2f} seconds")

    # Save user-item matrix for collaborative filtering
    print("Saving user-item matrix for collaborative filtering...")
    sparse.save_npz("user_item_matrix_processed.npz", user_item_matrix)
    print("Saved user_item_matrix_processed.npz")

    # Step 2a: Normalize item vectors
    print("\n" + "="*40)
    print("STEP 2A: NORMALIZING ITEM VECTORS")
    print("="*40)
    phase1_start = time.time()
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
    bytes_per_triple = 12
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
    phase2_start = time.time()

    if mode == "prealloc":
        print("Using in-memory generation...")
        triples = produce_similarity_products_scipy_optimized(normalized_item_user, SCALE_FACTOR)
        
        print(f"Saving {len(triples):,} partial products to {OUT_CSV}...")
        df_prod = pd.DataFrame(triples, columns=['prod', 'row_idx_i', 'col_idx_j'])
        df_prod['row_idx_i'] = df_prod['row_idx_i'].astype(np.int32)
        df_prod['col_idx_j'] = df_prod['col_idx_j'].astype(np.int32)
        df_prod.to_csv(OUT_CSV, index=False)
    else:
        print("Using streaming generation...")
        total_written = produce_similarity_products_stream(normalized_item_user, OUT_CSV, CHUNK_SZ, SCALE_FACTOR)
        print(f"Streamed {total_written:,} partial products to {OUT_CSV}")
    
    gen_time = time.time() - gen_start
    phase2_time = time.time() - phase2_start
    phase1_time = time.time() - phase1_start
    total_time = time.time() - start_time
    
    print("\nCOMPLETION SUMMARY")
    print("="*40)
    print(f"Data loading time: {load_time} seconds")
    print(f"Normalization time: {norm_time} seconds")
    print(f"Partial products generation: {gen_time} seconds")
    print(f"Phase 1 (Normalization -> End): {phase1_time} seconds")
    print(f"Phase 2 (Partial Products Only): {phase2_time} seconds")
    print(f"Total execution time: {total_time} seconds")
    print(f"Output file: {OUT_CSV}")
    
    # --- NEW: GATHER AND SAVE TIMING STATS ---
    timing_stats = {
        'data_loading_time_sec': load_time,
        'normalization_time_sec': norm_time,
        'partial_products_generation_time_sec': gen_time,
        'phase1_time_sec': phase1_time,
        'phase2_time_sec': phase2_time,
        'total_execution_time_sec': total_time
    }
    save_timing_stats_to_csv(timing_stats)
    
    print(f"Ready for MatRaptor processing!")

if __name__ == "__main__":
    main()