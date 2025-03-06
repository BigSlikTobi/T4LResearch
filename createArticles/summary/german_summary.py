"""
German Summary Generator for T4L Articles
This module generates a bold, engaging 2-sentence summary for German articles.
"""
import asyncio
import json
import sys
import os
import yaml
import google.generativeai as genai
from typing import Optional, Dict, Any

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from LLMSetup import initialize_model
from supabase_init import SupabaseClient

# Initialize Gemini model using LLMSetup
model_info = initialize_model("gemini")
gemini_model = model_info["model"]

# Initialize Supabase client
supabase = SupabaseClient()

# Load prompts from YAML file
with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts.yaml"), "r", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

async def generate_german_summary(article_content: str, verbose: bool = False) -> str:
    """
    Generates a bold, attention-grabbing 2-sentence summary of a German article.
    
    Args:
        article_content: The HTML content of the article to summarize
        verbose: Whether to print detailed information during processing
    
    Returns:
        A string containing the 2-sentence summary in German
    """
    prompt = f"""
Du bist ein Meister der Sport-Schlagzeilen und ein Journalist, der für packende, fesselnde NFL-Zusammenfassungen bekannt ist.

Erstelle eine außergewöhnlich fesselnde 2-Satz-Zusammenfassung des folgenden Artikels, die die Leser dazu bringt, mehr erfahren zu wollen.
Der erste Satz sollte eine KRAFTVOLLE, DRAMATISCHE ENTHÜLLUNG sein, die den wichtigsten oder überraschendsten Aspekt der Geschichte einfängt.
Der zweite Satz sollte wichtigen Kontext hinzufügen und dabei die Spannung aufrechterhalten.

Anforderungen:
- Schreibe wie für BREAKING NEWS
- Der erste Satz muss wie eine packende Schlagzeile klingen
- Verwende starke, dynamische Verben
- Sei präzise mit Zahlen, Namen und Fakten
- Erzeuge ein Gefühl von Dringlichkeit
- Bleibe absolut faktisch, während du dramatisch bist
- Jeder Satz muss prägnant und einprägsam sein

Beispiel Format:
"Star-Quarterback Brady schockt die NFL mit sensationellem Comeback! Der siebenfache Super-Bowl-Champion unterschreibt überraschend bei den Raiders und elektrisiert die AFC West."

**Artikelinhalt:**
{article_content}

Antworte NUR mit der 2-Satz-Zusammenfassung, ohne zusätzlichen Text oder Erklärung.
"""

    max_retries = 3
    retry_count = 0
    current_temperature = 0.9
    
    while retry_count < max_retries:
        try:
            # Generate summary with dynamically adjusted parameters
            response_obj = await asyncio.to_thread(
                gemini_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=current_temperature,
                    max_output_tokens=1024,
                    top_p=0.8,
                    top_k=40,
                )
            )
            
            # Check if we have a valid response
            if hasattr(response_obj, 'text') and response_obj.text:
                summary = response_obj.text.strip()
                
                if verbose:
                    print("Generated German Summary:")
                    print(summary)
                    
                return summary
            else:
                print(f"Empty response from model (attempt {retry_count + 1}/{max_retries})")
                current_temperature -= 0.2  # Reduce temperature for next attempt
                retry_count += 1
                await asyncio.sleep(1)  # Brief pause before retry
                
        except Exception as e:
            print(f"Error on attempt {retry_count + 1}/{max_retries}: {e}")
            current_temperature -= 0.2  # Reduce temperature for next attempt
            retry_count += 1
            await asyncio.sleep(1)  # Brief pause before retry
            
    # If all retries failed, try a fallback approach with much simpler prompt
    try:
        fallback_prompt = f"""
Fasse diesen NFL-Artikel in genau zwei Sätzen auf Deutsch zusammen:

{article_content}

Der erste Satz soll die Hauptnachricht dramatisch vermitteln.
Der zweite Satz soll wichtige Details hinzufügen.
Antwort nur mit den zwei Sätzen."""

        response_obj = await asyncio.to_thread(
            gemini_model.generate_content,
            fallback_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.5,  # Much lower temperature for more reliable output
                max_output_tokens=1024,
            )
        )
        
        if hasattr(response_obj, 'text') and response_obj.text:
            return response_obj.text.strip()
            
    except Exception as e:
        print(f"Fallback approach also failed: {e}")
        
    return ""

async def process_article_by_id(article_id: int, verbose: bool = False) -> Optional[str]:
    """
    Process a specific article by ID from the database and generate its summary.
    
    Args:
        article_id: The ID of the article to process
        verbose: Whether to print detailed information during processing
        
    Returns:
        The generated summary string or None if article not found
    """
    try:
        # Fetch article from database
        response = supabase.client.table("NewsArticle").select("*").eq("id", article_id).execute()
        
        if not response.data or len(response.data) == 0:
            print(f"Article with ID '{article_id}' not found in database")
            return None
            
        article_data = response.data[0]
        article_content = article_data.get("GermanArticle", "")
        
        if not article_content:
            print(f"Article {article_id} has no German content")
            return None
            
        print(f"Generating German summary for article ID: {article_id}")
        summary = await generate_german_summary(article_content, verbose)
        
        if summary:
            # Update the article with the new summary
            supabase.client.table("NewsArticle").update(
                {"GermanSummary": summary}
            ).eq("id", article_id).execute()
            
            print(f"German summary for article ID {article_id} generated and saved to database")
        
        return summary
        
    except Exception as e:
        print(f"Error processing article: {e}")
        return None

async def process_articles(verbose: bool = False, article_id: Optional[int] = None):
    """
    Process articles from the database and generate summaries.
    
    Args:
        verbose: Whether to print detailed information during processing
        article_id: Optional specific article ID to process instead of all articles
    """
    try:
        if article_id is not None:
            return await process_article_by_id(article_id, verbose)
            
        # Fetch all articles that don't have a German summary yet
        response = supabase.client.table("NewsArticle").select("*").is_("GermanSummary", "null").execute()
        
        if not response.data:
            print("No articles found needing German summaries")
            return
            
        for article in response.data:
            article_id = article["id"]
            await process_article_by_id(article_id, verbose)
            
        print("German summaries generation complete")
        
    except Exception as e:
        print(f"Error processing articles: {e}")

async def main():
    """Main function to run when executed as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate 2-sentence summaries for German articles")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Print detailed information during processing")
    parser.add_argument("--article-id", "-a", type=int,
                      help="Specific article ID to process instead of all articles")
    
    args = parser.parse_args()
    
    await process_articles(args.verbose, args.article_id)

if __name__ == "__main__":
    asyncio.run(main())