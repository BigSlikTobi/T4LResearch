"""
Module for updating articles with missing status values.
"""
from datetime import datetime, timedelta, timezone
from createArticles.fetchUnprocessedArticles import supabase_client

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