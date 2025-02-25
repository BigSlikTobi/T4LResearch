import os
import sys
import re
import requests
from dotenv import load_dotenv
import urllib.parse

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from supabase_init import SupabaseClient

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
    """
    supabase = SupabaseClient()
    
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
    image_url = article.get("imageUrl", "")  # Changed from ImageUrl to imageUrl to match database field
    print(f"\nChecking image accessibility for article {record_id}")
    print(f"Image URL: {image_url}")
    
    if not verify_image_accessibility(image_url):
        print(f"Article {record_id} failed review - image is not accessible: {image_url}")
        await delete_article_and_update_news_result(supabase, record_id, news_result_unique_name)
        return False
    else:
        print(f"Image accessibility check passed for article {record_id}")
    
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