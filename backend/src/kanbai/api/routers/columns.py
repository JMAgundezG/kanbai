"""Board columns: the phases of a board's workflow.

Any board member manages columns (create, rename, reorder, delete) — unlike
board-level admin (TASK-04), which restricts renaming/deleting the board and
managing membership to the owner. No route here checks a role.
"""

import uuid
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter

from kanbai.api.deps import CurrentActor, PaginationDep, SessionDep
from kanbai.schemas.column import ColumnCreate, ColumnRead, ColumnReorder, ColumnUpdate
from kanbai.schemas.pagination import Page
from kanbai.services import columns as columns_service

router = APIRouter(prefix="/boards/{board_id}/columns", tags=["columns"])

_NOT_A_MEMBER: dict[int | str, dict[str, Any]] = {
    HTTPStatus.NOT_FOUND: {
        "description": "No eres miembro de este tablero, o la columna no existe."
    }
}
_LAST_COLUMN: dict[int | str, dict[str, Any]] = {
    HTTPStatus.CONFLICT: {"description": "Es la última columna del tablero."}
}


@router.get(
    "",
    response_model=Page[ColumnRead],
    summary="Lista las columnas de un tablero, ordenadas por posición",
    responses=_NOT_A_MEMBER,
)
async def list_columns(
    board_id: uuid.UUID, session: SessionDep, actor: CurrentActor, pagination: PaginationDep
) -> Page[ColumnRead]:
    columns, total = await columns_service.list_columns(
        session, actor=actor, board_id=board_id, limit=pagination.limit, offset=pagination.offset
    )
    return Page[ColumnRead](
        items=[ColumnRead.model_validate(column) for column in columns],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.post(
    "",
    response_model=ColumnRead,
    status_code=HTTPStatus.CREATED,
    summary="Crea una columna al final del tablero",
    responses=_NOT_A_MEMBER,
)
async def create_column(
    board_id: uuid.UUID, payload: ColumnCreate, session: SessionDep, actor: CurrentActor
) -> ColumnRead:
    column = await columns_service.create_column(
        session, actor=actor, board_id=board_id, name=payload.name, wip_limit=payload.wip_limit
    )
    return ColumnRead.model_validate(column)


@router.put(
    "/reorder",
    response_model=list[ColumnRead],
    summary="Reordena todas las columnas de un tablero en una sola llamada",
    responses={
        **_NOT_A_MEMBER,
        HTTPStatus.UNPROCESSABLE_ENTITY: {
            "description": "La lista no coincide exactamente con las columnas actuales del tablero."
        },
    },
)
async def reorder_columns(
    board_id: uuid.UUID, payload: ColumnReorder, session: SessionDep, actor: CurrentActor
) -> list[ColumnRead]:
    columns = await columns_service.reorder_columns(
        session, actor=actor, board_id=board_id, column_ids=payload.column_ids
    )
    return [ColumnRead.model_validate(column) for column in columns]


@router.get(
    "/{column_id}",
    response_model=ColumnRead,
    summary="Obtiene una columna por id",
    responses=_NOT_A_MEMBER,
)
async def get_column(
    board_id: uuid.UUID, column_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> ColumnRead:
    column = await columns_service.get_column(
        session, actor=actor, board_id=board_id, column_id=column_id
    )
    return ColumnRead.model_validate(column)


@router.put(
    "/{column_id}",
    response_model=ColumnRead,
    summary="Sustituye nombre y límite de trabajo en curso de una columna",
    responses=_NOT_A_MEMBER,
)
async def update_column(
    board_id: uuid.UUID,
    column_id: uuid.UUID,
    payload: ColumnUpdate,
    session: SessionDep,
    actor: CurrentActor,
) -> ColumnRead:
    column = await columns_service.update_column(
        session,
        actor=actor,
        board_id=board_id,
        column_id=column_id,
        name=payload.name,
        wip_limit=payload.wip_limit,
    )
    return ColumnRead.model_validate(column)


@router.delete(
    "/{column_id}",
    status_code=HTTPStatus.NO_CONTENT,
    summary="Borra una columna (409 si es la última, o si tiene tarjetas desde TASK-06)",
    responses={**_NOT_A_MEMBER, **_LAST_COLUMN},
)
async def delete_column(
    board_id: uuid.UUID, column_id: uuid.UUID, session: SessionDep, actor: CurrentActor
) -> None:
    await columns_service.delete_column(
        session, actor=actor, board_id=board_id, column_id=column_id
    )
