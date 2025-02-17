import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

def find_gemini_models() -> list:
    google_api_key = os.getenv("GEMINI_API_KEY")
    if not google_api_key:
        raise EnvironmentError("GEMINI_API_KEY not set")
    genai.configure(api_key=google_api_key)
    all_models = list(genai.list_models())
    gemini_models = [model.name for model in all_models if hasattr(model, "name") and "gemini" in model.name.lower()]
    print("Found Gemini models:", gemini_models)
    return gemini_models

def init_openai() -> dict:
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    if not OPENAI_API_KEY:
        raise EnvironmentError("OPENAI_API_KEY not set")
    provider = "openai/gpt-4o-mini"
    return {"provider": provider, "api_key": OPENAI_API_KEY}

def initialize_model(provider: str = "gemini"):
    if provider.lower() == "gemini":
        models = find_gemini_models()
        if not models:
            raise ValueError("No Gemini models found")
        selected_model = "models/gemini-2.0-flash-thinking-exp-01-21"
        print("Initializing Gemini model:", selected_model)
        google_api_key = os.getenv("GEMINI_API_KEY")
        genai.configure(api_key=google_api_key)
        return {"provider": "gemini", "model_name": selected_model, "model": genai.GenerativeModel(selected_model)}
    elif provider.lower() == "openai":
        model_info = init_openai()
        print("Initializing OpenAI model with provider:", model_info["provider"])
        return {"provider": "openai", "model_name": model_info["provider"], "model": model_info}
    elif provider.lower() == "both":
        gemini_model = initialize_model("gemini")
        openai_model = initialize_model("openai")
        print("Initializing both models: Gemini and OpenAI")
        return {"gemini": gemini_model, "openai": openai_model}
    else:
        raise ValueError("Unsupported provider")

if __name__ == "__main__":
    model = initialize_model("both")
