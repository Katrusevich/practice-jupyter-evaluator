"""Модуль генерації універсального HTML-звіту з результатами AI-оцінювання."""

import html
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _render_task_section(task_id: str, task_data: dict[str, Any]) -> str:
    """Динамічно генерує HTML-секцію для одного завдання на основі оцінки LLM."""
    name = html.escape(task_data["name"])
    score = task_data["score"]
    max_points = task_data["max_points"]
    details = task_data["details"]  # Словник з результатами від Pydantic
    images = task_data["images"]

    # Розрахунок відсотка виконання для прогрес-бару секції
    part_pct = (score / max_points * 100) if max_points > 0 else 0.0
    bar_class = "good" if part_pct >= 80 else ("warn" if part_pct >= 50 else "bad")

    # Форматуємо розбивку балів
    breakdown_html = f"""
    <div class="score-breakdown">
        <div class="breakdown-item"><strong>Код:</strong> {details.get('code_score', 0)} б.</div>
        <div class="breakdown-item"><strong>Текст:</strong> {details.get('text_score', 0)} б.</div>
        <div class="breakdown-item"><strong>Графіки:</strong> {details.get('graphs_score', 0)} б.</div>
        <div class="breakdown-item bonus"><strong>Бонус:</strong> +{details.get('bonus_score', 0)} б.</div>
    </div>
    """

    # Форматуємо відгук ШІ
    feedback_text = html.escape(details.get('feedback', 'Коментар відсутній.'))
    feedback_html = f"""
    <div class="ai-feedback">
        <div class="feedback-title">🤖 Коментар AI-асистента:</div>
        <div class="feedback-text">{feedback_text}</div>
    </div>
    """

    # Форматуємо галерею зображень, якщо вони є
    images_html = ""
    if images:
        img_tags = []
        for img in images:
            mime = html.escape(img.get("mime_type", "image/png"))
            b64 = img.get("base64_data", "")
            img_tags.append(f'<img src="data:{mime};base64,{b64}" alt="Графік з ноутбука" class="preview-img">')
        
        images_html = f"""
        <div class="image-gallery">
            <div class="gallery-title">📊 Знайдені графіки:</div>
            <div class="gallery-container">{"".join(img_tags)}</div>
        </div>
        """

    return f"""
    <section class="part-section">
        <div class="part-header">
            <h2>{name}</h2>
            <div class="part-score">{score} / {max_points} б.</div>
        </div>

        <div class="part-progress-track">
            <div class="progress-fill {bar_class}" style="width: {min(part_pct, 100.0):.1f}%"></div>
        </div>
        
        {breakdown_html}
        {feedback_html}
        {images_html}
    </section>
    """


