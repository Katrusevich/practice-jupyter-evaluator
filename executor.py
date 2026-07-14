"""Модуль для виконання коду з Jupyter Notebook у ізольованому ядрі."""

import copy
import logging
import os
import re
from typing import Any

from jupyter_client import KernelManager
from nbclient import NotebookClient
from nbclient.exceptions import CellExecutionError
from nbformat import NotebookNode

logger = logging.getLogger(__name__)

# Значення за замовчуванням, якщо таймаут не передано з конфігурації
DEFAULT_TIMEOUT = 30


class NotebookExecutor:
    """
    Запускає ноутбук через nbclient.NotebookClient.

    Ядро працює у окремому фоновому процесі (KernelManager)
    з ізоляцією пам'яті. Помилки в окремих комірках не зупиняють виконання решти.
    """

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout
        self.cell_errors: dict[int, str] = {}

    def execute(self, notebook: NotebookNode) -> NotebookNode:
        """
        Виконує всі code-комірки ноутбука по порядку.

        Returns:
            Ноутбук із заповненими outputs після виконання.
        """
        # Працюємо з копією, щоб не змінювати оригінал
        executed_notebook = copy.deepcopy(notebook)
        self.cell_errors.clear()

        # Налаштування системних змінних для фонового ядра (зокрема для приглушення TF логів)
        env = os.environ.copy()
        env["TF_CPP_MIN_LOG_LEVEL"] = "3"
        env.setdefault("CUDA_VISIBLE_DEVICES", "-1")  # CPU-only для легшого виконання

        kernel_manager = KernelManager()
        kernel_manager.start_kernel(env=env)
        logger.info(
            "Ізольоване ядро Python запущено (timeout=%ds)",
            self.timeout,
        )

        try:
            client = NotebookClient(
                executed_notebook,
                timeout=self.timeout,
                kernel_manager=kernel_manager,
                allow_errors=True,  # Продовжуємо навіть якщо одна з комірок впала
            )

            try:
                executed_notebook = client.execute()
            except CellExecutionError as exc:
                logger.warning("Критична помилка виконання ядра: %s", exc)
                self._record_error_from_exception(exc)

            # Збираємо виникаючі помилки з outputs комірок
            self._collect_cell_errors(executed_notebook)

        finally:
            kernel_manager.shutdown_kernel(now=True)
            logger.info("Ядро Python зупинено")

        if self.cell_errors:
            logger.warning("Помилки у %d комірках", len(self.cell_errors))
        else:
            logger.info("Усі комірки виконано без помилок")

        return executed_notebook

    def _record_error_from_exception(self, exc: CellExecutionError) -> None:
        """Зберігає текст помилки з винятку CellExecutionError."""
        cell_index = getattr(exc, "cell_index", None)
        if cell_index is not None:
            self.cell_errors[cell_index] = str(exc)

    def _collect_cell_errors(self, notebook: NotebookNode) -> None:
        """Проходить по комірках і збирає error-outputs."""
        for index, cell in enumerate(notebook.cells):
            if cell.cell_type != "code":
                continue

            for output in cell.get("outputs", []):
                if output.get("output_type") != "error":
                    continue

                error_text = self._format_error_output(output)
                self.cell_errors[index] = error_text
                logger.warning(
                    "Помилка у комірці %d: %s",
                    index,
                    error_text.split("\n")[0],
                )

    @staticmethod
    def _format_error_output(output: dict[str, Any]) -> str:
        """Форматує error-output комірки у читабельний текст."""
        ename = output.get("ename", "Error")
        evalue = output.get("evalue", "")
        traceback_lines = output.get("traceback", [])

        if traceback_lines:
            clean_lines = [
                NotebookExecutor._strip_ansi(str(line)) for line in traceback_lines
            ]
            return "\n".join(clean_lines)

        return f"{ename}: {evalue}"

    @staticmethod
    def _strip_ansi(text: str) -> str:
        """Прибирає ANSI-коди (керуючі колірні послідовності) з тексту traceback."""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)