"""
Debugging script to investigate and fix topic assignment for a specific article.
This script focuses on finding and fixing the NFL Combine article topic assignment.
"""

import asyncio
import os
import sys
import json
from typing import Dict, List, Any

# Add parent directory to Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topicManagement.topic_matcher import process_article, match_article_with_topics, update_article_topic
from topicManagement.topic_fetcher import fetch_active_topics
from supabase_init import SupabaseClient

async def debug_article_topic_assignment(article_id: int):
    """
    Debug the topic assignment process for a specific article
    
    Args:
        article_id (int): The article ID to debug
    """
    print(f"\n===== DEBUGGING TOPIC ASSIGNMENT FOR ARTICLE {article_id} =====")
    
    # Initialize Supabase client
    supabase = SupabaseClient()
    
    # 1. Fetch the article content
    response = supabase.client.table("NewsArticle").select("id", "EnglishHeadline", "EnglishArticle", "Topic").eq("id", article_id).execute()
    
    if not response.data or len(response.data) == 0:
        print(f"Article {article_id} not found")
        return
    
    article = response.data[0]
    headline = article.get("EnglishHeadline", "")
    content = article.get("EnglishArticle", "")
    current_topic = article.get("Topic")
    
    print(f"Article: {headline}")
    print(f"Current topic: {current_topic}")
    
    # 2. Fetch all active topics
    topics = fetch_active_topics()
    print(f"Found {len(topics)} active topics")
    
    # 3. Debug: find a topic with "combine" in the name
    combine_topics = [t for t in topics if "combine" in t.get("TopicName", "").lower()]
    if combine_topics:
        print(f"Found topic(s) related to 'combine': {[t.get('TopicName') for t in combine_topics]}")
        combine_topic = combine_topics[0]
        print(f"Topic details for '{combine_topic.get('TopicName')}':")
        print(f"  - Description: {combine_topic.get('Description')}")
        print(f"  - Keywords: {combine_topic.get('Keywords')}")
    else:
        print("No topic found with 'combine' in the name")
    
    # 4. Debug keyword matching directly for all topics
    print("\nDEBUGGING KEYWORD MATCHING:")
    full_content = f"{headline}\n\n{content}"
    best_match = None
    best_score = 0
    
    for topic in topics:
        topic_name = topic.get("TopicName", "")
        topic_keywords = topic.get("Keywords", []) or []
        
        # Count keyword matches
        keyword_count = 0
        matched_keywords = []
        
        for keyword in topic_keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in full_content.lower():
                keyword_count += 1
                matched_keywords.append(keyword)
        
        # Calculate match score based on keyword frequency
        score = keyword_count / len(topic_keywords) if topic_keywords else 0
        
        print(f"Topic '{topic_name}': Score {score:.2f} ({keyword_count}/{len(topic_keywords)} keywords)")
        if matched_keywords:
            print(f"  - Matched keywords: {matched_keywords}")
        
        # Track best match
        if score > best_score:
            best_score = score
            best_match = topic
    
    if best_match:
        print(f"\nBest keyword match: '{best_match.get('TopicName')}' with score {best_score:.2f}")
    
    # 5. Try matching with the standard algorithm
    print("\nTrying standard matching algorithm:")
    matched_topic = match_article_with_topics(content, headline, topics)
    
    if matched_topic:
        topic_name = matched_topic.get("TopicName")
        print(f"Standard algorithm matched topic: '{topic_name}'")
        
        # Try to update with the matched topic
        print("\nAttempting to update with matched topic...")
        success = await update_article_topic(article_id, topic_name)
        if success:
            print(f"Successfully assigned topic '{topic_name}' to article {article_id}")
        else:
            print(f"Failed to assign matched topic '{topic_name}' to article {article_id}")
            
            # If automatic update failed, try force-assign
            if combine_topics:
                print("\nAttempting force-assign as fallback...")
                combine_topic_name = combine_topics[0].get("TopicName")
                force_success = await update_article_topic(article_id, combine_topic_name)
                if force_success:
                    print(f"Successfully force-assigned topic '{combine_topic_name}' to article {article_id}")
                else:
                    print(f"Failed to force-assign topic '{combine_topic_name}' to article {article_id}")
    else:
        print("Standard algorithm found no match")
        
        # Try force-assign if no match found
        if combine_topics:
            print("\nNo match found, attempting force-assign...")
            combine_topic_name = combine_topics[0].get("TopicName")
            success = await update_article_topic(article_id, combine_topic_name)
            if success:
                print(f"Successfully force-assigned topic '{combine_topic_name}' to article {article_id}")
            else:
                print(f"Failed to force-assign topic '{combine_topic_name}' to article {article_id}")

async def main():
    # Debug the newly created article with ID 712
    await debug_article_topic_assignment(712)

if __name__ == "__main__":
    asyncio.run(main())