import numpy as np
from scipy import sparse
import pandas as pd
import time

"""
Advanced Sparse Collaborative Filtering Implementation

Implements item-based collaborative filtering using optimized SciPy sparse matrices.
Serves as performance baseline for comparing against MatRaptor hardware acceleration.

INPUT:
- user_item_matrix_complete.csv: Complete user-item ratings matrix (user_id, item_id, rating)

OUTPUTS:
- recommendations.csv: Top N recommendations per user (user_id, item_id, predicted_rating)
- performance_stats.csv: Detailed timing and matrix statistics for benchmarking
"""

def load_user_item_matrix_from_csv(filename):
    """
    Load user-item matrix from CSV file
    
    Parameters:
    - filename: CSV file with columns [user_id, item_id, rating]
    
    Returns:
    - Sparse CSR matrix (users × items)
    """
    print(f"Loading user-item matrix from {filename}...")
    
    try:
        # Read CSV file
        df = pd.read_csv(filename)
        print(f"Loaded {len(df)} ratings from CSV")
        
        # Get expected column names (flexible naming)
        possible_user_cols = ['user_id', 'user', 'row', 'row_idx_i']
        possible_item_cols = ['item_id', 'movie_id', 'item', 'col', 'col_idx_k'] 
        possible_rating_cols = ['rating', 'value', 'val', 'a_val']
        
        # Find actual column names
        user_col = None
        item_col = None
        rating_col = None
        
        for col in df.columns:
            if col in possible_user_cols:
                user_col = col
            elif col in possible_item_cols:
                item_col = col
            elif col in possible_rating_cols:
                rating_col = col
        
        if user_col is None or item_col is None or rating_col is None:
            raise ValueError(f"Could not find required columns. Available columns: {list(df.columns)}")
        
        print(f"Using columns: user={user_col}, item={item_col}, rating={rating_col}")
        
        # Get matrix dimensions
        max_user = df[user_col].max()
        max_item = df[item_col].max()
        n_users = max_user + 1
        n_items = max_item + 1
        
        print(f"Matrix dimensions: {n_users} users × {n_items} items")
        
        # Create sparse matrix
        user_item_matrix = sparse.csr_matrix(
            (df[rating_col].values, (df[user_col].values, df[item_col].values)),
            shape=(n_users, n_items)
        )
        
        print(f"Matrix loaded successfully!")
        print(f"  Shape: {user_item_matrix.shape}")
        print(f"  Non-zero entries: {user_item_matrix.nnz:,}")
        print(f"  Density: {user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]):.4f}")
        
        return user_item_matrix
        
    except Exception as e:
        print(f"Error loading matrix from CSV: {e}")
        raise

def item_based_collaborative_filtering(user_item_matrix, k=10):
    """
    Item-based collaborative filtering recommendation system
    
    Parameters:
    - user_item_matrix: Sparse matrix (users × items) of ratings or interactions
    - k: Number of similar items to consider
    
    Returns:
    - recommendations: Matrix of predicted ratings
    """
    # Get dimensions
    n_users, n_items = user_item_matrix.shape
    print(f"Processing matrix with {n_users} users and {n_items} items")
    
    # Step 1: Calculate item-item similarity matrix
    start_time = time.time()
    print("Calculating item-item similarity matrix...")
    
    # Convert to CSR format for efficient operations
    if not sparse.isspmatrix_csr(user_item_matrix):
        user_item_matrix_csr = sparse.csr_matrix(user_item_matrix)
    else:
        user_item_matrix_csr = user_item_matrix
    
    # Transpose to get item-user matrix
    item_user = user_item_matrix_csr.T
    
    # Calculate similarity (cosine similarity)
    # This is a sparse × sparse matrix multiplication operation
    # This is the main bottleneck we'd offload to MATRaptor
    norms = sparse.linalg.norm(item_user, axis=1)
    norms[norms == 0] = 1  # Avoid division by zero
    
    # Create diagonal matrix of inverse norms
    inv_norms = sparse.diags(1/norms)
    
    # Normalize item vectors
    normalized_item_user = inv_norms @ item_user
    normalized_item_user_T = normalized_item_user.T
    # Calculate cosine similarity (sparse × sparse operation)
    spgemm_start = time.time()
    item_similarity = normalized_item_user @ normalized_item_user_T
    ##global spgemm_core_time  # Make it accessible outside function
    spgemm_time = time.time() - spgemm_start
    
    similarity_time = time.time() - start_time
    print(f"Similarity calculation took {similarity_time:.2f} seconds")
    
    # Step 2: Keep only top k similar items for each item
    start_time = time.time()
    print(f"Filtering to keep only top {k} similar items...")
    
    # Convert to array for top-k filtering (this could be optimized)
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
    
    # Step 3: Generate recommendations
    start_time = time.time()
    print("Generating recommendations...")
    
    # This is another sparse × sparse matrix multiplication
    # Could also potentially be offloaded to MATRaptor
    recommendations = user_item_matrix_csr @ filtered_item_similarity
    
    recommend_time = time.time() - start_time
    print(f"Recommendation generation took {recommend_time:.2f} seconds")
    
    return recommendations, spgemm_time

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
    # Configuration
    CSV_FILENAME = "user_item_matrix_complete.csv"  # Input CSV file
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
        # Load user-item matrix from CSV
        print("Loading data...")
        load_start = time.time()
        user_item_matrix = load_user_item_matrix_from_csv(CSV_FILENAME)
        load_time = time.time() - load_start
        
        # Store matrix info in stats
        perf_stats.update({
            'data_load_time_sec': load_time,
            'n_users': user_item_matrix.shape[0],
            'n_items': user_item_matrix.shape[1],
            'n_ratings': user_item_matrix.nnz,
            'matrix_density': user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]),
            'k_similar_items': K_SIMILAR
        })
        
        # Run collaborative filtering
        print("\nRunning collaborative filtering...")
        cf_start = time.time()
        recommendations, spgemm_time = item_based_collaborative_filtering(user_item_matrix, k=K_SIMILAR)
        cf_time = time.time() - cf_start
        
        # Update performance stats
        perf_stats.update({
            'collaborative_filtering_time_sec': cf_time,
            'spgemm_core_time_sec': spgemm_time,
            'recommendations_shape_users': recommendations.shape[0],
            'recommendations_shape_items': recommendations.shape[1],
            'recommendations_nnz': recommendations.nnz,
            'recommendations_density': recommendations.nnz / (recommendations.shape[0] * recommendations.shape[1])
        })
        
        print(f"\nTotal processing time: {cf_time:.2f} seconds")
        print(f"Recommendations matrix shape: {recommendations.shape}")
        print(f"Recommendations density: {recommendations.nnz / (recommendations.shape[0] * recommendations.shape[1]):.4f}")

        # Get top recommendations for users
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
            
    except FileNotFoundError:
        print(f"Error: Could not find input file '{CSV_FILENAME}'")
        print("Please make sure you've run the matrix generator first to create the input data.")
    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()