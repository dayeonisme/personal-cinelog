# *Cinelog*

내 컴퓨터에서만 돌아가는 개인 영화 일지. 본 영화를 별점과 코멘트로 기록하고, 보고 싶은 영화를 모아두는 앱. 계정도, 클라우드도, 구독도 없음.

---

## 기능

### 홈
등록한 모든 영화를 포스터 그리드로 표시. 카드에 마우스를 올리면 제목, 연도, 감독 정보가 나타남. 평가/보고싶어요 필터, 날짜·평점 정렬, 제목·감독·배우 통합 검색 지원.

### 평가
감상한 영화를 유연한 별점·코멘트 시스템으로 기록.

- **별점** — 기본 종합 평점 (0~5점, 0.5 단위) + 원하는 만큼 커스텀 별점 추가 (예: *연출*, *OST*, *재관람 의향*)
- **코멘트** — 기본 감상평 + 커스텀 코멘트 섹션 추가 가능. 마크다운 지원, 이미지 첨부 가능
- **감상 상태** — 완료 / 진행중 / 중단 으로 구분
- 이전에 등록한 별점명·코멘트명은 자동으로 기억되어 드롭다운으로 재사용 가능

### 보고싶어요
보고 싶은 영화를 큐에 담아두는 공간. 커스텀 코멘트 모듈로 메모 추가 가능. 제목, 감독, 배우로 검색 및 필터링 지원.

### 영화 정보 자동 완성
제목으로 검색하면 OMDb에서 실시간으로 결과를 불러오고, 선택 시 포스터·출연진·감독·장르·런타임이 자동으로 채워짐.

---

## 기술 스택

| | |
|---|---|
| 백엔드 | Python · Flask · SQLAlchemy |
| 데이터베이스 | SQLite (로컬 파일, 별도 설정 불필요) |
| 프론트엔드 | Vanilla JS · HTML · CSS |
| 영화 데이터 | [OMDb API](https://www.omdbapi.com/) — 무료 플랜, 1,000건/일 |

---

## 시작하기

### 사전 준비

- Python 3.10 이상
- OMDb 무료 API 키 발급 → [omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx)

### 설치

```bash
git clone https://github.com/dayeonisme/personal-cinelog.git
cd personal-cinelog
pip3 install -r requirements.txt
```

### 실행

```bash
export OMDB_API_KEY="발급받은_키"
python app.py
```

브라우저에서 **http://localhost:5001** 접속.

---

## macOS 자동 시작 설정

Mac 로그인 시 Cinelog가 자동으로 시작되도록 등록:

```bash
bash install_autostart.sh
```

제거하려면:

```bash
launchctl unload ~/Library/LaunchAgents/com.cinelog.app.plist
rm ~/Library/LaunchAgents/com.cinelog.app.plist
```

---

## 프로젝트 구조

```
cinelog/
├── app.py                   # Flask 앱 & REST API
├── models.py                # SQLAlchemy 모델
├── database.py              # DB 초기화
├── requirements.txt
├── install_autostart.sh     # macOS launchd 등록 스크립트
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── uploads/             # 첨부 이미지 저장 폴더 (gitignore 처리)
└── templates/
    └── index.html
```

---

## 데이터 구조

```
Movie
└── Entry  (타입: review | watchlist)
    ├── RatingModule   이름 · 이모지 · 점수 (0–5)
    └── CommentModule  이름 · 내용 (마크다운) · 이미지[]
```

---

## 디자인

Cinematic dark-mode. 따뜻한 블랙·에스프레소 배경, 브론즈/골드 포인트, 세이지 그린 상태 표시. 디스플레이 타이포그래피는 *Cormorant Garamond* 이탤릭 사용.

---

*개인 사용 목적. IMDb 및 OMDb와 무관합니다.*
