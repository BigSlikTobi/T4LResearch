import json
import asyncio
import requests
from dotenv import load_dotenv
import os
import yaml
from LLMSetup import initialize_model

class detectTeam:
    def __init__(self):
        load_dotenv()
        try:
            model_info = initialize_model("openai")
            self.model = model_info["model"]
            self.OPENAI_API_KEY = self.model["api_key"]
            
            # Load prompts from YAML file
            yaml_path = os.path.join(os.path.dirname(__file__), 'prompts.yaml')
            with open(yaml_path, 'r') as f:
                self.prompts = yaml.safe_load(f)
        except Exception as e:
            raise ValueError(f"Failed to initialize: {e}")

    def call_openai_api(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.OPENAI_API_KEY}",
        }
        payload = {
            "model": self.model["provider"],
            "messages": [
                {"role": "system", "content": "You are ChatGPT, a large language model trained by OpenAI."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 150,
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

    def strip_markdown(self, response_text: str) -> str:
        response_text = response_text.strip()
        if response_text.startswith("```json") and response_text.endswith("```"):
            return response_text[len("```json"): -len("```")].strip()
        return response_text

    def detect_team(self, article_content: str) -> dict:
        prompt = self.prompts['team_detection_prompt'].format(article_content=article_content)
        raw_response = self.call_openai_api(prompt)
        raw_response = self.strip_markdown(raw_response)
        try:
            result = json.loads(raw_response)
            team = result.get("team", "").strip()
            confidence = float(result.get("confidence", 0))
            return {"team": team, "confidence": confidence}
        except Exception as e:
            print(f"Error detecting team: {e}")
            return {"team": "", "confidence": 0}

    async def process_article(self, article_key: str, article_data: dict):
        content = article_data.get("content", "")
        if not content:
            print(f"Article {article_key} has no content. Skipping.")
            return

        detection = self.detect_team(content)
        team_name = detection.get("team", "")
        confidence = detection.get("confidence", 0)

        print(f"Article {article_key}: Detected team '{team_name}' with confidence {confidence}")
        return detection

    async def process_all_articles(self, articles: dict):
        tasks = []
        for article_key, article_data in articles.items():
            tasks.append(self.process_article(article_key, article_data))
        results = await asyncio.gather(*tasks)
        return results

def main():
    detector = detectTeam()
    
    # Load English articles from the JSON file
    with open("English_articles.json", "r", encoding="utf-8") as f:
        english_articles = json.load(f)

    # Run the asynchronous processing to detect teams
    results = asyncio.run(detector.process_all_articles(english_articles))
    
    # Print final results
    print("Team detection complete.")
    return results

if __name__ == "__main__":
    main()