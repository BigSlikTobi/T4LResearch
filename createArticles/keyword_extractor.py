import json
import requests
import os
import yaml
from typing import List, Dict

def load_prompts():
    with open(os.path.join(os.path.dirname(__file__), "prompts.yaml"), "r") as f:
        return yaml.safe_load(f)

def strip_markdown(response_text: str) -> str:
    response_text = response_text.strip()
    if response_text.startswith("```json") and response_text.endswith("```"):
        return response_text[len("```json"): -len("```")].strip()
    return response_text

class KeywordExtractor:
    def __init__(self, model_name: str, api_key: str):
        self.model_name = model_name
        self.api_key = api_key
        self.prompts = load_prompts()

    def _call_openai_api(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are ChatGPT, a large language model trained by OpenAI."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1800,
        }
        try:
            response = requests.post("https://api.openai.com/v1/chat/completions",
                                   headers=headers, json=payload, timeout=60)
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print("Error calling OpenAI API:", e)
            return ""

    async def extract_keywords(self, main_content: str) -> List[str]:
        """
        Extracts the top keywords from the main_content using the OpenAI API.
        Returns only keywords with a confidence score > 0.75.
        """
        prompt = self.prompts["keyword_extraction_prompt"].format(article_content=main_content)
        raw_response = self._call_openai_api(prompt)
        print("Raw API response for keywords:", raw_response)
        raw_response = strip_markdown(raw_response)
        try:
            keywords_data = json.loads(raw_response)
            if not isinstance(keywords_data, list):
                raise ValueError("Expected a list of keyword objects.")
            valid_keywords = [item["keyword"] for item in keywords_data 
                            if isinstance(item, dict) and float(item.get("confidence", 0)) > 0.75]
            print("Extracted and filtered Keywords:", valid_keywords)
            return valid_keywords
        except Exception as e:
            print("Error extracting keywords:", e)
            return []