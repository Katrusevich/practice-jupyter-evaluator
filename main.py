"""
Точка входу для автоматичного оцінювання студентських Jupyter Notebook.

Використання:
    python main.py path/to/student_notebook.ipynb
"""

import argparse
import logging
import sys
from pathlib import Path

from executor import NotebookExecutor
from grader import Grader
from parser import classify_cells, load_notebook
from reporter import generate_html_report, save_report


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
        description="Автоматичне оцінювання студентських Jupyter Notebook",
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


def main() -> int:
    """Головний пайплайн: parse → execute → grade → report."""
    args = parse_args()
    setup_logging(verbose=args.verbose)

    logger = logging.getLogger("main")
    notebook_path = Path(args.notebook_path)

    try:
        # 1. Зчитуємо та класифікуємо комірки
        logger.info("=== Крок 1: Парсинг ноутбука ===")
        notebook = load_notebook(notebook_path)
        classified = classify_cells(notebook)

        if not classified["test_cells"]:
            logger.warning("У ноутбуці не знайдено тестових комірок (тег 'autograder-test')")

        # 2. Виконуємо код у ізольованому ядрі
        logger.info("=== Крок 2: Виконання ноутбука ===")
        executor = NotebookExecutor(timeout=30)
        executed_notebook = executor.execute(notebook)

        if executor.cell_errors:
            for cell_idx, error in executor.cell_errors.items():
                logger.warning("Помилка у комірці %d (виконання продовжено): %s", cell_idx, error.split("\n")[0])

        # 3. Оцінюємо результати тестів
        logger.info("=== Крок 3: Оцінювання ===")
        grader = Grader(test_cells=classified["test_cells"])
        grading_result = grader.grade(executed_notebook)

        # 4. Генеруємо та зберігаємо HTML-звіт у поточну папку
        logger.info("=== Крок 4: Формування звіту ===")
        html_report = generate_html_report(
            notebook_filename=notebook_path.name,
            grading_result=grading_result,
        )

        report_filename = f"report_{notebook_path.stem}.html"
        report_path = Path.cwd() / report_filename
        save_report(html_report, report_path)

        # Підсумок у консоль
        print(f"\n{'=' * 50}")
        print(f"Файл:    {notebook_path.name}")
        print(f"Бал:     {grading_result.total_score} / {grading_result.max_score}")
        print(f"Звіт:    {report_path.resolve()}")
        print(f"{'=' * 50}\n")

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
