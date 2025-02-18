# Add package support when executing as script
if __name__ == '__main__' and __package__ is None:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    __package__ = 'getArticles'

import asyncio
from dotenv import load_dotenv
from fetchNews import get_all_news_items  # Using direct import after updating sys.path
from supabase_init import SupabaseClient
import LLMSetup
import logging
import re
import urllib.parse
from urllib.parse import urlparse
import os

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
    """Clean URL by removing non-printable characters and normalizing whitespace into hyphens."""
    if not url:
        return url
    # Remove non-printable characters (ASCII codes 0-31 and 127)
    url = ''.join(char for char in url if 32 <= ord(char) <= 126)
    # Replace any sequence of whitespace characters (including newlines) with a single hyphen
    url = re.sub(r'\s+', '-', url.strip())
    
    # Encode URL parts to preserve structure
    try:
        parts = urllib.parse.urlparse(url)
        path = urllib.parse.quote(parts.path)
        query = urllib.parse.quote_plus(parts.query, safe='=&')

        clean_url_result = urllib.parse.urlunparse((
            parts.scheme,
            parts.netloc,
            path,
            parts.params,
            query,
            parts.fragment
        ))

        return clean_url_result if is_valid_url(clean_url_result) else url
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

