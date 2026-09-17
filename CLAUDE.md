# DearPeople — 로컬 목업

## 무엇인가
내가 만든 AI 지인 캐릭터(엄마, 아빠, 동생, 친구 등)들이 카카오톡 같은 단톡방에서
서로 대화하고 사진을 공유하는 메신저형 목업. 배포하지 않고 로컬에서만 시연한다.

## 지켜야 할 원칙
1. 캐릭터는 사용자의 실제 지인을 AI로 만든 것이다.
2. 캐릭터의 말은 저장된 성격과 기억에서 나온다. 기억을 고치면 이후 말이 달라진다.
3. 캐릭터끼리도 대화한다. 사용자가 없는 방도 있다.

## 작업 규칙
- 목업이다. 완벽하게 만들지 말고 동작하는 최소 구현만 한다.
- 요청받지 않은 기능, 추상화, 설정 파일, 테스트 코드를 추가하지 않는다.
- 새 라이브러리는 꼭 필요할 때만 추가한다.
- 한 단계가 끝나면 실행 방법과 확인 방법을 3줄 이내로 알려준다.

## 기술 스택
- backend/: Python 3.11+, FastAPI, 내장 sqlite3 (ORM 없음), anthropic SDK
- frontend/: React + Vite, 일반 CSS. 모바일 세로 화면(최대 너비 430px) 기준
- DB 파일: backend/dearpeople.db
- 환경변수 (backend/.env): ANTHROPIC_API_KEY, CHAT_MODEL=claude-sonnet-5, FAST_MODEL=claude-haiku-4-5-20251001
- .env와 dearpeople.db는 .gitignore에 넣는다.
- API 키는 백엔드에만 둔다. 프론트엔드는 백엔드 API만 호출한다.

## 데이터 (사용자는 1명으로 고정, 로그인 없음)
- characters: id, relation, grp(family/friend), name, personality, speech_style, calls_me
- memories: id, character_id, content, created_at
- rooms: id, name, type, includes_me(0/1)
- room_members: room_id, character_id
- messages: id, room_id, sender_character_id(NULL이면 나), type(text/photo), content, caption, created_at
- settings: key, value (내 이름 등)

## AI 호출 규칙
- Claude 호출은 backend/ai.py 한 파일에 모은다.
- 구조화된 결과가 필요하면 JSON만 출력하게 하고, 코드블록 기호를 제거한 뒤 파싱한다. 파싱 실패 시 1회 재시도 후 건너뛴다.
- 캐릭터 응답 프롬프트에는 캐릭터 설정, 그 캐릭터의 기억, 방 멤버, 사용자가 방에 있는지 여부, 최근 메시지 20개를 넣는다.