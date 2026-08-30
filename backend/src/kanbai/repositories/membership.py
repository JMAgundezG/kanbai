"""The one place that encodes "boards this actor belongs to" as SQL.

Any repository whose rows hang off a board — columns, cards (via their column),
comments and events (via their card) — scopes its own queries through this
subquery instead of re-deriving the join, e.g.
`.where(Column.board_id.in_(board_ids_for_actor(actor_id)))`. Reused today by
repositories/boards.py; TASK-05 onward reuses it the same way for its own tables.
"""

import uuid

from sqlalchemy import Select, select

from kanbai.models.board_member import BoardMember


def board_ids_for_actor(actor_id: uuid.UUID) -> Select[tuple[uuid.UUID]]:
    return select(BoardMember.board_id).where(BoardMember.actor_id == actor_id)
