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

async def generate_german_article(main_content: str, related_source_articles: list, verbose: bool = False) -> dict:
    """ Generiert einen deutschen Artikel mit Überschrift und strukturiertem Inhalt.
        Gibt ein Dictionary mit 'headline' und 'content' zurück.
        Wenn verbose auf True gesetzt ist, wird die rohe Gemini-Antwort unter 'raw_response' in das Ergebnis aufgenommen.
    """
    prompt = f"""
{prompts['german_prompt']}

**Quellinformationen:**
Main content (main_content) – the central story:
{main_content}

Related articles (related_source_articles) – used as background information and for trivia (each contains an "extracted_content" field with detailed text):
{json.dumps(related_source_articles, indent=2, ensure_ascii=False)}

Bitte gib die Antwort ausschließlich im folgenden JSON-Format aus, ohne zusätzlichen Text:
{{
  "headline": "<h1>Deine generierte Überschrift</h1>",
  "content": "<div>Dein strukturierter Artikelinhalt als HTML (inkl. <p>, <h2>, etc.)</div>"
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
            print("Response Object:", response_obj) 
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raw_response = ""

    # Remove markdown code block markers if present.
    # This extracts text between the first '{' and the last '}'.
    json_start = raw_response.find("{")
    json_end = raw_response.rfind("}") + 1
    if json_start != -1 and json_end != -1:
        raw_response_clean = raw_response[json_start:json_end]
    else:
        raw_response_clean = raw_response  # Fallback if markers are not found

    try:
        response_data = json.loads(raw_response_clean)
        # Build the result from the parsed data.
        result = {
            "headline": response_data.get("headline", ""),
            "content": response_data.get("content", "")
        }
        if verbose:
            result["raw_response"] = raw_response_clean
        return result
    except json.JSONDecodeError:
        print("Error parsing JSON response.")
        print(f"Raw response: {raw_response_clean}")
        return {"headline": "", "content": "", "raw_response": raw_response_clean if verbose else ""}
    except Exception as e:
        print(f"Unknown error: {e}")
        return {"headline": "", "content": "", "raw_response": raw_response_clean if verbose else ""}

# Load main article contents and enriched related articles
with open("extracted_contents.json", "r", encoding="utf-8") as f:
    extracted_contents = json.load(f)
with open("enriched_background_articles.json", "r", encoding="utf-8") as f:
    enriched_related_articles = json.load(f)

async def main():
    german_articles = {}
    # Loop through each article and generate the German version.
    for article_id, main_content in extracted_contents.items():
        related_articles = enriched_related_articles.get(article_id, []) if isinstance(enriched_related_articles, dict) else enriched_related_articles
        print(f"Generating German article for article ID: {article_id}")
        try:
            article_data = await generate_german_article(main_content, related_articles, verbose=True)
            headline = article_data.get("headline", "")
            content = article_data.get("content", "")
            german_articles[str(article_id)] = {
                "headline": headline,
                "content": content
            }
        except Exception as e:
            print(f"[ERROR] Error generating German article for {article_id}: {e}")
            german_articles[str(article_id)] = {"headline": "", "content": ""}
    # Save the resulting dictionary to "German_articles.json"
    with open("German_articles.json", "w", encoding="utf-8") as f:
        json.dump(german_articles, f, indent=2, ensure_ascii=False)
    print("German article generation complete.")

if __name__ == "__main__":
    asyncio.run(main())