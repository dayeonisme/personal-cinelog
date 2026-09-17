import sqlite3

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, 'connect')
def enable_sqlite_wal(connection, _connection_record):
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        try:
            cursor.execute('PRAGMA journal_mode=WAL')
        finally:
            cursor.close()

db = SQLAlchemy()
