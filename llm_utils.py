import time

def generate_with_retry(client, model, contents, config=None, retries=5, backoff_factor=2):
    """
    Wrapper for Gemini's generate_content with exponential backoff and empty response handling.
    """
    delay = 2
    for attempt in range(retries):
        try:
            if config:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config
                )
            else:
                response = client.models.generate_content(
                    model=model,
                    contents=contents
                )
            
            # Check if response or text is None (safety blocks or weird internal errors)
            if not response or not hasattr(response, 'text') or not response.text:
                print(f"[LLM WARN] Empty or blocked response from Gemini on attempt {attempt+1}/{retries}. Retrying...")
                time.sleep(delay)
                delay *= backoff_factor
                continue
                
            return response
            
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "502" in error_str or "429" in error_str or "temporarily overloaded" in error_str.lower():
                print(f"[LLM WARN] Gemini API overloaded. Retrying in {delay}s (Attempt {attempt+1}/{retries})...")
                time.sleep(delay)
                delay *= backoff_factor
            else:
                # If it's a completely different error, we still want to retry just in case it's a network glitch
                print(f"[LLM ERROR] Unexpected error: {error_str}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= backoff_factor
                
    raise Exception(f"Gemini API failed after {retries} retries.")
