"""Queries on boards. The only place that talks SQL for this table."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.board import Board
from kanbai.models.board_member import BoardMember
from kanbai.repositories.membership import board_ids_for_actor


async def list_boards_for_actor(
    session: AsyncSession, actor_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[tuple[Board, str]], int]:
    """Each row needs the actor's own role on that board, so this joins straight
    to board_members rather than going through board_ids_for_actor (which does not
    carry the role) — the join *is* the same membership filter, expressed the way
    this particular query needs it."""
    total = await session.scalar(
        select(func.count()).select_from(Board).where(Board.id.in_(board_ids_for_actor(actor_id)))
    )
    result = await session.execute(
        select(Board, BoardMember.role)
        .join(BoardMember, BoardMember.board_id == Board.id)
        .where(BoardMember.actor_id == actor_id)
        .order_by(Board.created_at.desc(), Board.id)
        .limit(limit)
        .offset(offset)
    )
    rows = [(row[0], row[1]) for row in result.all()]
    return rows, total or 0


async def get_board_for_actor(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID
) -> tuple[Board, str] | None:
    """None whether the board does not exist at all, or exists but this actor is
    not a member — the caller never distinguishes the two, by design."""
    result = await session.execute(
        select(Board, BoardMember.role)
        .join(BoardMember, BoardMember.board_id == Board.id)
        .where(Board.id == board_id, BoardMember.actor_id == actor_id)
    )
    row = result.first()
    return (row[0], row[1]) if row is not None else None


async def create_board(session: AsyncSession, *, name: str) -> Board:
    board = Board(name=name)
    session.add(board)
    await session.flush()
    return board


async def rename_board(session: AsyncSession, board: Board, name: str) -> Board:
    board.name = name
    await session.flush()
    return board


async def delete_board(session: AsyncSession, board: Board) -> None:
    await session.delete(board)
