"""Column rules. Any board member manages columns — unlike board-level admin
(renaming/deleting the board, membership) which TASK-04 reserves to the owner.
Nothing here branches on actor.kind (CLAUDE.md §0)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import ConflictError, NotFoundError, ValidationError
from kanbai.models.actor import Actor
from kanbai.models.board_column import BoardColumn
from kanbai.repositories import boards as boards_repository
from kanbai.repositories import cards as cards_repository
from kanbai.repositories import columns as columns_repository
from kanbai.services import boards as boards_service

_COLUMN_NOT_FOUND_MESSAGE = "La columna solicitada no existe."
_DEFAULT_COLUMNS = ("Por hacer", "En curso", "Hecho")


async def seed_default_columns(session: AsyncSession, *, board_id: uuid.UUID) -> list[BoardColumn]:
    """Called by services.boards.create_board inside the same transaction: a board
    never exists, even for an instant observable from outside, without its
    starting columns. No lock needed here: the board row was just inserted in this
    same uncommitted transaction, so no concurrent request can see it yet."""
    columns = []
    for index, name in enumerate(_DEFAULT_COLUMNS, start=1):
        columns.append(
            await columns_repository.create_column(
                session,
                board_id=board_id,
                name=name,
                wip_limit=None,
                position=index * columns_repository.GAP,
            )
        )
    return columns


async def list_columns(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[BoardColumn], int]:
    await boards_service.get_board(session, actor=actor, board_id=board_id)  # 404 si ajeno
    return await columns_repository.list_columns_for_board(
        session, board_id, actor.id, limit=limit, offset=offset
    )


async def create_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, name: str, wip_limit: int | None
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    # Serializes concurrent creates on the same board: without this lock, two
    # requests can both read the same MAX(position) and collide at commit (the
    # unique constraint is deferred, so the collision surfaces late and ugly).
    await boards_repository.lock_board_for_update(session, board_id)
    current_max = await columns_repository.get_max_position(session, board_id)
    position = (current_max or 0.0) + columns_repository.GAP
    column = await columns_repository.create_column(
        session, board_id=board_id, name=name, wip_limit=wip_limit, position=position
    )
    await session.commit()
    return column


async def _get_column_or_404(
    session: AsyncSession, *, board_id: uuid.UUID, column_id: uuid.UUID, actor_id: uuid.UUID
) -> BoardColumn:
    column = await columns_repository.get_column_by_id(session, board_id, column_id, actor_id)
    if column is None:
        raise NotFoundError(_COLUMN_NOT_FOUND_MESSAGE)
    return column


async def get_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_id: uuid.UUID
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    return await _get_column_or_404(
        session, board_id=board_id, column_id=column_id, actor_id=actor.id
    )


async def update_column(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    name: str,
    wip_limit: int | None,
) -> BoardColumn:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    column = await _get_column_or_404(
        session, board_id=board_id, column_id=column_id, actor_id=actor.id
    )
    column = await columns_repository.update_column(session, column, name=name, wip_limit=wip_limit)
    await session.commit()
    return column


async def delete_column(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_id: uuid.UUID
) -> None:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    column = await _get_column_or_404(
        session, board_id=board_id, column_id=column_id, actor_id=actor.id
    )
    remaining = await columns_repository.count_columns_for_board(session, board_id)
    if remaining <= 1:
        raise ConflictError("No se puede borrar la última columna del tablero.")
    # The lock goes before the count (TASK-06): cards.column_id is ON DELETE
    # CASCADE, so a card created between counting and deleting would be wiped out
    # silently. Holding the column's row lock serializes this against
    # services/cards.py, which takes the same lock before adding to a column.
    if await columns_repository.lock_column_for_update(session, column_id) is None:
        raise NotFoundError(_COLUMN_NOT_FOUND_MESSAGE)  # borrada por otra transacción
    if await cards_repository.count_cards_in_column(session, column_id) > 0:
        raise ConflictError("No se puede borrar una columna con tarjetas.")
    await columns_repository.delete_column(session, column)
    await session.commit()


async def reorder_columns(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, column_ids: list[uuid.UUID]
) -> list[BoardColumn]:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    # Same lock as create_column: keeps a concurrent create from being read by
    # this reorder's snapshot and then silently dropped, or from landing on a
    # position this reorder is about to reuse.
    await boards_repository.lock_board_for_update(session, board_id)
    existing = await columns_repository.list_all_columns_for_board(session, board_id, actor.id)
    existing_ids = {column.id for column in existing}
    if len(column_ids) != len(set(column_ids)) or set(column_ids) != existing_ids:
        raise ValidationError(
            "La lista debe incluir, sin repetidos, exactamente las columnas actuales del tablero."
        )
    columns_by_id = {column.id: column for column in existing}
    await columns_repository.set_positions(session, columns_by_id, column_ids)
    await session.commit()
    return [columns_by_id[column_id] for column_id in column_ids]
