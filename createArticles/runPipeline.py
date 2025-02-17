import os
import subprocess
import sys

# Add parent directory to path to import LLMSetup
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from LLMSetup import initialize_model

def run_pipeline():
    # Initialize LLM models
    print("Initializing LLM models...")
    models = initialize_model("both")
    
    # Run the modules in sequence
    subprocess.run(["python", "fetchUnprocessedArticles.py"], check=True)
    subprocess.run(["python", "extractContent.py"], check=True)
    subprocess.run(["python", "relatedArticles.py"], check=True)
    subprocess.run(["python", "englishArticle.py"], check=True)
    subprocess.run(["python", "germanArticle.py"], check=True)
    subprocess.run(["python", "getImage.py"], check=True)
    # detectTeam is already used within storeInDB, so no separate call
    subprocess.run(["python", "storeInDB.py"], check=True)
    
    # Remove generated JSON files
    for json_file in [
        "extracted_contents.json",
        "English_articles.json",
        "German_articles.json",
        "images.json",
        "enriched_background_articles.json"
    ]:
        if os.path.exists(json_file):
            os.remove(json_file)

if __name__ == "__main__":
    run_pipeline()
