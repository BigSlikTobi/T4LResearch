"""
Functions for checking similarity between articles and handling similar content.
"""

import sys
import os
import numpy as np
import datetime
import traceback

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase_init import SupabaseClient
from LLMSetup import initialize_model
from .model_utils import generate_text_with_model
from .db_utils import update_article

def cosine_similarity(embedding1, embedding2):
    """
    Calculate cosine similarity between two embedding vectors.
    
    Args:
        embedding1: First embedding vector
        embedding2: Second embedding vector
        
    Returns:
        Cosine similarity score between 0 and 1
    """
    # Convert to numpy arrays if they aren't already
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    # Calculate cosine similarity
    dot_product = np.dot(vec1, vec2)
    norm_1 = np.linalg.norm(vec1)
    norm_2 = np.linalg.norm(vec2)
    
    if norm_1 == 0 or norm_2 == 0:
        return 0  # Handle zero vectors
        
    return dot_product / (norm_1 * norm_2)

async def check_similarity_and_update(threshold=0.89):
    """
    Check for similarity between unprocessed news results and processed articles.
    If similar articles are found, combine their content and update the existing article.
    
    Args:
        threshold: Cosine similarity threshold for considering articles as similar (0-1)
        
    Returns:
        A list of article IDs that have been processed by similarity check and should be
        skipped in normal processing. Empty list if none were processed.
    """
    processed_article_ids = []  # Track articles processed by this function
    
    print("\n===== SIMILARITY CHECK =====")
    print(f"Starting similarity check between unprocessed and processed articles with threshold: {threshold}...")
    supabase = SupabaseClient()
    llm_dict = initialize_model("openai")  # Use OpenAI for processing combined text
    
    # Get unprocessed news results with embeddings
    unprocessed_response = supabase.client.table("NewsResults").select("*").eq("isProcessed", False).execute()
    if not unprocessed_response.data:
        print("No unprocessed articles to check.")
        print("===== SIMILARITY CHECK COMPLETE =====\n")
        return processed_article_ids
    
    unprocessed_articles = unprocessed_response.data
    print(f"Found {len(unprocessed_articles)} unprocessed articles to check.")
    
    # Count articles with embeddings
    unprocessed_with_embeddings = [a for a in unprocessed_articles if a.get("embedding")]
    print(f"Of these, {len(unprocessed_with_embeddings)} have embeddings ({len(unprocessed_articles) - len(unprocessed_with_embeddings)} missing embeddings).")
    
    # Get processed news results with embeddings
    processed_response = supabase.client.table("NewsResults").select("*").eq("isProcessed", True).execute()
    if not processed_response.data:
        print("No processed articles to compare against.")
        print("===== SIMILARITY CHECK COMPLETE =====\n")
        return processed_article_ids
    
    processed_articles = processed_response.data
    processed_with_embeddings = [a for a in processed_articles if a.get("embedding")]
    print(f"Found {len(processed_articles)} processed articles to compare against.")
    print(f"Of these, {len(processed_with_embeddings)} have embeddings ({len(processed_articles) - len(processed_with_embeddings)} missing embeddings).")
    
    # Debug output
    print(f"Starting detailed similarity checks for {len(unprocessed_with_embeddings)} articles with embeddings...")
    
    # Check for similarity between unprocessed and processed articles
    similar_article_found = False
    
    for unprocessed in unprocessed_articles:
        unprocessed_id = unprocessed.get("id")
        print(f"Checking unprocessed article: {unprocessed.get('uniqueName')}")
        unprocessed_url = unprocessed.get("url", "")
        unprocessed_uniquename = unprocessed.get("uniqueName", "")
        
        # Skip articles without embeddings
        if not unprocessed.get("embedding"):
            print(f"Article {unprocessed_uniquename} has no embedding, skipping similarity check.")
            # Don't add to processed_article_ids so it will be processed normally
            continue
            
        unprocessed_embedding = unprocessed.get("embedding")
        
        # Find similar processed articles
        similar_processed = []
        for processed in processed_articles:
            processed_url = processed.get("url", "")
            processed_uniquename = processed.get("uniqueName", "")
            
            # Skip if comparing with self (based on URL or uniqueName)
            if (processed_url and processed_url == unprocessed_url) or \
               (processed_uniquename and processed_uniquename == unprocessed_uniquename):
                print(f"Skipping self-comparison for article {processed.get('id')}")
                continue
                
            if not processed.get("embedding"):
                continue
                
            processed_embedding = processed.get("embedding")
            
            # Verify both embeddings have the same dimensions
            if len(unprocessed_embedding) != len(processed_embedding):
                print(f"Warning: Embedding dimension mismatch: {len(unprocessed_embedding)} vs {len(processed_embedding)} - skipping comparison")
                continue
            
            # Calculate cosine similarity
            try:
                similarity = cosine_similarity(unprocessed_embedding, processed_embedding)
                print(f"Similarity with article {processed.get('id')}: {similarity:.4f}")
                
                if similarity >= threshold:
                    similar_processed.append({
                        "article": processed,
                        "similarity": similarity
                    })
                    similar_article_found = True
                    print(f"Found similar article with similarity score: {similarity:.4f} - ID: {processed.get('uniqueName')}")
            except Exception as e:
                print(f"Error calculating similarity: {e}")
                continue
        
        # If similar processed articles found, combine content and update
        if similar_processed:
            print(f"Found {len(similar_processed)} similar processed articles to {unprocessed.get('uniqueName')}")
            
            # Sort by similarity score (highest first)
            similar_processed.sort(key=lambda x: x["similarity"], reverse=True)
            
            # Get the NewsArticle record for the most similar article
            most_similar = similar_processed[0]["article"]
            most_similar_id = most_similar.get('id')
            most_similar_uniquename = most_similar.get('uniqueName', '')
            most_similar_url = most_similar.get('url', '')
            
            print(f"Most similar article score: {similar_processed[0]['similarity']:.4f}, ID: {most_similar_id}, UniqueName: {most_similar_uniquename}")
            
            # First try to find the article directly from NewsResult using the ID
            try:
                # First check if the NewsResult is still marked as processed
                # This helps verify the article hasn't been deleted and re-ingested
                news_result_check = supabase.client.table("NewsResults").select("isProcessed").eq("id", most_similar_id).execute()
                
                if not news_result_check.data or len(news_result_check.data) == 0:
                    print(f"Warning: NewsResult {most_similar_id} no longer exists in the database!")
                    # Do not mark as processed - let normal pipeline handle it
                    print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    continue
                    
                if not news_result_check.data[0].get("isProcessed", False):
                    print(f"Warning: NewsResult {most_similar_id} is no longer marked as processed!")
                    print("This suggests the article may have been deleted and reingested.")
                    # Let normal pipeline handle it
                    print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    continue
                
                # First look for articles specifically linked to this NewsResult ID
                article_response = supabase.client.table("NewsArticle").select("*").eq("NewsResult", str(most_similar_id)).execute()
                
                if not article_response.data or len(article_response.data) == 0:
                    print(f"No article found with NewsResult={most_similar_id}, trying with uniqueName")
                    article_response = supabase.client.table("NewsArticle").select("*").eq("NewsResult", most_similar_uniquename).execute()
                
                # If still no results, try searching through all articles to find a match by URL
                if not article_response.data or len(article_response.data) == 0:
                    print(f"No article found with NewsResult={most_similar_uniquename}, will search by URL in all articles")
                    all_articles_response = supabase.client.table("NewsArticle").select("*").execute()
                    
                    if not all_articles_response.data or len(all_articles_response.data) == 0:
                        print("No articles found in the database at all! The article database might be empty.")
                        # Process through normal pipeline
                        print(f"Will process article {unprocessed.get('uniqueName')} normally")
                        continue
                        
                    found_by_url = False
                    found_article = None
                    
                    for article in all_articles_response.data:
                        source_url = article.get("sourceURL", "")
                        if most_similar_url and most_similar_url in source_url:
                            found_article = article
                            found_by_url = True
                            print(f"Found article {article.get('id')} by matching URL {most_similar_url} in sourceURL")
                            break
                        
                    if found_by_url and found_article:
                        article_response = {"data": [found_article]}
                    else:
                        print(f"No article found with URL containing {most_similar_url}")
                        
                        # Check if the article was potentially deleted
                        print("Checking if the similar article might have been deleted...")
                        deleted_check = supabase.client.table("NewsArticle").select("id").eq("Status", "DELETED").execute()
                        if deleted_check.data and len(deleted_check.data) > 0:
                            deleted_ids = [item.get("id") for item in deleted_check.data]
                            print(f"Found {len(deleted_ids)} deleted articles in the database.")
                            
                        # Let the article be processed normally since we couldn't find a match to update
                        print(f"The similar article {most_similar_uniquename} may have been deleted or is otherwise inaccessible.")
                        print(f"Will process article {unprocessed.get('uniqueName')} normally")
                        continue
                
                if not article_response or not article_response.data or len(article_response.data) == 0:
                    print(f"No article found to update for similar article {most_similar_id}")
                    print("This article appears to have similar content to a processed result but the article is not found.")
                    print("It may have been deleted or never created properly.")
                    
                    # Process through normal pipeline
                    print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    continue
                
                # Use the found article
                existing_article = article_response.data[0]
                article_id = existing_article.get("id")
                
                # Check if the article is archived or deleted
                article_status = existing_article.get("Status", "")
                if article_status == "ARCHIVED" or article_status == "DELETED":
                    print(f"Found article {article_id} but its status is {article_status} - cannot update.")
                    print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    continue
                
                # Print debug information about the article we found
                print(f"Using article ID: {article_id} for update")
                print(f"Article headline: {existing_article.get('EnglishHeadline')}")
                print(f"Article source: {existing_article.get('sourceURL')}")
                
                # Get the source content for the unprocessed article
                unprocessed_source_url = unprocessed.get("url")
                
                # Get existing source content
                existing_source_urls = [existing_article.get("sourceURL")]
                
                # Add any additional sources from the similar articles
                for similar in similar_processed:
                    similar_url = similar["article"].get("url")
                    if similar_url and similar_url not in existing_source_urls:
                        existing_source_urls.append(similar_url)
                
                # Generate new article content by combining sources
                print(f"Combining content from {len(existing_source_urls) + 1} sources...")
                
                # Create a list of all sources for the combined content
                all_source_urls = existing_source_urls + [unprocessed_source_url]
                # Filter out None values and duplicates
                all_source_urls = list(filter(None, dict.fromkeys(all_source_urls)))
                all_source_urls_str = "\n".join(all_source_urls)
                
                # Use LLM to generate combined content
                try:
                    # Generate combined English content
                    english_prompt = f"""
                    I have multiple news articles about the same event or topic. Please create a comprehensive, 
                    updated article by combining information from all sources. The article should be in English, 
                    well-structured, and maintain a professional journalistic style. 
                    Keep the most essential and newest information, avoid redundancy, and ensure all key details are included.
                    
                    The sources are:
                    {all_source_urls_str}
                    
                    The existing article content is:
                    {existing_article.get('EnglishArticle', '')}
                    
                    Create an updated and enhanced version that incorporates new information from the other sources.
                    """
                    
                    combined_english_content = generate_text_with_model(llm_dict, english_prompt).strip()
                    
                    # Generate combined German content
                    german_prompt = f"""
                    I have multiple news articles about the same event or topic. Please create a comprehensive, 
                    updated article by combining information from all sources. The article should be in German, 
                    well-structured, and maintain a professional journalistic style.
                    Keep the most essential and newest information, avoid redundancy, and ensure all key details are included.
                    
                    The sources are:
                    {all_source_urls_str}
                    
                    The existing article content is:
                    {existing_article.get('GermanArticle', '')}
                    
                    Create an updated and enhanced version in German that incorporates new information from the other sources.
                    """
                    
                    combined_german_content = generate_text_with_model(llm_dict, german_prompt).strip()
                    
                    # Update the existing article
                    current_time = datetime.datetime.now().isoformat()
                    
                    updates = {
                        "EnglishArticle": combined_english_content,
                        "GermanArticle": combined_german_content,
                        "Status": "UPDATED",  # Fixed: Use uppercase "Status" to match schema
                        # Keep existing headlines
                        "sourceURL": ", ".join(all_source_urls),  # Combine all source URLs
                        "created_at": current_time  # Update the creation date to reflect update time
                    }
                    
                    # Update the article
                    print(f"Updating article {article_id} with combined content...")
                    if await update_article(supabase, article_id, updates):
                        print(f"Successfully updated article {article_id} with combined content")
                        
                        # Mark the unprocessed article as processed
                        supabase.client.table("NewsResults").update({"isProcessed": True}).eq("id", unprocessed_id).execute()
                        print(f"Marked unprocessed article {unprocessed.get('uniqueName')} as processed")
                        
                        # Add this article to the list of processed articles that should be skipped
                        processed_article_ids.append(unprocessed_id)
                    else:
                        print(f"Failed to update article {article_id}")
                        print("This could be due to the article being deleted or having restricted permissions.")
                        print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    
                except Exception as e:
                    print(f"Error generating combined content: {e}")
                    print(f"Exception traceback: {traceback.format_exc()}")
                    print(f"Will process article {unprocessed.get('uniqueName')} normally")
                    continue
                    
            except Exception as e:
                print(f"Error finding or updating article: {e}")
                print(f"Exception traceback: {traceback.format_exc()}")
                print(f"Will process article {unprocessed.get('uniqueName')} normally")
                continue
    
    if not similar_article_found:
        print("No similar articles were found with the current threshold.")
    
    print(f"Processed {len(processed_article_ids)} articles via similarity check.")
    print("===== SIMILARITY CHECK COMPLETE =====\n")
    
    return processed_article_ids