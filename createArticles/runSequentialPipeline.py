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
        
        # Process each group sequentially
        for group in groups:
            try:
                group_ids = [article["id"] for article in group]
                print(f"\nProcessing group with article IDs: {group_ids}")
                await process_article_group(group)
            except Exception as e:
                print(f"Error processing article group {group_ids}: {e}")
                import traceback
                print(f"Exception traceback: {traceback.format_exc()}")
                # Continue with next group even if this one fails
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
