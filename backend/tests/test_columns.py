"""Board columns: default seeding, CRUD, ownership (404 on an unrelated board),
and the reordering endpoint's core promise — N columns land with no gaps and no
duplicate positions."""

import asyncio
import uuid
from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from kanbai.models.actor import Person
from kanbai.repositories import actors as actors_repository
from kanbai.services import auth as auth_service
from kanbai.services import boards as boards_service
from kanbai.services import columns as columns_service

OWNER_PASSWORD = "correcto-caballo-batería-grapa"
OTHER_PASSWORD = "otra-contraseña-cualquiera"


@pytest.fixture
async def owner(db_session: Any) -> Person:
    return await auth_service.create_person(
        db_session, email="owner@example.com", password=OWNER_PASSWORD, display_name="Owner"
    )


@pytest.fixture
async def other_person(db_session: Any) -> Person:
    return await auth_service.create_person(
        db_session, email="otra@example.com", password=OTHER_PASSWORD, display_name="Otra"
    )


async def _login(client: AsyncClient, email: str, password: str) -> None:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == HTTPStatus.OK


async def _create_board(client: AsyncClient, name: str = "Tablero de prueba") -> dict[str, Any]:
    response = await client.post("/api/v1/boards", json={"name": name})
    assert response.status_code == HTTPStatus.CREATED
    result: dict[str, Any] = response.json()
    return result


async def _create_column(
    client: AsyncClient, board_id: str, name: str = "Columna", **kwargs: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/boards/{board_id}/columns", json={"name": name, **kwargs}
    )
    assert response.status_code == HTTPStatus.CREATED
    result: dict[str, Any] = response.json()
    return result


# --- columnas iniciales al crear un tablero --------------------------------------


