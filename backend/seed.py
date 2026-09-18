"""시연 준비용 시드 스크립트. 실행: python seed.py
'경민' 프로필이 없으면 새로 만들고, 있으면 그 프로필로 전환한 뒤 비우고 다시 채운다.
다른 프로필은 전혀 건드리지 않는다. 방/첫 대화 생성 단계에서만 AI를 호출한다."""

from db import clear_profile_data, get_connection, init_db
from routes_characters import CharacterSaveRequest, create_character
from routes_profiles import ProfileCreateRequest, create_profile
from routes_rooms import generate_rooms

MY_NAME = "경민"

CHARACTERS = [
    {
        "relation": "엄마", "grp": "family", "name": "은엽",
        "personality": "따뜻하고 다정하며 자식 걱정이 많은 성격. 잔소리가 많지만 그 안에 애정이 가득하다.",
        "speech_style": "부드러운 말투로 '얘'라고 부르며, 문장 끝에 '~해야지', '~해라'를 자주 붙인다.",
        "calls_me": "얘",
        "memories": [
            "초등학교 운동회 때 넘어져 울던 나를 업고 병원까지 뛰어갔던 일",
            "첫 출근 날 아침에 넥타이를 매주며 잘할 거라고 다독여준 일",
            "혼자 자취를 시작할 때 이불이며 그릇이며 바리바리 챙겨 보내준 일",
        ],
    },
    {
        "relation": "아빠", "grp": "family", "name": "재호",
        "personality": "무뚝뚝하지만 속정 깊은 성격. 말은 적어도 챙길 건 다 챙긴다.",
        "speech_style": "짧고 담백한 말투, '~했냐', '~해라'로 끝맺는다. 감정 표현은 서툴다.",
        "calls_me": "인마",
        "memories": [
            "자전거 타는 법을 알려주다가 몇 번을 넘어져도 끝까지 뒤에서 잡아준 일",
            "고등학교 졸업식날 말없이 어깨만 두드려주고는 눈시울이 붉어졌던 일",
            "운전면허 딴 첫날 옆자리에 앉아 도로 연수를 시켜준 일",
        ],
    },
    {
        "relation": "형제자매", "grp": "family", "name": "수아",
        "personality": "밝고 애교 많지만 은근히 할 말은 다 하는 성격. 오빠/언니를 잘 놀린다.",
        "speech_style": "반말에 애교 섞인 말투, 장난스러운 표현을 자주 쓴다.",
        "calls_me": "오빠/언니",
        "memories": [
            "어릴 때 내 방에 몰래 들어와 만화책을 다 읽어버리고 시치미 떼던 일",
            "내가 시험 망친 날 말없이 초콜릿을 책상 위에 두고 간 일",
            "같이 놀이공원 갔다가 무서운 놀이기구 앞에서 나만 겁먹었던 걸 아직도 놀리는 일",
        ],
    },
    {
        "relation": "친구", "grp": "friend", "name": "도윤",
        "personality": "성실하고 현실적인 성격. 조언을 잘해주는 든든한 친구.",
        "speech_style": "차분한 존댓말과 반말을 섞어 쓰며, 요점만 짚어 말한다.",
        "calls_me": "경민아",
        "memories": [
            "대학 신입생 때 같은 조 과제를 하다 밤새 편의점에서 라면 먹으며 친해진 일",
            "취업 준비로 힘들어할 때 도서관까지 아침마다 같이 가주던 일",
            "이사할 때 트럭까지 빌려서 짐 옮기는 걸 도와준 일",
        ],
    },
    {
        "relation": "친구", "grp": "friend", "name": "하린",
        "personality": "유쾌하고 즉흥적인 성격. 분위기 메이커에 여행을 좋아한다.",
        "speech_style": "밝고 텐션 높은 말투, 감탄사를 자주 쓴다.",
        "calls_me": "경민아",
        "memories": [
            "즉흥적으로 부산 여행을 가자고 꼬드겨서 밤기차를 탔던 일",
            "생일에 깜짝 파티를 준비해줬다가 문 앞에서 들켜버린 일",
            "동아리 첫 모임에서 어색해하던 나에게 먼저 말을 걸어준 일",
        ],
    },
]


def seed_profile():
    """'경민' 프로필이 이미 있으면 그 프로필로 전환 후 비우고, 없으면 새로 만든다.
    다른 프로필은 건드리지 않는다."""
    conn = get_connection()
    try:
        existing = conn.execute("SELECT id FROM profiles WHERE name = ?", (MY_NAME,)).fetchone()
    finally:
        conn.close()

    if existing:
        profile_id = existing["id"]
        conn = get_connection()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('current_profile_id', ?)",
                (str(profile_id),),
            )
            conn.commit()
        finally:
            conn.close()
        clear_profile_data(profile_id)
        print(f"[1/4] 기존 '{MY_NAME}' 프로필로 전환 후 비움 (id={profile_id})")
    else:
        result = create_profile(ProfileCreateRequest(name=MY_NAME))
        print(f"[1/4] 새 프로필 생성 및 전환: {MY_NAME} (id={result['id']})")


def seed_settings():
    conn = get_connection()
    try:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('me_name', ?)", (MY_NAME,))
        conn.commit()
    finally:
        conn.close()
    print(f"[2/4] 내 이름 설정: {MY_NAME}")


def seed_characters():
    for c in CHARACTERS:
        create_character(CharacterSaveRequest(**c))
        print(f"  - 캐릭터 추가: {c['name']} ({c['relation']})")
    print(f"[3/4] 캐릭터 {len(CHARACTERS)}명 추가 완료")


def seed_rooms():
    print("[4/4] 방 생성 및 첫 대화 생성 중 (AI 호출, 시간이 걸릴 수 있습니다)...")
    result = generate_rooms()
    print(f"[4/4] 방 {result['room_count']}개 생성 완료")


def main():
    init_db()
    seed_profile()
    seed_settings()
    seed_characters()
    seed_rooms()
    print("시연 준비 완료. 서버를 실행하세요: uvicorn main:app --reload")


if __name__ == "__main__":
    main()
