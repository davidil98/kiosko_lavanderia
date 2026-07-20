"""Genera el favicon .ico desde media/logo_slogan.png.

Uso:
    .venv/bin/python tools/build_favicon.py

Genera src/app/static/favicon.ico con 3 sizes (16, 32, 48) que es
lo que pide el formato ICO. Se sobreescribe el archivo cada vez.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "media" / "logo_slogan.png"
DST = ROOT / "src" / "app" / "static" / "favicon.ico"


def main() -> None:
    if not SRC.exists():
        print(f"[favicon] No se encontró {SRC}")
        return
    img = Image.open(SRC).convert("RGBA")
    DST.parent.mkdir(parents=True, exist_ok=True)
    sizes = [(16, 16), (32, 32), (48, 48)]
    img.save(
        DST,
        format="ICO",
        sizes=sizes,
    )
    print(f"[favicon] Generado: {DST} ({DST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
