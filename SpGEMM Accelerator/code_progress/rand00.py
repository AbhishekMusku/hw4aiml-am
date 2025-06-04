#!/usr/bin/env python3
"""
outputs aik x aTkj, i , j
MatRaptor-style sparse GEMM simulator (B = Aᵀ version)
======================================================

• Generates ONE sparse matrix  A (M×K)
• Sets  B = A.T   (shape K×M)   in CSR form
• Emits the elementary-product list
        [ prod = a_ik * a_jk ,  i ,  j ]
  (where a_jk is the element from A.T corresponding to B_kj)
• Can use pre-allocation (RAM) or streaming (disk) for products.
• Optionally saves A, A.T, and products to CSV files.
"""

import time, csv, multiprocessing, os
import numpy as np
import pandas as pd # Using pandas for easier CSV writing
from scipy import sparse
from scipy.stats import randint
from concurrent.futures import ProcessPoolExecutor

# ──────────────────────────────────────────────────────────────────────────
# 1. Sparse-matrix generator (returns CSR)
# ──────────────────────────────────────────────────────────────────────────
def generate_with_sparse_random(n_rows, n_cols, density,
                                v_low, v_high,
                                dtype, seed):
    """Generates a random sparse matrix and returns it in CSR format."""
    if not (0.0 <= density <= 1.0):
        raise ValueError("density must be in [0, 1]")
    print(f"  Generating matrix ({n_rows}x{n_cols}, density={density:.3f})...")
    rng = np.random.default_rng(seed)
    value_dist = randint(low=v_low, high=v_high) # low inclusive, high exclusive
    try:
        # Generate in COO format first as it's efficient for construction
        coo = sparse.random(n_rows, n_cols, density,
                            format='coo', dtype=dtype,
                            random_state=rng, data_rvs=value_dist.rvs)
        print(f"  Generated COO, converting to CSR...")
        # Convert to CSR for efficient row access later
        csr = coo.tocsr()
        print(f"  CSR conversion done. NNZ = {csr.nnz:,}")
        return csr
    except Exception as e:
        print(f"  Error during sparse matrix generation for shape ({n_rows}x{n_cols}): {e}")
        raise # Re-raise the exception to signal failure

# ──────────────────────────────────────────────────────────────────────────
# 2. Helpers
# ──────────────────────────────────────────────────────────────────────────
def estimate_products(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix) -> int:
    """Calculate the exact total number of a_ik * a_jk products using int64."""
    # Validate shapes for matrix multiplication compatibility
    if A_csr.shape[1] != AT_csr.shape[0]:
         raise ValueError(f"Incompatible shapes for product estimation: A{A_csr.shape}, AT{AT_csr.shape}")
    print("  Estimating total products...")
    start_time = time.time()
    # Number of non-zeros in each row of A.T
    # Use int64 to prevent overflow during intermediate calculations if nnz is large
    nnz_per_AT_row = np.diff(AT_csr.indptr).astype(np.int64, copy=False)
    # For each non-zero a_ik in A, its column index k corresponds to a row in AT.
    # We need the number of non-zeros in that corresponding row of AT.
    # A_csr.indices contains the 'k' values for each non-zero element in A.
    if A_csr.nnz == 0:
        total = 0 # No non-zeros in A means zero products
    else:
        # Ensure indices used for lookup (k values from A) are within the bounds of AT's rows
        valid_indices_k = A_csr.indices[A_csr.indices < len(nnz_per_AT_row)]
        if len(valid_indices_k) < len(A_csr.indices):
             # This indicates an issue, perhaps with matrix dimensions or generation
             print(f"  Warning: {len(A_csr.indices) - len(valid_indices_k)} column indices in A were out of bounds for AT's rows.")
        # Sum the counts of non-zeros for the relevant rows in AT, using only valid indices
        # Use dtype=np.int64 for the final sum to prevent overflow for large results
        total = int(nnz_per_AT_row[valid_indices_k].sum(dtype=np.int64))

    elapsed_time = time.time() - start_time
    print(f"  Estimation complete: {total:,} products (took {elapsed_time:.4f} s)")
    # Ensure the result is non-negative, which it should be if calculation is correct
    if total < 0:
        raise ValueError(f"Estimated products resulted in a negative number ({total}), indicating potential overflow or error.")
    return total

