import os, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from groq import Groq

client = Groq(api_key=os.getenv('GROQ_API_KEY'))
r = client.chat.completions.create(
    model='llama-3.1-8b-instant',
    messages=[{'role':'user','content':'Say OK'}],
    max_tokens=5
)
print('Groq response:', r.choices[0].message.content)
print('GROQ TEST PASSED')
