"""
Main script for running the complete news fetching pipeline.
"""
import asyncio
import logging
import os
import sys
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv

# Local imports
from getArticles.news_fetcher import fetch_from_all_sources, get_default_sources
from getArticles.db_operations import DatabaseManager
from getArticles.content_processor import ContentProcessor
from getArticles.url_utils import is_valid_url, clean_url

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class NewsFetchingPipeline:
    """Coordinates the complete news fetching, processing and storage pipeline."""
    
    def __init__(self, 
                 llm_choice: str = "openai", 
                 sources: Optional[List[Dict[str, Any]]] = None):
        """
        Initialize the news fetching pipeline.
        
        Args:
            llm_choice: LLM provider to use ("openai" or "gemini")
            sources: List of news sources to fetch from (uses defaults if None)
        """
        self.llm_choice = llm_choice
        self.sources = sources if sources is not None else get_default_sources()
        
        # Initialize API keys and providers
        self._initialize_api_config()
        
        # Initialize components
        self.db_manager = DatabaseManager()
        self.content_processor = ContentProcessor(llm_choice=llm_choice)
        
        logger.info("News fetching pipeline initialized")
        
    def _initialize_api_config(self) -> None:
        """Initialize API configurations based on LLM choice."""
        if self.llm_choice == "openai":
            self.api_key = os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")
            self.provider = "openai/gpt-4o-mini"
        elif self.llm_choice == "gemini":
            self.api_key = os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable not set")
            self.provider = "gemini"
        else:
            raise ValueError(f"Unsupported LLM choice: {self.llm_choice}")
            
    def validate_environment(self) -> bool:
        """
        Validate that all required environment variables and dependencies are available.
        
        Returns:
            True if the environment is valid, False otherwise
        """
        # Check Supabase environment variables
        if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
            logger.error("Supabase environment variables not set")
            return False
            
        # Check API key for chosen LLM
        if self.llm_choice == "openai" and not os.getenv("OPENAI_API_KEY"):
            logger.error("OpenAI API key not set")
            return False
        elif self.llm_choice == "gemini" and not os.getenv("GEMINI_API_KEY"):
            logger.error("Gemini API key not set")
            return False
            
        return True
        
    async def run(self) -> int:
        """
        Run the complete news fetching pipeline.
        
        Returns:
            Number of successfully processed articles
        """
        if not self.validate_environment():
            logger.error("Environment validation failed")
            return 0
            
        logger.info("Starting news fetching pipeline")
        
        try:
            # Step 1: Fetch news from all sources
            logger.info("Fetching news articles from sources")
            articles = await fetch_from_all_sources(
                self.sources, 
                self.provider, 
                self.api_key
            )
            
            if not articles:
                logger.warning("No articles fetched from any source")
                return 0
                
            logger.info(f"Successfully fetched {len(articles)} articles")
            
            # Step 2: Enrich articles with summaries and embeddings
            logger.info("Enriching articles with summaries and embeddings")
            enriched_articles = await self.content_processor.enrich_articles(articles)
            
            # Step 3: Store articles in the database
            logger.info("Storing articles in the database")
            success_count = self.db_manager.store_articles(enriched_articles)
            
            logger.info(f"Successfully processed and stored {success_count} articles")
            return success_count
            
        except Exception as e:
            logger.error(f"Error running news fetching pipeline: {e}")
            return 0

async def main():
    """Main entry point for the news fetching pipeline."""
    try:
        pipeline = NewsFetchingPipeline(llm_choice="openai")
        processed_count = await pipeline.run()
        logger.info(f"Pipeline completed. Processed {processed_count} articles.")
        
    except Exception as e:
        logger.error(f"Error in main function: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())