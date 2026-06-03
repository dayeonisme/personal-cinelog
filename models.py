from datetime import datetime
from database import db


class Movie(db.Model):
    __tablename__ = 'movies'
    id = db.Column(db.Integer, primary_key=True)
    imdb_id = db.Column(db.String(20), unique=True, nullable=True)
    title = db.Column(db.String(500), nullable=False)
    year = db.Column(db.String(10))
    director = db.Column(db.String(500))
    actors = db.Column(db.String(1000))
    plot = db.Column(db.Text)
    poster_url = db.Column(db.String(1000))
    genre = db.Column(db.String(500))
    runtime = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    entries = db.relationship('Entry', backref='movie', lazy=True, cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'imdb_id': self.imdb_id,
            'title': self.title,
            'year': self.year,
            'director': self.director,
            'actors': self.actors,
            'plot': self.plot,
            'poster_url': self.poster_url,
            'genre': self.genre,
            'runtime': self.runtime,
        }


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

    def to_dict(self):
        return {
            'id': self.id,
            'movie_id': self.movie_id,
            'movie': self.movie.to_dict(),
            'entry_type': self.entry_type,
            'watch_status': self.watch_status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'ratings': [r.to_dict() for r in self.ratings],
            'comments': [c.to_dict() for c in self.comments],
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
