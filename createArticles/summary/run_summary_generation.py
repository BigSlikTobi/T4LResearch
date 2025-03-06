"""
Summary Generation Runner
This script runs both English and German summary generators sequentially.
"""
import asyncio
import argparse
import sys
import os
from typing import Optional, List

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
            
            # Generate English summary
            print("Generating English summary...")
            await process_english(verbose, article_id)
            
            # Generate German summary
            print("Generating German summary...")
            await process_german(verbose, article_id)

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
        if args.english_only and args.german_only:
            print("Warning: Both --english-only and --german-only flags used; running both generators anyway")
            run_both = True
        elif args.english_only:
            run_both = False
            print("Running English summary generation only")
            await process_english(args.verbose, args.article_id)
            if args.print:
                await print_summaries(args.article_id)
        elif args.german_only:
            run_both = False
            print("Running German summary generation only")
            await process_german(args.verbose, args.article_id)
            if args.print:
                await print_summaries(args.article_id)
        else:
            run_both = True
        
        if run_both:
            print("===== Generating English Summaries =====")
            await process_english(args.verbose, args.article_id)
            
            print("\n===== Generating German Summaries =====")
            await process_german(args.verbose, args.article_id)
            
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