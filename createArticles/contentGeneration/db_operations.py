import sys
import os
import datetime

# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from createArticles.storeInDB import create_news_article_record, mark_article_as_processed
from createArticles.review import review_article_fields
from supabase_init import SupabaseClient

supabase_client = SupabaseClient()

async def create_new_article(representative_article, english_data, german_data, image_data, is_reviewed=True, topic_id=None):
    """
    Create a new article record in the database.
    
    Args:
        representative_article (dict): Source article data
        english_data (dict): English article content and headline
        german_data (dict): German article content and headline
        image_data (dict): Image data for the article
        is_reviewed (bool): Whether the article has been reviewed
        topic_id (int, optional): The topic ID to assign to this article
        
    Returns:
        int/None: The ID of the newly created article, or None if creation failed
    """
    new_record_id = create_news_article_record(
        representative_article, 
        english_data, 
        german_data, 
        image_data,
        is_reviewed=is_reviewed,
        topic_id=topic_id
    )
    
    if new_record_id:
        # Run review on the new article to ensure it passes validation
        review_passed = await review_article_fields(new_record_id, representative_article["uniqueName"])
        if review_passed:
            return new_record_id
        else:
            print("Article failed review process")
            return None
    else:
        print("Failed to store the article in the DB.")
        return None

async def update_existing_article(existing_article_id, english_data, german_data):
    """
    Update an existing article in the database.
    
    Args:
        existing_article_id (int): The ID of the existing article to update
        english_data (dict): English article content
        german_data (dict): German article content
        
    Returns:
        bool: True if update and review were successful, False otherwise
    """
    # Add current timestamp for the update
    current_time = datetime.datetime.now().isoformat()
    
    # Update the existing article
    record_to_update = {
        "EnglishArticle": english_data["content"],
        "GermanArticle": german_data["content"],
        "Status": "UPDATED",
        "created_at": current_time  # Update the creation date to reflect update time
    }
    
    try:
        # Update the existing article
        supabase_client.client.table("NewsArticle")\
            .update(record_to_update)\
            .eq("id", existing_article_id)\
            .execute()
        print(f"Updated existing article {existing_article_id} with new content")
        
        # Run review on the updated article to ensure it passes validation
        article_name = str(existing_article_id)
        review_passed = await review_article_fields(existing_article_id, article_name)
        return review_passed
    except Exception as e:
        print(f"Error updating existing article: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
        return False

def mark_articles_as_processed(article_ids):
    """
    Mark multiple articles as processed in the database.
    
    Args:
        article_ids (list): List of article IDs to mark as processed
    """
    for article_id in article_ids:
        mark_article_as_processed(article_id)