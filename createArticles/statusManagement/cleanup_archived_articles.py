"""
Module for cleaning up incorrectly archived articles.
"""
from datetime import datetime, timedelta, timezone
from createArticles.fetchUnprocessedArticles import supabase_client

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