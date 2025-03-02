import os
import sys
import json
import asyncio
import nest_asyncio
import random
from duckduckgo_search import DDGS
from createArticles.keyword_extractor import KeywordExtractor
from createArticles.content_extractor import ContentExtractor
from asyncio import sleep

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLMSetup import initialize_model

# Additional imports for Supabase and OpenAI embedding
from supabase import create_client, Client
import openai

nest_asyncio.apply()

# Initialize OpenAI model and API key
model_info = initialize_model("openai")
provider = model_info["model_name"]
api_token = model_info["model"]["api_key"]
openai.api_key = api_token

# Initialize extractors
keyword_extractor = KeywordExtractor(provider, api_token)
content_extractor = ContentExtractor(provider, api_token)

# Initialize Supabase client using environment variables
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# -------------------------------
# Helper Functions for Embedding Cache
# -------------------------------
def get_embedding(text: str) -> list:
    """Compute an embedding for the text using OpenAI's updated embeddings API."""
    response = openai.embeddings.create(
        input=text,
        model="text-embedding-ada-002"
    )
    # Use attribute access: response.data is a list of objects; each object’s embedding can be accessed via .embedding
    return response.data[0].embedding


def query_cache(embedding: list, threshold: float = 0.9):
    """
    Query the Supabase cache using the RPC 'match_keywords' that performs a vector similarity search.
    Returns the cached record if one is found with a similarity above the threshold.
    """
    try:
        response = supabase_client.rpc("match_keywords", {
            "query_embedding": embedding,
            "match_threshold": threshold,
            "match_count": 1
        }).execute()
        data = response.data
        if data and len(data) > 0:
            return data[0]
        else:
            return None
    except Exception as e:
        print(f"Error querying cache: {e}")
        return None

def store_cache(keyword: str, embedding: list, result: list):
    """Store the keyword, its embedding, and the associated result in Supabase."""
    try:
        data = {
            "keyword": keyword,
            "embedding": embedding,
            "result": result
        }
        supabase_client.table("keyword_cache").insert(data).execute()
    except Exception as e:
        print(f"Error storing cache: {e}")

# -------------------------------
# Asynchronous Related Articles Processing with Embedding Caching
# -------------------------------

# Defining a global Keyword variable to store a global keyword that well be combined with the extracted keywords to optimize the search 
GOBAL_KEYWORD = "American Football"

async def search_background_articles(keyword: str) -> list:
    """
    Searches for background articles using DuckDuckGo for the given keyword.
    First checks the embedding-based cache in Supabase; if a cached result exists, returns it.
    """
    print(f"Searching background articles for keyword: '{keyword}'")

    #combine the global keyword with the extracted keyword to optimize the search
    search_query = f"{keyword} {GOBAL_KEYWORD}"
    
    # Compute the embedding asynchronously (run in thread to avoid blocking)

    embedding = await asyncio.to_thread(get_embedding, search_query)
    
    # Check the cache using the computed embedding
    cached = await asyncio.to_thread(query_cache, embedding, 0.9)
    if cached:
        print(f"Cache hit for keyword '{search_query}'.")
        return cached.get("result", [])
    
    # No cache hit—perform DuckDuckGo search
    await asyncio.sleep(random.uniform(1, 2))
    
    valid_article = None
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=3))
    except Exception as e:
        print(f"Error during DuckDuckGo search for keyword '{search_query}': {e}")
        results = []
    
    if results:
        for result in results:
            url = result.get("href") or result.get("url") or ""
            if not url:
                continue
            if not url.startswith("http"):
                url = "https://" + url
            # Await the asynchronous URL validation
            if await content_extractor.is_valid_url(url):
                print(f"Valid article URL found for keyword '{search_query}': {url}")
                title = result.get("title", "")
                content = await content_extractor.extract_article_content(url)
                valid_article = {
                    "keyword": search_query,
                    "title": title,
                    "url": url,
                    "content": content
                }
                break
            else:
                print(f"Invalid URL skipped: {url}")
    else:
        print(f"No search results for keyword '{search_query}'")
    
    result_to_cache = [valid_article] if valid_article else []
    # Store the new result in cache asynchronously
    await asyncio.to_thread(store_cache, search_query, embedding, result_to_cache)
    
    return result_to_cache

async def process_source_article(article_id: str, article_content: str) -> dict:
    """
    Process a source article: extract keywords and concurrently retrieve related background articles.
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
    
    # Process all keywords concurrently using asyncio.gather
    background_articles = await asyncio.gather(
        *(search_background_articles(keyword) for keyword in keywords)
    )
    # Flatten the list of results
    flattened_articles = [
        article for sublist in background_articles for article in sublist if article
    ]
    return {article_id: flattened_articles}

async def process_all_source_articles():
    """
    Process all source articles from extracted_contents.json and save enriched background articles.
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
    
    # Combine all results into one dictionary
    enriched_background = {}
    for result in results:
        enriched_background.update(result)
    
    with open("enriched_background_articles.json", "w", encoding="utf-8") as f:
        json.dump(enriched_background, f, indent=2, ensure_ascii=False)
    print("Enriched background articles generation complete.")

if __name__ == '__main__':
    asyncio.run(process_all_source_articles())
