from duckduckgo_search import DDGS
from openai import AsyncOpenAI
import asyncio
import json
import os
import dotenv
import sys
import yaml

# Add parent directory to path to import LLMSetup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLMSetup import initialize_model

# Load environment variables
dotenv.load_dotenv()

# Initialize OpenAI model
model_config = initialize_model("openai")
aclient = AsyncOpenAI(api_key=model_config["model"]["api_key"])

# Load prompts
with open("prompts.yaml", "r") as f:
    prompts = yaml.safe_load(f)

async def generate_search_query(article_content: str) -> str:
    """
    Generate an image search query using LLM by extracting key visual elements,
    and include a constraint that the image should be from the last 6 months.
    """
    try:
        prompt = prompts["image_search_prompt"].format(article_content=article_content[:2000])
        response = await aclient.chat.completions.create(
            model=model_config["model"]["provider"],
            messages=[{"role": "user", "content": prompt}],
            max_tokens=50
        )
        query = response.choices[0].message.content.strip()
        # Remove surrounding quotation marks if present
        if query.startswith('"') and query.endswith('"'):
            query = query[1:-1].strip()
        print(f"Generated search query: {query}")
        return query
    except Exception as e:
        print(f"Query generation error: {e}")
        return ""

async def search_image(article_content: str) -> dict:
    """Search for an image using DuckDuckGo API via DDGS."""
    try:
        # Generate a search query that includes the recency constraint.
        search_query = await generate_search_query(article_content)
        if not search_query:
            print("Empty search query generated.")
            return {}

        print(f"Searching for images with query: {search_query}")
        # Use DDGS to search for images.
        with DDGS() as ddgs:
            # ddgs.images() returns an iterator; we convert it to a list.
            results = list(ddgs.images(search_query, max_results=1))
            print(f"DDGS returned {len(results)} result(s).")
            if not results:
                print("No image results returned from DDGS.")
                return {}
            result = results[0]
            print(f"Image result: {result}")
            return {
                "imageURL": result.get("image", ""),
                "imageAltText": result.get("title", ""),
                "imageSource": result.get("url", ""),
                "imageAttribution": result.get("source", "")
            }
    except Exception as e:
        print(f"Image search error: {e}")
        return {}

images_data = {}

async def process_single_article(article_id: str, article):
    """Process one article and store its image data."""
    print(f"Processing article {article_id}")
    # Determine article content.
    if isinstance(article, dict):
        content = article.get("content", "")
    elif isinstance(article, str):
        content = article
    else:
        content = ""

    if not content:
        images_data[article_id] = empty_image_data()
        return

    image_info = await search_image(content)
    images_data[article_id] = image_info if image_info else empty_image_data()

    if image_info:
        print(f"Found image for {article_id}")
    else:
        print(f"No image found for {article_id}")

def empty_image_data():
    return {
        "imageURL": "",
        "imageAltText": "",
        "imageSource": "",
        "imageAttribution": ""
    }

async def process_all_articles(english_articles):
    """Main processing coroutine for all articles."""
    tasks = []
    for article_id, article in english_articles.items():
        tasks.append(process_single_article(article_id, article))
    await asyncio.gather(*tasks)

def run_image_generation(english_articles):
    """Handle event loop creation and run image processing."""
    try:
        asyncio.run(process_all_articles(english_articles))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(process_all_articles(english_articles))

# Execute the processing
if __name__ == '__main__':
    # Load English articles
    with open("English_articles.json", "r", encoding='utf-8') as f:
        english_articles = json.load(f)

    run_image_generation(english_articles)

    # Save results to images.json
    with open("images.json", "w", encoding='utf-8') as f:
        json.dump(images_data, f, ensure_ascii=False, indent=2)

    print(f"\nImage generation complete. Saved {len(images_data)} entries.")

    # Show sample output
    if images_data:
        sample_id = next(iter(images_data))
        print(f"\nSample entry ({sample_id}):")
        print(json.dumps(images_data[sample_id], indent=2))
    else:
        print("No images generated")
