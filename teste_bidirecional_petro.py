from pathlib import Path
import sys

print("ARQUIVO:", Path(__file__).resolve())
print("RAIZ:", Path(__file__).resolve().parent)
print("PYTHON:", sys.executable)

import metodos
print("METODOS:", metodos.__file__)