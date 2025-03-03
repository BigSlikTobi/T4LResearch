#!/usr/bin/env python3
"""
Script to run the topic assignment process.

This script serves as the main entry point for assigning topics to articles.
It can be run as a standalone script or imported and used in other modules.
"""

import os
import sys
import asyncio
import argparse
from typing import Optional, List

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topicManagement.topic_matcher import process_article, process_all_articles, update_articles_with_topic_names
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def run_topic_assignment(article_ids: Optional[List[int]] = None, 
                               convert_ids_to_names: bool = False):
    """
    Run the topic assignment process for specified articles or all unassigned articles.
    
    Args:
        article_ids (Optional[List[int]]): List of article IDs to process, or None to process all
        convert_ids_to_names (bool): If True, convert numeric topic IDs to names for all articles
    """
    if convert_ids_to_names:
        print("Converting topic IDs to topic names for all articles...")
        processed, updated = await update_articles_with_topic_names()
        print(f"Summary: Processed {processed} articles, updated {updated} with topic names")
    elif article_ids:
        print(f"Processing {len(article_ids)} specified articles...")
        for article_id in article_ids:
            await process_article(article_id)
    else:
        print("Processing all unassigned articles...")
        processed, matched = await process_all_articles()
        print(f"Summary: Processed {processed} articles, matched {matched} with topics")
    
    print("Topic assignment process complete.")

def main():
    """Main function to parse arguments and run the topic assignment process."""
    parser = argparse.ArgumentParser(description="Assign topics to articles based on content matching")
    
    # Add optional argument for specific article IDs
    parser.add_argument(
        "--article-ids", 
        type=int, 
        nargs="+", 
        help="Optional: Specific article IDs to process"
    )
    
    # Add flag for converting topic IDs to names
    parser.add_argument(
        "--convert-ids-to-names",
        action="store_true",
        help="Convert numeric topic IDs to topic names for all articles"
    )
    
    args = parser.parse_args()
    
    # Run the topic assignment process
    asyncio.run(run_topic_assignment(args.article_ids, args.convert_ids_to_names))

if __name__ == "__main__":
    main()