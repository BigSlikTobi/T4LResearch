# Add package support when executing as script
if __name__ == '__main__' and __package__ is None:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    __package__ = 'getArticles'

import asyncio
import logging
import os
import re
import urllib.parse
from urllib.parse import urlparse
import unicodedata

from dotenv import load_dotenv
from .fetchNews import get_all_news_items  # Using relative import
from supabase_init import SupabaseClient
import LLMSetup

logging.basicConfig(level=logging.DEBUG)
load_dotenv()

def is_valid_url(url: str) -> bool:
    """Validate if a URL is properly formatted."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def remove_control_chars(s: str) -> str:
    """Remove all Unicode control characters from a string."""
    return ''.join(ch for ch in s if not unicodedata.category(ch).startswith('C'))

def build_url_from_parts(parts: urllib.parse.ParseResult) -> str:
    """Rebuild the URL from its parts, stripping extra whitespace and control characters."""
    scheme = parts.scheme.strip()
    netloc = parts.netloc.strip()
    # Clean and reassemble the path
    path_segments = [segment.strip() for segment in parts.path.split('/') if segment.strip()]
    path = '/' + '/'.join(path_segments) if path_segments else ''
    # Clean query parameters similarly
    query_params = [param.strip() for param in parts.query.split('&') if param.strip()]
    query = '&'.join(query_params)
    fragment = parts.fragment.strip()
    return urllib.parse.urlunparse((scheme, netloc, path, parts.params, query, fragment))

def clean_url(url: str) -> str:
    """Clean URL by removing control characters and, if on GitHub Actions, rebuild the URL.
       Finally, force percent-encoding of the entire URL to ensure no stray control characters remain."""
    if not url:
        return url

    # Remove all Unicode control characters and trim whitespace
    url = remove_control_chars(url).strip()

    # If running in GitHub Actions, rebuild the URL from parsed parts
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        logging.debug("Detected GitHub Actions environment; rebuilding URL from parts.")
        parts = urllib.parse.urlparse(url)
        url = build_url_from_parts(parts)
        logging.debug(f"Rebuilt URL: {url}")
    else:
        # Otherwise, perform standard cleaning:
        url = url.replace('\n', '').replace('\r', '')
        url = ''.join(char for char in url if 32 <= ord(char) <= 126)
        url = re.sub(r'\s+', '-', url.strip())
        try:
            parts = urllib.parse.urlparse(url)
            path = urllib.parse.quote(parts.path)
            query = urllib.parse.quote_plus(parts.query, safe='=&')
            url = urllib.parse.urlunparse((
                parts.scheme,
                parts.netloc,
                path,
                parts.params,
                query,
                parts.fragment
            ))
        except Exception as e:
            logging.warning(f"Error cleaning URL {url}: {e}")
            return url

    # Final forced percent-encoding to ensure no non-printable characters remain
    final_url = urllib.parse.quote(url, safe=":/?&=%#")
    return final_url

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
    
    # If DEBUG_ASCII mode is enabled, print ASCII codes and skip posting
    DEBUG_ASCII = os.getenv("DEBUG_ASCII", "").lower() == "true"
    if DEBUG_ASCII:
        logging.info("DEBUG_ASCII mode enabled. Printing ASCII codes for each article URL:")
        for article in news_articles:
            if 'url' in article:
                raw_url = article['url']
                cleaned = clean_url(raw_url)
                logging.info(f"Article '{article.get('uniqueName', article.get('id', 'Unknown'))}':")
                logging.info(f"  Raw URL: {repr(raw_url)}")
                logging.info(f"  Cleaned URL: {repr(cleaned)}")
                logging.info(f"  ASCII codes: {[ord(c) for c in cleaned]}")
        return  # Skip posting

    # Otherwise, post the articles to Supabase
    for article in news_articles:
        try:
            if 'url' in article:
                raw_url = article['url']
                logging.debug(f"Raw URL: {repr(raw_url)}")
                cleaned = clean_url(raw_url)
                logging.debug(f"Cleaned URL: {repr(cleaned)}")
                if not is_valid_url(cleaned):
                    logging.warning(f"Invalid URL after cleaning: {cleaned}")
                    continue
                # Additional logging right before posting:
                logging.debug(f"Final URL before posting: {repr(cleaned)}")
                logging.debug(f"Final URL ASCII codes: {[ord(c) for c in cleaned]}")
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
