import os
import sys
import re
from dotenv import load_dotenv

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
        
        # Delete the article
        try:
            supabase.client.table("NewsArticle").delete().eq("id", record_id).execute()
            print(f"Deleted article {record_id} from NewsArticle table")
            
            # Update NewsResults isProcessed to false
            supabase.client.table("NewsResults").update(
                {"isProcessed": False}
            ).eq("uniqueName", news_result_unique_name).execute()
            print(f"Updated NewsResults record {news_result_unique_name} to isProcessed=false")
            
            return False
        except Exception as e:
            print(f"Error during cleanup of invalid article: {e}")
            return False
    
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