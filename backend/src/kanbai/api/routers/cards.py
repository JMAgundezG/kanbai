"""Cards: the unit of work on a board.

Any board member manages cards, like columns (TASK-05) and unlike board-level
admin (TASK-04): no route here checks a role. Moving lives in its own endpoint
rather than in the PUT body — see the module docstring of services/cards.py for
why the move needs a transaction of its own.
"""

import uuid
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import APIRouter, Query

from kanbai.api.deps import CurrentActor, PaginationDep, SessionDep
from kanbai.schemas.card import CardCreate, CardMove, CardRead, CardUpdate
from kanbai.schemas.pagination import Page
from kanbai.services import cards as cards_service

router = APIRouter(prefix="/boards/{board_id}/cards", tags=["cards"])

_NOT_A_MEMBER: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {
        "description": "No eres miembro de este tablero, o la tarjeta o la columna no existen."
    }
}
_WIP_LIMIT: dict[int | str, dict[str, Any]] = {
    HTTPStatus.CONFLICT: {
        "description": "La columna de destino ha alcanzado su límite de trabajo en curso."
    }
}

ColumnFilter = Annotated[
    uuid.UUID | None, Query(description="Filtra las tarjetas de una sola columna")
]


@router.get(
    "",
    response_model=Page[CardRead],
    summary="Lista las tarjetas de un tablero, ordenadas por columna y posición",
    responses=_NOT_A_MEMBER,
)
async def list_cards(
    board_id: uuid.UUID,
    session: SessionDep,
    actor: CurrentActor,
    pagination: PaginationDep,
    column_id: ColumnFilter = None,
) -> Page[CardRead]:
    cards, total = await cards_service.list_cards(
        session,
        actor=actor,
        board_id=board_id,
        column_id=column_id,
        limit=pagination.limit,
        offset=pagination.offset,
    )
    return Page[CardRead](
        items=[CardRead.model_validate(card) for card in cards],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "",
    response_model=CardRead,
    status_code=HTTPStatus.CREATED,
    summary="Crea una tarjeta al final de una columna",
    responses={**_NOT_A_MEMBER, **_WIP_LIMIT},
)
async def create_card(
    board_id: uuid.UUID, payload: CardCreate, session: SessionDep, actor: CurrentActor
) -> CardRead:
    card = await cards_service.create_card(
        session,
        actor=actor,
        board_id=board_id,
        column_id=payload.column_id,
        title=payload.title,
        description=payload.description,
    )
    return CardRead.model_validate(card)


@router.get(
    "/{card_id}",
    response_model=CardRead,
    summary="Obtiene una tarjeta por id",
    responses=_NOT_A_MEMBER,
)
async def get_card(
    board_id: uuid.UUID, card_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> CardRead:
    card = await cards_service.get_card(session, actor=actor, board_id=board_id, card_id=card_id)
    return CardRead.model_validate(card)


@router.put(
    "/{card_id}",
    response_model=CardRead,
    summary="Sustituye el título y la descripción de una tarjeta",
    responses=_NOT_A_MEMBER,
)
async def update_card(
    board_id: uuid.UUID,
    card_id: uuid.UUID,
    payload: CardUpdate,
    session: SessionDep,
    actor: CurrentActor,
) -> CardRead:
    card = await cards_service.update_card(
        session,
        actor=actor,
        board_id=board_id,
        card_id=card_id,
        title=payload.title,
        description=payload.description,
    )
    return CardRead.model_validate(card)


@router.delete(
    "/{card_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Borra una tarjeta",
    responses=_NOT_A_MEMBER,
)
async def delete_card(
    board_id: uuid.UUID, card_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> None:
    await cards_service.delete_card(session, actor=actor, board_id=board_id, card_id=card_id)


@router.post(
    "/{card_id}/move",
    response_model=CardRead,
    summary="Mueve una tarjeta a una columna y una posición, en una sola operación atómica",
    responses={**_NOT_A_MEMBER, **_WIP_LIMIT},
)
async def move_card(
    board_id: uuid.UUID,
    card_id: uuid.UUID,
    payload: CardMove,
    session: SessionDep,
    actor: CurrentActor,
) -> CardRead:
    """POST, not PUT: the body is a relative intent ("put it in this column, in
    this slot"), resolved against the column's live contents, not the card's final
    state. Repeating the call can legitimately yield a different `position`, so the
    idempotence PUT promises would not hold — unlike PUT .../columns/reorder, which
    does send the complete desired order. The response carries the position the
    server actually computed, which is rarely the index the client sent."""
    card = await cards_service.move_card(
        session,
        actor=actor,
        board_id=board_id,
        card_id=card_id,
        column_id=payload.column_id,
        position=payload.position,
    )
    return CardRead.model_validate(card)
