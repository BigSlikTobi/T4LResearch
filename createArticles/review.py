import os
import sys
import re
import requests
from dotenv import load_dotenv
import urllib.parse
# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase_init import SupabaseClient
from LLMSetup import initialize_model
import numpy as np

def clean_text(text: str) -> str:
    """Remove all '\n' sequences, clean up spacing, and remove leading quotes."""
    if not text:
        return text
    
    # Replace literal '\n' sequences with spaces
    cleaned = text.replace('\\n', ' ')
    # Replace actual newlines with spaces
    cleaned = cleaned.replace('\n', ' ')
    # Replace multiple spaces with a single space
    cleaned = re.sub(r'\s+', ' ', cleaned)
    # Remove leading quotes and space after quote if present
    cleaned = re.sub(r'^[""]\s*', '', cleaned)
    # Final trim
    cleaned = cleaned.strip()
    
    return cleaned

def verify_image_accessibility(image_url: str) -> bool:
    """
    Verify if an image URL is accessible by attempting to fetch it.
    Returns True if the image is accessible, False otherwise.
    """
    try:
        if not image_url or not image_url.strip():
            print("Empty image URL")
            return False
        
        # Clean the URL
        image_url = image_url.strip()
        
        # Add https:// if the URL starts with //
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
            
        # Ensure URL is properly encoded
        parsed = urllib.parse.urlparse(image_url)
        encoded_url = urllib.parse.urlunparse(
            parsed._replace(
                path=urllib.parse.quote(parsed.path),
                query=urllib.parse.quote(parsed.query, safe='=&')
            )
        )
        
        print(f"Checking image URL: {encoded_url}")
        
        # Make request with extended timeout and allow redirects
        response = requests.get(
            encoded_url,
            timeout=15,
            allow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            },
            stream=True  # Don't download the whole image, just headers
        )
        
        # Print response details for debugging
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Check status code first (accept 200-299 range)
        if not (200 <= response.status_code < 300):
            print(f"Image URL returned status code {response.status_code}: {encoded_url}")
            return False
            
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        content_length = response.headers.get('content-length')
        
        print(f"Content type: {content_type}")
        print(f"Content length: {content_length}")
        
        # More permissive content type checking
        valid_content_types = ['image', 'application/octet-stream', 'binary/octet-stream']
        
        if not any(t in content_type for t in valid_content_types):
            # If content type check fails, try to check file extension
            file_ext = os.path.splitext(parsed.path)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
            
            if file_ext not in valid_extensions:
                print(f"URL does not appear to be an image (content-type: {content_type}, extension: {file_ext}): {encoded_url}")
                return False
        
        # Consider it valid if we got this far
        return True
        
    except requests.Timeout:
        print(f"Timeout while accessing image URL: {image_url}")
        return False
    except requests.RequestException as e:
        print(f"Error accessing image URL {image_url}: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error checking image URL {image_url}: {str(e)}")
        return False

def update_article(supabase_client, article_id: int, updates: dict) -> bool:
    """Update the article with cleaned text."""
    try:
        response = supabase_client.client.table('NewsArticle').update(updates)\
            .eq('id', article_id).execute()
        
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating article {article_id}: {e}")
        return False

