import json
import httpx
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
        self.model_name = model_name  # Fixed assignment
        self.api_key = api_key
        self.prompts = load_prompts()
        print(f"Using model: {self.model_name}")  # Added print statement

    async def _call_openai_api(self, prompt: str) -> str:
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
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers=headers,
                    json=payload,
                    timeout=60.0
                )
                if response.status_code != 200:
                    try:
                        error_data = response.json().get("error", {})
                        error_msg = error_data.get("message", response.text)
                    except Exception:
                        error_msg = response.text
                    print(f"Error calling OpenAI API (status code {response.status_code}): {error_msg}")
                    return ""
                data = response.json()
                if "error" in data:
                    print(f"API error returned: {data['error'].get('message', 'Unknown error')}")
                    return ""
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
        raw_response = await self._call_openai_api(prompt)
        print("Raw API response for keywords:", raw_response)
        if not raw_response:
            print("No valid API response received.")
            return []
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