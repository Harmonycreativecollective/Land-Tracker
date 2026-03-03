from pathlib import Path

from PIL import Image


def main() -> None:
    src = Path("assets/kblogo.png")
    out_dir = Path("static/icons")
    out_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(src).convert("RGBA") as img:
        for size in (192, 512):
            resized = img.resize((size, size), Image.Resampling.LANCZOS)
            resized.save(out_dir / f"icon-{size}.png", format="PNG")


if __name__ == "__main__":
    main()
