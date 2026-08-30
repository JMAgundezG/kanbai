"""Queries on board columns. The only place that talks SQL for this table."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.board_column import BoardColumn
from kanbai.repositories.membership import board_ids_for_actor

# Spacing left between two adjacent positions on append, so a future insert between
# them has room for a plain midpoint without immediately needing a full reindex.
# TASK-06 reuses this exact value for cards.position.
GAP = 1024.0


async def list_columns_for_board(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[BoardColumn], int]:
    """Filters by board_ids_for_actor in addition to board_id: the actual 404 for
    an unrelated board is still services.boards.get_board (an empty list alone
    cannot distinguish "not a member" from "a member of an empty board"), but every
    query here still scopes ownership in SQL itself, never in Python, per
    CLAUDE.md §4."""
    membership_filter = BoardColumn.board_id.in_(board_ids_for_actor(actor_id))
    total = await session.scalar(
        select(func.count())
        .select_from(BoardColumn)
        .where(BoardColumn.board_id == board_id, membership_filter)
    )
    result = await session.execute(
        select(BoardColumn)
        .where(BoardColumn.board_id == board_id, membership_filter)
        .order_by(BoardColumn.position)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def list_all_columns_for_board(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID
) -> list[BoardColumn]:
    """Unpaginated: the reorder endpoint needs every column in one shot to
    validate the incoming id set against it."""
    result = await session.execute(
        select(BoardColumn)
        .where(
            BoardColumn.board_id == board_id,
            BoardColumn.board_id.in_(board_ids_for_actor(actor_id)),
        )
        .order_by(BoardColumn.position)
    )
    return list(result.scalars().all())


async def count_columns_for_board(session: AsyncSession, board_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count()).select_from(BoardColumn).where(BoardColumn.board_id == board_id)
    )
    return total or 0


async def get_column_by_id(
    session: AsyncSession, board_id: uuid.UUID, column_id: uuid.UUID, actor_id: uuid.UUID
) -> BoardColumn | None:
    """Scoped by board_ids_for_actor too, not just board_id: ownership must be
    filtered in the query itself (CLAUDE.md §4), not left as a convention the
    caller has to remember to enforce upstream."""
    result = await session.execute(
        select(BoardColumn).where(
            BoardColumn.board_id == board_id,
            BoardColumn.id == column_id,
            BoardColumn.board_id.in_(board_ids_for_actor(actor_id)),
        )
    )
    return result.scalar_one_or_none()


async def get_max_position(session: AsyncSession, board_id: uuid.UUID) -> float | None:
    result = await session.scalar(
        select(func.max(BoardColumn.position)).where(BoardColumn.board_id == board_id)
    )
    return float(result) if result is not None else None


async def create_column(
    session: AsyncSession,
    *,
    board_id: uuid.UUID,
    name: str,
    wip_limit: int | None,
    position: float,
) -> BoardColumn:
    column = BoardColumn(board_id=board_id, name=name, wip_limit=wip_limit, position=position)
    session.add(column)
    await session.flush()
    return column


async def update_column(
    session: AsyncSession, column: BoardColumn, *, name: str, wip_limit: int | None
) -> BoardColumn:
    column.name = name
    column.wip_limit = wip_limit
    await session.flush()
    return column


async def delete_column(session: AsyncSession, column: BoardColumn) -> None:
    await session.delete(column)


async def set_positions(
    session: AsyncSession,
    columns_by_id: dict[uuid.UUID, BoardColumn],
    ordered_ids: list[uuid.UUID],
) -> None:
    """One UPDATE per row, all inside the caller's transaction. Safe against the
    deferrable unique constraint colliding mid-transaction because the constraint
    is DEFERRABLE INITIALLY DEFERRED — PostgreSQL only checks uniqueness at COMMIT,
    so it does not matter that row 2's new value might momentarily equal row 5's
    old value.

    Positions land on multiples of GAP (0, GAP, 2*GAP, ...), not bare 0..N-1: a
    reorder still yields no gaps and no duplicates in *rank* (there's exactly one
    column at each successive rank), but collapsing to bare integers would destroy
    the midpoint room the float scheme exists to preserve for the next insert-
    between — the exact thing TASK-06 needs when it copies this mechanism for
    cards.position.
    """
    for index, column_id in enumerate(ordered_ids):
        columns_by_id[column_id].position = float(index) * GAP
    await session.flush()
