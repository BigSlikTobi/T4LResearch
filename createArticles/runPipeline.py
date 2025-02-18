import os
import subprocess
import sys

# Add parent directory to path to import LLMSetup
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from LLMSetup import initialize_model

def run_pipeline():
    # Initialize LLM models
    print("Initializing LLM models...")
    models = initialize_model("both")
    
    # Set environment for subprocess calls
    env = os.environ.copy()
    env["PYTHONPATH"] = parent_dir + os.pathsep + env.get("PYTHONPATH", "")
    
    # Change to the script directory for running the pipeline
    os.chdir(current_dir)
    
    # Run the modules in sequence
    subprocess.run(["python", "fetchUnprocessedArticles.py"], check=True, env=env)
    subprocess.run(["python", "extractContent.py"], check=True, env=env)
    subprocess.run(["python", "relatedArticles.py"], check=True, env=env)
    subprocess.run(["python", "englishArticle.py"], check=True, env=env)
    subprocess.run(["python", "germanArticle.py"], check=True, env=env)
    subprocess.run(["python", "getImage.py"], check=True, env=env)
    subprocess.run(["python", "storeInDB.py"], check=True, env=env)
    
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
