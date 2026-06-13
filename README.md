# personal-cinelog
본 영화 평가 및 보고싶어요 목록 관리 데스크탑 웹앱.
영화 검색(TMDb) → 별점·코멘트 기록 → SQLite 로컬 저장 → localhost에서 실행.

---

## 주요 기능

- 영화별 `평가`와 `보고싶어요`를 별도로 등록하고 영화 상세에서 함께 확인
- 기본 평점과 커스텀 별점 모듈 지원
- 커스텀 별점 이모지 선택기 지원
- Markdown 코멘트와 이미지 첨부 지원
- 해시태그 자동완성 및 검색 지원
- TMDb 키워드 기반 `원작존재` 해시태그 자동 부여

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

**TMDb API 키 발급**

[TMDb API 문서](https://developer.themoviedb.org/docs/getting-started) 기준으로 계정을 만들고 API Read Access Token 또는 API Key를 발급합니다.

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
export TMDB_ACCESS_TOKEN="발급받은_Read_Access_Token"
```

또는 v3 API Key를 사용할 수 있습니다.

```bash
export TMDB_API_KEY="발급받은_API_Key"
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
TMDB_ACCESS_TOKEN="발급받은_Read_Access_Token" python app.py
```

---

## 데이터 모델

```
Movie
└── Entry  (type: review | watchlist)
    ├── RatingModule   이름 · 이모지 · 점수 (0~5, 0.5 단위)
    ├── CommentModule  이름 · 내용 (Markdown) · 이미지[]
    └── Hashtag        공백 없는 태그명
```

- **RatingTemplate** — 이전에 등록한 커스텀 별점명 목록 (재사용 드롭다운용)
- **CommentTemplate** — 이전에 등록한 커스텀 코멘트명 목록 (재사용 드롭다운용)

---

## 해시태그 정책

- 해시태그 이름에는 공백을 저장하지 않습니다. 예: `원작 존재` → `원작존재`
- `원작존재`
  - 새 항목 등록 시 TMDb `/movie/{id}/keywords`를 조회해 자동 추가합니다.
  - `based on novel`, `based on book`, `based on comic`, `based on play or musical` 등 원작 존재를 뜻하는 키워드가 기준입니다.
  - TMDb 조회 실패 시 등록은 계속 진행하고 태그만 생략합니다.
  - 기존 항목은 `tools/migrate_novel_hashtag.py`로 백필할 수 있습니다.
- `왓챠백업`
  - 왓챠에서 가져온 평가 항목 중 `RatingModule.name == "왓챠 별점"`인 경우에만 유지합니다.
  - `보고싶어요` 항목에는 유지하지 않습니다.
  - 정리는 `tools/migrate_watcha_hashtag.py`로 동기화합니다.

---

## API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/entries` | 목록 조회 (type, sort, filter, search, page) |
| POST | `/api/entries` | 새 항목 등록 |
| PUT | `/api/entries/<id>` | 수정 |
| DELETE | `/api/entries/<id>` | 삭제 |
| GET | `/api/search/movies?q=` | TMDb 영화 검색 |
| GET | `/api/search/movies/<movie_key>` | 영화 상세 조회 |
| GET | `/api/movies/<id>` | 앱 내 영화 상세 조회 |
| GET | `/api/hashtags` | 해시태그 목록 |
| POST | `/api/upload` | 이미지 첨부 |
| GET | `/api/templates/ratings` | 커스텀 별점명 목록 |
| GET | `/api/templates/comments` | 커스텀 코멘트명 목록 |

---

## TMDb 출처 표기

<a href="https://www.themoviedb.org/">
  <img src="https://www.themoviedb.org/assets/2/v4/logos/v2/blue_square_2-d537fb228cf3ded904ef09b136fe3fec72548ebc1fea3fbbd1ad9e36364db38b.svg" alt="The Movie Database (TMDB)" width="120">
</a>

이 제품은 TMDb API를 사용하지만, TMDb의 보증이나 인증을 받은 것은 아닙니다.

Cinelog는 영화 검색과 표시를 위해 [The Movie Database (TMDB)](https://www.themoviedb.org/)에서 제공하는 영화 메타데이터와 포스터 이미지를 사용합니다. TMDb 로고와 출처 표기 가이드는 공식 [Logos & Attribution](https://www.themoviedb.org/about/logos-attribution) 페이지에서 확인할 수 있습니다.

원문 고지: This product uses the TMDB API but is not endorsed or certified by TMDB.

---

## 커밋하지 않는 파일 (.gitignore)

| 파일 | 이유 |
|------|------|
| `*.db`, `*.db-journal` | 개인 영화 기록 DB |
| `static/uploads/*` | 사용자 첨부 이미지 |
| `.env` | API 키 등 환경 변수 |
| `logs/` | 런타임 로그 |
| `AGENTS.md` | 로컬 에이전트 지침 |

---

*개인 사용 목적. TMDb, IMDb, 왓챠와 무관합니다.*
