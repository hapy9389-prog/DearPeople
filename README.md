# DearPeople

## 최초 설정
cd backend && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && cp .env.example .env && deactivate
cd frontend && npm install
cd .. && npm install

## 실행
npm run dev

## 시연 순서
1. `cd backend && source venv/bin/activate && python seed.py` 실행 → 앱 열기
2. 방 목록에서 가족방·친구방·엿보기 방 확인
3. 엄마 1:1 방에서 "오늘 저녁 뭐 먹지?" 전송
4. 기억 탭에서 엄마에게 "경민이는 매운 걸 못 먹는다" 추가 → 같은 질문 재전송
5. 가족방에서 대화 → 시간 흐르기 → 나 빼고 가족방에서 그 이야기와 사진 확인
