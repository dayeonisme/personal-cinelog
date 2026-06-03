import os
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory, render_template
from flask_cors import CORS
from database import db
from models import Movie, Entry, RatingModule, CommentModule, RatingTemplate, CommentTemplate
from werkzeug.utils import secure_filename

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OMDb API key – free tier from https://www.omdbapi.com/apikey.aspx
# Set via environment variable or replace the default below
OMDB_API_KEY = os.environ.get('OMDB_API_KEY', 'YOUR_FREE_OMDB_KEY')

app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(BASE_DIR, 'movies.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB upload limit
CORS(app)
db.init_app(app)

with app.app_context():
    db.create_all()


# ── Helpers ──────────────────────────────────────────────────────────────────
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Frontend ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/static/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)


# ── Movie Search (OMDb) ───────────────────────────────────────────────────────
@app.route('/api/search/movies')
def search_movies():
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify([])

    if OMDB_API_KEY == 'YOUR_FREE_OMDB_KEY':
        # Fallback: return empty with instructions
        return jsonify({'error': 'OMDb API 키가 설정되지 않았습니다. .env 파일에 OMDB_API_KEY를 설정해주세요.'}), 400

    try:
        resp = requests.get('https://www.omdbapi.com/', params={
            'apikey': OMDB_API_KEY,
            's': query,
            'type': 'movie',
        }, timeout=10)
        data = resp.json()
        if data.get('Response') == 'True':
            results = []
            for item in data.get('Search', []):
                results.append({
                    'imdb_id': item.get('imdbID'),
                    'title': item.get('Title'),
                    'year': item.get('Year'),
                    'poster_url': item.get('Poster') if item.get('Poster') != 'N/A' else None,
                })
            return jsonify(results)
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/movies/<imdb_id>')
def get_movie_detail(imdb_id):
    # Check local DB first
    movie = Movie.query.filter_by(imdb_id=imdb_id).first()
    if movie:
        return jsonify(movie.to_dict())

    if OMDB_API_KEY == 'YOUR_FREE_OMDB_KEY':
        return jsonify({'error': 'OMDb API 키 미설정'}), 400

    try:
        resp = requests.get('https://www.omdbapi.com/', params={
            'apikey': OMDB_API_KEY,
            'i': imdb_id,
            'plot': 'short',
        }, timeout=10)
        data = resp.json()
        if data.get('Response') == 'True':
            return jsonify({
                'imdb_id': data.get('imdbID'),
                'title': data.get('Title'),
                'year': data.get('Year'),
                'director': data.get('Director'),
                'actors': data.get('Actors'),
                'plot': data.get('Plot'),
                'poster_url': data.get('Poster') if data.get('Poster') != 'N/A' else None,
                'genre': data.get('Genre'),
                'runtime': data.get('Runtime'),
            })
        return jsonify({'error': '영화를 찾을 수 없습니다.'}), 404
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
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    q = Entry.query.join(Movie)

    if entry_type:
        q = q.filter(Entry.entry_type == entry_type)
    if watch_status:
        q = q.filter(Entry.watch_status == watch_status)

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
        'items': [e.to_dict() for e in entries],
    })


@app.route('/api/entries', methods=['POST'])
def create_entry():
    data = request.get_json()
    movie_data = data.get('movie', {})
    entry_type = data.get('entry_type', 'review')

    # Upsert movie
    movie = Movie.query.filter_by(imdb_id=movie_data.get('imdb_id')).first() if movie_data.get('imdb_id') else None
    if not movie:
        movie = Movie(
            imdb_id=movie_data.get('imdb_id'),
            title=movie_data.get('title', ''),
            year=movie_data.get('year'),
            director=movie_data.get('director'),
            actors=movie_data.get('actors'),
            plot=movie_data.get('plot'),
            poster_url=movie_data.get('poster_url'),
            genre=movie_data.get('genre'),
            runtime=movie_data.get('runtime'),
        )
        db.session.add(movie)
        db.session.flush()

    entry = Entry(
        movie_id=movie.id,
        entry_type=entry_type,
        watch_status=data.get('watch_status'),
    )
    db.session.add(entry)
    db.session.flush()

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
            name=c.get('name', '감상평'),
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
                name=c.get('name', '감상평'),
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
    app.run(debug=True, port=5001)
