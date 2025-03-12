import math
import sys
import os
import asyncio

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from supabase_init import SupabaseClient
from createArticles.review import check_similarity_and_update

def cosine_similarity(vec1: list, vec2: list) -> float:
    """Compute the cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)

async def check_for_similar_articles(unprocessed_article):
    """
    Check if there are similar articles to the unprocessed article.
    Returns True if similar articles found and processed, False otherwise.
    """
    print(f"Checking if article {unprocessed_article.get('uniqueName')} has similar processed articles...")
    
    # Run similarity check for just this article
    threshold = 0.89  # Use the same threshold as in run_similarity_check.py
    supabase = SupabaseClient()
    
    # Get processed news results with embeddings
    processed_response = supabase.client.table("NewsResults").select("*").eq("isProcessed", True).execute()
    if not processed_response.data:
        print("No processed articles to compare against.")
        return False
    
    processed_articles = processed_response.data
    
    # Skip articles without embeddings
    if not unprocessed_article.get("embedding"):
        print(f"Article {unprocessed_article.get('uniqueName')} has no embedding, skipping similarity check.")
        return False
    
    unprocessed_embedding = unprocessed_article.get("embedding")
    
    # Find similar processed articles
    similar_processed = []
    for processed in processed_articles:
        if not processed.get("embedding"):
            continue
            
        processed_embedding = processed.get("embedding")
        
        # Verify both embeddings have the same dimensions
        if len(unprocessed_embedding) != len(processed_embedding):
            continue
        
        # Calculate cosine similarity
        try:
            similarity = cosine_similarity(unprocessed_embedding, processed_embedding)
            if similarity >= threshold:
                similar_processed.append({
                    "article": processed,
                    "similarity": similarity
                })
                print(f"Found similar article with similarity score: {similarity:.4f} - ID: {processed.get('uniqueName')}")
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            continue
    
    if similar_processed:
        print(f"Found {len(similar_processed)} similar articles to {unprocessed_article.get('uniqueName')}, running update...")
        # Pass the article's ID to check if it was processed
        processed_ids = await check_similarity_and_update(threshold=threshold)
        # Return True if this article ID is in the processed IDs list
        return unprocessed_article.get("id") in processed_ids
    
    return False

async def check_processed_articles_similarity():
    """
    Check for similarity between newly created articles and already processed ones.
    This handles the scenario of finding similar articles between those that were
    already processed (isProcessed = true) but weren't caught in the initial grouping.
    """
    print("\n===== STARTING EXTENDED SIMILARITY CHECK =====")
    print("Running extended similarity check between new and processed articles...")

    await check_similarity_and_update(threshold=0.89)
    print("===== COMPLETED EXTENDED SIMILARITY CHECK =====\n")