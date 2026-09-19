import os
import random
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 자리표시 사진과 업로드(uploads/)가 함께 있는 디렉터리. 환경변수가 없으면 저장소 안의 기본 경로.
PHOTOS_DIR = Path(os.environ.get("PHOTOS_DIR") or Path(__file__).parent / "static" / "photos")

CATEGORY_FILES = {
    "food": ["food_1.png", "food_2.png"],
    "scenery": ["scenery_1.png", "scenery_2.png"],
    "pet": ["pet_1.png"],
    "object": ["object_1.png"],
    "place": ["place_1.png"],
}


def pick_photo(category):
    """카테고리에 맞는 자리표시 사진 경로를 무작위로 반환한다. 없으면 None.
    나중에 실제 이미지 생성 API로 교체할 자리."""
    files = [f for f in CATEGORY_FILES.get(category, []) if (PHOTOS_DIR / f).exists()]
    if not files:
        return None
    return f"/static/photos/{random.choice(files)}"
