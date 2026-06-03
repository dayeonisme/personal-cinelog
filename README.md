# personal-cinelog
본 영화 평가 및 보고싶어요 목록 관리 데스크탑 웹앱.
영화 검색(OMDb) → 별점·코멘트 기록 → SQLite 로컬 저장 → localhost에서 실행.

---

## 폴더 구조

```
personal-cinelog/
├── app.py                    # Flask 앱 & REST API
├── models.py                 # SQLAlchemy 모델
├── database.py               # DB 초기화
├── requirements.txt
├── install_autostart.sh      # macOS 로그인 시 자동 시작 등록 (launchd)
├── run.sh                    # 수동 실행 스크립트
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── uploads/              # 첨부 이미지 저장 폴더 (gitignored)
└── templates/
    └── index.html
```

---

## 설정 전 필수 사항

**OMDb API 키 발급**

[omdbapi.com/apikey.aspx](https://www.omdbapi.com/apikey.aspx) 에서 무료 등록 (1,000건/일).

---

## 설치 및 실행

### Step 1 — 클론 및 의존성 설치

```bash
git clone https://github.com/dayeonisme/personal-cinelog.git
cd personal-cinelog
pip3 install -r requirements.txt
```

### Step 2 — 환경 변수 설정

```bash
export OMDB_API_KEY="발급받은_키"
```

영구 적용하려면 `~/.zshrc`에 추가.

### Step 3 — 실행

```bash
python app.py
```

브라우저에서 **http://localhost:5001** 접속.

---

## macOS 자동 시작 설정

로그인 시 자동 실행되도록 launchd에 등록:

```bash
bash install_autostart.sh
```

제거:

```bash
launchctl unload ~/Library/LaunchAgents/com.cinelog.app.plist
rm ~/Library/LaunchAgents/com.cinelog.app.plist
```

---

## 수동 실행

```bash
# 환경 변수 포함해서 실행
OMDB_API_KEY="발급받은_키" python app.py
```

---

## 데이터 모델

```
Movie
└── Entry  (type: review | watchlist)
    ├── RatingModule   이름 · 이모지 · 점수 (0~5, 0.5 단위)
    └── CommentModule  이름 · 내용 (Markdown) · 이미지[]
```

- **RatingTemplate** — 이전에 등록한 커스텀 별점명 목록 (재사용 드롭다운용)
- **CommentTemplate** — 이전에 등록한 커스텀 코멘트명 목록 (재사용 드롭다운용)

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/entries` | 목록 조회 (type, sort, filter, search, page) |
| POST | `/api/entries` | 새 항목 등록 |
| PUT | `/api/entries/<id>` | 수정 |
| DELETE | `/api/entries/<id>` | 삭제 |
| GET | `/api/search/movies?q=` | OMDb 영화 검색 |
| GET | `/api/search/movies/<imdb_id>` | 영화 상세 조회 |
| POST | `/api/upload` | 이미지 첨부 |
| GET | `/api/templates/ratings` | 커스텀 별점명 목록 |
| GET | `/api/templates/comments` | 커스텀 코멘트명 목록 |

---

## 커밋하지 않는 파일 (.gitignore)

| 파일 | 이유 |
|------|------|
| `*.db`, `*.db-journal` | 개인 영화 기록 DB |
| `static/uploads/*` | 사용자 첨부 이미지 |
| `.env` | API 키 등 환경 변수 |
| `logs/` | 런타임 로그 |

---

*개인 사용 목적. IMDb 및 OMDb와 무관합니다.*
