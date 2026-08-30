"""Queries on cards. The only place that talks SQL for this table.

Positions reuse TASK-05's scheme: `GAP` is imported from repositories/columns.py
rather than redefined, so the two tables cannot drift apart.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.board_column import BoardColumn
from kanbai.models.card import Card
from kanbai.repositories.columns import GAP
from kanbai.repositories.membership import board_ids_for_actor

__all__ = [
    "GAP",
    "count_cards_in_column",
    "create_card",
    "delete_card",
    "get_card_by_id",
    "get_max_position",
    "list_cards_for_board",
    "list_positions_in_column",
    "lock_card_for_update",
    "renumber_column",
    "set_placement",
    "update_card",
]


async def list_cards_for_board(
    session: AsyncSession,
    board_id: uuid.UUID,
    actor_id: uuid.UUID,
    *,
    column_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Card], int]:
    """Ordered by (column position, card position) — the order the board is drawn
    in, not an arbitrary one. Membership is filtered in SQL through
    board_ids_for_actor, like every other query in this module."""
    filters = [Card.board_id == board_id, Card.board_id.in_(board_ids_for_actor(actor_id))]
    if column_id is not None:
        filters.append(Card.column_id == column_id)

    total = await session.scalar(select(func.count()).select_from(Card).where(*filters))
    result = await session.execute(
        select(Card)
        .join(BoardColumn, BoardColumn.id == Card.column_id)
        .where(*filters)
        .order_by(BoardColumn.position, Card.position)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_card_by_id(
    session: AsyncSession, board_id: uuid.UUID, card_id: uuid.UUID, actor_id: uuid.UUID
) -> Card | None:
    """Scoped by board_ids_for_actor as well as by board_id: ownership belongs in
    the query itself (CLAUDE.md § 4), not in a convention the caller has to
    remember."""
    result = await session.execute(
        select(Card).where(
            Card.board_id == board_id,
            Card.id == card_id,
            Card.board_id.in_(board_ids_for_actor(actor_id)),
        )
    )
    return result.scalar_one_or_none()


async def lock_card_for_update(session: AsyncSession, card_id: uuid.UUID) -> Card | None:
    """Row-level lock on the card being moved, held until the caller's transaction
    ends, returning the card as it stands once the lock is held.

    `populate_existing` matters as much as the lock: it refreshes what the caller
    read before waiting, so the move decides on the card's *current* column rather
    than on one another transaction has already changed — and the ORM then emits
    the UPDATE it would have skipped if its cached value happened to match the new
    one. None when the row is gone, which the caller turns into a clean 404 instead
    of a StaleDataError (500) from an UPDATE that matches no row.

    Always taken *after* the destination column's lock: that single global ordering
    (column, then card) is what rules out deadlocks.
    """
    result = await session.execute(
        select(Card)
        .where(Card.id == card_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def count_cards_in_column(session: AsyncSession, column_id: uuid.UUID) -> int:
    """No membership filter: it returns a bare count, exposing no data, and both
    callers (the WIP check and the 409 on deleting a column) have already resolved
    membership against that column."""
    total = await session.scalar(
        select(func.count()).select_from(Card).where(Card.column_id == column_id)
    )
    return total or 0


async def list_positions_in_column(
    session: AsyncSession, column_id: uuid.UUID, *, exclude_card_id: uuid.UUID | None = None
) -> list[float]:
    """The column's positions in order, optionally without the card being moved —
    a card must not count as its own neighbour when it moves inside its column.
    No membership filter, same reasoning as count_cards_in_column: anonymous
    floats, and the caller has already authorized the column."""
    query = select(Card.position).where(Card.column_id == column_id)
    if exclude_card_id is not None:
        query = query.where(Card.id != exclude_card_id)
    result = await session.execute(query.order_by(Card.position))
    return [float(position) for position in result.scalars().all()]


async def get_max_position(session: AsyncSession, column_id: uuid.UUID) -> float | None:
    result = await session.scalar(
        select(func.max(Card.position)).where(Card.column_id == column_id)
    )
    return float(result) if result is not None else None


async def create_card(
    session: AsyncSession,
    *,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    title: str,
    description: str | None,
    position: float,
    created_by_actor_id: uuid.UUID,
) -> Card:
    card = Card(
        board_id=board_id,
        column_id=column_id,
        title=title,
        description=description,
        position=position,
        created_by_actor_id=created_by_actor_id,
    )
    session.add(card)
    await session.flush()
    return card


async def update_card(
    session: AsyncSession, card: Card, *, title: str, description: str | None
) -> Card:
    card.title = title
    card.description = description
    await session.flush()
    return card


async def delete_card(session: AsyncSession, card: Card) -> None:
    await session.delete(card)


async def set_placement(
    session: AsyncSession, card: Card, *, column_id: uuid.UUID, position: float
) -> Card:
    """The move itself: one UPDATE, one row. No other card is rewritten — that is
    the whole point of float positions with a gap (spec-TASK-05), and what lets two
    moves into different columns run without touching each other."""
    card.column_id = column_id
    card.position = position
    await session.flush()
    return card


async def renumber_column(session: AsyncSession, column_id: uuid.UUID) -> None:
    """Respread a column's cards over 0, GAP, 2*GAP, … keeping their current order.

    Only used when repeated midpoint inserts between the same two neighbours have
    eaten the float's precision. Rewriting several rows at once is safe here for
    exactly the reason the unique constraint is DEFERRABLE INITIALLY DEFERRED:
    PostgreSQL checks uniqueness at COMMIT, so a row may momentarily hold the value
    another row of the same batch has not released yet. The caller holds the
    column's lock, so nobody else is writing these rows meanwhile.
    """
    result = await session.execute(
        select(Card).where(Card.column_id == column_id).order_by(Card.position)
    )
    for index, card in enumerate(result.scalars().all()):
        card.position = float(index) * GAP
    await session.flush()
