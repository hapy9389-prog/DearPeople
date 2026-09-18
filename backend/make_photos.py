from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUTPUT_DIR = Path(__file__).parent / "static" / "photos"

SIZE = 512

PHOTOS = {
    "food_1.png": ("food", "음식 1"),
    "food_2.png": ("food", "음식 2"),
    "scenery_1.png": ("scenery", "풍경 1"),
    "scenery_2.png": ("scenery", "풍경 2"),
    "pet_1.png": ("pet", "반려동물"),
    "object_1.png": ("object", "물건"),
    "place_1.png": ("place", "장소"),
}

CATEGORY_COLORS = {
    "food": "#F6C87A",
    "scenery": "#A8D8B9",
    "pet": "#F0C9D8",
    "object": "#C9D6F0",
    "place": "#F0E2A8",
}

FONT_CANDIDATES = [
    "/System/Library/Fonts/AppleSDGothicNeo.ttc",
    "/System/Library/Fonts/Supplemental/AppleGothic.ttf",
]


def load_font(size):
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue
    return ImageFont.load_default()


def make_photo(filename, category, label):
    bg = CATEGORY_COLORS.get(category, "#DDDDDD")
    img = Image.new("RGB", (SIZE, SIZE), bg)
    draw = ImageDraw.Draw(img)
    font = load_font(64)
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((SIZE - text_w) / 2 - bbox[0], (SIZE - text_h) / 2 - bbox[1]), label, fill="#2E2823", font=font)
    img.save(OUTPUT_DIR / filename)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for filename, (category, label) in PHOTOS.items():
        make_photo(filename, category, label)
        print(f"생성됨: {filename}")


if __name__ == "__main__":
    main()
