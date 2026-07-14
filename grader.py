"""Модуль оцінювання результатів виконання тестових комірок."""

import logging
from dataclasses import dataclass, field
from typing import Any

from nbformat import NotebookNode

logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Результат одного тестового блоку."""

    test_index: int
    test_number: int
    passed: bool
    points: int
    error_message: str | None = None


@dataclass
class GradingResult:
    """Загальний результат оцінювання ноутбука."""

    total_score: int
    max_score: int
    test_results: list[TestResult] = field(default_factory=list)


class Grader:
    """
    Оцінює виконані комірки з тегом 'autograder-test'.

    За кожен успішний тест — 1 бал, за провал — 0 балів.
    AssertionError та інші помилки виконання = 0 балів.
    """

    POINTS_PER_TEST = 1

    def __init__(self, test_cells: list[dict[str, Any]]) -> None:
        """
        Args:
            test_cells: Список тестових комірок з parser.classify_cells().
        """
        self.test_cells = test_cells

    def grade(self, executed_notebook: NotebookNode) -> GradingResult:
        """
        Аналізує outputs тестових комірок після виконання.

        Args:
            executed_notebook: Ноутбук після NotebookExecutor.execute().

        Returns:
            GradingResult із деталізацією по кожному тесту.
        """
        test_results: list[TestResult] = []

        for test_number, test_info in enumerate(self.test_cells, start=1):
            cell_index = test_info["index"]
            cell = executed_notebook.cells[cell_index]

            passed, error_message = self._evaluate_test_cell(cell)
            points = self.POINTS_PER_TEST if passed else 0

            result = TestResult(
                test_index=cell_index,
                test_number=test_number,
                passed=passed,
                points=points,
                error_message=error_message,
            )
            test_results.append(result)

            status = "ПРОЙДЕНО" if passed else "ПРОВАЛЕНО"
            logger.info("Тест #%d (комірка %d): %s (%d б.)", test_number, cell_index, status, points)

        total_score = sum(result.points for result in test_results)
        max_score = len(test_results) * self.POINTS_PER_TEST

        logger.info("Підсумок: %d / %d балів", total_score, max_score)

        return GradingResult(
            total_score=total_score,
            max_score=max_score,
            test_results=test_results,
        )

    def _evaluate_test_cell(self, cell: NotebookNode) -> tuple[bool, str | None]:
        """
        Перевіряє, чи пройшла тестова комірка.

        Тест вважається проваленим, якщо:
        - у outputs є error (AssertionError або інша помилка)
        - комірка не має outputs, але execution_count = None (не виконалась)
        """
        outputs = cell.get("outputs", [])

        for output in outputs:
            if output.get("output_type") != "error":
                continue

            error_message = self._format_error(output)
            ename = output.get("ename", "")

            if ename == "AssertionError":
                logger.debug("AssertionError у тестовій комірці")
            else:
                logger.debug("Помилка виконання тесту: %s", ename)

            return False, error_message

        # Якщо комірка не виконалась взагалі
        if cell.get("execution_count") is None and not outputs:
            return False, "Комірка не була виконана (можливо, попередня помилка зупинила ядро)"

        # Немає error-output — assert-и пройшли успішно
        return True, None

    @staticmethod
    def _format_error(output: dict[str, Any]) -> str:
        """Формує текст помилки з error-output."""
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        traceback_lines = output.get("traceback", [])

        if traceback_lines:
            import re

            ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
            clean_lines = [ansi_escape.sub("", str(line)) for line in traceback_lines]
            return "\n".join(clean_lines)

        return f"{ename}: {evalue}"
