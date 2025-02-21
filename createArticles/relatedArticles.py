#TODO: Add related Articles for Keywords to Database to fetch information from there instead of scraping the web multiple times

import os
import sys

import json
import asyncio
import nest_asyncio
import random
from duckduckgo_search import DDGS
from keyword_extractor import KeywordExtractor
from content_extractor import ContentExtractor
from asyncio import sleep
# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLMSetup import initialize_model

nest_asyncio.apply()

# Initialize OpenAI model
model_info = initialize_model("openai")
provider = model_info["model_name"]
api_token = model_info["model"]["api_key"]

# Initialize extractors
keyword_extractor = KeywordExtractor(provider, api_token)
content_extractor = ContentExtractor(provider, api_token)

async def search_background_articles(keyword: str) -> list:
    """
    Searches for background articles using DuckDuckGo for the given keyword.
    """
    print(f"Searching background articles for keyword: '{keyword}'")
    
    await asyncio.sleep(random.uniform(1, 2))
    
    valid_article = None
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(keyword, max_results=3))
    except Exception as e:
        print(f"Error during DuckDuckGo search for keyword '{keyword}': {e}")
        results = []

    if results:
        for result in results:
            url = result.get("href") or result.get("url") or ""
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://" + url
            if await content_extractor.is_valid_url(url):  # Add await here
                print(f"Valid article URL found for keyword '{keyword}': {url}")
                title = result.get("title", "")
                content = await content_extractor.extract_article_content(url)
                valid_article = {
                    "keyword": keyword,
                    "title": title,
                    "url": url,
                    "content": content
                }
                break
            else:
                print(f"Invalid URL skipped: {url}")
    else:
        print(f"No search results for keyword '{keyword}'")
    return [valid_article] if valid_article else []

async def process_source_article(article_id: str, article_content: str) -> dict:
    """
    Process a source article to extract keywords and find background articles.
    """
    print(f"\nProcessing source article ID: {article_id}")
    try:
        keywords = await keyword_extractor.extract_keywords(article_content)
    except Exception as e:
        print(f"Error extracting keywords for article {article_id}: {e}")
        keywords = []
    if not keywords:
        print(f"No keywords extracted for article {article_id}")
        return {article_id: []}
        
    # Use asyncio.gather to process keywords concurrently
    background_articles = await asyncio.gather(
        *(search_background_articles(keyword) for keyword in keywords)
    )
    # Flatten the list of article lists
    flattened_articles = [
        article for sublist in background_articles 
        for article in sublist if article
    ]
    return {article_id: flattened_articles}

async def process_all_source_articles():
    """
    Process all source articles from extracted_contents.json
    """
    with open("extracted_contents.json", "r", encoding="utf-8") as f:
        source_articles = json.load(f)

    articles_dict = {}
    if isinstance(source_articles, list):
        for art in source_articles:
            art_id = str(art.get("id", "unknown"))
            content = art.get("headline", "") if isinstance(art, dict) and "headline" in art else str(art)
            articles_dict[art_id] = content
    else:
        articles_dict = source_articles

    # Process all articles concurrently
    results = await asyncio.gather(
        *(process_source_article(art_id, content) 
          for art_id, content in articles_dict.items())
    )
    
    # Combine all results into a single dictionary
    enriched_background = {}
    for result in results:
        enriched_background.update(result)

    with open("enriched_background_articles.json", "w", encoding="utf-8") as f:
        json.dump(enriched_background, f, indent=2, ensure_ascii=False)
    print("Enriched background articles generation complete.")

if __name__ == '__main__':
    asyncio.run(process_all_source_articles())