def save_matrix_to_coo_csv(matrix, filename, value_col, row_col, col_col):
    """
    Saves the non-zero elements of a sparse matrix to a CSV file
    in COO format (value, row_index, column_index).
    """
    print(f"Saving matrix {matrix.shape} NNZ={matrix.nnz:,} to COO format CSV: {filename} ...")
    start_time = time.time()
    try:
        # Convert to COO format for easy access to data, row, col arrays
        if not sparse.isspmatrix_coo(matrix):
            coo_matrix = matrix.tocoo()
        else:
            coo_matrix = matrix

        # Create a DataFrame using the COO attributes
        df = pd.DataFrame({
            value_col: coo_matrix.data,
            row_col: coo_matrix.row,
            col_col: coo_matrix.col
        })

        # Ensure correct dtypes for index columns for consistency
        df[row_col] = df[row_col].astype(np.int32)
        df[col_col] = df[col_col].astype(np.int32)

        # Reorder columns for the desired output format
        df = df[[value_col, row_col, col_col]]

        # Save to CSV using pandas
        df.to_csv(filename, index=False, float_format='%.6g') # '%.6g' is a reasonable default for floats
        elapsed_time = time.time() - start_time
        print(f"  Successfully saved to {filename} in {elapsed_time:.4f} s")
    except Exception as e:
        print(f"  Error saving matrix to {filename}: {e}")
        raise # Re-raise the exception

