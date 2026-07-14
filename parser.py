"""Модуль для зчитування та аналізу Jupyter Notebook."""

import logging
from pathlib import Path
from typing import Any

import nbformat
from nbformat import NotebookNode

logger = logging.getLogger(__name__)

# Теги метаданих комірок
TAG_SOLUTION = "solution"
TAG_AUTOGRADER_TEST = "autograder-test"


def load_notebook(path: str | Path) -> NotebookNode:
    """
    Зчитує файл .ipynb за допомогою nbformat (версія 4).

    Args:
        path: Шлях до ноутбука.

    Returns:
        Об'єкт ноутбука у форматі nbformat v4.

    Raises:
        FileNotFoundError: Якщо файл не існує.
        ValueError: Якщо файл має некоректний формат.
    """
    notebook_path = Path(path)

    if not notebook_path.exists():
        logger.error("Файл не знайдено: %s", notebook_path)
        raise FileNotFoundError(f"Notebook not found: {notebook_path}")

    try:
        with notebook_path.open("r", encoding="utf-8") as file:
            notebook = nbformat.read(file, as_version=4)
        logger.info("Ноутбук успішно завантажено: %s", notebook_path.name)
        return notebook
    except nbformat.NBFormatError as exc:
        logger.error("Некоректний формат ноутбука %s: %s", notebook_path, exc)
        raise ValueError(f"Invalid notebook format: {exc}") from exc
    except OSError as exc:
        logger.error("Помилка читання файлу %s: %s", notebook_path, exc)
        raise


def filter_code_cells(notebook: NotebookNode) -> list[NotebookNode]:
    """
    Залишає лише комірки типу 'code'.

    Args:
        notebook: Завантажений ноутбук.

    Returns:
        Список code-комірок.
    """
    code_cells = [cell for cell in notebook.cells if cell.cell_type == "code"]
    logger.debug("Знайдено %d code-комірок", len(code_cells))
    return code_cells


def get_cell_tags(cell: NotebookNode) -> list[str]:
    """Повертає список тегів з метаданих комірки."""
    tags = cell.metadata.get("tags", [])
    if not isinstance(tags, list):
        logger.warning("Некоректні теги у комірці, очікується list: %s", tags)
        return []
    return tags


def is_solution_cell(cell: NotebookNode) -> bool:
    """Перевіряє, чи містить комірка тег 'solution' (код студента)."""
    return TAG_SOLUTION in get_cell_tags(cell)


def is_autograder_test_cell(cell: NotebookNode) -> bool:
    """Перевіряє, чи містить комірка тег 'autograder-test' (тест викладача)."""
    return TAG_AUTOGRADER_TEST in get_cell_tags(cell)


def classify_cells(notebook: NotebookNode) -> dict[str, list[dict[str, Any]]]:
    """
    Класифікує code-комірки за тегами.

    Returns:
        Словник із двома списками:
        - solution_cells: комірки з кодом студента
        - test_cells: комірки з тестами викладача
    """
    solution_cells: list[dict[str, Any]] = []
    test_cells: list[dict[str, Any]] = []

    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue

        if is_solution_cell(cell):
            solution_cells.append({"index": index, "cell": cell})
            logger.debug("Комірка %d: solution", index)

        if is_autograder_test_cell(cell):
            test_cells.append({"index": index, "cell": cell})
            logger.debug("Комірка %d: autograder-test", index)

    logger.info(
        "Класифікація завершена: %d solution, %d autograder-test",
        len(solution_cells),
        len(test_cells),
    )
    return {
        "solution_cells": solution_cells,
        "test_cells": test_cells,
    }
