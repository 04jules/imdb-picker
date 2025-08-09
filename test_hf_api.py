import os
from huggingface_hub import InferenceClient

# Haal token op uit environment variables
# Zet dit lokaal via: export HF_TOKEN="jouw_token" (Linux/Mac)
# of: set HF_TOKEN="jouw_token" (Windows CMD)
hf_token = os.getenv("HF_TOKEN")

if not hf_token:
    raise ValueError("Geen Hugging Face token gevonden. Zet HF_TOKEN als environment variable.")

client = InferenceClient(
    model="HuggingFaceH4/zephyr-7b-beta",
    token=hf_token
)

prompt = """
Je bent een filmexpert. Kies exact 5 films uit onderstaande lijst die het meeste potentieel hebben. Baseer je op score, regisseur, cast en inhoud. Geef de output als JSON met `title` en `motivatie`. Gebruik GEEN andere films dan deze lijst:

[
{"title": "Dune: Part Two", "score": 8.3, "director": "Denis Villeneuve", "cast": ["Timothée Chalamet", "Zendaya"], "overview": "Paul Atreides joins the Fremen..."},
{"title": "Some Bad Movie", "score": 5.2, "director": "Unknown", "cast": [], "overview": "Een man gaat naar de winkel..."},
{"title": "The Green Knight", "score": 7.6, "director": "David Lowery", "cast": ["Dev Patel"], "overview": "Sir Gawain sets out..."}
]

Beantwoord enkel in geldig JSON, zonder extra uitleg.
"""

response = client.text_generation(prompt=prompt, temperature=0.7, max_new_tokens=400)
print(response)
