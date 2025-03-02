"""
Script to run all status management functions.
This script is designed to be called from a GitHub Actions workflow.
"""
import sys
import os
from pathlib import Path

# Add the project root directory to Python's module search path
project_root = str(Path(__file__).parent.parent.parent.absolute())
sys.path.insert(0, project_root)

# Now we can import our modules
from createArticles.statusManagement import (
    update_article_statuses,
    update_missing_statuses,
    cleanup_archived_articles
)

def main():
    """Run all status management functions in the correct order."""
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    print("Starting status management...")
    
    try:
        print("\nRunning update_missing_statuses...")
        update_missing_statuses()
        
        print("\nRunning cleanup_archived_articles...")
        cleanup_archived_articles()
        
        print("\nRunning update_article_statuses...")
        update_article_statuses()
        
        print("\nStatus management completed successfully")
    except Exception as e:
        print(f"Error during status management: {e}")
        # Raise the exception to ensure the workflow fails
        raise e

if __name__ == "__main__":
    main()