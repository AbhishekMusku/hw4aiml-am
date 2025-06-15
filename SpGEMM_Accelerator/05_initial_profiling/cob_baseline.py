import numpy as np
from scipy import sparse
import time

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
    
    # Convert to CSR format for efficient operations5
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
    item_similarity = normalized_item_user @ normalized_item_user_T
    
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
    
    return recommendations

# Function to generate a synthetic sparse user-item matrix for testing
def generate_test_data(n_users=1000, n_items=5000, density=0.01):
    """Generate synthetic sparse user-item matrix"""
    n_nonzero = int(n_users * n_items * density)
    row_indices = np.random.randint(0, n_users, n_nonzero)
    col_indices = np.random.randint(0, n_items, n_nonzero)
    values = np.random.randint(1, 6, n_nonzero)  # Ratings 1-5
    
    return sparse.csr_matrix((values, (row_indices, col_indices)), 
                           shape=(n_users, n_items))

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

# Main function to run the test
def main():
    # Generate test data
    print("Generating test data...")
    # Generate a larger test dataset
    user_item_matrix = generate_test_data(n_users=10000, n_items=10000, density=0.05)
    print(f"Matrix density: {user_item_matrix.nnz / (user_item_matrix.shape[0] * user_item_matrix.shape[1]):.4f}")
    
    # Run collaborative filtering
    start_time = time.time()
    recommendations = item_based_collaborative_filtering(user_item_matrix, k=10)
    total_time = time.time() - start_time
    
    print(f"Total processing time: {total_time:.2f} seconds")
    print(f"Recommendations matrix shape: {recommendations.shape}")
    print(f"Recommendations density: {recommendations.nnz / (recommendations.shape[0] * recommendations.shape[1]):.4f}")

        # Example usage:
    #recommendations = item_based_collaborative_filtering(user_item_matrix)
    top_recommendations = get_top_recommendations(recommendations, user_item_matrix, n=5)

    # Print recommendations for first 3 users
    for user_id in range(3):
        print(f"User {user_id} recommendations:")
        for item_id, predicted_rating in top_recommendations[user_id]:
            print(f"  Item {item_id}: Predicted rating {predicted_rating:.2f}")
        print()

if __name__ == "__main__":
    main()
