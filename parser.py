"""Модуль для парсингу Jupyter Notebook та екстракції даних для AI-оцінювання."""

import logging
import warnings
from pathlib import Path
from typing import Any

import nbformat
from nbformat import NotebookNode

logger = logging.getLogger(__name__)

# Пригнічуємо попередження про відсутність ID комірок для чистішого виводу
warnings.filterwarnings("ignore", category=UserWarning, module="nbformat")


def load_notebook(path: str | Path) -> NotebookNode:
    """
    Зчитує файл .ipynb за допомогою nbformat.
    Автоматично нормалізує структуру для запобігання помилкам метаданих.
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
        
        logger.info("Ноутбук успішно завантажено: %s", notebook_path.name)
        return notebook
    except nbformat.NBFormatError as exc:
        logger.error("Некоректний формат ноутбука %s: %s", notebook_path, exc)
        raise ValueError(f"Invalid notebook format: {exc}") from exc
    except OSError as exc:
        logger.error("Помилка читання файлу %s: %s", notebook_path, exc)
        raise


def get_cell_tags(cell: NotebookNode) -> list[str]:
    """Повертає список тегів з метаданих комірки."""
    tags = cell.metadata.get("tags", [])
    if not isinstance(tags, list):
        return []
    return tags


def extract_task_data(notebook: NotebookNode, config_parts: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """
    Трьохкомпонентний екстрактор.
    Проходить по всіх комірках ноутбука та групує їхній вміст за тегами завдань.
    Використовує логіку "активного тегу", щоб захоплювати комірки коду, 
    якщо студент позначив тегом лише першу комірку завдання.
    """
    extracted_data = {}
    valid_tags = set()
    
    for part in config_parts:
        tag = part.get("tag")
        if tag:
            valid_tags.add(tag)
            extracted_data[tag] = {
                "text_blocks": [],
                "code_blocks": [],
                "images": []
            }

    # Стан для відстеження поточного активного завдання
    current_active_tags = []

    for cell in notebook.cells:
        cell_tags = get_cell_tags(cell)
        matched_tags = [t for t in cell_tags if t in valid_tags]
        
        # Якщо знайшли нові теги — оновлюємо поточний стан
        if matched_tags:
            current_active_tags = matched_tags
            
        # Якщо ми ще не дійшли до жодного завдання (наприклад, імпорти на початку) - пропускаємо
        if not current_active_tags:
            continue
            
        for tag in current_active_tags:
            # А. Екстракція ТЕКСТУ (Markdown)
            if cell.cell_type == "markdown":
                extracted_data[tag]["text_blocks"].append(cell.source)
            
            # Б. Екстракція КОДУ та КАРТИНОК (Python Code)
            elif cell.cell_type == "code":
                extracted_data[tag]["code_blocks"].append(cell.source)
                
                for output in cell.get("outputs", []):
                    if output.output_type in ("display_data", "execute_result"):
                        data = output.get("data", {})
                        
                        for mime_type in ("image/png", "image/jpeg"):
                            if mime_type in data:
                                # Очищаємо Base64 від переносів рядків для сумісності з LLM API
                                raw_base64 = data[mime_type]
                                clean_base64 = raw_base64.replace("\n", "").strip()
                                
                                extracted_data[tag]["images"].append({
                                    "mime_type": mime_type,
                                    "base64_data": clean_base64
                                })

    # 3. Фінальна склейка
    final_data = {}
    for tag, content in extracted_data.items():
        final_data[tag] = {
            "text": "\n\n".join(content["text_blocks"]),
            "code": "\n\n".join(content["code_blocks"]),
            "images": content["images"]
        }
        logger.info(
            "Тег '%s': текст - %d симв., код - %d симв., графіків - %d", 
            tag, len(final_data[tag]["text"]), len(final_data[tag]["code"]), len(final_data[tag]["images"])
        )

    return final_data