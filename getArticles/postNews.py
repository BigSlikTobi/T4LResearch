import asyncio
import logging
import os
import re
import urllib.parse
from urllib.parse import urlparse

from dotenv import load_dotenv
from .fetchNews import get_all_news_items  # Using relative import
from supabase_init import SupabaseClient
import LLMSetup

logging.basicConfig(level=logging.INFO)
load_dotenv()

def get_env_var(name: str) -> str:
    """Load an environment variable and strip any extraneous whitespace/newlines."""
    value = os.getenv(name, "")
    value_stripped = value.strip()
    if not value_stripped:
        logging.error(f"Environment variable {name} is not set or is empty after stripping!")
    else:
        # For debugging purposes, we log that the variable was loaded.
        # We avoid printing the full value to prevent leaking sensitive information.
        logging.info(f"Loaded {name} with length {len(value_stripped)}")
    return value_stripped

# Load and sanitize secrets/environment variables
SUPABASE_URL = get_env_var("SUPABASE_URL")
SUPABASE_KEY = get_env_var("SUPABASE_KEY")
OPENAI_API_KEY = get_env_var("OPENAI_API_KEY")
GEMINI_API_KEY = get_env_var("GEMINI_API_KEY")

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
                # Remove any lingering newline chars (extra safety)
                cleaned = cleaned.replace('\n', '').replace('\r', '')
                if not is_valid_url(cleaned):
                    logging.warning(f"Invalid URL found: {cleaned}")
                    continue
                # Additional fallback cleaning
                cleaned = re.sub(r'[^\x20-\x7E]+', '', cleaned)
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