async def test_crear_tablero_siembra_tres_columnas_por_defecto(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.get(f"/api/v1/boards/{board['id']}/columns")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 3
    assert [item["name"] for item in body["items"]] == ["Por hacer", "En curso", "Hecho"]
    positions = [item["position"] for item in body["items"]]
    assert positions == sorted(positions)
    assert len(set(positions)) == 3


# --- creación ---------------------------------------------------------------------


async def test_crear_columna_como_owner(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    column = await _create_column(client, board["id"], "En revisión", wip_limit=3)

    assert column["name"] == "En revisión"
    assert column["wip_limit"] == 3
    assert column["board_id"] == board["id"]


async def test_crear_columna_como_member_no_owner_funciona_igual(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await client.post(
        f"/api/v1/boards/{board['id']}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.post(
        f"/api/v1/boards/{board['id']}/columns", json={"name": "Añadida por member"}
    )

    assert response.status_code == HTTPStatus.CREATED


async def test_crear_columna_en_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.post(
        f"/api/v1/boards/{board['id']}/columns", json={"name": "Intento ajeno"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_crear_columna_nombre_vacio_devuelve_422(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.post(f"/api/v1/boards/{board['id']}/columns", json={"name": ""})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_crear_columna_wip_limit_no_positivo_devuelve_422(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    response = await client.post(
        f"/api/v1/boards/{board['id']}/columns", json={"name": "Con límite malo", "wip_limit": 0}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- listado ------------------------------------------------------------------


async def test_listar_columnas_devuelve_orden_por_posicion(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    await _create_column(client, board["id"], "Extra")

    response = await client.get(f"/api/v1/boards/{board['id']}/columns")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 4
    names = [item["name"] for item in body["items"]]
    assert names == ["Por hacer", "En curso", "Hecho", "Extra"]


async def test_listar_columnas_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.get(f"/api/v1/boards/{board['id']}/columns")

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- lectura, edición y borrado de una columna ------------------------------------


async def test_obtener_columna_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    column = await _create_column(client, board["id"])

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.get(f"/api/v1/boards/{board['id']}/columns/{column['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_renombrar_columna(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    column = await _create_column(client, board["id"], "Nombre viejo")

    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/{column['id']}",
        json={"name": "Nombre nuevo", "wip_limit": 5},
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["name"] == "Nombre nuevo"
    assert body["wip_limit"] == 5


async def test_renombrar_columna_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    column = await _create_column(client, board["id"])

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/{column['id']}", json={"name": "Intento ajeno"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_columna_vacia(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    column = await _create_column(client, board["id"])

    response = await client.delete(f"/api/v1/boards/{board['id']}/columns/{column['id']}")
    get_response = await client.get(f"/api/v1/boards/{board['id']}/columns/{column['id']}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert get_response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_columna_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    column = await _create_column(client, board["id"])

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.delete(f"/api/v1/boards/{board['id']}/columns/{column['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_la_ultima_columna_devuelve_409(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    columns = (await client.get(f"/api/v1/boards/{board['id']}/columns")).json()["items"]
    assert len(columns) == 3

    first, second, last = (column["id"] for column in columns)
    await client.delete(f"/api/v1/boards/{board['id']}/columns/{first}")
    await client.delete(f"/api/v1/boards/{board['id']}/columns/{second}")

    response = await client.delete(f"/api/v1/boards/{board['id']}/columns/{last}")

    assert response.status_code == HTTPStatus.CONFLICT
    still_there = await client.get(f"/api/v1/boards/{board['id']}/columns/{last}")
    assert still_there.status_code == HTTPStatus.OK


# --- reordenación -----------------------------------------------------------------


async def test_reordenar_columnas_deja_orden_sin_huecos_ni_repetidos(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    # El tablero ya nace con 3 columnas; se añade una cuarta.
    extra = await _create_column(client, board["id"], "Cuarta")

    current = await client.get(f"/api/v1/boards/{board['id']}/columns")
    current_ids = [item["id"] for item in current.json()["items"]]
    assert extra["id"] in current_ids
    assert len(current_ids) == 4

    new_order = list(reversed(current_ids))
    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/reorder", json={"column_ids": new_order}
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert [item["id"] for item in body] == new_order

    positions = [item["position"] for item in body]
    # Sin huecos ni posiciones repetidas en el orden: exactamente N valores
    # distintos, estrictamente crecientes, uno por rango sucesivo — espaciados en
    # múltiplos de GAP (no 0,1,2,...) para no destruir el hueco que deja sitio a
    # una futura inserción entre dos columnas vecinas.
    assert positions == [index * 1024.0 for index in range(len(new_order))]
    assert len(set(positions)) == len(new_order)

    # La reordenación persiste: un listado posterior devuelve el mismo orden.
    listed = await client.get(f"/api/v1/boards/{board['id']}/columns")
    assert [item["id"] for item in listed.json()["items"]] == new_order


async def test_reordenar_columnas_con_id_repetido_devuelve_422(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    current = await client.get(f"/api/v1/boards/{board['id']}/columns")
    current_ids = [item["id"] for item in current.json()["items"]]

    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/reorder",
        json={"column_ids": [current_ids[0], current_ids[0], current_ids[1]]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_reordenar_columnas_con_id_ajeno_devuelve_422(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    current = await client.get(f"/api/v1/boards/{board['id']}/columns")
    current_ids = [item["id"] for item in current.json()["items"]]

    other_board = await _create_board(client, "Otro tablero")
    other_columns = await client.get(f"/api/v1/boards/{other_board['id']}/columns")
    foreign_id = other_columns.json()["items"][0]["id"]

    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/reorder",
        json={"column_ids": [foreign_id, *current_ids[1:]]},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_reordenar_columnas_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board = await _create_board(client)
    current = await client.get(f"/api/v1/boards/{board['id']}/columns")
    current_ids = [item["id"] for item in current.json()["items"]]

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.put(
        f"/api/v1/boards/{board['id']}/columns/reorder", json={"column_ids": current_ids}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- concurrencia y el constraint de posición que la sostiene --------------------


async def test_crear_columnas_concurrentes_en_el_mismo_tablero_no_colisiona(
    engine: AsyncEngine,
) -> None:
    """Regression for the race repositories/boards.py::lock_board_for_update
    fixes: two concurrent creates on the same board must not both compute the
    same MAX(position) and collide at commit. This needs genuinely concurrent,
    independently-committing sessions — the shared `db_session` fixture's
    savepoint-per-test isolation can't demonstrate real concurrency — so this
    test manages its own connections and cleans up explicitly afterward."""
    # Genuinely committed data (see the docstring above), so the email must be
    # unique per run — a fixed one would collide on a second local run or a retry.
    unique_email = f"concurrencia-crear-{uuid.uuid4().hex}@example.com"
    async with AsyncSession(engine, expire_on_commit=False) as setup_session:
        owner = await auth_service.create_person(
            setup_session,
            email=unique_email,
            password="cualquier-cosa-larga-1234",
            display_name="Concurrencia",
        )
        board, _ = await boards_service.create_board(
            setup_session, actor=owner, name="Carrera de creación"
        )
        owner_id, board_id = owner.id, board.id

    try:

        async def _create(name: str) -> None:
            async with AsyncSession(engine, expire_on_commit=False) as session:
                actor = await actors_repository.get_actor_by_id(session, owner_id)
                assert actor is not None
                await columns_service.create_column(
                    session, actor=actor, board_id=board_id, name=name, wip_limit=None
                )

        await asyncio.gather(_create("Carril A"), _create("Carril B"))

        async with AsyncSession(engine, expire_on_commit=False) as check_session:
            actor = await actors_repository.get_actor_by_id(check_session, owner_id)
            assert actor is not None
            columns, total = await columns_service.list_columns(
                check_session, actor=actor, board_id=board_id, limit=100, offset=0
            )
            assert total == 5  # 3 por defecto + las 2 creadas a la vez
            positions = [column.position for column in columns]
            assert len(set(positions)) == len(positions)
    finally:
        async with engine.connect() as cleanup:
            await cleanup.execute(text("DELETE FROM boards WHERE id = :id"), {"id": board_id})
            await cleanup.execute(text("DELETE FROM actors WHERE id = :id"), {"id": owner_id})
            await cleanup.commit()


async def test_constraint_de_posicion_se_aplaza_pero_se_comprueba_en_commit_real(
    engine: AsyncEngine,
) -> None:
    """DEFERRABLE INITIALLY DEFERRED only matters if PostgreSQL genuinely enforces
    it at a real COMMIT. Every other test in this file runs inside a SAVEPOINT that
    is always rolled back (conftest.py's `db_session` fixture), so
    `session.commit()` there never reaches an actual transaction COMMIT and this
    constraint is never exercised. This test opens its own connection and issues a
    real COMMIT to prove the safety net repositories/columns.py::set_positions
    leans on is not just declared on the model, but live in the database — and
    that a violation surfaces as the named constraint, not silently."""
    board_id = uuid.uuid4()
    column_a, column_b = uuid.uuid4(), uuid.uuid4()

    async with engine.connect() as connection:
        await connection.execute(
            text("INSERT INTO boards (id, name) VALUES (:id, 'Tablero de prueba')"),
            {"id": board_id},
        )
        await connection.execute(
            text(
                "INSERT INTO board_columns (id, board_id, name, position) "
                "VALUES (:id, :board_id, 'A', 1.0)"
            ),
            {"id": column_a, "board_id": board_id},
        )
        # Misma posición que la columna A: el INSERT en sí no falla — el
        # constraint está aplazado, no se comprueba sentencia a sentencia.
        await connection.execute(
            text(
                "INSERT INTO board_columns (id, board_id, name, position) "
                "VALUES (:id, :board_id, 'B', 1.0)"
            ),
            {"id": column_b, "board_id": board_id},
        )
        with pytest.raises(IntegrityError, match="uq_board_columns_board_id_position"):
            await connection.commit()
