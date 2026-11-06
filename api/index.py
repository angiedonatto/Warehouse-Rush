"""Entrypoint Vercel: el entrenamiento y el entorno no se reimplementan aquí."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api._cloud import CloudHandler


class handler(CloudHandler):
    """Handler explícito para el descubrimiento de funciones Python de Vercel."""

    pass
