import os
import itertools
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# list of models for substitution
MODEL_LIST = [
    "moonshotai/kimi-k2-instruct",
    "moonshotai/kimi-k2-instruct-0905",
    "llama-3.3-70b-versatile",
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "deepseek-r1-distill-llama-70b",
    "qwen/qwen3-32b",
    "gemma2-9b-it",
    "llama-3.1-8b-instant",
    "meta-llama/llama-4-maverick-17b-128e-instruct"
]

class ModelManager:
    def __init__(self):
        self.models = list(MODEL_LIST)
        self.index = 0

    def get_next_model(self):
        if self.index >= len(self.models):
            self.index = 0
        model = self.models[self.index]
        self.index += 1
        return model
