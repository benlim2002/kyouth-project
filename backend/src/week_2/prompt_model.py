
import logging
import os
from google import genai
from dotenv import load_dotenv
import requests
import time
from google.genai import types

SUPPORTED_MODELS = { 
					"gemini-2.5-flash",
					"gemini-2.5-flash-lite",
					"gemini-3.1-flash-preview",
					"gemini-3.1-flash-lite",
					"gemini-3.5-flash",
					}
SUPPORTED_LOCAL_MODELS = {"deepseek-r1:1.5b", "phi3:latest", "gemma4:31b-cloud"}

import time

def prompt_gemini(model: str, prompt: str, retries=5, delay=3) -> str:
    load_dotenv(override=True)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return "Error: GOOGLE_API_KEY environment variable not set."
    
    if not prompt or not prompt.strip():
        return "Error: Prompt is empty."

    selected_model = "gemini-2.5-flash"
    if model in SUPPORTED_MODELS:
        selected_model = model

    client = genai.Client(api_key=api_key)

    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=selected_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=8192
                )
            )
            if response and response.text:
                return response.text
            else:
                return "No text response received from the model."

        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                logging.warning(f"Model unavailable, retrying in {delay}s (attempt {attempt + 1}/{retries})")
                time.sleep(delay)
                delay *= 2  # 3s → 6s → 12s → 24s → 48s
            else:
                return f"An error occurred while generating content: {error_str}"

    return "The model is currently busy after several retries. Please try again later."


def prompt_local_model(model: str, prompt: str) -> str:
	# define the URL for the local model API
	url = "http://localhost:11434/api/generate"
	
	# build the request payload
	response = requests.post(
        url,
        json={
            "model": model,
            "prompt": prompt,
            "stream": False,
        },
        timeout=60,
    )
	# check if the request was successful
	response.raise_for_status()	

	# parse the response JSON and return the generated text
	data = response.json()
	# print(data)
	return data.get("response", "No text response received from the local model.")

def prompt_model(model: str, prompt: str) -> str :
	try:
		if not prompt or not prompt.strip():
			return "Error: Prompt is empty."
		if model in SUPPORTED_MODELS:
			return prompt_gemini(model, prompt)
		elif model in SUPPORTED_LOCAL_MODELS:
			return prompt_local_model(model, prompt)
		else:
			return f"Error: Unsupported model '{model}'."

	except Exception as e:
		return f"An error occurred while generating content: {str(e)}"
	
# def main():
#     prompt = "There is a car wash 20 meters from here, should I walk or driver there? Answer in 1 word"
#     print("Testing Gemini:")
#     print(prompt_model("gemini-2.5-flasuuyuyguyguyh", prompt))

#     print("\nTesting local model:")
#     print(prompt_model("deepseek-r1:1.5b", prompt))


# if __name__ == "__main__":
#     main()


	