"""Boards: the authorization unit for everything else on the board.

Being a row in `board_members` is what "mine" means from here on — TASK-05 onward
scopes columns, cards, comments and events through
`repositories.membership.board_ids_for_actor` the same way this router's service
scopes boards themselves.
"""

import uuid
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter

from kanbai.api.deps import CurrentActor, PaginationDep, SessionDep
from kanbai.models.board import Board
from kanbai.schemas.board import BoardCreate, BoardRead, BoardUpdate
from kanbai.schemas.board_member import BoardMemberCreate, BoardMemberRead
from kanbai.schemas.pagination import Page
from kanbai.services import boards as boards_service

router = APIRouter(prefix="/boards", tags=["boards"])

# Typed to match FastAPI's `responses` parameter exactly (dict is invariant, so
# this must be `dict[int | str, dict[str, Any]]` verbatim): building the dict as
# its own variable instead of an inline literal loses the bidirectional inference
# that lets an inline `{HTTPStatus.X: ...}` pass without this annotation.
_NOT_A_MEMBER: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {"description": "No eres miembro de este tablero."}
}
_OWNER_ONLY: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {"description": "No eres miembro de este tablero."},
    HTTPStatus.FORBIDDEN: {"description": "Eres miembro, pero no owner."},
}


def _board_read(board: Board, role: str) -> BoardRead:
    return BoardRead(id=board.id, name=board.name, created_at=board.created_at, role=role)


@router.post(
    "",
    response_model=BoardRead,
    status_code=HTTPStatus.CREATED,
    summary="Crea un tablero nuevo",
)
async def create_board(payload: BoardCreate, session: SessionDep, actor: CurrentActor) -> BoardRead:
    board, role = await boards_service.create_board(session, actor=actor, name=payload.name)
    return _board_read(board, role)


@router.get(
    "",
    response_model=Page[BoardRead],
    summary="Lista los tableros de los que el actor autenticado es miembro",
)
async def list_boards(
    session: SessionDep, actor: CurrentActor, pagination: PaginationDep
) -> Page[BoardRead]:
    rows, total = await boards_service.list_boards(
        session, actor=actor, limit=pagination.limit, offset=pagination.offset
    )
    return Page[BoardRead](
        items=[_board_read(board, role) for board, role in rows],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/{board_id}",
    response_model=BoardRead,
    summary="Obtiene un tablero por id",
    responses=_NOT_A_MEMBER,
)
async def get_board(board_id: uuid.UUID, session: SessionDep, actor: CurrentActor) -> BoardRead:
    board, role = await boards_service.get_board(session, actor=actor, board_id=board_id)
    return _board_read(board, role)


@router.patch(
    "/{board_id}",
    response_model=BoardRead,
    summary="Renombra un tablero (solo el owner)",
    responses=_OWNER_ONLY,
)
async def rename_board(
    board_id: uuid.UUID, payload: BoardUpdate, session: SessionDep, actor: CurrentActor
) -> BoardRead:
    board, role = await boards_service.rename_board(
        session, actor=actor, board_id=board_id, name=payload.name
    )
    return _board_read(board, role)


@router.delete(
    "/{board_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Borra un tablero (solo el owner)",
    responses=_OWNER_ONLY,
)
async def delete_board(board_id: uuid.UUID, session: SessionDep, actor: CurrentActor) -> None:
    await boards_service.delete_board(session, actor=actor, board_id=board_id)


@router.get(
    "/{board_id}/members",
    response_model=Page[BoardMemberRead],
    summary="Lista los miembros de un tablero",
    responses=_NOT_A_MEMBER,
)
async def list_members(
    board_id: uuid.UUID, session: SessionDep, actor: CurrentActor, pagination: PaginationDep
) -> Page[BoardMemberRead]:
    members, total = await boards_service.list_members(
        session, actor=actor, board_id=board_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[BoardMemberRead](
        items=[BoardMemberRead.model_validate(member) for member in members],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "/{board_id}/members",
    response_model=BoardMemberRead,
    status_code=HTTPStatus.CREATED,
    summary="Añade un miembro a un tablero (solo el owner; persona o agente por igual)",
    responses={
        **_OWNER_ONLY,
        HTTPStatus.CONFLICT: {
            "description": (
                "El actor ya es miembro del tablero, o es un agente cuya persona "
                "propietaria no tiene en este tablero un rol igual o superior."
            )
        },
    },
)
async def add_member(
    board_id: uuid.UUID, payload: BoardMemberCreate, session: SessionDep, actor: CurrentActor
) -> BoardMemberRead:
    member = await boards_service.add_member(
        session,
        actor=actor,
        board_id=board_id,
        new_actor_id=payload.actor_id,
        role=payload.role,
    )
    return BoardMemberRead.model_validate(member)


@router.delete(
    "/{board_id}/members/{member_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Quita a un miembro del tablero (el owner, o el propio miembro)",
    responses={
        **_OWNER_ONLY,
        HTTPStatus.CONFLICT: {"description": "Es el único owner del tablero."},
    },
)
async def remove_member(
    board_id: uuid.UUID, member_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> None:
    await boards_service.remove_member(session, actor=actor, board_id=board_id, member_id=member_id)
