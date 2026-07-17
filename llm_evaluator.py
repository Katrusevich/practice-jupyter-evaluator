"""Модуль для оцінювання виконаних завдань за допомогою Google Gemini (LangChain)."""

import os
import logging
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Завантажуємо змінні середовища з файлу .env (там має бути GOOGLE_API_KEY)
load_dotenv()

# --- Схеми даних (Pydantic) ---
# Це змусить нейромережу повертати відповідь у чіткому форматі, який нам потрібен для HTML-звіту

class TaskEvaluation(BaseModel):
    """Схема структурованої відповіді від LLM для одного завдання."""
    code_score: int = Field(description="Оцінка за код. Якщо коду не вимагалося, постав 0.")
    text_score: int = Field(description="Оцінка за текст/обґрунтування. Якщо тексту не вимагалося, постав 0.")
    graphs_score: int = Field(description="Оцінка за графіки. Якщо графіків не вимагалося, постав 0.")
    bonus_score: int = Field(default=0, description="Бонусні бали, якщо виконані додаткові умови з рубрики.")
    feedback: str = Field(description="Стислий, конструктивний коментар викладача українською мовою. Що зроблено добре, а що треба покращити. Форматуй як звичайний текст, можна використовувати базовий Markdown.")


class LLMEvaluator:
    def __init__(self, rubric_path: str = "rubric.md", model_name: str = "gemini-3.1-flash-lite", temperature: float = 0.1):
        """
        Ініціалізує LLM оцінювача на базі Google Gemini.
        
        Args:
            rubric_path: Шлях до Markdown-файлу з критеріями оцінювання.
            model_name: Назва моделі (gemini-2.5-pro підтримує аналіз зображень та великий контекст).
            temperature: Креативність моделі (0.1 - сувора, детермінована перевірка).
        """
        if not os.getenv("GOOGLE_API_KEY"):
            logger.error("GOOGLE_API_KEY не знайдено! Переконайтеся, що файл .env налаштовано.")
            raise ValueError("GOOGLE_API_KEY is missing in environment variables.")

        self.rubric_text = self._load_rubric(rubric_path)
        
        # Ініціалізуємо модель Gemini та одразу прив'язуємо її до нашої Pydantic-схеми
        # self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=temperature)
        self.llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
        self.structured_llm = self.llm.with_structured_output(TaskEvaluation)
        
        logger.info("LLMEvaluator ініціалізовано з моделлю %s", model_name)

    def _load_rubric(self, path: str) -> str:
        """Зчитує текст рубрики з Markdown файлу."""
        rubric_file = Path(path)
        if not rubric_file.exists():
            logger.warning("Файл рубрики %s не знайдено. Оцінювання може бути неточним.", path)
            return "Оцінюй завдання логічно на свій розсуд, виходячи з наданих даних."
        
        with open(rubric_file, "r", encoding="utf-8") as f:
            return f.read()

    def evaluate_task(self, task_name: str, max_points: int, task_data: dict[str, Any]) -> TaskEvaluation | None:
        """
        Оцінює конкретне завдання, надсилаючи код, текст та картинки до LLM.
        
        Args:
            task_name: Назва завдання з конфігурації (напр., 'Завдання 1: Підготовка даних').
            max_points: Максимальний бал за це завдання.
            task_data: Словник з ключами 'text', 'code', 'images' від парсера.
            
        Returns:
            Об'єкт TaskEvaluation або None у разі помилки.
        """
        logger.info("Починаю AI-аналіз для завдання: %s", task_name)
        
        # 1. Формуємо системний промпт із рубрикою
        system_prompt = (
            "Ти — експерт-асистент викладача з машинного навчання. "
            "Твоє завдання: об'єктивно оцінити виконану лабораторну роботу студента (Jupyter Notebook).\n\n"
            "КРИТЕРІЇ ОЦІНЮВАННЯ (Рубрика):\n"
            f"{self.rubric_text}\n\n"
            "ПРАВИЛА:\n"
            "1. Став бали суворо відповідно до рубрики.\n"
            "2. Якщо частина завдання відсутня (наприклад, немає графіків), став 0 балів за цю частину.\n"
            "3. Твій фідбек має бути написаний українською мовою, бути професійним та вказувати на конкретні помилки в коді чи обґрунтуванні."
        )

        # 2. Формуємо масив контенту для повідомлення від користувача (HumanMessage)
        content_parts = [
            {"type": "text", "text": f"Оціни наступні матеріали для блоку: **{task_name}** (Максимальний бал: {max_points})\n\n"}
        ]

        # Додаємо код
        if task_data.get("code"):
            content_parts.append({
                "type": "text", 
                "text": f"### КОД СТУДЕНТА (Python):\n```python\n{task_data['code']}\n```\n\n"
            })
        else:
            content_parts.append({"type": "text", "text": "### КОД СТУДЕНТА: [Відсутній]\n\n"})

        # Додаємо текст студента
        if task_data.get("text"):
            content_parts.append({
                "type": "text", 
                "text": f"### ОБҐРУНТУВАННЯ СТУДЕНТА (Markdown):\n{task_data['text']}\n\n"
            })
        else:
            content_parts.append({"type": "text", "text": "### ОБҐРУНТУВАННЯ СТУДЕНТА: [Відсутнє]\n\n"})

        # Додаємо зображення графіків
        images = task_data.get("images", [])
        if images:
            content_parts.append({"type": "text", "text": f"### ГРАФІКИ СТУДЕНТА (Кількість: {len(images)}):\n"})
            for img in images:
                # LangChain очікує URL формату data:image/png;base64,...
                img_url = f"data:{img['mime_type']};base64,{img['base64_data']}"
                content_parts.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })
        else:
            content_parts.append({"type": "text", "text": "### ГРАФІКИ СТУДЕНТА: [Відсутні]\n\n"})

        # 3. Викликаємо модель
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=content_parts)
            ]
            
            # structured_llm автоматично спарсить відповідь у Pydantic клас
            result: TaskEvaluation = self.structured_llm.invoke(messages)
            
            logger.info("Успішно оцінено: %s (Сума: %d балів)", task_name, result.code_score + result.text_score + result.graphs_score)
            print(f"DEBUG JSON Output for {task_name}: {result.model_dump_json(indent=2)}")
            return result
            
        except Exception as e:
            logger.error("Помилка під час виклику LLM для %s: %s", task_name, e)
            return None