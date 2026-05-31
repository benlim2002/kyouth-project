
import os
from google import genai
from dotenv import load_dotenv
import requests

SUPPORTED_MODELS = { "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3-flash-preview"}
SUPPORTED_LOCAL_MODELS = {"deepseek-r1:1.5b", "phi3:latest"}

def prompt_gemini(model: str, prompt: str) -> str:

	load_dotenv()

	# ensure the API key is set in the environment variables
	api_key = os.getenv("GOOGLE_API_KEY")

	if not api_key:
		return "Error: GOOGLE_API_KEY environment variable not set."
	
	if not prompt or not prompt.strip():
		return "Error: Prompt is empty."

	# set default model if provided model is not supported
	selected_model = "gemini-2.5-flash"

	if model in SUPPORTED_MODELS:
		selected_model = model

	# initialize the GenAI client and make the API call
	client = genai.Client(api_key=api_key)

	# generate content
	response = client.models.generate_content(model=selected_model, contents=prompt)

	# return the generated text if available, otherwise return an error message
	if response and response.text:
		return response.text
	else:
		return "No text response received from the model."
	
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


	