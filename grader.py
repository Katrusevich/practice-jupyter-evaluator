"""Модуль універсального оцінювання результатів виконання тестових комірок."""

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from nbformat import NotebookNode

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Результат одного тестового блоку (assert-комірки)."""

    test_index: int
    test_number: int
    part_id: str                        # ID частини з конфігурації (наприклад, "part_1")
    passed: bool
    points: float
    max_points: float = 1.0
    error_message: str | None = None


@dataclass
class PartResult:
    """Підсумок виконання однієї частини лабораторної роботи."""

    part_id: str
    title: str
    score: float
    max_score: float
    test_results: list[TestResult] = field(default_factory=list)


@dataclass
class GradingResult:
    """Загальний результат оцінювання всього ноутбука."""

    total_score: float
    max_score: float
    parts_results: dict[str, PartResult] = field(default_factory=dict)
    validation_warnings: list[str] = field(default_factory=list)


class Grader:
    """
    Універсальний оцінювач ноутбуків.
    Оцінює роботу виключно на основі успішності виконання assert-тестів
    і динамічно групує їх за частинами, визначеними у конфігурації.
    """

    def __init__(
        self,
        classified_test_cells: list[dict[str, Any]],
        config_parts: list[dict[str, Any]],
        validation_warnings: list[str] | None = None,
    ) -> None:
        """
        Args:
            classified_test_cells: Список тестових комірок з класифікатора.
            config_parts: Список частин лабораторної з grading_config.json.
            validation_warnings: Попередження про відсутні файли чи датасети.
        """
        self.test_cells = classified_test_cells
        self.config_parts = config_parts
        self.validation_warnings = validation_warnings or []

    def grade(self, executed_notebook: NotebookNode) -> GradingResult:
        """Аналізує виконані тестові комірки та формує загальний результат."""
        parts_results: dict[str, PartResult] = {}
        
        # 1. Ініціалізуємо структури для кожної частини з конфігурації
        for part in self.config_parts:
            part_id = part["id"]
            parts_results[part_id] = PartResult(
                part_id=part_id,
                title=part["name"],
                score=0.0,
                max_score=0.0,
                test_results=[]
            )

        # Резервна категорія для тестів без чітко визначеної частини
        fallback_part_id = self.config_parts[0]["id"] if self.config_parts else "general"
        if fallback_part_id not in parts_results:
            parts_results[fallback_part_id] = PartResult(
                part_id=fallback_part_id,
                title="Загальні тести",
                score=0.0,
                max_score=0.0,
                test_results=[]
            )

        # 2. Оцінюємо кожну тестову комірку
        for test_number, test_info in enumerate(self.test_cells, start=1):
            cell_index = test_info["index"]
            part_id = test_info.get("part", fallback_part_id)
            
            # Якщо з якихось причин частина не прописана в результатах
            if part_id not in parts_results:
                part_id = fallback_part_id

            cell = executed_notebook.cells[cell_index]
            passed, error_message = self._evaluate_test_cell(cell)
            points = 1.0 if passed else 0.0

            result = TestResult(
                test_index=cell_index,
                test_number=test_number,
                part_id=part_id,
                passed=passed,
                points=points,
                max_points=1.0,
                error_message=error_message,
            )

            parts_results[part_id].test_results.append(result)
            parts_results[part_id].score += points
            parts_results[part_id].max_score += 1.0

            status = "ПРОЙДЕНО" if passed else "ПРОВАЛЕНО"
            logger.info(
                "Тест #%d (комірка %d, %s): %s (%.1f б.)",
                test_number, cell_index, part_id, status, points
            )

        # 3. Підраховуємо фінальні бали
        total_score = sum(part.score for part in parts_results.values())
        max_score = sum(part.max_score for part in parts_results.values())

        logger.info("Підсумок оцінювання: %.1f / %.1f балів", total_score, max_score)

        return GradingResult(
            total_score=total_score,
            max_score=max_score,
            parts_results=parts_results,
            validation_warnings=self.validation_warnings,
        )

    def _evaluate_test_cell(self, cell: NotebookNode) -> tuple[bool, str | None]:
        """
        Перевіряє, чи успішно виконалася тестова комірка.
        Тест провалений, якщо у виводах (outputs) є помилка або комірка не запускалася.
        """
        outputs = cell.get("outputs", [])

        for output in outputs:
            if output.get("output_type") != "error":
                continue

            error_message = self._format_error(output)
            ename = output.get("ename", "Error")

            if ename == "AssertionError":
                logger.debug("Тест завалився на етапі перевірки умов (AssertionError)")
            else:
                logger.debug("Помилка виконання коду під час тесту: %s", ename)

            return False, error_message

        # Перевірка на запуск комірки
        if cell.get("execution_count") is None and not outputs:
            return False, "Комірка не була виконана (можливо, попередній збій зупинив роботу ядра)"

        return True, None

    @staticmethod
    def _format_error(output: dict[str, Any]) -> str:
        """Очищає та форматує traceback помилки для збереження у звіті."""
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        traceback_lines = output.get("traceback", [])

        if traceback_lines:
            # Видаляємо кольорові символи терміналу (ANSI коди)
            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            clean_lines = [ansi_escape.sub("", str(line)) for line in traceback_lines]
            return "\n".join(clean_lines)

        return f"{ename}: {evalue}"