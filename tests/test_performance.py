import gzip
import subprocess
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import brotli
import pytest
from flask import Flask

from app import app
from database import db


@pytest.mark.parametrize('path', [
    '/static/js/app.js?v=test',
    '/static/css/style.css?v=test',
    '/static/vendor/marked.min.js?v=test',
])
def test_versioned_assets_can_be_reused_without_revalidation(path):
    response = app.test_client().get(path)

    assert response.status_code == 200
    assert response.cache_control.public
    assert response.cache_control.max_age == 31536000
    assert not response.cache_control.no_cache


@pytest.mark.parametrize('path', ['/', '/static/js/app.js'])
def test_unversioned_responses_do_not_get_long_lived_cache(path):
    response = app.test_client().get(path)

    assert response.status_code == 200
    assert not response.cache_control.max_age


@pytest.mark.parametrize('path', ['/', '/static/js/app.js?v=test', '/static/css/style.css?v=test'])
@pytest.mark.parametrize('encoding,decode', [('gzip', gzip.decompress), ('br', brotli.decompress)])
def test_text_responses_are_compressed_when_requested(path, encoding, decode):
    client = app.test_client()
    plain = client.get(path, headers={'Accept-Encoding': 'identity'})
    compressed = client.get(path, headers={'Accept-Encoding': encoding})

    assert compressed.status_code == 200
    assert compressed.headers.get('Content-Encoding') == encoding
    assert 'Accept-Encoding' in compressed.vary
    assert decode(compressed.data) == plain.data
    assert len(compressed.data) < len(plain.data) * 0.5


def test_compressed_static_asset_supports_conditional_requests():
    client = app.test_client()
    first = client.get('/static/js/app.js?v=test', headers={'Accept-Encoding': 'gzip'})
    cached = client.get('/static/js/app.js?v=test', headers={
        'Accept-Encoding': 'gzip', 'If-None-Match': first.headers['ETag'],
    })

    assert cached.status_code == 304
    assert cached.data == b''
    assert cached.cache_control.max_age == 31536000


def test_static_range_is_not_compressed_as_a_complete_file():
    response = app.test_client().get('/static/js/app.js', headers={
        'Accept-Encoding': 'br, gzip', 'Range': 'bytes=0-1023',
    })

    assert response.status_code == 206
    assert len(response.data) == 1024
    assert 'Content-Encoding' not in response.headers


def test_json_responses_are_compressed_without_adding_cache(monkeypatch):
    # Exercise the real response hooks with a deterministic JSON payload.
    monkeypatch.setitem(app.view_functions, 'index', lambda: {'items': ['영화 기록'] * 200})
    client = app.test_client()
    plain = client.get('/', headers={'Accept-Encoding': 'identity'})
    compressed = client.get('/', headers={'Accept-Encoding': 'gzip'})

    assert compressed.mimetype == 'application/json'
    assert compressed.headers.get('Content-Encoding') == 'gzip'
    assert gzip.decompress(compressed.data) == plain.data
    assert not compressed.cache_control.max_age


def test_sqlite_reader_does_not_block_a_writer_commit(tmp_path):
    test_app = Flask(__name__)
    path = tmp_path / 'concurrent.db'
    test_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{path}'
    db.init_app(test_app)

    with test_app.app_context():
        with db.engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE records (value TEXT)')
            connection.exec_driver_sql("INSERT INTO records VALUES ('before')")

        # An independent sync process must inherit WAL and commit while a
        # request keeps its read snapshot open.
        with db.engine.connect() as reader, closing(sqlite3.connect(path, timeout=0.1)) as writer:
            assert reader.exec_driver_sql('PRAGMA journal_mode').scalar() == 'wal'
            assert writer.execute('PRAGMA journal_mode').fetchone()[0] == 'wal'
            reader.exec_driver_sql('BEGIN')
            assert reader.exec_driver_sql('SELECT value FROM records').scalar() == 'before'
            writer.execute("UPDATE records SET value = 'after'")
            writer.commit()
            assert reader.exec_driver_sql('SELECT value FROM records').scalar() == 'before'
            reader.rollback()
            assert reader.exec_driver_sql('SELECT value FROM records').scalar() == 'after'
        db.engine.dispose()


def test_backup_includes_committed_data_still_in_wal(tmp_path):
    source = tmp_path / 'source.db'
    target = tmp_path / 'snapshot.db'
    with closing(sqlite3.connect(source)) as connection:
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA wal_autocheckpoint=0')
        connection.execute('CREATE TABLE records (value TEXT)')
        connection.execute("INSERT INTO records VALUES ('in WAL')")
        connection.commit()
        assert source.with_suffix('.db-wal').stat().st_size > 0
        result = subprocess.run([
            sys.executable, str(Path(__file__).resolve().parents[1] / 'tools/backup_sqlite.py'),
            str(source), str(target),
        ], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr

    with closing(sqlite3.connect(target)) as snapshot:
        assert snapshot.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert snapshot.execute('SELECT value FROM records').fetchall() == [('in WAL',)]