# ──────────────────────────────────────────────────────────────────────────
# 3A. Pre-allocated product generator
# ──────────────────────────────────────────────────────────────────────────
def produce_products_prealloc(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix):
    """Generates [prod=a_ik*a_jk, i, j] triples using pre-allocated NumPy arrays."""
    print("  Starting prealloc product generation...")
    # Extract CSR components for faster access in loops
    ia, ja, va = A_csr.indptr, A_csr.indices, A_csr.data
    ib, jb, vb = AT_csr.indptr, AT_csr.indices, AT_csr.data  # B = Aᵀ

    # Estimate total products needed for allocation
    P = estimate_products(A_csr, AT_csr)
    if P == 0:
        print("  Warning: Zero products estimated. Returning empty array.")
        # Return empty array with correct column structure and dtypes
        prod_dtype = np.result_type(va.dtype, vb.dtype)
        return np.empty((0, 3), dtype=np.result_type(prod_dtype, np.int32))

    # Allocate memory
    print(f"  Allocating memory for {P:,} product triples...")
    start_alloc_time = time.time()
    try:
        # Determine the appropriate dtype for the product
        prod_dtype = np.result_type(va.dtype, vb.dtype)
        prod = np.empty(P, dtype=prod_dtype)
        i_idx = np.empty(P, dtype=np.int32) # Row index from A
        j_idx = np.empty(P, dtype=np.int32) # Column index from AT
    except MemoryError:
        print(f"  MemoryError: Failed to allocate arrays for {P:,} triples.")
        raise # Propagate memory error
    print(f"  Allocation done (took {time.time() - start_alloc_time:.4f} s)")

    # Perform fused traversal and fill arrays
    print("  Performing fused traversal (prealloc)...")
    start_traversal_time = time.time()
    ptr = 0 # Output pointer, tracks current position in allocated arrays
    for i in range(A_csr.shape[0]): # Iterate through rows of A
        # Iterate through non-zeros (column k and value a_ik) in row i of A
        for p in range(ia[i], ia[i + 1]):
            k   = ja[p]  # Column index k for a_ik (becomes row index for AT)
            a_ik = va[p]  # Value a_ik

            # Bounds check for k (ensure it's a valid row index for AT)
            if k < 0 or k >= AT_csr.shape[0]:
                print(f"  Warning: Index k={k} from A (row {i}) is out of bounds for AT (shape {AT_csr.shape}). Skipping.")
                continue

            # Get pointers for row k in AT
            bs, be = ib[k], ib[k + 1] # Start and end pointers for row k in AT's data/indices
            nnz_k  = be - bs         # Number of non-zeros in row k of AT

            # Skip if row k in AT is empty
            if nnz_k == 0:
                continue

            # Calculate the end pointer in the output arrays for this batch
            end = ptr + nnz_k

            # Bounds check before writing (important sanity check for allocation/estimation)
            if end > P:
                print(f"  Error: Output pointer ({end}) exceeds allocated size ({P}) at i={i}, k={k}. Mismatch likely.")
                # Trim arrays to the current pointer and break, or raise an error
                prod = prod[:ptr]
                i_idx = i_idx[:ptr]
                j_idx = j_idx[:ptr]
                P = ptr # Adjust P to actual filled size
                break # Exit inner loop (processing non-zeros of row i in A)

            # --- Core Calculation and Assignment ---
            # Get values (a_jk) and column indices (j) from row k of AT
            at_kj_values = vb[bs:be]  # These are the a_jk values
            at_kj_indices = jb[bs:be] # These are the j indices

            # Calculate products: a_ik * a_jk for all j where a_jk is non-zero
            products_for_aik = a_ik * at_kj_values

            # Assign calculated values to the pre-allocated arrays using slicing
            prod[ptr:end] = products_for_aik
            i_idx[ptr:end] = i             # Broadcast row index i from A
            j_idx[ptr:end] = at_kj_indices # Assign column indices j from AT
            # --- End Core Calculation ---

            ptr = end # Move output pointer to the next available position

        # Check if the inner loop was broken due to the bounds error
        if end > P:
             break # Exit outer loop (processing rows of A) as well

    print(f"  Traversal done (took {time.time() - start_traversal_time:.4f} s)")
    print(f"  Final output pointer = {ptr:,}")

    # Final check: if ptr != P, the estimation might have been slightly off,
    # or some elements might have been skipped due to bounds checks. Trim if necessary.
    if ptr != P:
        print(f"  Warning: Final pointer ({ptr:,}) != estimated products ({P:,}). Trimming result array.")
        prod = prod[:ptr]
        i_idx = i_idx[:ptr]
        j_idx = j_idx[:ptr]

    # Stack the columns into the final (N, 3) array
    print("  Stacking columns...")
    start_stack_time = time.time()
    result = np.column_stack((prod, i_idx, j_idx))
    print(f"  Stacking done (took {time.time() - start_stack_time:.4f} s)")
    return result

