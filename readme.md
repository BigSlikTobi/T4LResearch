# T4L Research Project
## Overview
This project is designed to fetch, process, and store news articles using various AI models and APIs. The main components of the project include fetching news articles, processing them to extract relevant content, and storing the processed data in a Supabase database.

## Project Structure
createArticles: Contains scripts for processing articles.

content_extractor.py: Extracts content from articles.
detectTeam.py: Detects the team associated with an article.
englishArticle.py: Processes English articles.
extractContent.py: Extracts core content from articles.
fetchUnprocessedArticles.py: Fetches unprocessed articles.
germanArticle.py: Processes German articles.
getImage.py: Retrieves images for articles.
keyword_extractor.py: Extracts keywords from articles.
relatedArticles.py: Finds related articles based on keywords.
runPipeline.py: Runs the entire processing pipeline.
storeInDB.py: Stores processed articles in the database.
prompts.yaml: Contains prompts for AI models.
env: Virtual environment containing dependencies.

getArticles: Contains scripts for fetching news articles.

fetchNews.py: Fetches news articles from various sources.
postNews.py: Posts news articles to the database.
tests: Contains test scripts.

test_supabase.py: Tests for Supabase integration.
LLMSetup.py: Sets up language models for processing articles.

supabase_init.py: Initializes Supabase client for database operations.

requirements.txt: Lists project dependencies.

readme.md: Project documentation.

## Setup
### ,Prerequisites
Python 3.12
Virtual environment

Installation

1. Clone the repository:
git clone https://github.com/BigSlikTobi/T4LResearch.git
cd T4LResearch

2. Create and activate a virtual environment:
python3 -m venv env
source env/bin/activate

3. Install dependencies:
pip install -r requirements.txt

4. Set up the environment:
run crawl4ai-setup / crawl4ai-doctor
python -m playwright install

## Usage

### Fetching News Articles
To fetch news articles, run:
python getArticles/fetchNews.py

### Processing Articles
To process articles, run:
python createArticles/runPipeline.py

## Configuration

Set your Supabase environment variables in a .env file or using the shell:

export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"

## Testing
To run tests, use:

pytest tests/
Contributing

Contributions are welcome! Please submit a pull request or open an issue to discuss your ideas.

ääLicense
This project is licensed under the MIT License.

