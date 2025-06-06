import numpy as np
from scipy import sparse
import pandas as pd
import time

"""
Item-Based Collaborative Filtering with Verilog Similarity Input

INPUTS:
- user_item_matrix_processed.npz: Preprocessed user-item matrix from partial_prod_gen_adv_int.py
- out.csv: Item similarity matrix from Verilog (scaled integers)

OUTPUTS:
- recommendations.csv: Top N recommendations per user (user_id, item_id, predicted_rating)
- performance_stats.csv: Processing time and matrix statistics
"""

def load_user_item_matrix_from_npz(filename):
    """
    Load preprocessed user-item matrix from .npz file
    
    Parameters:
    - filename: NPZ file from partial_prod_gen_adv_int.py
    
    Returns:
    - Sparse CSR matrix (users × items)
    """
    print(f"Loading preprocessed user-item matrix from {filename}...")
    
    try:
        user_item_matrix = sparse.load_npz(filename)
        
        print(f"Matrix loaded successfully!")
        print(f"  Shape: {user_item_matrix.shape}")
        print(f"  Non-zero entries: {user_item_matrix.nnz:,}")
        print(f"  Density: {user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]):.4f}")
        
        return user_item_matrix
        
    except Exception as e:
        print(f"Error loading matrix from NPZ: {e}")
        raise

def load_similarity_matrix_from_csv(filename, n_items, scale_factor=65536):
    """
    Load item similarity matrix from Verilog output CSV and descale
    
    Parameters:
    - filename: CSV file with (row, col, value) format from Verilog
    - n_items: Number of items (for matrix dimensions)
    - scale_factor: Scaling factor used in preprocessing (default: 65536)
    
    Returns:
    - Sparse CSR matrix (items × items) with descaled similarity values
    """
    print(f"Loading item similarity matrix from {filename}...")
    print(f"Descaling with factor: {scale_factor}")
    
    try:
        # Read CSV file - skip comment lines and add column names
        df = pd.read_csv(filename, 
                        comment='#',           # Skip lines starting with #
                        header=None,           # No column headers in file
                        names=['row', 'col', 'value'])  # Assign column names, use default comma separator
        
        print(f"Loaded {len(df)} similarity entries from CSV")
        print(f"Sample rows from CSV:")
        print(df.head())
        
        # Ensure proper data types
        df['row'] = df['row'].astype(int)
        df['col'] = df['col'].astype(int)
        df['value'] = df['value'].astype(float)
        
        # Descale the values (convert back from integers to floats)
        descaled_values = df['value'].values.astype(np.float32) / scale_factor
        
        print(f"Sample scaled values: {df['value'].values[:5]}")
        print(f"Sample descaled values: {descaled_values[:5]}")
        
        # Create sparse similarity matrix
        similarity_matrix = sparse.csr_matrix(
            (descaled_values, (df['row'].values, df['col'].values)),
            shape=(n_items, n_items),
            dtype=np.float32
        )
        
        print(f"Similarity matrix loaded successfully!")
        print(f"  Shape: {similarity_matrix.shape}")
        print(f"  Non-zero entries: {similarity_matrix.nnz:,}")
        print(f"  Density: {similarity_matrix.nnz / (similarity_matrix.shape[0] * similarity_matrix.shape[1]):.4f}")
        print(f"  Value range: [{similarity_matrix.data.min():.6f}, {similarity_matrix.data.max():.6f}]")
        
        return similarity_matrix
        
    except Exception as e:
        print(f"Error loading similarity matrix from CSV: {e}")
        raise

def item_based_collaborative_filtering_with_precomputed_similarity(user_item_matrix, item_similarity, k=10):
    """
    Item-based collaborative filtering with precomputed similarity matrix
    
    Parameters:
    - user_item_matrix: Sparse matrix (users × items) of ratings
    - item_similarity: Precomputed item similarity matrix (items × items)
    - k: Number of similar items to consider
    
    Returns:
    - recommendations: Matrix of predicted ratings
    """
    # Get dimensions
    n_users, n_items = user_item_matrix.shape
    print(f"Processing matrix with {n_users} users and {n_items} items")
    
    # Convert to CSR format for efficient operations
    if not sparse.isspmatrix_csr(user_item_matrix):
        user_item_matrix_csr = sparse.csr_matrix(user_item_matrix)
    else:
        user_item_matrix_csr = user_item_matrix
    
    # SKIP STEP 2 - Use precomputed similarity matrix from Verilog
    print("Using precomputed item similarity matrix from Verilog...")
    
    # Step 3: Keep only top k similar items for each item
    start_time = time.time()
    print(f"Filtering to keep only top {k} similar items...")
    
    # Convert to array for top-k filtering
    item_similarity_array = item_similarity.toarray()
    
    # For each item, keep only the top k most similar items
    for i in range(n_items):
        sim_items = item_similarity_array[i, :]
        # Set the similarity with itself to 0
        sim_items[i] = 0
        
        # Find threshold for top k
        if len(sim_items) > k:
            # Get kth largest value
            threshold = np.partition(sim_items, -k)[-k]
            # Set values below threshold to 0
            sim_items[sim_items < threshold] = 0
    
    # Convert back to sparse matrix
    filtered_item_similarity = sparse.csr_matrix(item_similarity_array)
    
    filter_time = time.time() - start_time
    print(f"Filtering took {filter_time:.2f} seconds")
    
    # Step 4: Generate recommendations
    start_time = time.time()
    print("Generating recommendations...")
    
    # Sparse × sparse matrix multiplication
    recommendations = user_item_matrix_csr @ filtered_item_similarity
    
    recommend_time = time.time() - start_time
    print(f"Recommendation generation took {recommend_time:.2f} seconds")
    
    return recommendations

