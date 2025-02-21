import asyncio  
import json
import google.generativeai as genai
import sys
import os
import yaml

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLMSetup import initialize_model

# Initialize Gemini model using LLMSetup
model_info = initialize_model("gemini")
gemini_model = model_info["model"]

# Load prompts from YAML file
with open(os.path.join(os.path.dirname(__file__), "prompts.yaml"), "r", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

async def generate_english_article(main_content: str, related_source_articles: list, verbose: bool = False) -> dict:
    """
    Generates an English article with headline and structured content.
    Returns a dict with 'headline' and 'content'.
    If verbose is True, includes the raw Gemini response in the result under 'raw_response'.
    """
    prompt = f"""
{prompts['english_prompt']}

**Source Information:**
Main content (main_content) – the central story:
{main_content}

Related articles (related_source_articles) – used as background information and for trivia (each contains an "extracted_content" field with detailed text):
{json.dumps(related_source_articles, indent=2, ensure_ascii=False)}

Please provide your answer strictly in the following JSON format without any additional text:
{{
  "headline": "<h1>Your generated headline</h1>",
  "content": "<div>Your structured article content as HTML, including <p>, <h2>, etc.</div>"
}}
"""
    try:
        # Generate content with increased max_output_tokens.
        response_obj = await asyncio.to_thread(
            gemini_model.generate_content,
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.7,
                max_output_tokens=2048,
            )
        )
        raw_response = response_obj.text
        if verbose:
            print("Raw Gemini response:")
            print(raw_response)
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raw_response = ""

    # Remove markdown code block markers if present.
    if (raw_response.strip().startswith("```")):
        lines = raw_response.strip().splitlines()
        # Remove the first line (```json) and the last line if it's a markdown fence.
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        raw_response = "\n".join(lines)
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}") + 1
    if (json_start != -1 and json_end != -1):
        raw_response_clean = raw_response[json_start:json_end]
    else:
        raw_response_clean = raw_response  # Fallback if markers are not found

    try:
        # Removed unnecessary newline replacement and quote stripping
        response_data = json.loads(raw_response_clean)
        
        # Build the result from the parsed data directly
        result = {
            "headline": response_data.get("headline", ""),
            "content": response_data.get("content", "")
        }
        if verbose:
            result["raw_response"] = raw_response_clean
        return result
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON response: {e}")
        # Fallback: Try to extract content using string manipulation
        try:
            headline_start = raw_response_clean.find('"headline": "') + 12
            headline_end = raw_response_clean.find('",', headline_start)
            content_start = raw_response_clean.find('"content": "') + 11
            content_end = raw_response_clean.rfind('"')
            
            headline = raw_response_clean[headline_start:headline_end]
            content = raw_response_clean[content_start:content_end]
            
            return {
                "headline": headline,
                "content": content,
                "raw_response": raw_response_clean if verbose else ""
            }
        except Exception as e:
            print(f"Fallback parsing failed: {e}")
            return {"headline": "", "content": "", "raw_response": raw_response_clean if verbose else ""}
    except Exception as e:
        print(f"Unknown error: {e}")
        return {"headline": "", "content": "", "raw_response": raw_response_clean if verbose else ""}

async def main():
    # Load files only when running as script
    with open("extracted_contents.json", "r", encoding="utf-8") as f:
        extracted_contents = json.load(f)
    with open("enriched_background_articles.json", "r", encoding="utf-8") as f:
        enriched_related_articles = json.load(f)

    english_articles = {}
    # Loop through each article and generate the English version.
    for article_id, main_content in extracted_contents.items():
        if isinstance(enriched_related_articles, dict):
            related_articles = enriched_related_articles.get(article_id, [])
        else:
            related_articles = enriched_related_articles
        print(f"Generating English article for article ID: {article_id}")
        try:
            article_data = await generate_english_article(main_content, related_articles, verbose=True)
            headline = article_data.get("headline", "")
            content = article_data.get("content", "")
            english_articles[str(article_id)] = {
                "headline": headline,
                "content": content
            }
        except Exception as e:
            print(f"[ERROR] Error generating English article for {article_id}: {e}")
            english_articles[str(article_id)] = {"headline": "", "content": ""}
    # Store resulting dictionary to "English_articles.json"
    with open("English_articles.json", "w", encoding="utf-8") as f:
        json.dump(english_articles, f, indent=2, ensure_ascii=False)
    print("English article generation complete.")

if __name__ == "__main__":
    asyncio.run(main())