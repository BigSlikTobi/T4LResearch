"""
Module for fetching active topics from the database.

This module handles the retrieval of topic data from the Topics table.
It focuses on retrieving active topics that can be assigned to articles.
"""

import os
import sys
from typing import List, Dict, Any
from dotenv import load_dotenv

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from supabase import create_client, Client

# Load environment variables
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_active_topics() -> List[Dict[str, Any]]:
    """
    Fetches all active topics from the Topics table.
    
    Returns:
        List[Dict[str, Any]]: List of active topic records with their attributes
    """
    try:
        # Query only active topics
        response = supabase_client.table("Topics").select("*").eq("isActive", True).execute()
        
        if not response.data:
            print("No active topics found in the database.")
            return []
            
        print(f"Retrieved {len(response.data)} active topics from the database.")
        return response.data
        
    except Exception as e:
        print(f"Error fetching active topics from database: {e}")
        return []

if __name__ == "__main__":
    # Simple test when run directly
    topics = fetch_active_topics()
    for topic in topics:
        print(f"Topic: {topic.get('TopicName')}, Keywords: {topic.get('Keywords', [])}")