import json
from typing import Dict, List
import supabase
from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load environment variables from .env in project root
load_dotenv("/Users/tobiaslatta/Desktop/Private/T4L/T4LResearch/.env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_unprocessed_articles() -> List[Dict]:
    """
    Fetches NewsResults records where isProcessed = false.
    """
    try:
        response = supabase_client.table("NewsResults").select("*").eq("isProcessed", False).execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching unprocessed items from Supabase: {e}")
        return []

def get_active_articles() -> List[Dict]:
    """
    Fetches all active NewsArticle records (not ARCHIVED).
    """
    try:
        response = supabase_client.table("NewsArticle")\
            .select("*")\
            .not_.eq("Status", "ARCHIVED")\
            .execute()
        return response.data or []
    except Exception as e:
        print(f"Error fetching active articles from Supabase: {e}")
        return []

def get_all_active_news() -> tuple[List[Dict], List[Dict]]:
    """
    Fetches both unprocessed NewsResults and active NewsArticle records.
    Returns a tuple of (unprocessed_articles, active_articles).
    """
    return get_unprocessed_articles(), get_active_articles()

if __name__ == "__main__":
    unprocessed_articles = get_unprocessed_articles()
    print(f"Found {len(unprocessed_articles)} unprocessed articles.")
