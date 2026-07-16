import os
from dotenv import load_dotenv # Додаємо імпорт для читання .env
import google.generativeai as genai

load_dotenv() # Обов'язково завантажуємо змінні з .env

# Вручну конфігуруємо ключ з системних змінних
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)