def generate_html_report(
    notebook_filename: str,
    evaluation_results: dict[str, dict[str, Any]],
    total_score: int,
    max_total_score: int
) -> str:
    """
    Створює HTML-звіт на основі результатів AI-оцінювання.
    """
    percentage = (total_score / max_total_score * 100) if max_total_score > 0 else 0.0

    safe_filename = html.escape(notebook_filename)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Динамічний рендеринг карток підсумків (Summary Cards)
    parts_summary_html = []
    for task_id, task_data in evaluation_results.items():
        parts_summary_html.append(f"""
        <div class="score-box">
            <div class="score">{task_data['score']} / {task_data['max_points']}</div>
            <div class="label">{html.escape(task_data['name'])}</div>
        </div>
        """)
    
    parts_cards = "\n".join(parts_summary_html)

    # Динамічний рендеринг секцій завдань
    sections_list = []
    for task_id, task_data in evaluation_results.items():
        sections_list.append(_render_task_section(task_id, task_data))
    
    content_html = "\n".join(sections_list) if sections_list else "<p style='text-align:center; padding: 2rem; color: #666;'>Немає даних для відображення.</p>"

    report_html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI-Звіт оцінювання — {safe_filename}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: "Segoe UI", Tahoma, Geneva, Verdana, sans-serif;
            background: #f0f2f5;
            color: #1a1a2e;
            line-height: 1.6;
            padding: 2rem;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: #fff;
            border-radius: 12px;
            box-shadow: 0 4px 24px rgba(0,0,0,0.08);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #4361ee, #3a0ca3);
            color: #fff;
            padding: 2rem;
        }}
        .header h1 {{ font-size: 1.6rem; margin-bottom: 0.25rem; }}
        .header .subtitle {{ opacity: 0.85; font-size: 0.95rem; }}
        .header .filename {{ opacity: 0.75; font-size: 0.9rem; margin-top: 0.5rem; }}
        
        .summary {{
            display: flex;
            gap: 1.5rem;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid #e8e8e8;
            flex-wrap: wrap;
        }}
        .score-box {{
            text-align: center;
            padding: 1rem 1.5rem;
            background: #f8f9ff;
            border-radius: 8px;
            flex: 1;
            min-width: 140px;
            border: 1px solid #e2e8f0;
        }}
        .score-box .score {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #4361ee;
        }}
        .score-box .label {{ color: #666; font-size: 0.8rem; margin-top: 0.25rem; }}
        
        .content {{ padding: 1rem 2rem 2rem; }}
        
        .part-section {{
            margin-top: 2rem;
            padding: 1.5rem;
            border: 1px solid #e8e8e8;
            border-radius: 10px;
            border-top: 4px solid #4361ee;
            background: #fafafc;
        }}
        .part-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1rem;
        }}
        .part-header h2 {{ color: #3a0ca3; font-size: 1.2rem; }}
        .part-score {{
            font-size: 1.4rem;
            font-weight: 700;
            color: #4361ee;
        }}
        
        .part-progress-track {{ 
            margin-bottom: 1.5rem; 
            height: 8px; 
            background: #e9ecef;
            border-radius: 5px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            border-radius: 5px;
            transition: width 0.4s ease;
        }}
        .progress-fill.good {{ background: linear-gradient(90deg, #2ecc71, #27ae60); }}
        .progress-fill.warn {{ background: linear-gradient(90deg, #f39c12, #e67e22); }}
        .progress-fill.bad  {{ background: linear-gradient(90deg, #e74c3c, #c0392b); }}
        
        .score-breakdown {{
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }}
        .breakdown-item {{
            background: #fff;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
            font-size: 0.9rem;
            color: #4a5568;
        }}
        .breakdown-item.bonus {{
            background: #f0fff4;
            border-color: #9ae6b4;
            color: #276749;
        }}
        
        .ai-feedback {{
            background: #fff;
            border-left: 4px solid #805ad5;
            padding: 1.25rem;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-bottom: 1.5rem;
        }}
        .feedback-title {{
            font-weight: 700;
            color: #553c9a;
            margin-bottom: 0.5rem;
            font-size: 0.95rem;
        }}
        .feedback-text {{
            font-size: 0.95rem;
            color: #2d3748;
            white-space: pre-wrap; /* Зберігає абзаци */
        }}

        .image-gallery {{
            background: #fff;
            padding: 1rem;
            border-radius: 6px;
            border: 1px solid #e2e8f0;
        }}
        .gallery-title {{
            font-weight: 600;
            color: #4a5568;
            margin-bottom: 0.75rem;
            font-size: 0.9rem;
        }}
        .gallery-container {{
            display: flex;
            gap: 1rem;
            overflow-x: auto;
            padding-bottom: 0.5rem;
        }}
        .preview-img {{
            max-height: 250px;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        }}
        
        .footer {{
            padding: 1rem 2rem;
            background: #f8f9ff;
            color: #888;
            font-size: 0.85rem;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>AI-Звіт оцінювання</h1>
            <p class="subtitle">Перевірка виконана за допомогою LangChain та LLM</p>
            <p class="filename">Файл: {safe_filename}</p>
        </div>

        <div class="summary">
            <div class="score-box">
                <div class="score">{total_score} / {max_total_score}</div>
                <div class="label">Загальний бал</div>
            </div>
            <div class="score-box">
                <div class="score">{percentage:.0f}%</div>
                <div class="label">Відсоток виконання</div>
            </div>
            {parts_cards}
        </div>

        <div class="content">
            {content_html}
        </div>

        <div class="footer">Згенеровано: {generated_at}</div>
    </div>
</body>
</html>"""

    logger.info("HTML-звіт успішно сформовано для %s", notebook_filename)
    return report_html


def save_report(html_content: str, output_path: str | Path) -> Path:
    """Зберігає згенерований HTML-звіт у файл."""
    path = Path(output_path)
    try:
        path.write_text(html_content, encoding="utf-8")
        logger.info("Звіт збережено: %s", path.resolve())
        return path
    except OSError as exc:
        logger.error("Не вдалося зберегти звіт %s: %s", path, exc)
        raise