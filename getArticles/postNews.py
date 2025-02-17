import asyncio
from dotenv import load_dotenv
from getArticles.fetchNews import get_all_news_items 
from supabase_init import SupabaseClient
import LLMSetup
import logging
import re
import urllib.parse
from urllib.parse import urlparse
import os
import sys

# Add parent directory to PYTHONPATH to import modules from root
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.INFO)
load_dotenv()

def is_valid_url(url: str) -> bool:
    """Validate if a URL is properly formatted."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def clean_url(url: str) -> str:
    """Clean URL by removing non-printable characters and normalizing spaces."""
    if not url:
        return url
    
    # Remove all non-printable characters
    url = ''.join(char for char in url if ord(char) >= 32 and ord(char) <= 126)
    
    # Normalize spaces and remove unwanted characters
    url = url.strip().replace('\n', '').replace('\r', '').replace(' ', '-')
    
    # Encode URL properly while preserving structure
    try:
        parts = urllib.parse.urlparse(url)
        path = urllib.parse.quote(parts.path)
        query = urllib.parse.quote_plus(parts.query, safe='=&')
        
        # Reconstruct the URL
        clean_url = urllib.parse.urlunparse((
            parts.scheme,
            parts.netloc,
            path,
            parts.params,
            query,
            parts.fragment
        ))
        
        return clean_url if is_valid_url(clean_url) else url
    except Exception as e:
        logging.warning(f"Error cleaning URL {url}: {e}")
        return url

async def main():
    supabase_client = SupabaseClient()
    llm_choice = "openai"
    try:
        llms = LLMSetup.initialize_model(llm_choice)
        logging.info("LLMs initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize LLMs: {e}")
        return
    
    # Obtain news articles using the helper from fetchNews.py
    news_articles = await get_all_news_items()
    for article in news_articles:
        try:
            if 'url' in article:
                cleaned = clean_url(article['url'])
                if not is_valid_url(cleaned):
                    logging.warning(f"Invalid URL found: {cleaned}")
                    continue
                article['url'] = cleaned
            
            result = supabase_client.post_new_source_article_to_supabase(article)
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.info(f"Successfully posted article: {article_name}")
        except Exception as e:
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.error(f"Error posting {article_name}: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(main())

