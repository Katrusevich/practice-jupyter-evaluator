"""
Головний пайплайн AI-оцінювання Jupyter Notebook.

Використання:
    python main.py path/to/student_notebook.ipynb
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any
import time

# Імпортуємо наші нові модулі
from parser import load_notebook, extract_task_data
from llm_evaluator import LLMEvaluator
from reporter import generate_html_report, save_report

logger = logging.getLogger("main")


def setup_logging(verbose: bool = False) -> None:
    """Налаштовує базове логування для всіх модулів."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def parse_args() -> argparse.Namespace:
    """Парсить аргументи командного рядка."""
    parser = argparse.ArgumentParser(description="AI-оцінювання Jupyter Notebook")
    parser.add_argument("notebook_path", help="Шлях до файлу .ipynb")
    parser.add_argument("-v", "--verbose", action="store_true", help="Детальне логування")
    return parser.parse_args()


def load_grading_config() -> dict[str, Any]:
    """Зчитує оновлений конфігураційний файл grading_config.json."""
    config_path = Path("grading_config.json")
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    logger.error("Файл grading_config.json не знайдено! Він обов'язковий для AI-оцінювання.")
    sys.exit(1)


def main() -> int:
    """Головний пайплайн: parse → LLM evaluate → report."""
    args = parse_args()
    setup_logging(verbose=args.verbose)
    notebook_path = Path(args.notebook_path)
    
    logger.info("=== Запуск AI-грейдера для %s ===", notebook_path.name)

    # 0. Завантажуємо налаштування завдань
    config = load_grading_config()
    config_parts = config.get("parts", [])

    try:
        # 1. Парсинг та збір даних (код, текст, картинки)
        logger.info("=== Крок 1: Парсинг ноутбука ===")
        notebook = load_notebook(notebook_path)
        extracted_data = extract_task_data(notebook, config_parts)

        # 2. Оцінювання через LLM
        logger.info("=== Крок 2: AI-оцінювання ===")
        # Підключаємо ШІ (вимагає наявності файлів rubric.md та .env з OPENAI_API_KEY)
        evaluator = LLMEvaluator(rubric_path="rubric.md")
        
        evaluation_results = {}
        total_score = 0
        max_total_score = 0

        for part in config_parts:
            task_id = part["id"]
            task_name = part["name"]
            tag = part["tag"]
            max_points = part["max_points"]
            
            max_total_score += max_points
            
            # Беремо дані для конкретного тегу. Якщо студент не поставив тег — віддаємо порожні дані
            task_data = extracted_data.get(tag, {"text": "", "code": "", "images": []})
            
            # Запитуємо оцінку в нейромережі
            result = evaluator.evaluate_task(task_name, max_points, task_data)
            time.sleep(20)
            
            if result:
                task_score = result.code_score + result.text_score + result.graphs_score + result.bonus_score
                total_score += task_score
                
                # Зберігаємо результат для HTML-звіту
                evaluation_results[task_id] = {
                    "name": task_name,
                    "max_points": max_points,
                    "score": task_score,
                    "details": result.model_dump(),  # Перетворюємо Pydantic-об'єкт у словник
                    "images": task_data["images"]    # Зберігаємо картинки, щоб вивести їх у звіті
                }
            else:
                logger.error("Не вдалося оцінити завдання: %s", task_name)

        # 3. Генерація HTML-звіту
        logger.info("=== Крок 3: Формування звіту ===")
        # Передаємо нові структури даних до репортера
        html_report = generate_html_report(
            notebook_filename=notebook_path.name,
            evaluation_results=evaluation_results,
            total_score=total_score,
            max_total_score=max_total_score
        )

        report_filename = f"report_{notebook_path.stem}.html"
        report_path = Path.cwd() / report_filename
        save_report(html_report, report_path)

        # 4. Підсумок у консоль
        print(f"\n{'=' * 65}")
        print(f"Файл:     {notebook_path.name}")
        print(f"Загалом:  {total_score} / {max_total_score} б.")
        print("-" * 65)
        
        for part_id, res in evaluation_results.items():
            print(f"  {res['name']:<40} | {res['score']} / {res['max_points']} б.")
            
        print(f"\nЗвіт:     {report_path.resolve()}")
        print(f"{'=' * 65}\n")

        return 0

    except Exception as exc:
        logger.exception("Непередбачена помилка: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())