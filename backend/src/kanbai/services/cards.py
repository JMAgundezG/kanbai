"""Card rules, including the move — the central operation of the product.

Any board member manages cards, exactly like columns (TASK-05); no route or rule
here reads `actor.kind`. The creator is recorded as `created_by_actor_id`, which
works the same for a person and for an agent (CLAUDE.md § 0).

**How the move stays atomic.** Both invariants a move can break belong to the
*destination column*: `UNIQUE (column_id, position)` and the column's `wip_limit`.
So every operation that reads a column's contents in order to write into it first
takes that column's row lock (`columns_repository.lock_column_for_update`) and
holds it until commit. Under READ COMMITTED, whoever waited on the lock re-reads
afterwards and sees the other transaction's committed rows, so the neighbour
positions and the card count it works from are never stale: two simultaneous moves
into one column cannot compute the same position, and cannot both slip into the
last WIP slot. The write itself stays a single-row UPDATE.

**Lock ordering, globally: column, then card, and never two columns in one
transaction.** No cycle is possible, so there are no deadlocks.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import ConflictError, NotFoundError
from kanbai.models.actor import Actor
from kanbai.models.board_column import BoardColumn
from kanbai.models.card import Card
from kanbai.repositories import cards as cards_repository
from kanbai.repositories import columns as columns_repository
from kanbai.services import boards as boards_service

_CARD_NOT_FOUND_MESSAGE = "La tarjeta solicitada no existe."
_COLUMN_NOT_FOUND_MESSAGE = "La columna de destino no existe."


async def _get_card_or_404(
    session: AsyncSession, *, board_id: uuid.UUID, card_id: uuid.UUID, actor_id: uuid.UUID
) -> Card:
    card = await cards_repository.get_card_by_id(session, board_id, card_id, actor_id)
    if card is None:
        raise NotFoundError(_CARD_NOT_FOUND_MESSAGE)
    return card


async def _get_destination_column_or_404(
    session: AsyncSession, *, board_id: uuid.UUID, column_id: uuid.UUID, actor_id: uuid.UUID
) -> BoardColumn:
    """Filtering by board_id here is also what keeps `Card.board_id` consistent
    with `Card.column_id`: a column of another board simply cannot be reached."""
    column = await columns_repository.get_column_by_id(session, board_id, column_id, actor_id)
    if column is None:
        raise NotFoundError(_COLUMN_NOT_FOUND_MESSAGE)
    return column


async def _lock_destination_column_or_404(
    session: AsyncSession, *, column_id: uuid.UUID
) -> BoardColumn:
    """The lock, plus the column as it stands once it is held. Membership is
    already resolved by _get_destination_column_or_404 before this is called; what
    this adds is freshness — the `wip_limit` applied is the one in effect after
    waiting, not the one read before — and a clean 404 if the column was deleted
    while we waited, instead of a foreign key violation at flush time."""
    column = await columns_repository.lock_column_for_update(session, column_id)
    if column is None:
        raise NotFoundError(_COLUMN_NOT_FOUND_MESSAGE)
    return column


async def _reject_if_wip_limit_reached(session: AsyncSession, column: BoardColumn) -> None:
    """Must be called with the column's row already locked: that is what stops the
    count from going stale between this check and the write that follows it."""
    if column.wip_limit is None:
        return
    count = await cards_repository.count_cards_in_column(session, column.id)
    if count >= column.wip_limit:
        raise ConflictError(
            f"No se pueden añadir más tarjetas a «{column.name}»: "
            f"ha alcanzado su límite de {column.wip_limit} tarjetas."
        )


async def _position_at_index(
    session: AsyncSession, *, column_id: uuid.UUID, index: int, exclude_card_id: uuid.UUID | None
) -> float:
    """The float position for a desired 0-based index in an already locked column.

    `index` is clamped to the column's real size: a client's view can legitimately
    be stale (someone just emptied that column), and refusing something with an
    obvious right answer would only force a reload. Negative indexes never reach
    here — `CardMove.position` rejects them with 422.
    """
    positions = await cards_repository.list_positions_in_column(
        session, column_id, exclude_card_id=exclude_card_id
    )
    target = min(index, len(positions))

    if not positions:
        return cards_repository.GAP
    if target == 0:
        return positions[0] - cards_repository.GAP
    if target == len(positions):
        return positions[-1] + cards_repository.GAP

    before, after = positions[target - 1], positions[target]
    midpoint = (before + after) / 2
    if before < midpoint < after:
        return midpoint

    # Repeated inserts between the same two neighbours have exhausted the float's
    # precision: there is no representable value left between them. Respread the
    # whole column (safe here — the unique constraint is deferred and this
    # transaction holds the column's lock) and compute again over the new values.
    await cards_repository.renumber_column(session, column_id)
    positions = await cards_repository.list_positions_in_column(
        session, column_id, exclude_card_id=exclude_card_id
    )
    # `target` is still a strict interior index (the head and tail cases returned
    # above) and respreading changes no card's rank, so there is a neighbour on
    # each side and now a wide gap between them.
    return (positions[target - 1] + positions[target]) / 2


async def list_cards(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    column_id: uuid.UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[Card], int]:
    await boards_service.get_board(session, actor=actor, board_id=board_id)  # 404 si ajeno
    return await cards_repository.list_cards_for_board(
        session, board_id, actor.id, column_id=column_id, limit=limit, offset=offset
    )


async def get_card(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, card_id: uuid.UUID
) -> Card:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    return await _get_card_or_404(session, board_id=board_id, card_id=card_id, actor_id=actor.id)


async def create_card(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    title: str,
    description: str | None,
) -> Card:
    """The card lands at the end of its column. The WIP limit is enforced here too,
    not only on moves: a limit that can be sidestepped by creating the card
    straight into a full column is not a limit."""
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    await _get_destination_column_or_404(
        session, board_id=board_id, column_id=column_id, actor_id=actor.id
    )
    column = await _lock_destination_column_or_404(session, column_id=column_id)
    await _reject_if_wip_limit_reached(session, column)
    current_max = await cards_repository.get_max_position(session, column_id)
    position = (current_max or 0.0) + cards_repository.GAP
    card = await cards_repository.create_card(
        session,
        board_id=board_id,
        column_id=column_id,
        title=title,
        description=description,
        position=position,
        created_by_actor_id=actor.id,
    )
    await session.commit()
    return card


async def update_card(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    card_id: uuid.UUID,
    title: str,
    description: str | None,
) -> Card:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    card = await _get_card_or_404(session, board_id=board_id, card_id=card_id, actor_id=actor.id)
    card = await cards_repository.update_card(session, card, title=title, description=description)
    await session.commit()
    return card


async def delete_card(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, card_id: uuid.UUID
) -> None:
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    card = await _get_card_or_404(session, board_id=board_id, card_id=card_id, actor_id=actor.id)
    await cards_repository.delete_card(session, card)
    await session.commit()


async def move_card(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    card_id: uuid.UUID,
    column_id: uuid.UUID,
    position: int,
) -> Card:
    """Destination column plus destination index, resolved in one transaction that
    holds the destination column's row lock (see the module docstring)."""
    await boards_service.get_board(session, actor=actor, board_id=board_id)
    card = await _get_card_or_404(session, board_id=board_id, card_id=card_id, actor_id=actor.id)
    await _get_destination_column_or_404(
        session, board_id=board_id, column_id=column_id, actor_id=actor.id
    )

    column = await _lock_destination_column_or_404(session, column_id=column_id)
    locked_card = await cards_repository.lock_card_for_update(session, card_id)
    if locked_card is None:
        raise NotFoundError(_CARD_NOT_FOUND_MESSAGE)
    # Everything from here on decides on state read *under* the two locks: the
    # card's column as it is now, not as it was when we authorized the request.
    card = locked_card

    if column_id != card.column_id:
        # Only when the card actually changes column: it is already counted in its
        # own one, so reordering inside a column that sits at its limit must keep
        # working instead of freezing the column.
        await _reject_if_wip_limit_reached(session, column)

    new_position = await _position_at_index(
        session, column_id=column_id, index=position, exclude_card_id=card_id
    )
    card = await cards_repository.set_placement(
        session, card, column_id=column_id, position=new_position
    )
    await session.commit()
    return card
