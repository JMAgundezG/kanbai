"""Board and membership rules.

Nothing here — or in any repository it calls — branches on `actor.kind`. An agent
is a board member exactly like a person is (CLAUDE.md § 0): the only place `kind`
is ever read is inside ActorRead, which TASK-03 already built to not need changes
for TASK-09.

TASK-09 adds one thing that *is* about agents without ever reading `kind`:
`create_board` and `add_member` call `Actor.permission_ceiling_actor_id()`, a
method every actor answers (a plain `Actor`/`Person` always with `None`, an
`Agent` with its owning person's id — see models/actor.py and models/agent.py).
This is what keeps "an agent never outranks the person who created it"
(CLAUDE.md § 0) true: an agent can never end up a member — at a role its owner
does not also hold — of a board its owner cannot also reach, and creating a
board as an agent hands the owning person the same access, in the same
transaction.

`add_member` and `remove_member` both take `boards_repository.lock_board_for_update`
before touching `board_members`, the same primitive `services/columns.py` uses to
serialize writes on a board's columns. Without it, the ceiling check above is a
plain read-then-insert: a concurrent `remove_member` on the ceiling actor's own
membership could commit in the gap between the check and the insert, and the
agent would be granted access whose ceiling had, by commit time, already been
pulled out from under it. The lock makes the two operations serialize instead —
whichever commits first is the one the other observes.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from kanbai.core.exceptions import AuthorizationError, ConflictError, NotFoundError
from kanbai.models.actor import Actor
from kanbai.models.board import Board
from kanbai.models.board_member import BoardMember
from kanbai.repositories import actors as actors_repository
from kanbai.repositories import board_members as board_members_repository
from kanbai.repositories import boards as boards_repository

OWNER = "owner"
MEMBER = "member"
_ROLE_RANK = {MEMBER: 0, OWNER: 1}

_BOARD_NOT_FOUND_MESSAGE = "El tablero solicitado no existe."
_EXCEEDS_OWNER_MESSAGE = (
    "El agente no puede tener en este tablero más permisos que su persona propietaria."
)


async def list_boards(
    session: AsyncSession, *, actor: Actor, limit: int, offset: int
) -> tuple[list[tuple[Board, str]], int]:
    return await boards_repository.list_boards_for_actor(
        session, actor.id, limit=limit, offset=offset
    )


async def create_board(session: AsyncSession, *, actor: Actor, name: str) -> tuple[Board, str]:
    """A board never exists without an owner or its starting columns, not even for
    an instant observable from outside: creation, the owner membership, and the
    default columns share one transaction.

    The import of `services.columns` is deferred to inside the function body:
    that module imports this one back (it needs `get_board` to authorize its own
    operations), so importing it at module level here would be circular.
    """
    from kanbai.services import columns as columns_service

    board = await boards_repository.create_board(session, name=name)
    await board_members_repository.add_member(
        session, board_id=board.id, actor_id=actor.id, role=OWNER
    )
    # An agent's owning person always gets the same access to a board the agent
    # just created — otherwise the agent would own something its person cannot
    # even see, exceeding the permissions of whoever created it.
    ceiling_actor_id = actor.permission_ceiling_actor_id()
    if ceiling_actor_id is not None:
        await board_members_repository.add_member(
            session, board_id=board.id, actor_id=ceiling_actor_id, role=OWNER
        )
    await columns_service.seed_default_columns(session, board_id=board.id)
    await session.commit()
    return board, OWNER


async def get_board(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID
) -> tuple[Board, str]:
    found = await boards_repository.get_board_for_actor(session, board_id, actor.id)
    if found is None:
        raise NotFoundError(_BOARD_NOT_FOUND_MESSAGE)
    return found


async def rename_board(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, name: str
) -> tuple[Board, str]:
    board, role = await get_board(session, actor=actor, board_id=board_id)
    if role != OWNER:
        raise AuthorizationError("Solo el owner puede modificar el tablero.")
    board = await boards_repository.rename_board(session, board, name)
    await session.commit()
    return board, role


async def delete_board(session: AsyncSession, *, actor: Actor, board_id: uuid.UUID) -> None:
    board, role = await get_board(session, actor=actor, board_id=board_id)
    if role != OWNER:
        raise AuthorizationError("Solo el owner puede borrar el tablero.")
    await boards_repository.delete_board(session, board)
    await session.commit()


async def list_members(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, limit: int, offset: int
) -> tuple[list[BoardMember], int]:
    await get_board(session, actor=actor, board_id=board_id)
    return await board_members_repository.list_members(
        session, board_id, limit=limit, offset=offset
    )


async def add_member(
    session: AsyncSession,
    *,
    actor: Actor,
    board_id: uuid.UUID,
    new_actor_id: uuid.UUID,
    role: str,
) -> BoardMember:
    _, requester_role = await get_board(session, actor=actor, board_id=board_id)
    if requester_role != OWNER:
        raise AuthorizationError("Solo el owner puede añadir miembros.")

    # Held until commit: serializes this against any other membership write on
    # the same board (see the module docstring) — in particular against a
    # concurrent `remove_member` racing the ceiling check just below.
    await boards_repository.lock_board_for_update(session, board_id)

    target_actor = await actors_repository.get_actor_by_id(session, new_actor_id)
    if target_actor is None:
        raise NotFoundError("El actor indicado no existe.")

    ceiling_actor_id = target_actor.permission_ceiling_actor_id()
    if ceiling_actor_id is not None:
        ceiling_membership = await board_members_repository.get_member_by_actor(
            session, board_id, ceiling_actor_id
        )
        if ceiling_membership is None or _ROLE_RANK[ceiling_membership.role] < _ROLE_RANK[role]:
            raise ConflictError(_EXCEEDS_OWNER_MESSAGE)

    existing = await board_members_repository.get_member_by_actor(session, board_id, new_actor_id)
    if existing is not None:
        raise ConflictError("Este actor ya es miembro del tablero.")

    member = await board_members_repository.add_member(
        session, board_id=board_id, actor_id=new_actor_id, role=role
    )
    await session.commit()
    return member


async def remove_member(
    session: AsyncSession, *, actor: Actor, board_id: uuid.UUID, member_id: uuid.UUID
) -> None:
    _, requester_role = await get_board(session, actor=actor, board_id=board_id)

    # Same lock `add_member` takes, and for the same reason: without it, this
    # removal and a concurrent `add_member`'s ceiling check could each read the
    # membership state from before the other's write.
    await boards_repository.lock_board_for_update(session, board_id)

    member = await board_members_repository.get_member_by_id(session, board_id, member_id)
    if member is None:
        raise NotFoundError("El miembro indicado no existe.")

    is_self = member.actor_id == actor.id
    if requester_role != OWNER and not is_self:
        raise AuthorizationError("Solo el owner puede quitar a otros miembros.")

    if member.role == OWNER:
        owners = await board_members_repository.count_owners(session, board_id)
        if owners <= 1:
            raise ConflictError("No puedes quitar al único owner del tablero.")

    await board_members_repository.remove_member(session, member)
    await session.commit()
