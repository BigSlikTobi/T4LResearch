# T4L Research Project
## A Cutting-Edge News Enrichment Platform

## Table of Contents
- [Overview](#overview)
- [Features](#features)
- [Project Structure](#project-structure)
- [Installation & Setup](#installation--setup)
  - [Prerequisites](#prerequisites)
  - [Steps](#steps)
- [Usage](#usage)
  - [Fetching News Articles](#fetching-news-articles)
  - [Processing Articles](#processing-articles)
- [Configuration](#configuration)
- [Testing](#testing)
- [Contributing](#contributing)
- [License](#license)

## Overview
The T4L Research Project is an innovative approach that automatically scrapes news content from leading websites, enriches it with essential background information, and generates unique, informative articles. The project leverages the power of Crawl4AI for content extraction, modern LLMs for content enrichment, and Supabase for seamless database integration and frontend sharing.

## Features
- **Automated News Scraping**: Seamlessly extracts articles from major news websites.
- **Content Enrichment**: Uses advanced LLMs (Gemini and OpenAI) to enhance article information.
- **Multi-Language Support**: Processes both English and German articles.
- **Robust Pipeline**: Integrated scripts for extraction, enrichment, and storage.
- **Supabase Integration**: Efficiently stores and manages processed articles.
- **Modular Design**: Easily extendable for additional features or new news sources.

## Project Structure
```
T4LResearch/
├── createArticles/          # Scripts for processing and enriching articles
│   ├── content_extractor.py
│   ├── detectTeam.py
│   ├── englishArticle.py
│   ├── extractContent.py
│   ├── fetchUnprocessedArticles.py
│   ├── germanArticle.py
│   ├── getImage.py
│   ├── keyword_extractor.py
│   ├── relatedArticles.py
│   ├── runPipeline.py
│   ├── storeInDB.py
│   ├── prompts.yaml
│   └── env/                 # Virtual environment for dependencies
│
├── getArticles/             # Scripts for fetching news articles
│   ├── fetchNews.py
│   ├── postNews.py
│   ├── tests/               # Test scripts
│   └── test_supabase.py
│
├── LLMSetup.py              # Setup and initialization of LLM models
├── supabase_init.py         # Supabase client and database operations
├── requirements.txt         # Project dependencies
└── readme.md                # Project documentation (this file)
```

## Installation & Setup
### Prerequisites
- **Python**: Version 3.12
- **Virtual Environment**: Recommended for dependency management

### Steps
#### Clone the Repository:
```bash
git clone <repository_url>
cd T4LResearch
```

#### Create & Activate Virtual Environment:
```bash
python3 -m venv env
source env/bin/activate  # For Windows use `env\Scripts\activate`
```

#### Install Dependencies:
```bash
pip install -r requirements.txt
```

#### Environment Setup:
Run the following to configure Crawl4AI and Playwright:
```bash
run crawl4ai-setup  # or crawl4ai-doctor as needed
python -m playwright install
```

#### Supabase Configuration:
Create a `.env` file or set your environment variables:
```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
export OPENAI_API_KEY="your-openai-api-key"      # if using OpenAI
export GEMINI_API_KEY="your-gemini-api-key"      # if using Gemini
```

## Usage
### Fetching News Articles
Run the fetch script to scrape the latest news:
```bash
python getArticles/fetchNews.py
```

### Processing Articles
After fetching, process and enrich articles by running:
```bash
python createArticles/runPipeline.py
```
The scripts use advanced LLM setups (both Gemini and OpenAI) for content enrichment as configured in `LLMSetup.py`.

## Configuration
### Supabase:
Set your credentials in a `.env` file or via shell environment variables:
```bash
export SUPABASE_URL="your-supabase-url"
export SUPABASE_KEY="your-supabase-key"
```

### LLM Providers:
Ensure that the required API keys for OpenAI and Gemini are set:
```bash
export OPENAI_API_KEY="your-openai-api-key"
export GEMINI_API_KEY="your-gemini-api-key"
```

## Testing
Run the test suite to validate your setup:
```bash
pytest tests/
```

## Contributing
Contributions are welcome!

1. Fork the repository
2. Create a new branch for your feature or bug fix
3. Submit a pull request for review

Feel free to open an issue if you have any questions or suggestions.

## License
This project is licensed under the MIT License.
