"""
Database operations for the news fetching pipeline.
"""
import os
import logging
from typing import Dict, Any, List, Optional, Union

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Handle database operations for news articles."""
    
    def __init__(self, supabase_client=None):
        """
        Initialize the database manager.
        
        Args:
            supabase_client: A Supabase client instance. If not provided,
                             will attempt to create one.
        """
        if supabase_client is None:
            try:
                # Dynamically import to reduce dependencies
                from supabase_init import SupabaseClient
                self.supabase_client = SupabaseClient()
            except ImportError as e:
                logger.error(f"Failed to import SupabaseClient: {e}")
                self.supabase_client = None
        else:
            self.supabase_client = supabase_client
    
    def store_article(self, article: Dict[str, Any]) -> bool:
        """
        Store a single article in the database.
        
        Args:
            article: Article data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        if not self.supabase_client:
            logger.error("No Supabase client available")
            return False
            
        try:
            result = self.supabase_client.post_new_source_article_to_supabase(article)
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logger.info(f"Successfully posted article: {article_name}")
            return True
        except Exception as e:
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logger.error(f"Error posting {article_name} to Supabase: {e}")
            return False
    
    def store_articles(self, articles: List[Dict[str, Any]]) -> int:
        """
        Store multiple articles in the database.
        
        Args:
            articles: List of article data dictionaries
            
        Returns:
            Number of successfully stored articles
        """
        success_count = 0
        
        for article in articles:
            if self.store_article(article):
                success_count += 1
        
        return success_count
        
    def get_existing_articles(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve existing articles from the database.
        
        Args:
            limit: Maximum number of articles to retrieve
            
        Returns:
            List of article data dictionaries
        """
        if not self.supabase_client:
            logger.error("No Supabase client available")
            return []
            
        try:
            return self.supabase_client.get_articles(limit)
        except Exception as e:
            logger.error(f"Error retrieving articles from Supabase: {e}")
            return []