def get_top_recommendations(recommendations_matrix, user_item_matrix, n=5):
    """
    Get top N recommendations for each user
    
    Parameters:
    - recommendations_matrix: Matrix of predicted ratings
    - user_item_matrix: Original user-item matrix with actual ratings
    - n: Number of recommendations to return per user
    
    Returns:
    - Dictionary mapping user IDs to their recommended items
    """
    # Convert to arrays for easier manipulation
    if sparse.issparse(recommendations_matrix):
        recommendations_array = recommendations_matrix.toarray()
    else:
        recommendations_array = recommendations_matrix
        
    if sparse.issparse(user_item_matrix):
        user_item_array = user_item_matrix.toarray()
    else:
        user_item_array = user_item_matrix
    
    n_users = recommendations_array.shape[0]
    user_recommendations = {}
    
    for user_id in range(n_users):
        # Get items the user hasn't rated yet
        unrated_items = np.where(user_item_array[user_id, :] == 0)[0]
        
        if len(unrated_items) == 0:
            user_recommendations[user_id] = []
            continue
            
        # Get predicted ratings for unrated items
        predicted_ratings = recommendations_array[user_id, unrated_items]
        
        # Sort by predicted rating (highest first)
        sorted_indices = np.argsort(-predicted_ratings)
        top_indices = sorted_indices[:n]
        
        # Get the actual item IDs and their predicted ratings
        recommended_items = [(unrated_items[idx], recommendations_array[user_id, unrated_items[idx]]) 
                           for idx in top_indices]
        
        user_recommendations[user_id] = recommended_items
    
    return user_recommendations

def save_recommendations_to_csv(user_recommendations, filename="recommendations.csv"):
    """
    Save user recommendations to CSV file
    
    Parameters:
    - user_recommendations: Dictionary from get_top_recommendations()
    - filename: Output CSV filename
    """
    print(f"Saving recommendations to {filename}...")
    
    recommendations_list = []
    for user_id, items in user_recommendations.items():
        for item_id, predicted_rating in items:
            recommendations_list.append({
                'user_id': user_id,
                'item_id': item_id,
                'predicted_rating': predicted_rating
            })
    
    if recommendations_list:
        df = pd.DataFrame(recommendations_list)
        df.to_csv(filename, index=False)
        print(f"Saved {len(df)} recommendations to {filename}")
    else:
        print("No recommendations to save")

def save_performance_stats(stats, filename="performance_stats.csv"):
    """
    Save performance statistics to CSV
    
    Parameters:
    - stats: Dictionary containing performance metrics
    - filename: Output CSV filename
    """
    print(f"Saving performance statistics to {filename}...")
    
    df = pd.DataFrame([stats])
    df.to_csv(filename, index=False)
    print(f"Performance stats saved to {filename}")

