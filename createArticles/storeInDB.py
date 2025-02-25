import json
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from createArticles.detectTeam import detectTeam
from createArticles.fetchUnprocessedArticles import get_unprocessed_articles, supabase_client

def create_news_article_record(
    article: dict,
    english_data: dict,
    german_data: dict,
    image_data: dict,
    is_reviewed: bool = False  # Add parameter with default False
) -> int:
    """
    Inserts a new record into 'NewsArticle'.
    'english_data', 'german_data', and 'image_data' should each be a dict containing
    the respective fields.
    This version also detects the team name from the English article content.
    Returns the ID of the newly created record or None on failure.
    
    Args:
        article: Source article data
        english_data: English translation data
        german_data: German translation data
        image_data: Image metadata
        is_reviewed: Whether the article has been reviewed/cleaned
    """
    try:
        # Extract base URL from imageSource for imageAttribution
        image_source_url = image_data.get("url", "")  # Changed from imageSource to url
        parsed_url = urlparse(image_source_url)
        base_image_url = parsed_url.scheme + "://" + parsed_url.netloc if parsed_url.netloc else image_source_url

        # Instantiate detectTeam and detect the team from the English article content.
        team_detector = detectTeam()  # CHANGED
        team_detection = team_detector.detect_team(english_data.get("content", ""))  # CHANGED
        team_name = team_detection.get("team", "")

        # Build the record to insert, now including the team field.
        record_to_insert = {
            "NewsResult": article.get("uniqueName"),
            "sourceURL": article.get("url"),
            "sourceArticlePublishedAt": article.get("publishedAt"),
            "sourceArticleUpdatedAt": article.get("publishedAt"),
            "sourceAutor": article.get("author", "Unknown"),
            "EnglishHeadline": english_data.get("headline", ""),
            "EnglishArticle": english_data.get("content", ""),
            "GermanHeadline": german_data.get("headline", ""),
            "GermanArticle": german_data.get("content", ""),
            "imageUrl": image_data.get("image", ""),  # Changed from imageURL to image
            "imageAltText": image_data.get("imageAltText", ""),
            "imageSource": image_data.get("url", ""),  # Changed from imageSource to url
            "imageAttribution": base_image_url,
            "isHeadline": False,  # Assuming default value is false.
            "Team": team_name,
            "isReviewed": is_reviewed,  # Use the parameter instead of hardcoding False
            "Status": "NEW"  # Adding Status field with default value "NEW"
        }

        # CHANGED: use direct access to result.data
        result = supabase_client.table("NewsArticle").insert([record_to_insert]).execute()
        if result.data:
            new_id = result.data[0]["id"]
            print(f"Created new record in 'NewsArticle' table with ID: {new_id}")
            return new_id
        else:
            print("Failed to create new record: No data returned from insert operation.")
            return None
    except Exception as e:
        print(f"Error creating record in 'NewsArticle' table: {e}")
        return None

def mark_article_as_processed(article_id: int):
    """
    Marks the article as processed in 'NewsResults' table by setting isProcessed = True.
    """
    try:
        # CHANGED: use supabase_client for DB operations
        supabase_client.table("NewsResults").update({"isProcessed": True}).eq("id", article_id).execute()
        print(f"Article ID {article_id} marked as processed.")
    except Exception as e:
        print(f"Error marking article {article_id} as processed: {e}")

def process_articles(unprocessed_articles, english_articles, german_articles, images_data):
    """Main function to process and store articles in the database."""
    for article in unprocessed_articles:
        article_id = article["id"]
        print(f"\nStoring data for article ID: {article_id}")

        # Convert integer ID to string if your JSON uses string keys
        str_id = str(article_id)

        # Get the English and German data for this article
        english_data = english_articles.get(str_id, {"headline": "", "content": ""})
        german_data = german_articles.get(str_id, {"headline": "", "content": ""})
        image_data = images_data.get(str_id, {
            "image": "",  # Changed from imageURL to image
            "imageAltText": "",
            "url": "",  # Changed from imageSource to url
            "imageAttribution": ""
        })

        # Create the record in 'NewsArticle'
        new_record_id = create_news_article_record(article, english_data, german_data, image_data)

        # If insertion succeeded, mark the article as processed
        if new_record_id:
            mark_article_as_processed(article_id)

