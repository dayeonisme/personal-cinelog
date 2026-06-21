# personal-cinelog

개인용 영화 평가·보고싶어요 기록 웹앱.
영화 검색(TMDb) → 별점·코멘트 기록 → SQLite 저장. 왓챠피디아의 내 평가를 가져와 동기화한다.

**GCP 상시 서버에 배포하고 Tailscale 사설망으로 PC·모바일 어디서나 접속한다.** (레거시: Mac 에서 앱 버튼으로 서버를 켜는 방식, 로컬 `python app.py` 방식은 개발용으로만 남겨둔다.)

---

## 접속 방식

- **배포 (권장·기본)** — GCP Always Free VM 에 gunicorn + systemd 로 **상시 구동**. **Tailscale 사설망**으로만 접근하므로 공개 인터넷에 노출되지 않고, PC·아이폰에서 동일하게 `http://<VM의 Tailscale IP>:5001` 로 접속한다. 컴퓨터를 꺼도 폰에서 접속·기록 가능.
  - 설정/운영 전체 절차는 **[`deploy/README.md`](deploy/README.md)** 참고.
- **로컬 개발** — `python app.py` → `http://localhost:5001` (아래 [로컬 개발 실행](#로컬-개발-실행)).

> **데이터 정본은 배포 VM 한 곳.** 로컬에서 따로 실행하면 DB 가 갈라지므로, 평소엔 Mac 에서도 Tailscale 주소로 접속한다.

---

## 주요 기능

- 영화별 `평가`와 `보고싶어요`를 별도로 등록하고 상세에서 함께 확인
- 기본 평점 + 커스텀 별점 모듈, 커스텀 이모지 별점 선택기
- Markdown 코멘트와 이미지 첨부
- 해시태그 자동완성·검색, TMDb 키워드 기반 `원작존재` 해시태그 자동 부여
- 홈에서는 **한글** 영화명·감독명, 상세에서는 **원제·원어 감독**도 다른 정보와 함께 표기
- **모바일 반응형 UI** — 하단 탭바(평가·홈·보고싶어요), 2열 포스터 그리드, 카드에 제목·연도·별점 상시 표시
- **왓챠피디아 연동** — 내 평가/보고싶어요를 가져와 TMDb 메타데이터(포스터·감독·배우·러닝타임·장르)로 보강
  - GNB 의 **↻ 버튼으로 수동 동기화** (서버에서 실행 → PC·모바일 어디서 눌러도 동작)
  - **매일 새벽 자동 동기화** (systemd 타이머)

---

## 배포 (GCP + Tailscale)

상시 접속을 위해 GCP Always Free e2-micro VM 에 올리고 **Tailscale 사설망**으로 접근한다.
공개 인터넷에 노출하지 않으므로 별도 로그인/HTTPS 없이 **내 기기에서만** 접속한다.

- gunicorn + systemd(`deploy/cinelog.service`) 로 상시 구동·부팅 자동 시작·크래시 자동 재시작
- 앱을 **Tailscale IP 에만 바인딩** → 외부 IP 로는 보이지 않음(이중 안전장치로 방화벽 5001 미개방)
- e2-micro(1GB) 보호용 swap 자동 생성

요약 (자세한 절차·보안 체크리스트는 [`deploy/README.md`](deploy/README.md)):

```bash
# VM 안에서 — Tailscale 설치 후
git clone https://github.com/dayeonisme/personal-cinelog.git ~/movie-review
cd ~/movie-review
bash deploy/setup-vm.sh                 # venv + 의존성 + swap + systemd 서비스 등록

# Mac 에서 — DB·.env 전송 (gitignore 라 git 에 없음)
deploy/push-data.sh <VM이름> <zone>
```

폰: App/Play 스토어에서 **Tailscale** 설치 → 같은 계정 로그인 → 브라우저로 `http://<VM의 Tailscale IP>:5001` → Safari "홈 화면에 추가" 하면 앱처럼 사용.

---

## 왓챠피디아 동기화

왓챠피디아의 내 평가·보고싶어요를 가져와 Cinelog DB 에 반영하고 TMDb 로 보강한다.

- **세션 이식** — 포터블 `watcha_state.json`(쿠키)로 OS 무관하게 이식. Mac 에서 `tools/dump_watcha_state.py` 로 생성 후 VM 으로 복사. (브라우저 프로필 복사는 OS 키체인 암호화로 불가)
- **파이프라인** (`deploy/watcha-sync.sh`): `export(왓챠 내부 API) → import → TMDb 보강 → 원작존재 태그`.
- **자동** — `deploy/cinelog-watcha-sync.timer` 가 매일 04:00 KST 실행. 설정: `bash deploy/setup-watcha-sync.sh`.
- **수동** — 앱 GNB 의 ↻ 버튼 → `POST /api/watcha/sync` 가 systemd 서비스를 비차단으로 트리거. 상태는 폴링으로 표시(완료 시 토스트 + 홈 새로고침).

주요 도구 (`tools/`):

| 파일 | 역할 |
|------|------|
| `dump_watcha_state.py` | (Mac) 로그인 세션 → 포터블 `watcha_state.json` 추출 |
| `export_watchapedia.py` | 왓챠 내부 API 로 평가/보고싶어요 수집 → CSV |
| `import_watcha_csv.py` | CSV → DB |
| `enrich_tmdb_metadata.py` / `enrich_via_watcha_detail.py` | TMDb 메타데이터 보강(한국어 제목/감독 보존) |
| `fix_watcha_korean.py` | 원어로 덮인 한국어 제목/감독 보정 |
| `backfill_original_source_tag.py` | `원작존재` 태그 백필 |

---

## 로컬 개발 실행

배포 없이 로컬에서만 돌릴 때.

```bash
git clone https://github.com/dayeonisme/personal-cinelog.git
cd personal-cinelog
pip3 install -r requirements.txt
export TMDB_ACCESS_TOKEN="발급받은_Read_Access_Token"   # 또는 export TMDB_API_KEY="..."
python app.py        # http://localhost:5001
```

TMDb 키 발급: [TMDb API 문서](https://developer.themoviedb.org/docs/getting-started) 에서 계정 생성 후 API Read Access Token(또는 v3 API Key) 발급. 영구 적용은 `~/.zshrc` 또는 `.env` 에 저장.

### (레거시) macOS 더블클릭 런처

> 이전 방식. 이제는 GCP 배포로 상시 접속하므로 **로컬 개발 편의용**으로만 둔다.

```bash
bash launcher/build.sh    # 저장소 루트에 Cinelog.app 생성
```

`Cinelog` 더블클릭 → 로컬 서버 켜짐(localhost:5001 자동 오픈) ↔ 다시 클릭 → 꺼짐. (`Cinelog.app` 은 빌드 산출물이라 git 에 미포함, `launcher/` 소스로 재생성.)

---

## 폴더 구조

```
personal-cinelog/
├── app.py                    # Flask 앱 & REST API (왓챠 동기화 트리거 포함)
├── models.py                 # SQLAlchemy 모델
├── database.py               # DB 초기화
├── requirements.txt
├── deploy/                   # GCP + Tailscale 배포 + 왓챠 자동 동기화
│   ├── README.md             # 배포 전체 절차 + 보안 체크리스트
│   ├── setup-vm.sh           # VM 셋업(venv·swap·systemd)
│   ├── cinelog.service       # gunicorn systemd 서비스(Tailscale IP 바인딩)
│   ├── push-data.sh          # Mac → VM 데이터(DB·이미지) 전송
│   ├── watcha-sync.sh        # 왓챠 동기화 파이프라인
│   ├── setup-watcha-sync.sh  # Chromium 설치 + 동기화 타이머·sudoers 등록
│   └── cinelog-watcha-sync.{service,timer}
├── tools/                    # 왓챠 수집·TMDb 보강·교정 스크립트
├── launcher/                 # (레거시) macOS 더블클릭 런처 소스
├── static/
│   ├── css/style.css
│   ├── js/app.js
│   └── uploads/              # 첨부 이미지 (gitignored)
└── templates/index.html
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

`Movie` 는 한국어 표시명(`title_ko`/`director_ko`)과 원어(`title_en`/`director_en`, 원제·원어 감독)를 함께 보관한다.

---

## 해시태그 정책

- 해시태그 이름에는 공백을 저장하지 않습니다. 예: `원작 존재` → `원작존재`
- `원작존재`
  - 새 항목 등록 시 TMDb `/movie/{id}/keywords` 를 조회해 자동 추가합니다.
  - `based on novel`, `based on book`, `based on comic`, `based on play or musical` 등 원작 존재를 뜻하는 키워드가 기준입니다.
  - TMDb 조회 실패 시 등록은 계속 진행하고 태그만 생략합니다.
  - 기존/가져온 항목은 `tools/backfill_original_source_tag.py` 로 백필합니다.
- `왓챠백업`
  - 왓챠에서 가져온 평가 항목 중 `RatingModule.name == "왓챠 별점"` 인 경우에만 유지합니다.
  - `보고싶어요` 항목에는 유지하지 않습니다.

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
| GET | `/api/templates/ratings` · `/api/templates/comments` | 커스텀 별점/코멘트명 목록 |
| POST | `/api/watcha/sync` | 왓챠 동기화 서비스 트리거(systemd, 비차단) |
| GET | `/api/watcha/sync/status` | 동기화 진행/결과 상태 |

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
| `.env`, `*.env` | TMDb 키 등 환경 변수 |
| `watcha_state.json` | 왓챠 세션(평문 쿠키) |
| `.watchapedia-browser/` | 왓챠 브라우저 프로필 |
| `AGENTS.md` | 로컬 에이전트 지침 |

> 배포 VM 의 `~/.cinelog-watcha.env`(왓챠 동기화 URL 등)는 레포 밖에 두며 `chmod 600` 으로 보호한다.

---

*개인 사용 목적. TMDb, IMDb, 왓챠와 무관합니다.*