# ──────────────────────────────────────────────────────────────────────────
# 3B. Streaming writer (constant RAM)
# ──────────────────────────────────────────────────────────────────────────
def produce_products_stream(A_csr: sparse.csr_matrix, AT_csr: sparse.csr_matrix,
                            csv_path: str, chunk_size: int = 2_000_000):
    """Generates [prod=a_ik*a_jk, i, j] triples and streams them to a CSV."""
    print("  Starting streaming product generation...")
    # Extract CSR components
    ia, ja, va = A_csr.indptr, A_csr.indices, A_csr.data
    ib, jb, vb = AT_csr.indptr, AT_csr.indices, AT_csr.data

    # Allocate buffers for chunking
    print(f"  Allocating streaming buffers (chunk size = {chunk_size:,})...")
    try:
        prod_dtype = np.result_type(va.dtype, vb.dtype)
        buf_p = np.empty(chunk_size, dtype=prod_dtype) # Buffer for products
        buf_i = np.empty(chunk_size, dtype=np.int32)   # Buffer for i indices
        buf_j = np.empty(chunk_size, dtype=np.int32)   # Buffer for j indices
    except MemoryError:
        print(f"  MemoryError: Failed to allocate streaming buffers of size {chunk_size:,}.")
        raise

    total_written = 0 # Counter for total rows written to CSV
    ptr = 0           # Current position within the buffers

    print(f"  Opening CSV file for writing: {csv_path}")
    # Open CSV file for writing
    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        wr = csv.writer(f)
        # Write header row
        wr.writerow(['prod', 'row_idx_i', 'col_idx_j'])

        print("  Performing fused traversal (streaming)...")
        start_traversal_time = time.time()
        # Iterate through A and AT similar to prealloc version
        for i in range(A_csr.shape[0]): # Rows of A
            for p in range(ia[i], ia[i + 1]): # Non-zeros in row i of A
                k, a_ik = ja[p], va[p] # k = column index, a_ik = value

                # Bounds check for k
                if k < 0 or k >= AT_csr.shape[0]: continue

                # Get pointers for row k in AT
                bs, be = ib[k], ib[k + 1]
                nnz_k  = be - bs # Number of non-zeros in row k of AT
                if nnz_k == 0: continue # Skip if row k is empty

                # --- Core Calculation ---
                at_kj_values = vb[bs:be]  # a_jk values
                at_kj_indices = jb[bs:be] # j indices
                products_for_aik = a_ik * at_kj_values # Calculate products
                # --- End Core Calculation ---

                # --- Write to buffer, flushing when full ---
                current_chunk_start = 0 # Position within the current batch of nnz_k items
                while current_chunk_start < nnz_k:
                    # How much space is left in the current buffer?
                    space_left = chunk_size - ptr
                    # How many items from this batch (nnz_k) can we write into the remaining space?
                    num_to_write = min(nnz_k - current_chunk_start, space_left)

                    # Calculate slice boundaries for buffer and data
                    write_end = ptr + num_to_write
                    data_start = current_chunk_start
                    data_end = current_chunk_start + num_to_write

                    # Fill the buffer segment with calculated data
                    buf_p[ptr:write_end] = products_for_aik[data_start:data_end]
                    buf_i[ptr:write_end] = i # Broadcast i
                    buf_j[ptr:write_end] = at_kj_indices[data_start:data_end]

                    # Update buffer pointer and position within the current batch
                    ptr = write_end
                    current_chunk_start += num_to_write

                    # If buffer is full, write (flush) it to the CSV file
                    if ptr == chunk_size:
                        # print(f"    Flushing buffer ({chunk_size:,} rows)...") # Optional verbose output
                        # Use zip to iterate through buffer columns row by row for writerows
                        wr.writerows(zip(buf_p, buf_i, buf_j))
                        total_written += ptr # Update total count
                        ptr = 0 # Reset buffer pointer
                # --- End Buffer Writing Logic ---

        # After loops finish, flush any remaining data in the buffer
        if ptr > 0:
            print(f"  Flushing final buffer segment ({ptr:,} rows)...")
            wr.writerows(zip(buf_p[:ptr], buf_i[:ptr], buf_j[:ptr]))
            total_written += ptr

        print(f"  Traversal & streaming done (took {time.time() - start_traversal_time:.4f} s)")

    print(f"  Total rows written to CSV: {total_written:,}")
    return total_written # Return total rows written

