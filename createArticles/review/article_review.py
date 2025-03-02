"""
Main article review functionality for processing and reviewing articles.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase_init import SupabaseClient
from .text_utils import clean_text
from .image_utils import verify_image_accessibility
from .db_utils import update_article, delete_article_and_update_news_result

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
                
                if await update_article(supabase, record_id, updates):
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