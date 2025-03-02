"""
Utility functions for interacting with language models.
"""

def generate_text_with_model(model_dict, prompt):
    """
    Generate text using the model returned by initialize_model().
    Handles different model structures.
    """
    try:
        provider = model_dict.get("provider", "").lower()
        if provider == "openai":
            from openai import OpenAI
            openai_client = OpenAI(api_key=model_dict.get("model", {}).get("api_key"))
            response = openai_client.chat.completions.create(
                model=model_dict.get("model_name", "gpt-4o-mini"),
                messages=[{"role": "user", "content": prompt}]
            )
            return response.choices[0].message.content
        elif provider == "gemini":
            gemini_model = model_dict.get("model")
            if hasattr(gemini_model, "generate_content"):
                response = gemini_model.generate_content(prompt)
                return response.text
        
        raise ValueError(f"Unsupported model provider: {provider}")
    except Exception as e:
        print(f"Error generating text with model: {e}")
        import traceback
        print(f"Exception traceback: {traceback.format_exc()}")
        raise