# ──────────────────────────────────────────────────────────────────────────
# 4. Main driver
# ──────────────────────────────────────────────────────────────────────────
def main():
    # —— USER CONFIG ————————————————————————————————————————————————
    M, K        = 1000, 1000          # A is M×K,   B=Aᵀ is K×M
    DENS_A      = 0.01
    VAL_LOW, VAL_HIGH = 1, 50           # Value range for non-zeros
    SEED      = 123                   # Random seed for reproducibility
    DTYPE     = np.float32            # Data type for matrix elements
    # PAR_GEN is not used here as only one matrix is generated
    WRITE_CSV      = True             # Write the final product stream CSV?
    OUT_CSV        = "products_A_AT.csv" # Filename for product stream
    WRITE_COO_CSV  = True             # Write individual matrix COO CSVs?
    OUT_A_COO_CSV  = "matrix_A_coo.csv"  # Filename for matrix A COO
    OUT_AT_COO_CSV = "matrix_AT_coo.csv" # Filename for matrix AT COO
    MAX_RAM_GiB = 4                   # Threshold (GiB) to switch to streaming mode
    CHUNK_SZ      = 2_000_000         # Buffer size (rows) for streaming CSV write
    DO_SCIPY_CHECK = True             # Verify with SciPy C = A @ Aᵀ?
    # ————————————————————————————————————————————————————————————————

    print("\n=== MatRaptor product-stream (B = Aᵀ) ===")
    t_all0 = time.time() # Start overall timer

    # 1. Generate A and AT = A.T -------------------------------------------
    print("\nGenerating matrix A …")
    t0 = time.time()
    A = None # Initialize
    AT = None # Initialize
    try:
        # Generate matrix A
        A = generate_with_sparse_random(M, K, DENS_A,
                                        VAL_LOW, VAL_HIGH,
                                        DTYPE, SEED)
        if A is None: raise RuntimeError("Matrix generation returned None.")

        # Calculate B = A.T and ensure it's CSR
        print("Calculating B = A.T and converting to CSR...")
        AT = A.transpose().tocsr()
        t_gen = time.time() - t0 # End generation timer
        print(f"  A : {A.shape}, nnz={A.nnz:,}")
        print(f"  AT: {AT.shape}, nnz={AT.nnz:,} (B=A.T)")
        print(f"Generation & Transpose done in {t_gen:.4f} s")
    except Exception as e:
        print(f"An error occurred during matrix generation or transpose: {e}")
        return # Exit if generation fails


    # --- Save A and AT to COO CSV if requested ---
    t_coo_save = 0 # Initialize timer for this step
    if WRITE_COO_CSV:
        print("\nSaving individual matrices to COO CSVs...")
        t_coo_start = time.time()
        try:
            # Save A: format [a_ik, i, k]
            save_matrix_to_coo_csv(A, OUT_A_COO_CSV, 'a_val', 'row_idx_i', 'col_idx_k')
            # Save AT: format [at_kj, k, j] (value, row index of AT, col index of AT)
            save_matrix_to_coo_csv(AT, OUT_AT_COO_CSV, 'at_val', 'row_idx_k', 'col_idx_j')
            t_coo_save = time.time() - t_coo_start # End timer for this step
            print(f"Individual COO CSVs saved in {t_coo_save:.4f} s")
        except Exception as e:
            print(f"Error during COO CSV saving: {e}")
            # Decide whether to continue or exit based on severity
            # return


    # 2. Decide RAM strategy based on estimated memory usage --------------
    products = estimate_products(A, AT) # Estimate number of output triples
    # Estimate memory needed for prealloc mode: product + i_idx + j_idx
    bytes_per_triple = np.dtype(DTYPE).itemsize + np.dtype(np.int32).itemsize * 2
    est_mem_bytes = products * bytes_per_triple
    est_mem_GiB = est_mem_bytes / (1024**3) # Convert bytes to GiB
    print(f"\nElementary products   : {products:,}")
    print(f"Estimated memory need: {est_mem_GiB:.2f} GiB (using {bytes_per_triple} bytes/triple)")

    # Determine mode based on estimated memory vs available RAM threshold
    mode = "prealloc" if est_mem_GiB <= MAX_RAM_GiB else "stream"
    print(f"Selected mode: {mode.upper()}")

    t_prod = 0 # Initialize product creation/streaming time
    t_csv_write = 0 # Initialize CSV write time (only for prealloc mode)

    # 3. Produce product stream using selected mode -----------------------
    if mode == "prealloc":
        print("\nProducing products in RAM (prealloc mode)...")
        t0 = time.time() # Start timer for product creation
        triples = None # Initialize result array
        try:
            # Generate all triples in memory
            triples = produce_products_prealloc(A, AT)
            t_prod = time.time() - t0 # End timer for product creation
            print(f"  produced {triples.shape[0]:,} triples "
                  f"in {t_prod:.2f} s ({triples.nbytes/1e6:.1f} MB)")

            # Write the pre-allocated array to CSV if requested
            if WRITE_CSV:
                print(f"\nWriting Product CSV → {OUT_CSV} …")
                t_csv_start = time.time() # Start timer for CSV writing
                # Using pandas DataFrame for potentially better performance/handling
                df_prod = pd.DataFrame(triples, columns=['prod', 'row_idx_i', 'col_idx_j'])
                # Ensure index columns have the correct integer type
                df_prod['row_idx_i'] = df_prod['row_idx_i'].astype(np.int32)
                df_prod['col_idx_j'] = df_prod['col_idx_j'].astype(np.int32)
                # Write DataFrame to CSV
                df_prod.to_csv(OUT_CSV, index=False, float_format='%.6g')
                t_csv_write = time.time() - t_csv_start # End timer for CSV writing
                print(f"  Product CSV done in {t_csv_write:.2f} s")
        except (MemoryError, ValueError, IndexError, RuntimeError) as e:
             print(f"Error during prealloc product generation or saving: {e}")
        except Exception as e: # Catch any other unexpected errors
             print(f"An unexpected error occurred during prealloc mode: {e}")

    else: # Streaming mode
        if not WRITE_CSV:
            # Streaming mode fundamentally requires writing to a file
            print("\nError: Streaming mode selected but WRITE_CSV is False. Cannot proceed.")
            # Or raise ValueError("Streaming mode requires WRITE_CSV=True")
        else:
            print(f"\nStreaming products directly to CSV → {OUT_CSV} ...")
            t0 = time.time() # Start timer for streaming process
            try:
                # Generate products and write them directly to CSV in chunks
                rows_written = produce_products_stream(A, AT, OUT_CSV, CHUNK_SZ)
                # In streaming mode, t_prod includes the CSV writing time
                t_prod = time.time() - t0
                print(f"  wrote {rows_written:,} rows in {t_prod:.2f} s")
            except (MemoryError, ValueError, IndexError, RuntimeError) as e:
                 print(f"Error during streaming product generation: {e}")
            except Exception as e: # Catch any other unexpected errors
                 print(f"An unexpected error occurred during streaming mode: {e}")


    # 4. Optional SciPy verification (A @ A.T) ---------------------------
    t_scipy = 0 # Initialize SciPy timer
    if DO_SCIPY_CHECK:
        print("\nSciPy reference multiply (A @ A.T) …")
        t0 = time.time() # Start timer for SciPy multiplication
        try:
            # Perform the standard sparse matrix multiplication
            C = A @ AT
            t_scipy = time.time() - t0 # End timer for SciPy multiplication
            print(f"  C: shape={C.shape}, nnz={C.nnz:,}, "
                  f"time {t_scipy:.2f} s")
        except Exception as e:
             print(f"  Error during SciPy verification: {e}")


    # 5. Summary -----------------------------------------------------------
    t_total = time.time() - t_all0 # Calculate total elapsed time
    print("\n── Summary ─────────────────────────")
    print(f"Matrix generation : {t_gen:.2f} s")
    if WRITE_COO_CSV:
        print(f"COO CSV saving    : {t_coo_save:.2f} s")
    # Product creation time depends on the mode
    print(f"Product creation  : {t_prod:.2f} s ({mode})")
    # Only print separate CSV write time if prealloc mode was used
    if mode == 'prealloc' and WRITE_CSV and t_csv_write > 0:
         print(f"Product CSV write : {t_csv_write:.2f} s (separate from creation)")
    if DO_SCIPY_CHECK and t_scipy > 0:
        print(f"SciPy check       : {t_scipy:.2f} s")
    print(f"Total             : {t_total:.2f} s")
    print("Done.")

# ──────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Optional: Set NumPy error handling if desired, e.g., to catch overflows
    # np.seterr(all='raise') # Raise errors for overflow, invalid operations, etc.
    main()
