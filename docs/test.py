import os
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")

client = Groq(api_key=os.environ["GROQ_API_KEY"])

response = client.chat.completions.create(
    model="llama-3.3-70b-versatile",
    messages=[
        {"role": "system", "content": "Tu es un assistant IA pour une entreprise."},
        {"role": "user", "content": "Dis bonjour en français et présente-toi en 2 phrases."}
    ]
)

print(response.choices[0].message.content)