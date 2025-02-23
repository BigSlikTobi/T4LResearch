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

async def rank_images_by_content(article_content: str, image_candidates: list) -> dict:
    """
    Use an LLM to rank candidate images by content fit and return the best one.
    """
    # Prepare an excerpt of the article to keep the prompt concise.
    article_excerpt = article_content[:1500]

    # Create a structured, numbered list of candidate images with key metadata.
    candidate_info = "\n".join(
        f"{i+1}. URL: {img.get('image', 'N/A')}\n   Title: {img.get('title', 'N/A')}\n   Source: {img.get('url', 'N/A')}"
        for i, img in enumerate(image_candidates)
    )

    # Craft the prompt for the LLM.
    prompt = (
        f"Below is an excerpt from a news article:\n\n"
        f"{article_excerpt}\n\n"
        f"And here are 10 candidate images with their metadata:\n"
        f"{candidate_info}\n\n"
        f"Based on the content of the article, please select the image that best fits the story. "
        f"Provide only the number corresponding to the best candidate."
    )

    print("Sending ranking prompt to LLM...")
    response = await aclient.chat.completions.create(
        model=model_config["model"]["provider"],
        messages=[{"role": "user", "content": prompt}],
        max_tokens=20
    )
    ranking_result = response.choices[0].message.content.strip()
    print(f"LLM ranking result: {ranking_result}")

    try:
        # Parse the result to extract the selected candidate number.
        selected_index = int(ranking_result) - 1  # assuming numbering starts at 1
        best_candidate = image_candidates[selected_index]
        return best_candidate
    except Exception as e:
        print(f"Error parsing LLM ranking response: {e}")
        # Fallback: return the first candidate if parsing fails.
        return image_candidates[0] if image_candidates else {}

async def search_image(article_content: str) -> dict:
    """
    Search for an image using the DuckDuckGo API via DDGS, gather 10 candidate images,
    and then use an LLM to rank them by content fit.
    """
    try:
        # Generate a search query that includes the recency constraint.
        search_query = await generate_search_query(article_content)
        if not search_query:
            print("Empty search query generated.")
            return {}

        print(f"Searching for images with query: {search_query}")
        # Use DDGS to search for images and collect 10 candidates.
        with DDGS() as ddgs:
            results = list(ddgs.images(search_query, max_results=10))
            print(f"DDGS returned {len(results)} result(s).")
            if not results:
                print("No image results returned from DDGS.")
                return {}

        # Use the LLM to select the best candidate based on content.
        best_candidate = await rank_images_by_content(article_content, results)
        print(f"Selected best image: {best_candidate}")

        return {
            "imageURL": best_candidate.get("image", ""),
            "imageAltText": best_candidate.get("title", ""),
            "imageSource": best_candidate.get("url", ""),
            "imageAttribution": best_candidate.get("source", "")
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
