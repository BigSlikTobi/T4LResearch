"""
English Summary Generator for T4L Articles
This module generates a bold, engaging 2-sentence summary for English articles.
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

async def generate_english_summary(article_content: str, verbose: bool = False) -> str:
    """
    Generates a bold, attention-grabbing 2-sentence summary of an English article.
    
    Args:
        article_content: The HTML content of the article to summarize
        verbose: Whether to print detailed information during processing
    
    Returns:
        A string containing the 2-sentence summary
    """
    prompt = f"""
You are a master headline writer and expert sports journalist known for creating irresistible, attention-grabbing summaries.

Create an extremely engaging 2-sentence summary of the following article that will make readers want to learn more.
The first sentence should be a BOLD, IMPACTFUL REVELATION that captures the most dramatic or interesting aspect of the story.
The second sentence should add crucial context while maintaining the intrigue.

Requirements:
- Write as if this is BREAKING NEWS
- Make the first sentence read like a powerful headline
- Use strong, dynamic verbs
- Be specific and concrete with numbers, names, and facts
- Create a sense of urgency or importance
- Stay completely factual while being dramatic
- Each sentence must be punchy and memorable

Example format:
"Star QB Tom Brady's Shock Return Rocks NFL! The 7-time Super Bowl champion's surprise comeback deal with the Raiders sets up an epic AFC West showdown."

**Article Content:**
{article_content}

Respond with ONLY the 2-sentence summary, without any additional text or explanation.
"""

    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            # Generate summary with adjusted parameters
            response_obj = await asyncio.to_thread(
                gemini_model.generate_content,
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.9,  # Increased temperature for more creative language
                    max_output_tokens=1024,
                    top_p=0.8,
                    top_k=40,
                )
            )
            
            # Check if we have a valid response
            if hasattr(response_obj, 'text') and response_obj.text:
                summary = response_obj.text.strip()
                
                if verbose:
                    print("Generated English Summary:")
                    print(summary)
                    
                return summary
            else:
                print(f"Empty response from model (attempt {retry_count + 1}/{max_retries})")
                retry_count += 1
                await asyncio.sleep(1)  # Brief pause before retry
                
        except Exception as e:
            print(f"Error on attempt {retry_count + 1}/{max_retries}: {e}")
            retry_count += 1
            await asyncio.sleep(1)  # Brief pause before retry
            
    # If all retries failed, try a fallback approach with simpler prompt
    try:
        fallback_prompt = f"""
Write a 2-sentence breaking news summary of this article:

{article_content}

Make the first sentence dramatic like a headline, and the second sentence add key context.
Respond with only the two sentences."""

        response_obj = await asyncio.to_thread(
            gemini_model.generate_content,
            fallback_prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.5,  # Lower temperature for more reliable output
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
        article_content = article_data.get("EnglishArticle", "")
        
        if not article_content:
            print(f"Article {article_id} has no English content")
            return None
            
        print(f"Generating English summary for article ID: {article_id}")
        summary = await generate_english_summary(article_content, verbose)
        
        if summary:
            # Update the article with the new summary
            supabase.client.table("NewsArticle").update(
                {"EnglishSummary": summary}
            ).eq("id", article_id).execute()
            
            print(f"English summary for article ID {article_id} generated and saved to database")
        
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
            
        # Fetch all articles that don't have an English summary yet
        response = supabase.client.table("NewsArticle").select("*").is_("EnglishSummary", "null").execute()
        
        if not response.data:
            print("No articles found needing English summaries")
            return
            
        for article in response.data:
            article_id = article["id"]
            await process_article_by_id(article_id, verbose)
            
        print("English summaries generation complete")
        
    except Exception as e:
        print(f"Error processing articles: {e}")

async def main():
    """Main function to run when executed as a script"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate 2-sentence summaries for English articles")
    parser.add_argument("--verbose", "-v", action="store_true",
                      help="Print detailed information during processing")
    parser.add_argument("--article-id", "-a", type=int,
                      help="Specific article ID to process instead of all articles")
    
    args = parser.parse_args()
    
    await process_articles(args.verbose, args.article_id)

if __name__ == "__main__":
    asyncio.run(main())