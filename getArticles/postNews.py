import asyncio
from dotenv import load_dotenv
from getArticles.fetchNews import get_all_news_items 
from supabase_init import SupabaseClient
import LLMSetup
import logging

logging.basicConfig(level=logging.INFO)
load_dotenv()

async def main():
    supabase_client = SupabaseClient()
    # Initialize LLMs if not already initialized
    try:
        llms = LLMSetup.initialize_model("both")
        logging.info("LLMs initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize LLMs: {e}")
        return

    # Obtain news articles using the helper from fetchNews.py
    news_articles = await get_all_news_items()

    # Post news articles to Supabase one by one
    for article in news_articles:
        try:
            supabase_client.post_new_source_article_to_supabase([article])
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.info(f"Successfully posted article: {article_name}")
        except Exception as e:
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.error(f"Failed to post article {article_name}: {e}")

if __name__ == "__main__":
    asyncio.run(main())

