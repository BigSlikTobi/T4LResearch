import json
import requests
import os
import yaml
from LLMSetup import initialize_model

# Initialize the model (this example uses OpenAI, but you can adjust for Gemini or another provider)
model_info = initialize_model("openai")
model = model_info["model"]

# Load your prompts (adjust the path as needed)
with open(os.path.join(os.path.dirname(__file__), "prompts.yaml"), "r", encoding="utf-8") as f:
    prompts = yaml.safe_load(f)

def call_llm_api(prompt: str) -> str:
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {model['api_key']}",
    }
    payload = {
        "model": model["provider"],
        "messages": [
            {"role": "system", "content": "You are a professional editor."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens": 1500,
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]

def post_process_content(article_content: str, language: str = "english") -> str:
    if language.lower() == "english":
        prompt = prompts["post_processing_prompt"].format(article_content=article_content)
    else:
        prompt = prompts["post_processing_prompt"].format(article_content=article_content)
    
    cleaned_text = call_llm_api(prompt)
    
    # Remove markdown code fences if present
    if cleaned_text.startswith("```html") and cleaned_text.endswith("```"):
        # Remove the first line and the last fence
        lines = cleaned_text.splitlines()
        # Remove the first line (```html) and the last (```)
        cleaned_text = "\n".join(lines[1:-1]).strip()
    
    return cleaned_text.strip()