async def review_article_fields(record_id: int, news_result_unique_name: str) -> bool:
    """
    Review article fields and handle invalid articles.
    Returns True if article passes review, False if it fails and is deleted.
    
    Now includes fallback image selection if the primary image is not accessible.
    """
    supabase = SupabaseClient()
    print(f"=== REVIEW: Starting review for article {record_id} with news result {news_result_unique_name} ===")
    
    # Get the article record
    response = supabase.client.table("NewsArticle").select("*").eq("id", record_id).execute()
    if not response.data or len(response.data) == 0:
        print(f"No article found with ID {record_id}")
        return False
    
    article = response.data[0]
    
    # Check required fields
    required_fields = {
        "EnglishArticle": article.get("EnglishArticle", ""),
        "GermanArticle": article.get("GermanArticle", ""),
        "EnglishHeadline": article.get("EnglishHeadline", ""),
        "GermanHeadline": article.get("GermanHeadline", "")
    }
    
    # Check if any required field is empty
    if any(not field.strip() for field in required_fields.values()):
        print(f"Article {record_id} failed review - missing required content")
        await delete_article_and_update_news_result(supabase, record_id, news_result_unique_name)
        return False
    
    # Check image accessibility
    image_url = article.get("imageUrl", "")
    print(f"\nREVIEW: Checking image accessibility for article {record_id}")
    print(f"REVIEW: Image URL: {image_url}")
    
    if not verify_image_accessibility(image_url):
        print(f"REVIEW: Primary image is not accessible: {image_url}. Attempting to find backup images...")
        
        # Try to find backup images using the article content and keywords
        try:
            from getImage import search_image
            
            # Use article content and headline to generate new search keywords
            content = article.get("EnglishArticle", "")
            headline = article.get("EnglishHeadline", "")
            search_text = f"{headline}\n{content[:500]}"  # Use headline and part of content
            
            # Get team info if available to use as keyword
            team = article.get("Team", "")
            keywords = [team] if team and team.strip() else []
            print(f"REVIEW: Searching for backup images using keywords: {keywords} and headline: {headline[:50]}...")
            
            # Search for multiple backup images (get 5 candidates)
            backup_images = await search_image(search_text, keywords, return_multiple=True, num_images=5)
            
            if not backup_images:
                print("REVIEW: No backup images found")
                await delete_article_and_update_news_result(supabase, record_id, news_result_unique_name)
                return False
                
            print(f"REVIEW: Found {len(backup_images)} backup image candidates")
                
            # Try each backup image until we find one that's accessible
            accessible_image = None
            for i, img_data in enumerate(backup_images):
                backup_img_url = img_data.get("image")
                if not backup_img_url:
                    continue
                    
                print(f"REVIEW: Checking backup image {i+1}: {backup_img_url}")
                if verify_image_accessibility(backup_img_url):
                    print(f"REVIEW: Found accessible backup image: {backup_img_url}")
                    accessible_image = img_data
                    break
                else:
                    print(f"REVIEW: Backup image {i+1} is not accessible")
            
            # If we found an accessible backup image, update the article
            if accessible_image:
                updates = {
                    "imageUrl": accessible_image.get("image", ""),
                    "imageSource": accessible_image.get("url", ""),
                    "imageAltText": accessible_image.get("imageAltText", ""),
                    "imageAttribution": accessible_image.get("imageAttribution", "")
                }
                
                print(f"REVIEW: Updating article {record_id} with new image: {updates['imageUrl']}")
                
                if update_article(supabase, record_id, updates):
                    print(f"REVIEW: Article {record_id} updated with backup image")
                    return True
                else:
                    print(f"REVIEW: Failed to update article {record_id} with backup image")
            else:
                print(f"REVIEW: None of the backup images are accessible")
            
            # If we reach here, all image attempts failed
            print(f"REVIEW: Article {record_id} failed review - could not find an accessible image")
            await delete_article_and_update_news_result(supabase, record_id, news_result_unique_name)
            return False
            
        except Exception as e:
            print(f"REVIEW: Error while searching for backup images: {e}")
            import traceback
            print(f"REVIEW: Exception traceback: {traceback.format_exc()}")
            await delete_article_and_update_news_result(supabase, record_id, news_result_unique_name)
            return False
    else:
        print(f"REVIEW: Image accessibility check passed for article {record_id}")
    
    print(f"=== REVIEW: Article {record_id} successfully passed review ===")
    return True

async def delete_article_and_update_news_result(supabase, record_id: int, news_result_unique_name: str):
    """Helper function to delete article and update NewsResults"""
    try:
        # Delete the article
        supabase.client.table("NewsArticle").delete().eq("id", record_id).execute()
        print(f"Deleted article {record_id} from NewsArticle table")
        
        # Update NewsResults isProcessed to false
        supabase.client.table("NewsResults").update(
            {"isProcessed": False}
        ).eq("uniqueName", news_result_unique_name).execute()
        print(f"Updated NewsResults record {news_result_unique_name} to isProcessed=false")
    except Exception as e:
        print(f"Error during cleanup of invalid article: {e}")

