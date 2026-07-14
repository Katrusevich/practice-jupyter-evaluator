"""Модуль для універсального зчитування та аналізу Jupyter Notebook."""

import json
import logging
import warnings
from pathlib import Path
from typing import Any

import nbformat
from nbformat import NotebookNode

logger = logging.getLogger(__name__)

# Пригнічуємо попередження про відсутність ID комірок для чистішого виводу в консолі
warnings.filterwarnings("ignore", category=UserWarning, module="nbformat")

# --- Базові теги метаданих комірок ---
TAG_SOLUTION = "solution"
TAG_AUTOGRADER_TEST = "autograder-test"  # Загальний дефолтний тег тесту


def load_notebook(path: str | Path) -> NotebookNode:
    """
    Зчитує файл .ipynb за допомогою nbformat (версія 4).
    Автоматично нормалізує структуру для запобігання MissingIDFieldWarning.

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
        
        # Виправляємо структуру (додаємо відсутні id комірок)
        from nbformat.validator import normalize
        normalize(notebook)
        
        logger.info("Ноутбук успішно завантажено та нормалізовано: %s", notebook_path.name)
        return notebook
    except nbformat.NBFormatError as exc:
        logger.error("Некоректний формат ноутбука %s: %s", notebook_path, exc)
        raise ValueError(f"Invalid notebook format: {exc}") from exc
    except OSError as exc:
        logger.error("Помилка читання файлу %s: %s", notebook_path, exc)
        raise


def _collect_notebook_text(notebook: NotebookNode) -> str:
    """Збирає весь текст ноутбука (код, markdown, метадані) для пошуку."""
    parts: list[str] = []

    for cell in notebook.cells:
        source = cell.source
        if isinstance(source, list):
            parts.append("".join(source))
        else:
            parts.append(str(source))

    try:
        parts.append(json.dumps(notebook.metadata, ensure_ascii=False))
    except (TypeError, ValueError):
        pass

    return "\n".join(parts).lower()


def validate_data_references(notebook: NotebookNode, required_files: list[str]) -> list[str]:
    """
    Перевіряє наявність згадок про обов'язкові файли (наприклад, датасети) у коді.

    Returns:
        Список попереджень (порожній, якщо всі згадки знайдено).
    """
    if not required_files:
        return []

    notebook_text = _collect_notebook_text(notebook)
    warnings_list: list[str] = []

    for file_name in required_files:
        if file_name.lower() not in notebook_text:
            message = (
                f"У ноутбуці не знайдено згадки про обов'язковий файл '{file_name}'. "
                f"Переконайтесь, що студент використовує правильні вхідні дані."
            )
            warnings_list.append(message)
            logger.warning(message)
        else:
            logger.info("Згадку про обов'язковий файл '%s' знайдено у коді", file_name)

    return warnings_list


def filter_code_cells(notebook: NotebookNode) -> list[NotebookNode]:
    """Повертає лише виконувані code-комірки ноутбука."""
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
    """Перевіряє, чи є комірка рішенням студента (містить тег 'solution')."""
    return TAG_SOLUTION in get_cell_tags(cell)


def classify_cells(
    notebook: NotebookNode, 
    config_parts: list[dict[str, Any]] | None = None,
    required_files: list[str] | None = None
) -> dict[str, Any]:
    """
    Універсально класифікує виконувані комірки.
    Зв'язує тестові блоки з конкретними частинами роботи на основі конфігурації.

    Returns:
        Словник із рішеннями студентів, списком тестів та попередженнями валідації.
    """
    config_parts = config_parts or []
    required_files = required_files or []

    solution_cells: list[dict[str, Any]] = []
    test_cells: list[dict[str, Any]] = []

    # Створюємо мапу тегів для швидкого пошуку: { "назва-тегу": "id_частини" }
    tag_to_part_map = {part["tag"]: part["id"] for part in config_parts if "tag" in part}
    fallback_part_id = config_parts[0]["id"] if config_parts else "general"

    for index, cell in enumerate(notebook.cells):
        if cell.cell_type != "code":
            continue

        # 1. Визначаємо, чи це рішення студента
        if is_solution_cell(cell):
            solution_cells.append({"index": index, "cell": cell})
            logger.debug("Комірка %d: solution", index)

        # 2. Перевіряємо теги тестів
        tags = get_cell_tags(cell)
        
        # Шукаємо, чи відповідає якийсь із тегів комірки конфігурації частин
        assigned_part = None
        for tag in tags:
            if tag in tag_to_part_map:
                assigned_part = tag_to_part_map[tag]
                break

        # Якщо знайдено специфічний тег частини або загальний тег автогрейдера
        if assigned_part:
            entry = {"index": index, "cell": cell, "part": assigned_part, "tags": tags}
            test_cells.append(entry)
            logger.debug("Комірка %d: тест для частини '%s'", index, assigned_part)
            
        elif TAG_AUTOGRADER_TEST in tags:
            # Якщо є тільки загальний тег, відносимо до першої частини як фолбек
            entry = {"index": index, "cell": cell, "part": fallback_part_id, "tags": tags}
            test_cells.append(entry)
            logger.debug("Комірка %d: загальний тест (призначено для '%s')", index, fallback_part_id)

    # Валідація наявності згадок файлів у коді
    validation_warnings = validate_data_references(notebook, required_files)

    logger.info(
        "Універсальна класифікація: %d solution-комірок | %d знайдених тестів",
        len(solution_cells),
        len(test_cells),
    )

    return {
        "solution_cells": solution_cells,
        "test_cells": test_cells,
        "validation_warnings": validation_warnings,
    }