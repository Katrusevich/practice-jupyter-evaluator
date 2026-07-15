"""
Універсальна точка входу для автоматичного оцінювання Jupyter Notebook.

Використання:
    python main.py path/to/student_notebook.ipynb
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from executor import NotebookExecutor
from grader import Grader
from parser import classify_cells, load_notebook
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
    parser = argparse.ArgumentParser(
        description="Автоматичне універсальне оцінювання Jupyter Notebook",
    )
    parser.add_argument(
        "notebook_path",
        help="Шлях до файлу .ipynb студента",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Детальне логування (DEBUG)",
    )
    return parser.parse_args()


def load_grading_config() -> dict[str, Any]:
    """
    Зчитує конфігураційний файл grading_config.json.
    Якщо файлу немає, повертає базовий дефолтний конфіг.
    """
    config_path = Path("grading_config.json")
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                logger.info("Конфігурацію успішно завантажено з %s", config_path.name)
                return config
        except Exception as exc:
            logger.warning("Помилка читання конфігурації (%s). Використовуємо дефолтні налаштування.", exc)
    
    # Резервний дефолтний конфіг, якщо файлу немає
    return {
        "required_files": [],
        "timeout": 30,
        "parts": [
            {
                "id": "part_1",
                "name": "Частина 1 (Тести)",
                "tag": "autograder-test"
            }
        ]
    }


def main() -> int:
    """Головний пайплайн: parse → execute → grade → report."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    notebook_path = Path(args.notebook_path)
    
    # 0. Завантажуємо налаштування
    config = load_grading_config()
    required_files = config.get("required_files", [])
    timeout = config.get("timeout", 30)
    config_parts = config.get("parts", [])

    try:
        # 1. Парсинг та валідація структури
        logger.info("=== Крок 1: Парсинг та валідація ноутбука ===")
        notebook = load_notebook(notebook_path)
        
        # Передаємо конфіг для класифікації та динамічного пошуку тегів
        # Передаємо конфіг для класифікації та динамічного пошуку тегів
        classified = classify_cells(
            notebook=notebook,
            config_parts=config_parts,
            required_files=required_files
        )

        for warning in classified.get("validation_warnings", []):
            logger.warning(warning)

        if not classified["test_cells"]:
            logger.warning("У ноутбуці не знайдено тестових комірок")

        # 2. Виконання у ізольованому ядрі з таймаутом з конфігурації
        logger.info("=== Крок 2: Виконання ноутбука ===")
        executor = NotebookExecutor(timeout=timeout)
        executed_notebook = executor.execute(notebook)

        if executor.cell_errors:
            for cell_idx, error in executor.cell_errors.items():
                logger.warning(
                    "Помилка у комірці %d (виконання продовжено): %s",
                    cell_idx,
                    error.split("\n")[0],
                )

        # 3. Універсальне оцінювання за assert-тестами та частинами
        logger.info("=== Крок 3: Оцінювання ===")
        grader = Grader(
            classified_test_cells=classified["test_cells"],
            config_parts=config_parts,
            validation_warnings=classified.get("validation_warnings", []),
        )
        grading_result = grader.grade(executed_notebook)

        # 4. HTML-звіт у поточну папку
        logger.info("=== Крок 4: Формування звіту ===")
        html_report = generate_html_report(
            notebook_filename=notebook_path.name,
            grading_result=grading_result,
        )

        report_filename = f"report_{notebook_path.stem}.html"
        report_path = Path.cwd() / report_filename
        save_report(html_report, report_path)

        # Універсальний динамічний підсумок у консоль
        print(f"\n{'=' * 55}")
        print(f"Файл:     {notebook_path.name}")
        print(f"Загалом:  {grading_result.total_score:.1f} / {grading_result.max_score:.0f} б.")
        
        # Виводимо результати по кожній частині динамічно
        for part_id, part in grading_result.parts_results.items():
            print(f"  {part.title}:  {part.score:.1f} / {part.max_score:.0f} б.")
            
        print(f"Звіт:     {report_path.resolve()}")
        print(f"{'=' * 55}\n")

        return 0

    except FileNotFoundError:
        logger.error("Файл не знайдено: %s", notebook_path)
        return 1
    except ValueError as exc:
        logger.error("Помилка формату ноутбука: %s", exc)
        return 1
    except Exception as exc:
        logger.exception("Непередбачена помилка: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())