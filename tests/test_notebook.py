"""Roda o notebook do começo ao fim. Falha se qualquer célula falhar, inclusive as verificações."""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

RAIZ = Path(__file__).resolve().parent.parent


def test_experimentos():
    nb = nbformat.read(RAIZ / "experimentos.ipynb", as_version=4)
    NotebookClient(nb, timeout=1200, kernel_name="python3", resources={"metadata": {"path": str(RAIZ)}}).execute()
