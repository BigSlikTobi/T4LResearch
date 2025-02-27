#!/usr/bin/env python3
"""
Standalone script to run the similarity check between articles.
This can be executed separately from the main pipeline to find and update similar articles.
"""

import asyncio
import sys
import os
# Add parent directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from review import check_similarity_and_update

async def main():
    print("Starting standalone similarity check...")
    
    # Run with default threshold of 0.75
    try:
        await check_similarity_and_update(threshold=0.89)
        print("Similarity check completed successfully!")
    except Exception as e:
        print(f"Error during similarity check: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)