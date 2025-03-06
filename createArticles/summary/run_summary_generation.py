"""
Summary Generation Runner
This script runs both English and German summary generators sequentially.
"""
import asyncio
import argparse
import sys
import os
from typing import Optional, List, Dict, Any

# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from supabase_init import SupabaseClient
from createArticles.summary.english_summary import process_articles as process_english
from createArticles.summary.german_summary import process_articles as process_german

# Initialize Supabase client
supabase = SupabaseClient()

async def print_summaries(article_id: Optional[int] = None):
    """Print summaries from the database"""
    try:
        # Build query
        query = supabase.client.table("NewsArticle").select("id", "EnglishSummary", "GermanSummary")
        if article_id is not None:
            query = query.eq("id", article_id)
        
        # Execute query
        response = query.execute()
        
        if not response.data:
            print("No summaries found in database")
            return
            
        print("\n===== Article Summaries =====")
        for article in response.data:
            article_id = article["id"]
            english_summary = article.get("EnglishSummary")
            german_summary = article.get("GermanSummary")
            
            print(f"\nArticle ID: {article_id}")
            if english_summary:
                print(f"English Summary: {english_summary}")
            if german_summary:
                print(f"German Summary: {german_summary}")
            print("-" * 40)
            
    except Exception as e:
        print(f"Error fetching summaries: {e}")

async def get_all_article_ids() -> List[int]:
    """Fetch all article IDs from the database that need summary generation"""
    try:
        # Query articles that don't have either English or German summaries
        response = supabase.client.table("NewsArticle") \
            .select("id") \
            .or_("EnglishSummary.is.null,GermanSummary.is.null") \
            .execute()
        
        return [article["id"] for article in response.data]
    except Exception as e:
        print(f"Error fetching article IDs: {e}")
        return []

async def get_article_status(article_id: int) -> Dict[str, Any]:
    """Check which summaries need to be generated for a specific article"""
    try:
        response = supabase.client.table("NewsArticle") \
            .select("id", "EnglishSummary", "GermanSummary") \
            .eq("id", article_id) \
            .execute()
        
        if not response.data:
            return {"exists": False, "english_needed": False, "german_needed": False}
            
        article = response.data[0]
        return {
            "exists": True,
            "english_needed": article.get("EnglishSummary") is None,
            "german_needed": article.get("GermanSummary") is None
        }
    except Exception as e:
        print(f"Error checking article status: {e}")
        return {"exists": False, "english_needed": False, "german_needed": False}

async def get_articles_status(article_ids: List[int]) -> Dict[int, Dict[str, Any]]:
    """Check which summaries need to be generated for multiple articles"""
    try:
        # Query to get status for all articles in the batch
        response = supabase.client.table("NewsArticle") \
            .select("id", "EnglishSummary", "GermanSummary") \
            .in_("id", article_ids) \
            .execute()
        
        # Initialize results dictionary
        results = {article_id: {"exists": False, "english_needed": False, "german_needed": False} 
                   for article_id in article_ids}
        
        # Process response data
        for article in response.data:
            article_id = article["id"]
            results[article_id] = {
                "exists": True,
                "english_needed": article.get("EnglishSummary") is None,
                "german_needed": article.get("GermanSummary") is None
            }
        
        return results
    except Exception as e:
        print(f"Error checking articles status: {e}")
        # Return default status for all articles in case of error
        return {article_id: {"exists": False, "english_needed": False, "german_needed": False} 
                for article_id in article_ids}

async def process_all_articles(verbose: bool = False, batch_size: int = 10):
    """Process all articles in batches"""
    article_ids = await get_all_article_ids()
    total_articles = len(article_ids)
    
    if total_articles == 0:
        print("No articles found that need summary generation")
        return
    
    print(f"Found {total_articles} articles to process")
    
    # Process articles in batches
    for i in range(0, total_articles, batch_size):
        batch = article_ids[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1} of {(total_articles + batch_size - 1)//batch_size}")
        
        for article_id in batch:
            print(f"\nProcessing article ID: {article_id}")
            
        # Check articles status in batch
        statuses = await get_articles_status(batch)
        
        for article_id in batch:
            status = statuses[article_id]
            if not status["exists"]:
                print(f"Article ID {article_id} not found in database. Skipping.")
                continue
            
            # Generate English summary if needed
            if status["english_needed"]:
                print("Generating English summary...")
                await process_english(verbose, article_id)
            else:
                print("English summary already exists. Skipping.")
            
            # Generate German summary if needed
            if status["german_needed"]:
                print("Generating German summary...")
                await process_german(verbose, article_id)
            else:
                print("German summary already exists. Skipping.")

async def main():
    parser = argparse.ArgumentParser(description="Generate summaries for both English and German articles")
    
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Print detailed information during processing")
    parser.add_argument("--english-only", action="store_true",
                        help="Only generate English summaries")
    parser.add_argument("--german-only", action="store_true",
                        help="Only generate German summaries")
    parser.add_argument("--print", "-p", action="store_true",
                        help="Print the generated summaries after completion")
    parser.add_argument("--article-id", "-a", type=int,
                        help="Specific article ID to process instead of all articles")
    parser.add_argument("--batch-size", "-b", type=int, default=10,
                        help="Number of articles to process in each batch (default: 10)")
    
    args = parser.parse_args()
    
    if args.article_id:
        # Process single article
        article_status = await get_article_status(args.article_id)
        
        if not article_status["exists"]:
            print(f"Article ID {args.article_id} not found in database.")
            return
            
        english_needed = article_status["english_needed"]
        german_needed = article_status["german_needed"]
        
        # Check if there's anything to process
        if not english_needed and not german_needed:
            print(f"Article ID {args.article_id} already has both summaries. Nothing to process.")
            if args.print:
                await print_summaries(args.article_id)
            return
            
        if args.english_only and args.german_only:
            print("Warning: Both --english-only and --german-only flags used; will process only missing summaries")
        
        # Process English summary if needed and requested
        if (english_needed and not args.german_only) or args.english_only:
            print("===== Generating English Summaries =====")
            await process_english(args.verbose, args.article_id)
        elif not args.english_only:
            print("English summary already exists. Skipping.")
            
        # Process German summary if needed and requested
        if (german_needed and not args.english_only) or args.german_only:
            print("\n===== Generating German Summaries =====")
            await process_german(args.verbose, args.article_id)
        elif not args.german_only:
            print("German summary already exists. Skipping.")
            
        if args.print:
            await print_summaries(args.article_id)
    else:
        # Process all articles that need summaries
        await process_all_articles(args.verbose, args.batch_size)
        
        if args.print:
            await print_summaries()
    
    print("Summary generation complete!")

if __name__ == "__main__":
    asyncio.run(main())