def update_missing_statuses():
    """
    Updates articles that don't have a status set (NULL).
    Sets their status based on their age:
    - Articles older than 2 hours -> "OLD"
    - Articles older than 48 hours -> "ARCHIVED"
    - Articles newer than 2 hours -> "NEW"
    """
    try:
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        two_hours_ago = now - timedelta(hours=2)
        two_days_ago = now - timedelta(days=2)

        # Fetch all articles with NULL status
        response = supabase_client.table("NewsArticle")\
            .select("id", "created_at")\
            .is_("Status", "null")\
            .execute()

        if not response.data:
            print("No articles found with missing status.")
            return

        for article in response.data:
            article_id = article['id']
            # Parse the timestamp and make it timezone-aware
            created_at = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
            
            # Determine status based on age
            if created_at < two_days_ago:
                new_status = "ARCHIVED"
            elif created_at < two_hours_ago:
                new_status = "OLD"
            else:
                new_status = "NEW"

            # Update article status
            supabase_client.table("NewsArticle")\
                .update({"Status": new_status})\
                .eq("id", article_id)\
                .execute()
            
            print(f"Set status of article {article_id} to {new_status}")

    except Exception as e:
        print(f"Error updating missing statuses: {e}")

def update_article_statuses():
    """
    Updates the status of articles based on their age:
    - Articles older than 2 hours -> "OLD"
    - Articles older than 48 hours -> "ARCHIVED"
    """
    try:
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        two_hours_ago = now - timedelta(hours=2)
        two_days_ago = now - timedelta(days=2)

        # First update any articles with missing status
        update_missing_statuses()

        # Then update existing statuses
        # Fetch all articles that are not ARCHIVED and have a status
        response = supabase_client.table("NewsArticle")\
            .select("id", "created_at", "Status")\
            .not_.eq("Status", "ARCHIVED")\
            .not_.is_("Status", "null")\
            .execute()

        if not response.data:
            print("No articles found to update.")
            return

        for article in response.data:
            article_id = article['id']
            # Parse the timestamp and make it timezone-aware
            created_at = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
            current_status = article['Status']
            
            # Don't change UPDATED status articles unless they're old enough to be archived
            if current_status == "UPDATED" and created_at >= two_days_ago:
                continue
                
            # Determine new status based on age
            if created_at < two_days_ago:
                new_status = "ARCHIVED"
            elif created_at < two_hours_ago:
                new_status = "OLD"
            else:
                continue  # Skip if article is newer than 2 hours

            # Update article status
            supabase_client.table("NewsArticle")\
                .update({"Status": new_status})\
                .eq("id", article_id)\
                .execute()
            
            print(f"Updated article {article_id} status to {new_status}")

    except Exception as e:
        print(f"Error updating article statuses: {e}")

def cleanup_archived_articles():
    """
    One-time cleanup function to fix articles that were incorrectly marked as ARCHIVED
    when using sourceArticlePublishedAt instead of created_at.
    """
    try:
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        two_hours_ago = now - timedelta(hours=2)
        two_days_ago = now - timedelta(days=2)

        # Fetch all articles
        response = supabase_client.table("NewsArticle")\
            .select("id", "created_at", "Status")\
            .execute()

        if not response.data:
            print("No articles found.")
            return

        fixed_count = 0
        for article in response.data:
            article_id = article['id']
            created_at = datetime.fromisoformat(article['created_at'].replace('Z', '+00:00'))
            current_status = article.get('Status')
            
            # Determine correct status based on created_at
            if created_at < two_days_ago:
                new_status = "ARCHIVED"
            elif created_at < two_hours_ago:
                new_status = "OLD"
            else:
                new_status = "NEW"

            # Only update if status is different
            if current_status != new_status:
                supabase_client.table("NewsArticle")\
                    .update({"Status": new_status})\
                    .eq("id", article_id)\
                    .execute()
                print(f"Fixed article {article_id}: {current_status} -> {new_status}")
                fixed_count += 1

        print(f"\nCleanup complete. Fixed {fixed_count} articles.")

    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == '__main__':
    # Load all necessary data
    unprocessed_articles = get_unprocessed_articles()
    
    with open("English_articles.json", "r", encoding='utf-8') as f:
        english_articles = json.load(f)
    with open("German_articles.json", "r", encoding='utf-8') as f:
        german_articles = json.load(f)
    with open("images.json", "r", encoding='utf-8') as f:
        images_data = json.load(f)

    process_articles(unprocessed_articles, english_articles, german_articles, images_data)
    print("Data storage complete.")
    
    # Run the cleanup function
    print("\nStarting cleanup of archived articles...")
    cleanup_archived_articles()
    
    # Then run regular status updates
    print("\nRunning regular status updates...")
    update_missing_statuses()
    update_article_statuses()
