import numpy as np
import pandas as pd
import time

def load_user_item_matrix_from_npy(filename):
    """Load dense matrix directly from .npy file (zeros already preserved)"""
    print(f"Loading dense matrix from {filename}...")
    
    start_time = time.time()
    dense_matrix = np.load(filename)
    load_time = time.time() - start_time
    
    print(f"Matrix loaded in {load_time:.4f} seconds!")
    print(f"  Shape: {dense_matrix.shape}")
    print(f"  Data type: {dense_matrix.dtype}")
    print(f"  Non-zero entries: {np.count_nonzero(dense_matrix):,}")
    print(f"  Zero entries: {np.count_nonzero(dense_matrix == 0):,}")
    
    return dense_matrix

def basic_matrix_multiply(A, B):
    """Basic matrix multiplication using for loops"""
    M, K = A.shape
    K2, N = B.shape
    
    if K != K2:
        raise ValueError(f"Matrix dimension mismatch: {K} != {K2}")
    
    C = np.zeros((M, N), dtype=np.float32)
    
    for i in range(M):
        for j in range(N):
            for k in range(K):
                C[i, j] += A[i, k] * B[k, j]
    
    return C

def item_based_collaborative_filtering_dense(user_item_matrix, k=10):
    """Collaborative filtering using basic matrix multiplication"""
    n_users, n_items = user_item_matrix.shape
    
    # Step 1: Calculate item similarity
    item_user = user_item_matrix.T
    
    # Calculate norms
    item_norms = np.sqrt(np.sum(item_user**2, axis=1))
    item_norms[item_norms == 0] = 1
    
    # Normalize
    normalized_item_user = np.zeros_like(item_user, dtype=np.float32)
    for i in range(n_items):
        normalized_item_user[i, :] = item_user[i, :] / item_norms[i]
    
    # Basic matrix multiplication for similarity
    spgemm_start = time.time()
    item_similarity = basic_matrix_multiply(normalized_item_user, normalized_item_user.T)
    spgemm_time = time.time() - spgemm_start

    # Step 2: Filter to top k
    for i in range(n_items):
        sim_items = item_similarity[i, :]
        sim_items[i] = 0
        
        if len(sim_items) > k:
            threshold = np.partition(sim_items, -k)[-k]
            sim_items[sim_items < threshold] = 0
    
    # Step 3: Generate recommendations
    recommendations = basic_matrix_multiply(user_item_matrix, item_similarity)
    
    return recommendations, spgemm_time

def get_top_recommendations(recommendations_matrix, user_item_matrix, n=5):
    """Get top N recommendations per user"""
    n_users = recommendations_matrix.shape[0]
    user_recommendations = {}
    
    for user_id in range(n_users):
        unrated_items = np.where(user_item_matrix[user_id, :] == 0)[0]
        
        if len(unrated_items) == 0:
            user_recommendations[user_id] = []
            continue
            
        predicted_ratings = recommendations_matrix[user_id, unrated_items]
        sorted_indices = np.argsort(-predicted_ratings)
        top_indices = sorted_indices[:n]
        
        recommended_items = [(unrated_items[idx], recommendations_matrix[user_id, unrated_items[idx]]) 
                           for idx in top_indices]
        
        user_recommendations[user_id] = recommended_items
    
    return user_recommendations

def save_recommendations_to_csv(user_recommendations, filename):
    """Save recommendations to CSV"""
    recommendations_list = []
    for user_id, items in user_recommendations.items():
        for item_id, predicted_rating in items:
            recommendations_list.append({
                'user_id': user_id,
                'item_id': item_id,
                'predicted_rating': predicted_rating
            })
    
    df = pd.DataFrame(recommendations_list)
    df.to_csv(filename, index=False)

def save_performance_stats(stats, filename):
    """Save performance stats to CSV"""
    df = pd.DataFrame([stats])
    df.to_csv(filename, index=False)

def main():
    # Configuration
    NPY_FILENAME = "user_item_matrix_dense.npy"
    K_SIMILAR = 10
    N_RECOMMENDATIONS = 5
    RECOMMENDATIONS_CSV = "recommendations_basic_similarity.csv"
    PERFORMANCE_CSV = "performance_stats_basic_similarity.csv"
    
    # Performance tracking
    perf_stats = {}
    overall_start = time.time()
    
    # Load data
    load_start = time.time()
    user_item_matrix = load_user_item_matrix_from_npy(NPY_FILENAME)
    load_time = time.time() - load_start
    
    # Run collaborative filtering
    cf_start = time.time()
    recommendations, spgemm_time = item_based_collaborative_filtering_dense(user_item_matrix, k=K_SIMILAR)
    cf_time = time.time() - cf_start
    
    # Get top recommendations
    rec_start = time.time()
    top_recommendations = get_top_recommendations(recommendations, user_item_matrix, n=N_RECOMMENDATIONS)
    rec_time = time.time() - rec_start
    
    # Store stats
    total_time = time.time() - overall_start
    perf_stats = {
        'data_load_time_sec': load_time,
        'collaborative_filtering_time_sec': cf_time,
        'spgemm_core_time_sec': spgemm_time,
        'top_recommendations_time_sec': rec_time,
        'total_execution_time_sec': total_time,
        'n_users': user_item_matrix.shape[0],
        'n_items': user_item_matrix.shape[1],
        'k_similar_items': K_SIMILAR,
        'n_recommendations_per_user': N_RECOMMENDATIONS
    }
    
    # Save outputs
    save_recommendations_to_csv(top_recommendations, RECOMMENDATIONS_CSV)
    save_performance_stats(perf_stats, PERFORMANCE_CSV)

if __name__ == "__main__":
    main()