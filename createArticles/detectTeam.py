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
        # Initial team detection
        prompt = self.prompts['team_detection_prompt'].format(article_content=article_content)
        raw_response = self.call_openai_api(prompt)
        raw_response = self.strip_markdown(raw_response)
        try:
            result = json.loads(raw_response)
            team_value = result.get("team", "").strip()
            confidence = float(result.get("confidence", 0))
            
            # Check if confidence is too low - prefer "others" for uncertain cases
            if confidence < 0.6:
                return {"team": "others", "confidence": confidence}
                
            # Multiple teams check
            teams = [t.strip() for t in team_value.split(",") if t.strip()]
            if len(teams) != 1:
                return {"team": "others", "confidence": confidence}
                
            # Always perform refinement analysis for more reliable detection
            refinement_prompt = self.prompts.get('team_refinement_prompt', None)
            if refinement_prompt:
                formatted_refinement = refinement_prompt.format(
                    article_content=article_content, 
                    team_candidate=team_value
                )
                raw_refinement = self.call_openai_api(formatted_refinement)
                raw_refinement = self.strip_markdown(raw_refinement)
                try:
                    refinement_result = json.loads(raw_refinement)
                    is_consistent = refinement_result.get("is_consistent", False)
                    primary_team = refinement_result.get("primary_team", "").strip().lower()
                    
                    # If refinement says it's not consistent with the initial team
                    if not is_consistent:
                        # Use the primary_team from refinement if provided and valid
                        if primary_team and primary_team != "others":
                            # Verify primary_team is in our allowed list
                            allowed_teams = [
                                'chiefs', 'browns', 'ravens', 'steelers', 'bengals', 'bills', 
                                'dolphins', 'jets', 'patriots', 'texans', 'colts', 'jaguars', 
                                'titans', 'chargers', 'broncos', 'raiders', 'lions', 'vikings', 
                                'packers', 'bears', 'eagles', 'commanders', 'cowboys', 'giants', 
                                'buccaneers', 'falcons', 'saints', 'panthers', 'rams', 'seahawks', 
                                'cardinals', '49ers'
                            ]
                            if primary_team in allowed_teams:
                                return {"team": primary_team, "confidence": 0.8}  # Higher confidence from refinement
                        
                        # If primary_team isn't valid, default to "others"
                        return {"team": "others", "confidence": confidence}
                    
                    # The initial team is correct
                    return {"team": team_value, "confidence": max(confidence, 0.8)}  # Boost confidence after refinement
                except Exception as e:
                    print(f"Error refining team detection: {e}")
                    # Fall back to the initial detection with original confidence
            
            # If we couldn't run refinement, return the original detection
            return {"team": team_value, "confidence": confidence}
        except Exception as e:
            print(f"Error detecting team: {e}")
            return {"team": "others", "confidence": 0}
            
    def get_article_length(self, article_content: str) -> int:
        """Calculate the length of the article in words"""
        return len(article_content.split())

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