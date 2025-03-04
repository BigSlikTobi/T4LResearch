"""
Pipeline for processing articles sequentially, including topic assignment and verification.
"""

import asyncio
import sys
import os
# Add the parent directory to the Python path to allow for absolute imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from createArticles.fetchUnprocessedArticles import get_all_active_news
from createArticles.storeInDB import mark_article_as_processed
from createArticles.review import check_similarity_and_update
# Import functions from the dataPrep package
from createArticles.dataPrep import (
    check_processed_articles_similarity,
    group_similar_articles,
    process_article_group
)
# Import topic assignment functions
from topicManagement.topic_matcher import process_article
from topicManagement.debug_topic_assignment import debug_article_topic_assignment

async def main():
    try:
        # First run similarity check on any unprocessed articles to update existing ones
        # This ensures that we don't create duplicates when similar articles already exist
        processed_ids = await check_similarity_and_update(threshold=0.89)
        
        # Get both unprocessed and active articles
        unprocessed_articles, active_articles = get_all_active_news()
        
        if not unprocessed_articles:
            print("No unprocessed articles found.")
            # Even if no unprocessed articles were found, still run the similarity check
            print("Running similarity check on existing articles...")
            await check_processed_articles_similarity()
            return
            
        # Filter out articles that were already processed by similarity check
        if processed_ids:
            unprocessed_articles = [a for a in unprocessed_articles if a["id"] not in processed_ids]
            print(f"Filtered out {len(processed_ids)} articles already processed by similarity check")
            
        if not unprocessed_articles:
            print("All unprocessed articles were handled by similarity check.")
            return
            
        # Group similar articles, now considering both new and existing articles
        groups = group_similar_articles(unprocessed_articles, active_articles, threshold=0.85)
        print(f"Found {len(groups)} group(s) of similar articles.")
        
        # Track newly processed article IDs for topic assignment - Store as {news_result_id: news_article_id} mapping
        newly_processed_article_mapping = {}
        
        # Process each group sequentially
        for group in groups:
            try:
                group_ids = [article["id"] for article in group]
                print(f"\nProcessing group with article IDs: {group_ids}")
                processed_article_ids, news_article_ids = await process_article_group(group)
                
                # Add successfully processed articles to our tracking dictionary
                if processed_article_ids and news_article_ids:
                    for i, news_result_id in enumerate(processed_article_ids):
                        if i < len(news_article_ids):  # Safety check
                            newly_processed_article_mapping[news_result_id] = news_article_ids[i]
                
            except Exception as e:
                print(f"Error processing article group {group_ids}: {e}")
                import traceback
                print(f"Exception traceback: {traceback.format_exc()}")
                # Continue with next group even if this one fails
                continue
        
        # After processing all groups, assign topics to the newly processed articles
        if newly_processed_article_mapping:
            print("\n========= ASSIGNING TOPICS TO NEW ARTICLES =========")
            print(f"Assigning topics to {len(newly_processed_article_mapping)} newly processed articles...")
            
            for news_result_id, news_article_id in newly_processed_article_mapping.items():
                try:
                    print(f"Assigning topic to article {news_article_id} (from NewsResult {news_result_id})...")
                    
                    # Process article with news_article_id directly
                    await process_article(news_article_id)
                    
                    # After processing, run the debug routine to verify and fix if needed
                    print(f"\n========= VERIFYING TOPIC ASSIGNMENT FOR ARTICLE {news_article_id} =========")
                    await debug_article_topic_assignment(news_article_id)
                        
                except Exception as e:
                    print(f"Error assigning topic to article {news_article_id}: {e}")
                    import traceback
                    print(f"Exception traceback: {traceback.format_exc()}")
                    # Continue with next article even if this one fails
                    continue
    
    except Exception as e:
        print(f"Error in main processing pipeline: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
    
    finally:
        # Always run the extended similarity check, even if there were errors
        print("\n========= RUNNING FINAL SIMILARITY CHECK =========")
        print("This check will find similar articles between newly processed and existing articles.")
        try:
            await check_processed_articles_similarity()
        except Exception as e:
            print(f"Error in extended similarity check: {e}")
            import traceback
            print(f"Exception traceback: {traceback.format_exc()}")
        
        print("\nPipeline completed.")

if __name__ == "__main__":
    asyncio.run(main())