# Main function to run the test
def main():
    print("=" * 60)
    print("COLLABORATIVE FILTERING WITH VERILOG SIMILARITY")
    print("=" * 60)
    
    # Configuration
    USER_ITEM_NPZ = "user_item_matrix_processed.npz"  # From partial_prod_gen_adv_int.py
    SIMILARITY_CSV = "out.csv"  # From Verilog
    SCALE_FACTOR = 65536  # Must match partial_prod_gen_adv_int.py
    
    K_SIMILAR = 10  # Number of similar items to consider
    N_RECOMMENDATIONS = 5  # Number of recommendations per user
    
    # Output file configuration
    SAVE_RECOMMENDATIONS = True
    SAVE_PERFORMANCE = True
    
    RECOMMENDATIONS_CSV = "recommendations.csv"
    PERFORMANCE_CSV = "performance_stats.csv"
    
    # Initialize performance tracking
    perf_stats = {}
    overall_start = time.time()
    
    try:
        # Step 1: Load preprocessed user-item matrix
        print("\n" + "="*50)
        print("STEP 1: LOADING PREPROCESSED USER-ITEM MATRIX")
        print("="*50)
        load_start = time.time()
        user_item_matrix = load_user_item_matrix_from_npz(USER_ITEM_NPZ)
        load_time = time.time() - load_start
        
        n_users, n_items = user_item_matrix.shape
        
        # Step 2: Load item similarity matrix from Verilog output
        print("\n" + "="*50)
        print("STEP 2: LOADING ITEM SIMILARITY FROM VERILOG")
        print("="*50)
        similarity_start = time.time()
        item_similarity = load_similarity_matrix_from_csv(SIMILARITY_CSV, n_items, SCALE_FACTOR)
        similarity_load_time = time.time() - similarity_start
        
        # Store matrix info in stats
        perf_stats.update({
            'data_load_time_sec': load_time,
            'similarity_load_time_sec': similarity_load_time,
            'n_users': n_users,
            'n_items': n_items,
            'n_ratings': user_item_matrix.nnz,
            'matrix_density': user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]),
            'similarity_nnz': item_similarity.nnz,
            'similarity_density': item_similarity.nnz / (item_similarity.shape[0] * item_similarity.shape[1]),
            'k_similar_items': K_SIMILAR,
            'scale_factor': SCALE_FACTOR
        })
        
        # Step 3: Run collaborative filtering with precomputed similarity
        print("\n" + "="*50)
        print("STEP 3: COLLABORATIVE FILTERING")
        print("="*50)
        cf_start = time.time()
        recommendations = item_based_collaborative_filtering_with_precomputed_similarity(
            user_item_matrix, item_similarity, k=K_SIMILAR)
        cf_time = time.time() - cf_start
        
        # Update performance stats
        perf_stats.update({
            'collaborative_filtering_time_sec': cf_time,
            'recommendations_shape_users': recommendations.shape[0],
            'recommendations_shape_items': recommendations.shape[1],
            'recommendations_nnz': recommendations.nnz,
            'recommendations_density': recommendations.nnz / (recommendations.shape[0] * recommendations.shape[1])
        })
        
        print(f"\nCollaborative filtering time: {cf_time:.2f} seconds")
        print(f"Recommendations matrix shape: {recommendations.shape}")
        print(f"Recommendations density: {recommendations.nnz / (recommendations.shape[0] * recommendations.shape[1]):.4f}")

        # Step 4: Get top recommendations for users
        print(f"\nGenerating top {N_RECOMMENDATIONS} recommendations per user...")
        rec_start = time.time()
        top_recommendations = get_top_recommendations(recommendations, user_item_matrix, n=N_RECOMMENDATIONS)
        rec_time = time.time() - rec_start
        
        # Update performance stats
        total_recommendations = sum(len(recs) for recs in top_recommendations.values())
        perf_stats.update({
            'top_recommendations_time_sec': rec_time,
            'n_recommendations_per_user': N_RECOMMENDATIONS,
            'total_recommendations_generated': total_recommendations
        })

        # Print sample recommendations
        print(f"\nSample recommendations:")
        for user_id in range(min(3, len(top_recommendations))):
            print(f"User {user_id} recommendations:")
            if len(top_recommendations[user_id]) == 0:
                print("  No recommendations (user has rated all items)")
            else:
                for item_id, predicted_rating in top_recommendations[user_id]:
                    print(f"  Item {item_id}: Predicted rating {predicted_rating:.2f}")
            print()
        
        # Calculate total execution time
        total_time = time.time() - overall_start
        perf_stats['total_execution_time_sec'] = total_time
        
        # Save outputs to CSV files
        print("\n" + "="*50)
        print("SAVING OUTPUTS TO CSV FILES")
        print("="*50)
        
        if SAVE_RECOMMENDATIONS:
            save_recommendations_to_csv(top_recommendations, RECOMMENDATIONS_CSV)
        
        if SAVE_PERFORMANCE:
            save_performance_stats(perf_stats, PERFORMANCE_CSV)
        
        print(f"\nAll outputs saved! Total execution time: {total_time:.2f} seconds")
        print(f"Verilog similarity computation was successfully integrated!")
            
    except FileNotFoundError as e:
        print(f"Error: Could not find input file - {e}")
        print("Make sure you have:")
        print(f"1. {USER_ITEM_NPZ} (from partial_prod_gen_adv_int.py)")
        print(f"2. {SIMILARITY_CSV} (from Verilog)")
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()



    