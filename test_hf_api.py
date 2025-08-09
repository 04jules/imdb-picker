from huggingface_hub import InferenceClient

client = InferenceClient(
    model="HuggingFaceH4/zephyr-7b-beta",
    token="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"
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
