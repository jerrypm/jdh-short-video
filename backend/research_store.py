"""Local research library; future/corrupt versions fail closed without overwriting."""

from .research_models import State


def read(connection):
    row = connection.execute("SELECT document FROM research WHERE id=1").fetchone()
    try:
        if not row or len(row[0].encode()) > 2 * 1024 * 1024:
            raise ValueError
        return State.model_validate_json(row[0])
    except ValueError as error:
        raise RuntimeError(
            "Pustaka riset tidak valid; file dipertahankan untuk pemulihan."
        ) from error


def write(connection, state):
    document = State.model_validate(state.model_dump()).model_dump_json()
    if len(document.encode()) > 2 * 1024 * 1024:
        raise ValueError("Pustaka riset penuh.")
    connection.execute("UPDATE research SET document=? WHERE id=1", (document,))
