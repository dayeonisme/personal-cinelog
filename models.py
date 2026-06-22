from datetime import datetime
from database import db


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    imdb_id = db.Column(db.String(20), unique=True, nullable=True)
    tmdb_id = db.Column(db.String(20), nullable=True)
    title = db.Column(db.String(500), nullable=False)
    title_ko = db.Column(db.String(500))
    title_en = db.Column(db.String(500))
    year = db.Column(db.String(10))
    director = db.Column(db.String(500))
    director_ko = db.Column(db.String(500))
    director_en = db.Column(db.String(500))
    actors = db.Column(db.String(1000))
    plot = db.Column(db.Text)
    poster_url = db.Column(db.String(1000))
    genre = db.Column(db.String(500))
    runtime = db.Column(db.String(50))
    country = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship('Entry', backref='movie', lazy=True, cascade='all, delete-orphan')

    def to_dict(self, lang='ko'):
        title_ko = self.title_ko or self.title
        director_ko = self.director_ko or self.director
        title_en = self.title_en or self.title
        director_en = self.director_en or self.director
        display_title = title_en if lang == 'en' and title_en else title_ko
        display_director = director_en if lang == 'en' and director_en else director_ko

        return {
            'id': self.id,
            'imdb_id': self.imdb_id,
            'tmdb_id': self.tmdb_id,
            'title': display_title,
            'title_ko': title_ko,
            'title_en': title_en,
            'year': self.year,
            'director': display_director,
            'director_ko': director_ko,
            'director_en': director_en,
            'actors': self.actors,
            'plot': self.plot,
            'poster_url': self.poster_url,
            'genre': self.genre,
            'runtime': self.runtime,
            'country': self.country,
        }


entry_hashtags = db.Table(
    'entry_hashtags',
    db.Column('entry_id', db.Integer, db.ForeignKey('entries.id'), primary_key=True),
    db.Column('hashtag_id', db.Integer, db.ForeignKey('hashtags.id'), primary_key=True),
)


class Hashtag(db.Model):
    """평가/보고싶어요 공용 해시태그 (등록순으로 노출)"""
    __tablename__ = 'hashtags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}


class Entry(db.Model):
    """평가(review) 또는 보고싶어요(watchlist) 항목"""
    __tablename__ = 'entries'
    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey('movies.id'), nullable=False)
    entry_type = db.Column(db.String(20), nullable=False)  # 'review' | 'watchlist'
    watch_status = db.Column(db.String(20))  # 'completed' | 'in_progress' | 'stopped' (review only)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ratings = db.relationship('RatingModule', backref='entry', lazy=True,
                              cascade='all, delete-orphan', order_by='RatingModule.order')
    comments = db.relationship('CommentModule', backref='entry', lazy=True,
                               cascade='all, delete-orphan', order_by='CommentModule.order')
    hashtags = db.relationship('Hashtag', secondary=entry_hashtags, lazy='subquery',
                               order_by='Hashtag.id')

    def watchlist_kind(self):
        if self.entry_type != 'watchlist':
            return None
        has_review = Entry.query.filter(
            Entry.movie_id == self.movie_id,
            Entry.entry_type == 'review',
        ).first() is not None
        return 'rewatch' if has_review else 'wish'

    def to_dict(self, lang='ko', review_movie_ids=None):
        if review_movie_ids is None:
            watchlist_kind = self.watchlist_kind()
        elif self.entry_type != 'watchlist':
            watchlist_kind = None
        else:
            watchlist_kind = 'rewatch' if self.movie_id in review_movie_ids else 'wish'
        return {
            'id': self.id,
            'movie_id': self.movie_id,
            'movie': self.movie.to_dict(lang=lang),
            'entry_type': self.entry_type,
            'watch_status': self.watch_status,
            'watchlist_kind': watchlist_kind,
            'watchlist_label': '다시 보고싶어요' if watchlist_kind == 'rewatch' else ('보고싶어요' if watchlist_kind == 'wish' else None),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ratings': [r.to_dict() for r in self.ratings],
            'comments': [c.to_dict() for c in self.comments],
            'hashtags': [h.to_dict() for h in self.hashtags],
        }


class RatingModule(db.Model):
    __tablename__ = 'rating_modules'
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entries.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # '평점' or custom
    emoji = db.Column(db.String(10), default='⭐')
    value = db.Column(db.Float)  # 0~5, 0.5 step
    is_default = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'emoji': self.emoji,
            'value': self.value,
            'is_default': self.is_default,
            'order': self.order,
        }


class CommentModule(db.Model):
    __tablename__ = 'comment_modules'
    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey('entries.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)  # '감상평' or custom
    content = db.Column(db.Text)
    images = db.Column(db.Text)  # JSON array of image paths
    is_default = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)

    def to_dict(self):
        import json
        return {
            'id': self.id,
            'name': self.name,
            'content': self.content,
            'images': json.loads(self.images) if self.images else [],
            'is_default': self.is_default,
            'order': self.order,
        }


class RatingTemplate(db.Model):
    """사용자가 이전에 등록한 커스텀 별점 이름 목록"""
    __tablename__ = 'rating_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    emoji = db.Column(db.String(10), default='⭐')

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'emoji': self.emoji}


class CommentTemplate(db.Model):
    """사용자가 이전에 등록한 커스텀 코멘트 이름 목록"""
    __tablename__ = 'comment_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'name': self.name}
