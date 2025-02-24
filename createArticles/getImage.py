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
model_config["model"]["temperature"] = 0.1
aclient = AsyncOpenAI(api_key=model_config["model"]["api_key"])

# Load prompts
with open("prompts.yaml", "r") as f:
    prompts = yaml.safe_load(f)

# Import KeywordExtractor to extract keywords instead of relying solely on LLM query generation
from keyword_extractor import KeywordExtractor

async def generate_search_query(article_content: str, keywords: list = None) -> str:
    """
    Generate an image search query using both the extracted keywords and a summary of the article content.
    The summary is generated via an LLM call to capture key visual elements.
    The final query also includes recency and aspect ratio constraints.
    """
    try:
        if keywords is None or not keywords:
            print("No extracted keywords available; returning empty query.")
            return ""
        
        # Truncate the article content to avoid overly long prompts
        article_excerpt = article_content[:1500]
        summarization_prompt = (
            f"Summarize the following article text to extract key visual elements for an image search "
            f"(such as the subject, location, and notable objects). Provide your answer as a short, "
            f"comma-separated list of keywords:\n\n{article_excerpt}"
        )
        print("Generating summary for image search query...")
        summary_response = await aclient.chat.completions.create(
            model=model_config["model"]["provider"],
            messages=[{"role": "user", "content": summarization_prompt}],
            max_tokens=50
        )
        summary_text = summary_response.choices[0].message.content.strip()
        
        # Combine the extracted keywords with the summary keywords.
        combined = " ".join(keywords) + " " + summary_text
        final_query = combined + " recent 14-day 16:9"
        print(f"Generated search query from keywords and summary: {final_query}")
        return final_query
    except Exception as e:
        print(f"Error in generating search query: {e}")
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

async def search_image(article_content: str, extracted_keywords: list = None) -> dict:
    """
    Search for an image using the DuckDuckGo API via DDGS, gather candidate images,
    filter them ensuring they are not older than 14 days and have a 16:9 aspect ratio,
    and then use an LLM to rank them by content fit.
    Uses already extracted keywords to generate the search query.
    """
    try:
        # Generate a search query with recency and aspect ratio constraints using provided keywords and article summary.
        search_query = await generate_search_query(article_content, extracted_keywords)
        if not search_query:
            print("Empty search query generated.")
            return {}
        print(f"Searching for images with query: {search_query}")
        # Use DDGS to search for images and collect candidates across simulated pages
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=14)
        filtered_results = []
        fallback_candidate = None  # Fallback candidate if no image passes filtering
        with DDGS() as ddgs:
            page = 1
            max_pages = 5  # try up to 5 pages
            while page <= max_pages:
                total_requested = page * 10
                results = list(ddgs.images(search_query, max_results=total_requested))
                if fallback_candidate is None and results:
                    fallback_candidate = results[0]
                current_page_results = results[(page-1)*10 : page*10]
                print(f"Page {page} returned {len(current_page_results)} result(s) (total requested {total_requested}).")
                if not current_page_results:
                    break
                for img in current_page_results:
                    try:
                        if 'date' not in img:
                            continue
                        candidate_date = datetime.fromisoformat(img['date'])
                        if candidate_date < cutoff_date:
                            continue
                        if 'width' in img and 'height' in img and img['height'] > 0:
                            aspect = img['width'] / img['height']
                            if abs(aspect - (16/9)) > 0.1:
                                continue
                        else:
                            continue
                        filtered_results.append(img)
                    except Exception as e:
                        continue
                if filtered_results:
                    break
                page += 1
        if not filtered_results:
            if fallback_candidate is not None:
                print("No candidates passed filtering; using fallback candidate.")
                best_candidate = fallback_candidate
            else:
                print("No candidates passed filtering for date and aspect ratio after searching multiple pages.")
                return {}
        else:
            best_candidate = await rank_images_by_content(article_content, filtered_results)
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
    if isinstance(article, dict):
        content = article.get("content", "")
        extracted_keywords = article.get("keywords", [])
    elif isinstance(article, str):
        content = article
        extracted_keywords = []
    else:
        content = ""
        extracted_keywords = []

    if not content:
        images_data[article_id] = empty_image_data()
        return

    image_info = await search_image(content, extracted_keywords)
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

if __name__ == '__main__':
    with open("English_articles.json", "r", encoding='utf-8') as f:
        english_articles = json.load(f)

    run_image_generation(english_articles)

    with open("images.json", "w", encoding='utf-8') as f:
        json.dump(images_data, f, ensure_ascii=False, indent=2)

    print(f"\nImage generation complete. Saved {len(images_data)} entries.")

    if images_data:
        sample_id = next(iter(images_data))
        print(f"\nSample entry ({sample_id}):")
        print(json.dumps(images_data[sample_id], indent=2))
    else:
        print("No images generated")
