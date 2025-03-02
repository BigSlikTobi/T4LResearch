"""
Module for updating article status values based on their age.
"""
from datetime import datetime, timedelta, timezone
from createArticles.fetchUnprocessedArticles import supabase_client
from .update_missing_statuses import update_missing_statuses

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