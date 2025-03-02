"""
Database utility functions for interacting with the Supabase database.
"""

async def update_article(supabase_client, article_id: int, updates: dict) -> bool:
    """Update the article with provided updates."""
    try:
        response = supabase_client.client.table('NewsArticle').update(updates)\
            .eq('id', article_id).execute()
        
        return len(response.data) > 0
    except Exception as e:
        print(f"Error updating article {article_id}: {e}")
        return False

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