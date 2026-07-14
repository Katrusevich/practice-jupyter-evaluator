"""Модуль генерації HTML-звіту з результатами оцінювання."""

import html
import logging
from datetime import datetime
from pathlib import Path

from grader import GradingResult

logger = logging.getLogger(__name__)


def generate_html_report(
    notebook_filename: str,
    grading_result: GradingResult,
) -> str:
    """
    Створює HTML-звіт із результатами оцінювання.

    Args:
        notebook_filename: Ім'я файлу студентської роботи.
        grading_result: Результат від Grader.grade().

    Returns:
        HTML-документ як рядок.
    """
    total = grading_result.total_score
    maximum = grading_result.max_score
    percentage = (total / maximum * 100) if maximum > 0 else 0.0

    # Будуємо рядки таблиці тестів
    table_rows = []
    for result in grading_result.test_results:
        status_class = "passed" if result.passed else "failed"
        status_text = "Пройдено" if result.passed else "Не пройдено"
        error_block = ""

        if result.error_message:
            safe_error = html.escape(result.error_message)
            error_block = f'<pre class="error-text">{safe_error}</pre>'

        table_rows.append(
            f"""
            <tr class="{status_class}">
                <td>Тест #{result.test_number}</td>
                <td>Комірка {result.test_index}</td>
                <td><span class="badge {status_class}">{status_text}</span></td>
                <td>{result.points} / 1</td>
                <td>{error_block}</td>
            </tr>
            """
        )

    rows_html = "\n".join(table_rows) if table_rows else (
        '<tr><td colspan="5">Тестових комірок не знайдено</td></tr>'
    )

    safe_filename = html.escape(notebook_filename)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    report_html = f"""<!DOCTYPE html>
<html lang="uk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Звіт оцінювання — {safe_filename}</title>
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
            max-width: 960px;
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
        .header h1 {{ font-size: 1.6rem; margin-bottom: 0.5rem; }}
        .header .filename {{ opacity: 0.85; font-size: 1rem; }}
        .summary {{
            display: flex;
            gap: 2rem;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid #e8e8e8;
            flex-wrap: wrap;
        }}
        .score-box {{
            text-align: center;
            padding: 1rem 2rem;
            background: #f8f9ff;
            border-radius: 8px;
        }}
        .score-box .score {{
            font-size: 2.4rem;
            font-weight: 700;
            color: #4361ee;
        }}
        .score-box .label {{ color: #666; font-size: 0.9rem; }}
        .content {{ padding: 2rem; }}
        h2 {{ margin-bottom: 1rem; color: #3a0ca3; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95rem;
        }}
        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }}
        th {{
            background: #f8f9ff;
            font-weight: 600;
            color: #3a0ca3;
        }}
        tr.passed td:first-child {{ border-left: 4px solid #2ecc71; }}
        tr.failed td:first-child {{ border-left: 4px solid #e74c3c; }}
        .badge {{
            display: inline-block;
            padding: 0.2rem 0.7rem;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 600;
        }}
        .badge.passed {{ background: #d4edda; color: #155724; }}
        .badge.failed {{ background: #f8d7da; color: #721c24; }}
        .error-text {{
            background: #fff5f5;
            border: 1px solid #fed7d7;
            border-radius: 6px;
            padding: 0.5rem 0.75rem;
            font-size: 0.82rem;
            white-space: pre-wrap;
            word-break: break-word;
            max-height: 200px;
            overflow-y: auto;
            margin-top: 0.25rem;
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
            <p class="filename">Файл: {safe_filename}</p>
        </div>

        <div class="summary">
            <div class="score-box">
                <div class="score">{total} / {maximum}</div>
                <div class="label">Загальний бал</div>
            </div>
            <div class="score-box">
                <div class="score">{percentage:.0f}%</div>
                <div class="label">Відсоток виконання</div>
            </div>
            <div class="score-box">
                <div class="score">{sum(1 for r in grading_result.test_results if r.passed)}</div>
                <div class="label">Тестів пройдено</div>
            </div>
        </div>

        <div class="content">
            <h2>Деталізація по тестах</h2>
            <table>
                <thead>
                    <tr>
                        <th>Тест</th>
                        <th>Комірка</th>
                        <th>Статус</th>
                        <th>Бали</th>
                        <th>Помилка</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>

        <div class="footer">
            Згенеровано: {generated_at}
        </div>
    </div>
</body>
</html>"""

    logger.info("HTML-звіт сформовано для %s", notebook_filename)
    return report_html


def save_report(html_content: str, output_path: str | Path) -> Path:
    """
    Зберігає HTML-звіт у файл.

    Args:
        html_content: HTML-документ.
        output_path: Шлях для збереження.

    Returns:
        Path до збереженого файлу.
    """
    path = Path(output_path)

    try:
        path.write_text(html_content, encoding="utf-8")
        logger.info("Звіт збережено: %s", path.resolve())
        return path
    except OSError as exc:
        logger.error("Не вдалося зберегти звіт %s: %s", path, exc)
        raise
