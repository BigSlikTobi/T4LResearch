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
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv
from .fetchNews import get_all_news_items  # Using relative import
from supabase_init import SupabaseClient
import LLMSetup

# Import the new client from OpenAI (v1.0.0+)
from openai import OpenAI

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
    path_segments = [segment.strip() for segment in parts.path.split('/') if segment.strip()]
    path = '/' + '/'.join(path_segments) if path_segments else ''
    query_params = [param.strip() for param in parts.query.split('&') if param.strip()]
    query = '&'.join(query_params)
    fragment = parts.fragment.strip()
    return urllib.parse.urlunparse((scheme, netloc, path, parts.params, query, fragment))


def clean_url(url: str) -> str:
    """Clean URL by removing control characters and performing percent-encoding."""
    if not url:
        return url

    url = remove_control_chars(url).strip()

    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        logging.debug("Detected GitHub Actions environment; rebuilding URL from parts.")
        parts = urllib.parse.urlparse(url)
        url = build_url_from_parts(parts)
        logging.debug(f"Rebuilt URL: {url}")
    else:
        url = url.replace('\n', '').replace('\r', '')
        url = ''.join(char for char in url if 32 <= ord(char) <= 126)
        url = re.sub(r'\s+', '-', url.strip())
        try:
            parts = urllib.parse.urlparse(url)
            path = urllib.parse.quote(parts.path)
            query = urllib.parse.quote_plus(parts.query, safe='=&')
            url = urllib.parse.urlunparse((parts.scheme, parts.netloc, path, parts.params, query, parts.fragment))
        except Exception as e:
            logging.warning(f"Error cleaning URL {url}: {e}")
            return url

    final_url = urllib.parse.quote(url, safe=":/?&=%#")
    return final_url


async def generate_summary(article_url: str, article_headline: str, llm_choice: str) -> Optional[str]:
    """Generate a summary of the article using the OpenAI client."""
    try:
        prompt = f"""Summarize the article with headline: "{article_headline}"
URL: {article_url}

Provide a brief, informative summary in 2-3 sentences."""
        
        if llm_choice == "openai":
            # Instantiate a new client using your API key
            client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            # Use the new chat.completions.create() method; note that we use asyncio.to_thread here
            response = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=150
            )
            return response.choices[0].message.content.strip()
        else:
            return None
    except Exception as e:
        logging.error(f"Error generating summary: {e}")
        return None


async def generate_embedding(text: str) -> Optional[list[float]]:
    """Generate an embedding vector for the given text using the new client."""
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = await asyncio.to_thread(
            client.embeddings.create,
            model="text-embedding-ada-002",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Error generating embedding: {e}")
        return None


async def main():
    supabase_client = SupabaseClient()
    llm_choice = "openai"
    try:
        # Initialize the client (this can be reused if desired)
        LLMSetup.initialize_model(llm_choice)
        logging.info("LLMs initialized successfully.")
    except Exception as e:
        logging.error(f"Failed to initialize LLMs: {e}")
        return
    
    try:
        # Obtain news articles using the helper from fetchNews.py
        news_articles = await get_all_news_items()
        
        if not news_articles:
            logging.warning("No news articles were fetched. Check the fetchNews.py implementation.")
            return
            
        logging.info(f"Successfully fetched {len(news_articles)} articles")
    except Exception as e:
        logging.error(f"Failed to fetch news articles: {e}")
        return
    
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
        return  # Skip posting if debugging
    
    for article in news_articles:
        try:
            if 'url' not in article:
                logging.warning(f"Article missing URL field: {article}")
                continue
                
            raw_url = article['url']
            if not raw_url:
                logging.warning(f"Empty URL for article: {article.get('headline', 'Unknown headline')}")
                continue
                
            logging.debug(f"Raw URL: {repr(raw_url)}")
            cleaned = clean_url(raw_url)
            logging.debug(f"Cleaned URL: {repr(cleaned)}")
            
            if not is_valid_url(cleaned):
                logging.warning(f"Invalid URL after cleaning: {cleaned}")
                continue
                
            article['url'] = cleaned
            
            # Generate summary and embedding using the new client methods
            summary = await generate_summary(cleaned, article.get('headline', ''), llm_choice)
            if summary:
                article['summary'] = summary
                embedding = await generate_embedding(summary)
                if embedding:
                    article['embedding'] = embedding
            
            # Pass the single article directly, not wrapped in a list
            result = supabase_client.post_new_source_article_to_supabase(article)
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.info(f"Successfully posted article: {article_name}")
        except Exception as e:
            article_name = article.get("uniqueName", article.get("id", "Unknown"))
            logging.error(f"Error posting {article_name}: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(main())
