import os
import re
import json
import requests
import subprocess
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from database import db
from models import Movie, Entry, RatingModule, CommentModule, RatingTemplate, CommentTemplate, Hashtag
from werkzeug.utils import secure_filename

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def load_local_env():
    env_path = os.path.join(BASE_DIR, '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_local_env()

# TMDb API credentials. Prefer the v4 access token; v3 api_key also works.
TMDB_ACCESS_TOKEN = os.environ.get('TMDB_ACCESS_TOKEN')
TMDB_API_KEY = os.environ.get('TMDB_API_KEY')
TMDB_API_BASE = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE = 'https://image.tmdb.org/t/p/w342'

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'movies.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit
CORS(app)
db.init_app(app)


def ensure_movie_schema():
    columns = {
        row[1]
        for row in db.session.execute(db.text("PRAGMA table_info(movies)")).fetchall()
    }
    migrations = {
        'tmdb_id': "ALTER TABLE movies ADD COLUMN tmdb_id VARCHAR(20)",
        'title_ko': "ALTER TABLE movies ADD COLUMN title_ko VARCHAR(500)",
        'title_en': "ALTER TABLE movies ADD COLUMN title_en VARCHAR(500)",
        'director_ko': "ALTER TABLE movies ADD COLUMN director_ko VARCHAR(500)",
        'director_en': "ALTER TABLE movies ADD COLUMN director_en VARCHAR(500)",
        'country': "ALTER TABLE movies ADD COLUMN country VARCHAR(200)",
    }
    for column, statement in migrations.items():
        if column not in columns:
            db.session.execute(db.text(statement))
    db.session.commit()


with app.app_context():
    db.create_all()
    ensure_movie_schema()


# ── Helpers ──────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ORIGINAL_SOURCE_TAG_NAME = '원작존재'
ORIGINAL_SOURCE_KEYWORD_HINTS = [
    'based on novel',
    'based on book',
    'based on young adult novel',
    'based on short story',
    'based on graphic novel',
    'based on comic',
    'based on memoir or autobiography',
    'based on play or musical',
]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _tmdb_configured():
    return bool(TMDB_ACCESS_TOKEN or TMDB_API_KEY)


def _tmdb_headers():
    if TMDB_ACCESS_TOKEN:
        return {'Authorization': f'Bearer {TMDB_ACCESS_TOKEN}'}
    return {}


def _tmdb_params(params):
    merged = dict(params)
    if not TMDB_ACCESS_TOKEN and TMDB_API_KEY:
        merged['api_key'] = TMDB_API_KEY
    return merged


def _tmdb_keywords_indicate_original_source(keywords):
    names = [(k.get('name') or '').strip().lower() for k in keywords or []]
    return any(
        any(hint in name for hint in ORIGINAL_SOURCE_KEYWORD_HINTS)
        for name in names
    )


def _fetch_tmdb_keywords(tmdb_id):
    if not tmdb_id or not _tmdb_configured():
        return None
    resp = requests.get(
        f'{TMDB_API_BASE}/movie/{tmdb_id}/keywords',
        params=_tmdb_params({}),
        headers=_tmdb_headers(),
        timeout=10,
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    return data.get('keywords') or data.get('results') or []


def _movie_has_original_source(tmdb_id):
    try:
        keywords = _fetch_tmdb_keywords(tmdb_id)
    except Exception:
        return False
    if keywords is None:
        return False
    return _tmdb_keywords_indicate_original_source(keywords)


def _hashtags_with_original_source(names, movie):
    tag_names = list(names or [])
    if not app.config.get('AUTO_ORIGINAL_SOURCE_HASHTAG', True):
        return tag_names
    if movie and _movie_has_original_source(movie.tmdb_id):
        tag_names.append(ORIGINAL_SOURCE_TAG_NAME)
    return tag_names


def _tmdb_poster_url(path):
    return f'{TMDB_IMAGE_BASE}{path}' if path else None


def _release_year(release_date):
    return release_date[:4] if release_date else None


def _resolve_hashtags(names):
    """이름 목록을 받아 Hashtag 레코드 목록(등록순 유지, 신규는 생성)으로 변환"""
    tags = []
    seen = set()
    for raw in names or []:
        # 해시태그는 공백을 포함할 수 없음 — 모든 공백 문자를 제거
        name = re.sub(r'\s+', '', (raw or '').strip().lstrip('#'))
        if not name or name in seen:
            continue
        seen.add(name)
        tag = Hashtag.query.filter_by(name=name).first()
        if not tag:
            tag = Hashtag(name=name)
            db.session.add(tag)
            db.session.flush()
        tags.append(tag)
    return tags


def _default_comment_name(entry_type):
    return '보고싶은 이유' if entry_type == 'watchlist' else '감상평'


def _comment_name(raw_comment, entry_type):
    return raw_comment.get('name') or _default_comment_name(entry_type)


def _delete_watchlist_only_entries_before_review(movie_id):
    existing_review = Entry.query.filter_by(movie_id=movie_id, entry_type='review').first()
    if existing_review:
        return
    watchlist_entries = Entry.query.filter_by(movie_id=movie_id, entry_type='watchlist').all()
    for watchlist_entry in watchlist_entries:
        db.session.delete(watchlist_entry)


def _tmdb_search_result_to_movie(item):
    tmdb_id = item.get('id')
    title_ko = item.get('title') or item.get('original_title') or ''
    title_en = item.get('original_title') or title_ko
    return {
        'imdb_id': f'tmdb:{tmdb_id}',
        'title': title_ko,
        'title_ko': title_ko,
        'title_en': title_en,
        'year': _release_year(item.get('release_date')),
        'poster_url': _tmdb_poster_url(item.get('poster_path')),
    }


def _tmdb_detail_to_movie(data):
    credits = data.get('credits') or {}
    crew = credits.get('crew') or []
    cast = credits.get('cast') or []
    directors = [p.get('name') for p in crew if p.get('job') == 'Director' and p.get('name')]
    director_names_en = [
        p.get('original_name') or p.get('name')
        for p in crew
        if p.get('job') == 'Director' and (p.get('original_name') or p.get('name'))
    ]
    actors = [p.get('name') for p in cast[:5] if p.get('name')]
    genres = [g.get('name') for g in data.get('genres', []) if g.get('name')]
    runtime = data.get('runtime')
    countries = [c.get('name') for c in data.get('production_countries', []) if c.get('name')]
    external_ids = data.get('external_ids') or {}

    title_ko = data.get('title') or data.get('original_title') or ''
    title_en = data.get('original_title') or title_ko
    director_ko = ', '.join(directors)
    director_en = ', '.join(director_names_en) or director_ko

    return {
        'imdb_id': f"tmdb:{data.get('id')}",
        'tmdb_id': str(data.get('id')) if data.get('id') else None,
        'external_imdb_id': external_ids.get('imdb_id') or data.get('imdb_id'),
        'title': title_ko,
        'title_ko': title_ko,
        'title_en': title_en,
        'year': _release_year(data.get('release_date')),
        'director': director_ko,
        'director_ko': director_ko,
        'director_en': director_en,
        'actors': ', '.join(actors),
        'plot': data.get('overview'),
        'poster_url': _tmdb_poster_url(data.get('poster_path')),
        'genre': ', '.join(genres),
        'runtime': f"{runtime} min" if runtime else None,
        'country': ', '.join(countries) or None,
    }


# ── Frontend ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ── 왓챠 수동 동기화 (systemd 서비스 트리거) ──────────────────────────────────
WATCHA_SYNC_SERVICE = 'cinelog-watcha-sync.service'


def _systemctl(args):
    """systemctl 호출(읽기 전용은 sudo 불필요). 실패해도 예외 대신 결과 객체 반환."""
    try:
        return subprocess.run(
            ['systemctl', *args], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None


@app.route('/api/watcha/sync', methods=['POST'])
def start_watcha_sync():
    """버튼 → 동기화 서비스를 비차단으로 시작. 이미 실행 중이면 409.
    배포 환경에서만 동작(systemd + sudoers). 로컬/미배포면 503."""
    active = _systemctl(['is-active', WATCHA_SYNC_SERVICE])
    if active is None:
        return jsonify({'status': 'unavailable', 'detail': 'systemd 환경 아님'}), 503
    if active.stdout.strip() in ('active', 'activating'):
        return jsonify({'status': 'already_running'}), 409
    try:
        r = subprocess.run(
            ['sudo', '-n', 'systemctl', 'start', '--no-block', WATCHA_SYNC_SERVICE],
            capture_output=True, text=True, timeout=10,
        )
    except Exception as exc:
        return jsonify({'status': 'error', 'detail': str(exc)[:300]}), 500
    if r.returncode != 0:
        return jsonify({'status': 'error', 'detail': (r.stderr or r.stdout)[:300]}), 500
    return jsonify({'status': 'started'})


@app.route('/api/watcha/sync/status')
def watcha_sync_status():
    active = _systemctl(['is-active', WATCHA_SYNC_SERVICE])
    if active is None:
        return jsonify({'available': False, 'running': False})
    state = active.stdout.strip()
    props = {}
    show = _systemctl(['show', WATCHA_SYNC_SERVICE, '-p', 'Result', '-p', 'InactiveEnterTimestamp'])
    if show is not None:
        for line in show.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                props[key] = value
    return jsonify({
        'available': True,
        'running': state in ('active', 'activating'),
        'state': state,
        'result': props.get('Result', ''),
        'finished_at': props.get('InactiveEnterTimestamp', ''),
    })


# ── Movie Search (TMDb) ───────────────────────────────────────────────────────
@app.route('/api/search/movies')
def search_movies():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    if not _tmdb_configured():
        return jsonify({'error': 'TMDb API 키가 설정되지 않았습니다. TMDB_ACCESS_TOKEN 또는 TMDB_API_KEY를 설정해주세요.'}), 400

    try:
        resp = requests.get(
            f'{TMDB_API_BASE}/search/movie',
            params=_tmdb_params({
                'query': query,
                'language': 'ko-KR',
                'region': 'KR',
                'include_adult': 'false',
                'page': 1,
            }),
            headers=_tmdb_headers(),
            timeout=10,
        )
        data = resp.json()
        return jsonify([_tmdb_search_result_to_movie(item) for item in data.get('results', [])])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/movies/<movie_key>')
def get_movie_detail(movie_key):
    # Check local DB first
    movie = Movie.query.filter_by(imdb_id=movie_key).first()
    if movie:
        return jsonify(movie.to_dict())

    if not movie_key.startswith('tmdb:'):
        return jsonify({'error': '지원하지 않는 영화 ID입니다.'}), 400

    if not _tmdb_configured():
        return jsonify({'error': 'TMDb API 키 미설정'}), 400

    try:
        tmdb_id = movie_key.split(':', 1)[1]
        resp = requests.get(
            f'{TMDB_API_BASE}/movie/{tmdb_id}',
            params=_tmdb_params({
                'language': 'ko-KR',
                'append_to_response': 'credits,external_ids',
            }),
            headers=_tmdb_headers(),
            timeout=10,
        )
        data = resp.json()
        if data.get('success') is False:
            return jsonify({'error': data.get('status_message', '영화를 찾을 수 없습니다.')}), 404
        return jsonify(_tmdb_detail_to_movie(data))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Entries ───────────────────────────────────────────────────────────────────
@app.route('/api/entries', methods=['GET'])
def list_entries():
    entry_type = request.args.get('type')  # 'review' | 'watchlist' | None
    sort = request.args.get('sort', 'newest')
    watch_status = request.args.get('watch_status')
    search = request.args.get('search', '').strip()
    search_field = request.args.get('search_field', 'all')
    watchlist_kind = request.args.get('watchlist_kind')
    scope = request.args.get('scope')
    lang = request.args.get('lang', 'ko')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    q = Entry.query.join(Movie)

    if entry_type:
        q = q.filter(Entry.entry_type == entry_type)
    if watch_status:
        q = q.filter(Entry.watch_status == watch_status)

    from sqlalchemy.orm import aliased
    ReviewEntry = aliased(Entry)
    review_exists = db.session.query(ReviewEntry.id).filter(
        ReviewEntry.movie_id == Movie.id,
        ReviewEntry.entry_type == 'review',
    ).exists()

    if scope == 'home':
        from sqlalchemy import or_
        q = q.filter(or_(Entry.entry_type != 'watchlist', ~review_exists))

    if entry_type == 'watchlist' and watchlist_kind in {'wish', 'rewatch'}:
        q = q.filter(review_exists if watchlist_kind == 'rewatch' else ~review_exists)

    if search:
        if search_field == 'title':
            q = q.filter(Movie.title.ilike(f'%{search}%'))
        elif search_field == 'director':
            q = q.filter(Movie.director.ilike(f'%{search}%'))
        elif search_field == 'actor':
            q = q.filter(Movie.actors.ilike(f'%{search}%'))
        elif search_field == 'rating_name':
            q = q.join(RatingModule).filter(RatingModule.name.ilike(f'%{search}%'))
        elif search_field == 'comment_name':
            q = q.join(CommentModule).filter(CommentModule.name.ilike(f'%{search}%'))
        elif search_field == 'hashtag':
            q = q.join(Entry.hashtags).filter(Hashtag.name.ilike(f'%{search}%'))
        else:  # all
            from sqlalchemy import or_
            q = q.filter(or_(
                Movie.title.ilike(f'%{search}%'),
                Movie.director.ilike(f'%{search}%'),
                Movie.actors.ilike(f'%{search}%'),
            ))

    if sort == 'newest':
        q = q.order_by(Entry.created_at.desc())
    elif sort == 'oldest':
        q = q.order_by(Entry.created_at.asc())
    elif sort == 'rating_high':
        # Sort by default rating value desc
        from sqlalchemy import desc
        q = q.outerjoin(RatingModule, (RatingModule.entry_id == Entry.id) & (RatingModule.is_default == True))
        q = q.order_by(desc(RatingModule.value))
    elif sort == 'rating_low':
        q = q.outerjoin(RatingModule, (RatingModule.entry_id == Entry.id) & (RatingModule.is_default == True))
        q = q.order_by(RatingModule.value)
    else:
        q = q.order_by(Entry.created_at.desc())

    total = q.count()
    entries = q.offset((page - 1) * per_page).limit(per_page).all()
    return jsonify({
        'total': total,
        'page': page,
        'per_page': per_page,
        'items': [e.to_dict(lang=lang) for e in entries],
    })


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.get_json()
    movie_data = data.get('movie', {})
    entry_type = data.get('entry_type', 'review')

    # Upsert movie — imdb_id로 우선 매칭하고, 못 찾으면 tmdb_id로도 매칭한다.
    # (왓챠 마이그레이션 데이터는 imdb_id에 'watcha:...' 형식을 쓰고, 직접 검색해
    #  등록할 때는 'tmdb:...' 형식을 쓰는 등 같은 영화라도 imdb_id 표기가 달라질 수
    #  있어 이것만으로 매칭하면 동일 영화가 중복 생성될 수 있다. tmdb_id는 두 경로
    #  모두에서 동일하게 채워지므로 보조 매칭 키로 사용한다.)
    incoming_imdb_id = movie_data.get('imdb_id')
    incoming_tmdb_id = movie_data.get('tmdb_id') or (
        incoming_imdb_id.split(':', 1)[1]
        if incoming_imdb_id and incoming_imdb_id.startswith('tmdb:')
        else None
    )
    if incoming_tmdb_id is not None:
        incoming_tmdb_id = str(incoming_tmdb_id)

    movie = None
    if incoming_imdb_id:
        movie = Movie.query.filter_by(imdb_id=incoming_imdb_id).first()
    if not movie and incoming_tmdb_id:
        movie = Movie.query.filter_by(tmdb_id=incoming_tmdb_id).first()

    if not movie:
        movie = Movie(
            imdb_id=incoming_imdb_id,
            tmdb_id=incoming_tmdb_id,
            title=movie_data.get('title', ''),
            title_ko=movie_data.get('title_ko') or movie_data.get('title', ''),
            title_en=movie_data.get('title_en') or movie_data.get('title', ''),
            year=movie_data.get('year'),
            director=movie_data.get('director'),
            director_ko=movie_data.get('director_ko') or movie_data.get('director'),
            director_en=movie_data.get('director_en') or movie_data.get('director'),
            actors=movie_data.get('actors'),
            plot=movie_data.get('plot'),
            poster_url=movie_data.get('poster_url'),
            genre=movie_data.get('genre'),
            runtime=movie_data.get('runtime'),
            country=movie_data.get('country'),
        )
        db.session.add(movie)
        db.session.flush()

    if entry_type == 'review':
        _delete_watchlist_only_entries_before_review(movie.id)

    entry = Entry(
        movie_id=movie.id,
        entry_type=entry_type,
        watch_status=data.get('watch_status'),
    )
    db.session.add(entry)
    db.session.flush()

    entry.hashtags = _resolve_hashtags(_hashtags_with_original_source(data.get('hashtags', []), movie))

    # Ratings
    for i, r in enumerate(data.get('ratings', [])):
        rm = RatingModule(
            entry_id=entry.id,
            name=r.get('name', '평점'),
            emoji=r.get('emoji', '⭐'),
            value=r.get('value'),
            is_default=r.get('is_default', False),
            order=i,
        )
        db.session.add(rm)
        # Save template for custom ratings
        if not r.get('is_default') and r.get('name'):
            _upsert_rating_template(r['name'], r.get('emoji', '⭐'))

    # Comments
    for i, c in enumerate(data.get('comments', [])):
        cm = CommentModule(
            entry_id=entry.id,
            name=_comment_name(c, entry_type),
            content=c.get('content', ''),
            images=json.dumps(c.get('images', [])),
            is_default=c.get('is_default', False),
            order=i,
        )
        db.session.add(cm)
        if not c.get('is_default') and c.get('name'):
            _upsert_comment_template(c['name'])

    db.session.commit()
    return jsonify(entry.to_dict()), 201


@app.route('/api/entries/<int:entry_id>', methods=['GET'])
def get_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    return jsonify(entry.to_dict())


@app.route('/api/entries/<int:entry_id>', methods=['PUT'])
def update_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    data = request.get_json()

    entry.watch_status = data.get('watch_status', entry.watch_status)
    entry.updated_at = datetime.utcnow()

    if 'hashtags' in data:
        entry.hashtags = _resolve_hashtags(data.get('hashtags', []))

    # Replace ratings
    if 'ratings' in data:
        RatingModule.query.filter_by(entry_id=entry.id).delete()
        for i, r in enumerate(data['ratings']):
            rm = RatingModule(
                entry_id=entry.id,
                name=r.get('name', '평점'),
                emoji=r.get('emoji', '⭐'),
                value=r.get('value'),
                is_default=r.get('is_default', False),
                order=i,
            )
            db.session.add(rm)
            if not r.get('is_default') and r.get('name'):
                _upsert_rating_template(r['name'], r.get('emoji', '⭐'))

    # Replace comments
    if 'comments' in data:
        CommentModule.query.filter_by(entry_id=entry.id).delete()
        for i, c in enumerate(data['comments']):
            cm = CommentModule(
                entry_id=entry.id,
                name=_comment_name(c, entry.entry_type),
                content=c.get('content', ''),
                images=json.dumps(c.get('images', [])),
                is_default=c.get('is_default', False),
                order=i,
            )
            db.session.add(cm)
            if not c.get('is_default') and c.get('name'):
                _upsert_comment_template(c['name'])

    db.session.commit()
    return jsonify(entry.to_dict())


@app.route('/api/entries/<int:entry_id>', methods=['DELETE'])
def delete_entry(entry_id):
    entry = Entry.query.get_or_404(entry_id)
    db.session.delete(entry)
    db.session.commit()
    return jsonify({'ok': True})


# ── Hashtags ──────────────────────────────────────────────────────────────────
@app.route('/api/hashtags')
def list_hashtags():
    tags = Hashtag.query.order_by(Hashtag.id.asc()).all()
    return jsonify([t.to_dict() for t in tags])


# ── Movie Detail Page ─────────────────────────────────────────────────────────
@app.route('/api/movies/<int:movie_id>')
def get_movie(movie_id):
    movie = Movie.query.get_or_404(movie_id)
    lang = request.args.get('lang', 'ko')
    review = Entry.query.filter_by(movie_id=movie.id, entry_type='review').order_by(Entry.created_at.desc()).first()
    watchlist = Entry.query.filter_by(movie_id=movie.id, entry_type='watchlist').order_by(Entry.created_at.desc()).first()
    return jsonify({
        'movie': movie.to_dict(lang=lang),
        'review': review.to_dict(lang=lang) if review else None,
        'watchlist': watchlist.to_dict(lang=lang) if watchlist else None,
    })


# ── Image Upload ──────────────────────────────────────────────────────────────
@app.route('/api/upload', methods=['POST'])
def upload_image():
    if 'file' not in request.files:
        return jsonify({'error': '파일이 없습니다.'}), 400
    file = request.files['file']
    if file.filename == '' or not allowed_file(file.filename):
        return jsonify({'error': '허용되지 않는 파일 형식입니다.'}), 400
    filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{file.filename}")
    file.save(os.path.join(UPLOAD_FOLDER, filename))
    return jsonify({'url': f'/static/uploads/{filename}'})


# ── Templates ─────────────────────────────────────────────────────────────────
@app.route('/api/templates/ratings')
def list_rating_templates():
    return jsonify([t.to_dict() for t in RatingTemplate.query.all()])

@app.route('/api/templates/comments')
def list_comment_templates():
    return jsonify([t.to_dict() for t in CommentTemplate.query.all()])


def _upsert_rating_template(name, emoji):
    t = RatingTemplate.query.filter_by(name=name).first()
    if not t:
        db.session.add(RatingTemplate(name=name, emoji=emoji))

def _upsert_comment_template(name):
    t = CommentTemplate.query.filter_by(name=name).first()
    if not t:
        db.session.add(CommentTemplate(name=name))


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    # HOST=0.0.0.0 으로 실행하면 같은 와이파이의 다른 기기(휴대폰 등)에서도 접속 가능합니다.
    host = os.environ.get('HOST', '127.0.0.1')
    port = int(os.environ.get('PORT', '5001'))
    debug = os.environ.get('FLASK_DEBUG', '1') == '1'
    app.run(host=host, port=port, debug=debug)
