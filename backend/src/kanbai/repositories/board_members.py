"""Queries on board membership. The only place that talks SQL for this table."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.models.board_member import BoardMember


async def list_members(
    session: AsyncSession, board_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[BoardMember], int]:
    total = await session.scalar(
        select(func.count()).select_from(BoardMember).where(BoardMember.board_id == board_id)
    )
    result = await session.execute(
        select(BoardMember)
        .where(BoardMember.board_id == board_id)
        .order_by(BoardMember.created_at, BoardMember.id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all()), total or 0


async def get_member_by_actor(
    session: AsyncSession, board_id: uuid.UUID, actor_id: uuid.UUID
) -> BoardMember | None:
    result = await session.execute(
        select(BoardMember).where(
            BoardMember.board_id == board_id, BoardMember.actor_id == actor_id
        )
    )
    return result.scalar_one_or_none()


async def get_member_by_id(
    session: AsyncSession, board_id: uuid.UUID, member_id: uuid.UUID
) -> BoardMember | None:
    result = await session.execute(
        select(BoardMember).where(BoardMember.board_id == board_id, BoardMember.id == member_id)
    )
    return result.scalar_one_or_none()


async def count_owners(session: AsyncSession, board_id: uuid.UUID) -> int:
    total = await session.scalar(
        select(func.count())
        .select_from(BoardMember)
        .where(BoardMember.board_id == board_id, BoardMember.role == "owner")
    )
    return total or 0


async def add_member(
    session: AsyncSession, *, board_id: uuid.UUID, actor_id: uuid.UUID, role: str
) -> BoardMember:
    member = BoardMember(board_id=board_id, actor_id=actor_id, role=role)
    session.add(member)
    await session.flush()
    # `actor` is lazy="selectin": refresh it so the caller can build BoardMemberRead
    # (which nests ActorRead) without a second round trip through this module.
    await session.refresh(member, attribute_names=["actor"])
    return member


async def remove_member(session: AsyncSession, member: BoardMember) -> None:
    await session.delete(member)
