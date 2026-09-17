"""Create a consistent SQLite snapshot, including committed WAL contents."""
import argparse
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_database(source, destination):
    source = Path(source).resolve()
    destination = Path(destination).resolve()
    if source == destination:
        raise ValueError('Source and destination must be different files')
    with closing(sqlite3.connect(f'{source.as_uri()}?mode=ro', uri=True)) as reader:
        with closing(sqlite3.connect(destination)) as writer:
            reader.backup(writer)
            # Make the snapshot self-contained for scp and file-based restores.
            writer.execute('PRAGMA journal_mode=DELETE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source')
    parser.add_argument('destination')
    args = parser.parse_args()
    backup_database(args.source, args.destination)
