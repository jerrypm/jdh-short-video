"""Bounded analytics snapshots in the same atomic transaction as idea invalidation."""

from .performance_models import State


def read(connection):
    row = connection.execute("SELECT document FROM performance WHERE id=1").fetchone()
    try:
        if not row or len(row[0].encode()) > 4 * 1024 * 1024:
            raise ValueError("Invalid size")
        return State.model_validate_json(row[0])
    except ValueError as error:
        raise RuntimeError(
            "Data performa tidak valid; file dipertahankan untuk pemulihan."
        ) from error


def write(connection, state):
    document = State.model_validate(state.model_dump()).model_dump_json()
    if len(document.encode()) > 4 * 1024 * 1024:
        raise ValueError("Penyimpanan performa penuh.")
    connection.execute("UPDATE performance SET document=? WHERE id=1", (document,))
