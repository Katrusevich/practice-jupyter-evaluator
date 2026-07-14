"""Модуль генерації універсального HTML-звіту з результатами оцінювання."""

import html
import logging
from datetime import datetime
from pathlib import Path

from grader import GradingResult, PartResult, TestResult

logger = logging.getLogger(__name__)


def _render_test_rows(tests: list[TestResult]) -> str:
    """Формує рядки таблиці для виконаних тестів конкретної частини."""
    if not tests:
        return '<tr><td colspan="5" style="text-align: center; color: #999;">Тести для цієї частини не запускалися або відсутні</td></tr>'

    rows = []
    for t in tests:
        status_class = "passed" if t.passed else "failed"
        status_text = "Пройдено" if t.passed else "Не пройдено"
        error_block = ""
        
        if t.error_message:
            error_block = f'<pre class="error-text">{html.escape(t.error_message)}</pre>'

        rows.append(f"""
        <tr class="{status_class}">
            <td>Тест #{t.test_number}</td>
            <td>Комірка {t.test_index}</td>
            <td><span class="badge {status_class}">{status_text}</span></td>
            <td>{t.points:.0f} / {t.max_points:.0f}</td>
            <td>{error_block}</td>
        </tr>
        """)

    return "".join(rows)


def _render_part_section(part: PartResult) -> str:
    """Динамічно генерує HTML-секцію для однієї частини роботи."""
    test_rows = _render_test_rows(part.test_results)
    
    # Розрахунок відсотка виконання для прогрес-бару секції
    part_pct = (part.score / part.max_score * 100) if part.max_score > 0 else 0.0
    bar_class = "good" if part_pct >= 80 else ("warn" if part_pct >= 50 else "bad")

    return f"""
    <section class="part-section">
        <div class="part-header">
            <h2>{html.escape(part.title)}</h2>
            <div class="part-score">{part.score:.1f} / {part.max_score:.0f} б.</div>
        </div>

        <div class="part-progress-track">
            <div class="progress-fill {bar_class}" style="width: {min(part_pct, 100.0):.1f}%"></div>
        </div>

        <table>
            <thead>
                <tr>
                    <th style="width: 15%;">Тест</th>
                    <th style="width: 15%;">Комірка</th>
                    <th style="width: 15%;">Статус</th>
                    <th style="width: 15%;">Бали</th>
                    <th style="width: 40%;">Помилка / Деталі</th>
                </tr>
            </thead>
            <tbody>
                {test_rows}
            </tbody>
        </table>
    </section>
    """


def generate_html_report(
    notebook_filename: str,
    grading_result: GradingResult,
) -> str:
    """
    Створює універсальний HTML-звіт на основі динамічних результатів оцінювання.

    Args:
        notebook_filename: Ім'я файлу студентської роботи.
        grading_result: Результат оцінювання Grader.grade().

    Returns:
        HTML-документ як рядок.
    """
    total = grading_result.total_score
    maximum = grading_result.max_score
    percentage = (total / maximum * 100) if maximum > 0 else 0.0

    safe_filename = html.escape(notebook_filename)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Рендеринг попереджень про файли чи датасети
    warnings_html = ""
    if grading_result.validation_warnings:
        items = "".join(
            f"<li>{html.escape(w)}</li>"
            for w in grading_result.validation_warnings
        )
        warnings_html = f"""
        <div class="warnings-box">
            <strong>⚠ Попередження:</strong>
            <ul>{items}</ul>
        </div>
        """

    # 2. Динамічний рендеринг карток підсумків (Summary Cards) для кожної частини
    parts_summary_html = []
    for part_id, part in grading_result.parts_results.items():
        parts_summary_html.append(f"""
        <div class="score-box">
            <div class="score">{part.score:.1f} / {part.max_score:.0f}</div>
            <div class="label">{html.escape(part.title)}</div>
        </div>
        """)
    
    parts_cards = "\n".join(parts_summary_html)

    # 3. Динамічний рендеринг секцій з таблицями тестів
    sections_list = []
    for part_id, part in grading_result.parts_results.items():
        sections_list.append(_render_part_section(part))
    
    content_html = "\n".join(sections_list) if sections_list else "<p style='text-align:center; padding: 2rem; color: #666;'>Не виявлено жодної частини для оцінювання.</p>"

    report_html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Звіт автоматичного оцінювання — {safe_filename}</title>
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
        }}
        .score-box .score {{
            font-size: 1.8rem;
            font-weight: 700;
            color: #4361ee;
        }}
        .score-box .label {{ color: #666; font-size: 0.8rem; margin-top: 0.25rem; }}
        
        .warnings-box {{
            margin: 1.5rem 2rem 0;
            padding: 1rem 1.25rem;
            background: #fff8e1;
            border-left: 4px solid #ffc107;
            border-radius: 6px;
            font-size: 0.9rem;
        }}
        .warnings-box ul {{ margin: 0.5rem 0 0 1.25rem; }}
        
        .content {{ padding: 1rem 2rem 2rem; }}
        
        .part-section {{
            margin-top: 2rem;
            padding: 1.5rem;
            border: 1px solid #e8e8e8;
            border-radius: 10px;
            border-top: 4px solid #4361ee;
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
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            margin-bottom: 1rem;
        }}
        th, td {{
            padding: 0.75rem 0.85rem;
            text-align: left;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }}
        th {{
            background: #f8f9ff;
            font-weight: 600;
            color: #3a0ca3;
        }}
        tr.passed td:first-child {{ border-left: 3px solid #2ecc71; }}
        tr.failed td:first-child {{ border-left: 3px solid #e74c3c; }}
        
        .badge {{
            display: inline-block;
            padding: 0.15rem 0.6rem;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: 600;
        }}
        .badge.passed  {{ background: #d4edda; color: #155724; }}
        .badge.failed  {{ background: #f8d7da; color: #721c24; }}
        
        .error-text {{
            background: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 6px;
            padding: 0.5rem 0.75rem;
            font-size: 0.78rem;
            font-family: Consolas, "Courier New", monospace;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 200px;
            overflow-y: auto;
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
            <h1>Звіт автоматичного оцінювання</h1>
            <p class="subtitle">Універсальна система перевірки лабораторних робіт Jupyter</p>
            <p class="filename">Файл: {safe_filename}</p>
        </div>

        <div class="summary">
            <div class="score-box">
                <div class="score">{total:.1f} / {maximum:.0f}</div>
                <div class="label">Загальний бал</div>
            </div>
            <div class="score-box">
                <div class="score">{percentage:.0f}%</div>
                <div class="label">Відсоток виконання</div>
            </div>
            {parts_cards}
        </div>

        {warnings_html}

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