async def check_similarity_and_update(threshold=0.85):
    """
    Check for similarity between unprocessed news results and processed articles.
    If similar articles are found, combine their content and update the existing article.
    
    Args:
        threshold: Cosine similarity threshold for considering articles as similar (0-1)
    """
    print("Starting similarity check between unprocessed and processed articles...")
    supabase = SupabaseClient()
    llm = initialize_model("openai")  # Use OpenAI for processing combined text
    
    # Get unprocessed news results with embeddings
    unprocessed_response = supabase.client.table("NewsResults").select("*").eq("isProcessed", False).execute()
    if not unprocessed_response.data:
        print("No unprocessed articles to check.")
        return
    
    unprocessed_articles = unprocessed_response.data
    print(f"Found {len(unprocessed_articles)} unprocessed articles to check.")
    
    # Get processed news results with embeddings
    processed_response = supabase.client.table("NewsResults").select("*").eq("isProcessed", True).execute()
    if not processed_response.data:
        print("No processed articles to compare against.")
        return
    
    processed_articles = processed_response.data
    print(f"Found {len(processed_articles)} processed articles to compare against.")
    
    # Check for similarity between unprocessed and processed articles
    for unprocessed in unprocessed_articles:
        print(f"Checking unprocessed article: {unprocessed.get('uniqueName')}")
        
        # Skip articles without embeddings
        if not unprocessed.get("embedding"):
            print(f"Article {unprocessed.get('uniqueName')} has no embedding, skipping.")
            continue
            
        unprocessed_embedding = unprocessed.get("embedding")
        
        # Find similar processed articles
        similar_processed = []
        for processed in processed_articles:
            if not processed.get("embedding"):
                continue
                
            processed_embedding = processed.get("embedding")
            
            # Calculate cosine similarity
            try:
                similarity = cosine_similarity(unprocessed_embedding, processed_embedding)
                if similarity >= threshold:
                    similar_processed.append({
                        "article": processed,
                        "similarity": similarity
                    })
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
            
            # Get the NewsArticle record for the most similar processed article
            article_response = supabase.client.table("NewsArticle").select("*").eq("NewsResult", most_similar.get("uniqueName")).execute()
            if not article_response.data or len(article_response.data) == 0:
                print(f"No NewsArticle record found for {most_similar.get('uniqueName')}")
                continue
            
            existing_article = article_response.data[0]
            
            # Get the source content for the unprocessed article
            unprocessed_source_url = unprocessed.get("url")
            
            # Get existing source content
            existing_source_urls = [existing_article.get("sourceURL")]
            
            # Add any additional sources from the similar articles
            for similar in similar_processed:
                if similar["article"].get("url") not in existing_source_urls:
                    existing_source_urls.append(similar["article"].get("url"))
            
            # Generate new article content by combining sources
            print(f"Combining content from {len(existing_source_urls)} sources...")
            
            # Create a list of all sources for the combined content
            all_source_urls = existing_source_urls + [unprocessed_source_url]
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
                
                combined_english_content = llm.generate(english_prompt).strip()
                
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
                
                combined_german_content = llm.generate(german_prompt).strip()
                
                # Update the existing article
                updates = {
                    "EnglishArticle": combined_english_content,
                    "GermanArticle": combined_german_content,
                    "status": "UPDATED",
                    # Keep existing headlines
                    "sourceURL": ", ".join(all_source_urls)  # Combine all source URLs
                }
                
                # Update the article
                article_id = existing_article.get("id")
                if update_article(supabase, article_id, updates):
                    print(f"Successfully updated article {article_id} with combined content")
                    
                    # Mark the unprocessed article as processed
                    supabase.client.table("NewsResults").update({"isProcessed": True}).eq("id", unprocessed.get("id")).execute()
                    print(f"Marked unprocessed article {unprocessed.get('uniqueName')} as processed")
                else:
                    print(f"Failed to update article {article_id}")
                
            except Exception as e:
                print(f"Error generating combined content: {e}")
                continue

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

def main():
    load_dotenv()
    
    # Initialize Supabase client
    supabase_client = SupabaseClient()
    
    try:
        # Fetch only unreviewed articles
        response = supabase_client.client.table('NewsArticle')\
            .select('id', 'EnglishHeadline', 'GermanHeadline', 'EnglishArticle', 'GermanArticle')\
            .eq('isReviewed', False)\
            .execute()
        
        if not response.data:
            print("No unreviewed articles found.")
            return
            
        print(f"Found {len(response.data)} unreviewed articles to process.")
        
        # Process each article
        for article in response.data:
            article_id = article['id']
            fields = {
                'EnglishHeadline': article.get('EnglishHeadline', ''),
                'GermanHeadline': article.get('GermanHeadline', ''),
                'EnglishArticle': article.get('EnglishArticle', ''),
                'GermanArticle': article.get('GermanArticle', '')
            }
            
            # Clean all fields
            cleaned_fields = {
                key: clean_text(value) for key, value in fields.items()
            }
            
            # Check if any changes were made
            needs_update = any(cleaned_fields[key] != fields[key] for key in fields)
            
            if needs_update:
                print(f"Cleaning article {article_id}...")
                # Add isReviewed flag to the update
                cleaned_fields['isReviewed'] = True
                if update_article(supabase_client, article_id, cleaned_fields):
                    print(f"Successfully cleaned and updated article {article_id}")
                    # Print which fields were cleaned
                    for key in fields:
                        if cleaned_fields[key] != fields[key]:
                            print(f"  - Cleaned {key}")
                else:
                    print(f"Failed to update article {article_id}")
            else:
                print(f"No cleaning needed for article {article_id}")
                # Mark as reviewed even if no cleaning was needed
                if update_article(supabase_client, article_id, {'isReviewed': True}):
                    print(f"Article {article_id} marked as reviewed")
                else:
                    print(f"Failed to mark article {article_id} as reviewed")
                
    except Exception as e:
        print(f"Error processing articles: {e}")

if __name__ == "__main__":
    main()