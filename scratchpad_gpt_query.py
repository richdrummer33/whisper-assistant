import os
import sys
import openai

openai.api_key = os.getenv("OPENAI_API_KEY") # Set your OpenAI API key as an environment variable
# openai.organization = "org-abc123def456ghi789jkl012"

def query_gpt(string=""):
    parameters = {
        'model': 'gpt-3.5-turbo',  # For GPT-4
        'messages': [
            {"role": "system", "content": "You are a helpful assistant. You speak exactly like snoop dogg, but as brilliant as Bill Gates."},  
            {"role": "user", "content": string}
        ]
    }
    response = openai.ChatCompletion.create(**parameters)
    return response.choices[0].message.content
    
response = query_gpt("snoop, what's up?")
print(response, file=sys.stderr)