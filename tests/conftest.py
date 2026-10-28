# Garante que `import mec0003` funcione independendo do diretorio de onde
# o pytest e chamado (raiz do repo ou nao).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
