"""Cards: CRUD, ownership (404 on anything from a board you are not a member of),
the WIP limit, and the core promise of the task — a move that stays atomic while
several actors move cards at the same time."""

import asyncio
import math
import uuid
from http import HTTPStatus
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from kanbai.core.exceptions import ConflictError
from kanbai.models.actor import Person
from kanbai.repositories import actors as actors_repository
from kanbai.services import auth as auth_service
from kanbai.services import boards as boards_service
from kanbai.services import cards as cards_service
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


async def _columns(client: AsyncClient, board_id: str) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/boards/{board_id}/columns")
    assert response.status_code == HTTPStatus.OK
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def _create_column(
    client: AsyncClient, board_id: str, name: str, **kwargs: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/boards/{board_id}/columns", json={"name": name, **kwargs}
    )
    assert response.status_code == HTTPStatus.CREATED
    result: dict[str, Any] = response.json()
    return result


async def _create_card(
    client: AsyncClient, board_id: str, column_id: str, title: str = "Tarjeta", **kwargs: Any
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/boards/{board_id}/cards",
        json={"column_id": column_id, "title": title, **kwargs},
    )
    assert response.status_code == HTTPStatus.CREATED, response.text
    result: dict[str, Any] = response.json()
    return result


async def _cards_in_column(
    client: AsyncClient, board_id: str, column_id: str
) -> list[dict[str, Any]]:
    response = await client.get(f"/api/v1/boards/{board_id}/cards", params={"column_id": column_id})
    assert response.status_code == HTTPStatus.OK
    items: list[dict[str, Any]] = response.json()["items"]
    return items


async def _board_with_two_columns(client: AsyncClient) -> tuple[str, str, str]:
    """A board plus the ids of its first and last seeded columns."""
    board = await _create_board(client)
    columns = await _columns(client, board["id"])
    return board["id"], columns[0]["id"], columns[-1]["id"]


# --- creación ---------------------------------------------------------------------


async def test_crear_tarjeta_registra_al_actor_creador(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)

    card = await _create_card(client, board_id, column_id, "Primera", description="Con detalle")

    # El creador sale del actor autenticado, sin mirar de qué tipo es (CLAUDE.md § 0):
    # el día que un agente cree una tarjeta, este mismo camino la firma igual.
    assert card["created_by_actor_id"] == str(owner.id)
    assert card["title"] == "Primera"
    assert card["description"] == "Con detalle"
    assert card["board_id"] == board_id
    assert card["column_id"] == column_id


async def test_crear_tarjeta_como_member_no_owner_funciona_igual(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    await client.post(
        f"/api/v1/boards/{board_id}/members",
        json={"actor_id": str(other_person.id), "role": "member"},
    )

    await _login(client, other_person.email, OTHER_PASSWORD)
    card = await _create_card(client, board_id, column_id, "De un member")

    assert card["created_by_actor_id"] == str(other_person.id)


async def test_crear_tarjeta_en_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.post(
        f"/api/v1/boards/{board_id}/cards", json={"column_id": column_id, "title": "Intento ajeno"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_crear_tarjeta_en_columna_de_otro_tablero_devuelve_404(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, _, _ = await _board_with_two_columns(client)
    other_board = await _create_board(client, "Otro tablero")
    foreign_column = (await _columns(client, other_board["id"]))[0]

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards",
        json={"column_id": foreign_column["id"], "title": "Columna de otro tablero"},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_crear_tarjeta_titulo_vacio_devuelve_422(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards", json={"column_id": column_id, "title": ""}
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


# --- listado ----------------------------------------------------------------------


async def test_listar_tarjetas_ordenadas_por_columna_y_posicion(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, first_column, last_column = await _board_with_two_columns(client)
    # Se crean a propósito en orden cruzado: el listado no puede depender del orden
    # de creación, sino de (posición de la columna, posición de la tarjeta).
    await _create_card(client, board_id, last_column, "Z en la última")
    await _create_card(client, board_id, first_column, "A en la primera")
    await _create_card(client, board_id, first_column, "B en la primera")

    response = await client.get(f"/api/v1/boards/{board_id}/cards")

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 3
    assert [item["title"] for item in body["items"]] == [
        "A en la primera",
        "B en la primera",
        "Z en la última",
    ]


async def test_listar_tarjetas_filtrando_por_columna(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, first_column, last_column = await _board_with_two_columns(client)
    await _create_card(client, board_id, first_column, "En la primera")
    await _create_card(client, board_id, last_column, "En la última")

    response = await client.get(
        f"/api/v1/boards/{board_id}/cards", params={"column_id": last_column}
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["total"] == 1
    assert [item["title"] for item in body["items"]] == ["En la última"]


async def test_listar_tarjetas_tablero_ajeno_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    await _create_card(client, board_id, column_id)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.get(f"/api/v1/boards/{board_id}/cards")

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- lectura, edición y borrado ---------------------------------------------------


async def test_obtener_tarjeta_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.get(f"/api/v1/boards/{board_id}/cards/{card['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_editar_tarjeta(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id, "Título viejo")

    response = await client.put(
        f"/api/v1/boards/{board_id}/cards/{card['id']}",
        json={"title": "Título nuevo", "description": "Descripción nueva"},
    )

    assert response.status_code == HTTPStatus.OK
    body = response.json()
    assert body["title"] == "Título nuevo"
    assert body["description"] == "Descripción nueva"
    # Editar no mueve: la columna y la posición siguen siendo las de antes.
    assert body["column_id"] == card["column_id"]
    assert body["position"] == card["position"]


async def test_editar_tarjeta_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.put(
        f"/api/v1/boards/{board_id}/cards/{card['id']}", json={"title": "Intento ajeno"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_tarjeta(client: AsyncClient, owner: Person) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)

    response = await client.delete(f"/api/v1/boards/{board_id}/cards/{card['id']}")
    get_response = await client.get(f"/api/v1/boards/{board_id}/cards/{card['id']}")

    assert response.status_code == HTTPStatus.NO_CONTENT
    assert get_response.status_code == HTTPStatus.NOT_FOUND


async def test_borrar_tarjeta_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.delete(f"/api/v1/boards/{board_id}/cards/{card['id']}")

    assert response.status_code == HTTPStatus.NOT_FOUND


# --- movimiento -------------------------------------------------------------------


async def test_mover_tarjeta_a_otra_columna_y_posicion_persiste(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, origin, destination = await _board_with_two_columns(client)
    first = await _create_card(client, board_id, destination, "Ya estaba primera")
    second = await _create_card(client, board_id, destination, "Ya estaba segunda")
    travelling = await _create_card(client, board_id, origin, "Viajera")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{travelling['id']}/move",
        json={"column_id": destination, "position": 1},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    moved = response.json()
    assert moved["column_id"] == destination

    # El orden se conserva al releer, que es lo que de verdad importa: la respuesta
    # sola no demuestra que se haya persistido.
    titles = [card["title"] for card in await _cards_in_column(client, board_id, destination)]
    assert titles == [first["title"], "Viajera", second["title"]]
    assert await _cards_in_column(client, board_id, origin) == []


async def test_mover_tarjeta_dentro_de_la_misma_columna_reordena(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    await _create_card(client, board_id, column_id, "A")
    await _create_card(client, board_id, column_id, "B")
    last = await _create_card(client, board_id, column_id, "C")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{last['id']}/move",
        json={"column_id": column_id, "position": 0},
    )

    assert response.status_code == HTTPStatus.OK
    titles = [card["title"] for card in await _cards_in_column(client, board_id, column_id)]
    assert titles == ["C", "A", "B"]


async def test_mover_tarjeta_con_indice_mayor_que_la_columna_la_deja_al_final(
    client: AsyncClient, owner: Person
) -> None:
    """El índice del cliente puede estar desfasado; se ajusta al tamaño real en vez
    de devolver un 422 por algo que tiene una respuesta obvia."""
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, origin, destination = await _board_with_two_columns(client)
    await _create_card(client, board_id, destination, "Única del destino")
    travelling = await _create_card(client, board_id, origin, "Viajera")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{travelling['id']}/move",
        json={"column_id": destination, "position": 99},
    )

    assert response.status_code == HTTPStatus.OK
    titles = [card["title"] for card in await _cards_in_column(client, board_id, destination)]
    assert titles == ["Única del destino", "Viajera"]


async def test_mover_tarjeta_con_posicion_negativa_devuelve_422(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{card['id']}/move",
        json={"column_id": column_id, "position": -1},
    )

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


async def test_mover_tarjeta_a_columna_de_otro_tablero_devuelve_404(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, column_id)
    other_board = await _create_board(client, "Otro tablero")
    foreign_column = (await _columns(client, other_board["id"]))[0]

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{card['id']}/move",
        json={"column_id": foreign_column["id"], "position": 0},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    still_here = await client.get(f"/api/v1/boards/{board_id}/cards/{card['id']}")
    assert still_here.json()["column_id"] == column_id


async def test_mover_tarjeta_ajena_devuelve_404(
    client: AsyncClient, owner: Person, other_person: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, origin, destination = await _board_with_two_columns(client)
    card = await _create_card(client, board_id, origin)

    await _login(client, other_person.email, OTHER_PASSWORD)
    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{card['id']}/move",
        json={"column_id": destination, "position": 0},
    )

    assert response.status_code == HTTPStatus.NOT_FOUND


async def test_mover_tarjeta_entre_vecinas_sin_hueco_recompacta_la_columna(
    client: AsyncClient, owner: Person, db_session: AsyncSession
) -> None:
    """Insertar siempre en el mismo hueco acaba agotando la precisión del float. Se
    fuerza el caso extremo (dos vecinas en flotantes consecutivos, sin ningún valor
    representable entre ellas) y se comprueba que el movimiento no duplica
    posiciones: recompacta la columna y coloca la tarjeta donde se pidió."""
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, column_id, _ = await _board_with_two_columns(client)
    first = await _create_card(client, board_id, column_id, "A")
    second = await _create_card(client, board_id, column_id, "B")
    travelling = await _create_card(client, board_id, column_id, "C")

    glued = math.nextafter(1.0, math.inf)
    await db_session.execute(
        text("UPDATE cards SET position = :position WHERE id = :id"),
        {"position": 1.0, "id": uuid.UUID(first["id"])},
    )
    await db_session.execute(
        text("UPDATE cards SET position = :position WHERE id = :id"),
        {"position": glued, "id": uuid.UUID(second["id"])},
    )
    # La sesión del test es la misma que usa la app (dependency_overrides), así que
    # hay que invalidar lo que el ORM tenga cacheado tras escribir por SQL directo.
    db_session.expire_all()

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{travelling['id']}/move",
        json={"column_id": column_id, "position": 1},
    )

    assert response.status_code == HTTPStatus.OK, response.text
    cards = await _cards_in_column(client, board_id, column_id)
    assert [card["title"] for card in cards] == ["A", "C", "B"]
    positions = [card["position"] for card in cards]
    assert len(set(positions)) == 3
    assert positions == sorted(positions)


# --- límite WIP -------------------------------------------------------------------


async def test_mover_a_columna_con_wip_lleno_devuelve_409(
    client: AsyncClient, owner: Person
) -> None:
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, origin, _ = await _board_with_two_columns(client)
    limited = await _create_column(client, board_id, "Con límite", wip_limit=1)
    await _create_card(client, board_id, limited["id"], "La que ocupa el hueco")
    travelling = await _create_card(client, board_id, origin, "La que se queda fuera")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{travelling['id']}/move",
        json={"column_id": limited["id"], "position": 0},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert response.json()["detail"] == (
        "No se pueden añadir más tarjetas a «Con límite»: ha alcanzado su límite de 1 tarjetas."
    )
    # Y la tarjeta sigue donde estaba: el rechazo no deja nada a medias.
    unchanged = await client.get(f"/api/v1/boards/{board_id}/cards/{travelling['id']}")
    assert unchanged.json()["column_id"] == origin


async def test_crear_en_columna_con_wip_lleno_devuelve_409(
    client: AsyncClient, owner: Person
) -> None:
    """El límite se aplica también al crear: uno que se puede esquivar creando la
    tarjeta directamente en la columna llena no es un límite."""
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, _, _ = await _board_with_two_columns(client)
    limited = await _create_column(client, board_id, "Con límite", wip_limit=2)
    await _create_card(client, board_id, limited["id"], "Primera")
    await _create_card(client, board_id, limited["id"], "Segunda")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards",
        json={"column_id": limited["id"], "title": "Tercera"},
    )

    assert response.status_code == HTTPStatus.CONFLICT
    assert "límite de 2 tarjetas" in response.json()["detail"]


async def test_mover_dentro_de_la_misma_columna_con_wip_lleno_funciona(
    client: AsyncClient, owner: Person
) -> None:
    """Reordenar dentro de una columna que está en su límite tiene que seguir
    funcionando: la tarjeta ya está contada, y bloquearlo dejaría la columna
    congelada."""
    await _login(client, owner.email, OWNER_PASSWORD)
    board_id, _, _ = await _board_with_two_columns(client)
    limited = await _create_column(client, board_id, "Con límite", wip_limit=2)
    await _create_card(client, board_id, limited["id"], "Primera")
    last = await _create_card(client, board_id, limited["id"], "Segunda")

    response = await client.post(
        f"/api/v1/boards/{board_id}/cards/{last['id']}/move",
        json={"column_id": limited["id"], "position": 0},
    )

    assert response.status_code == HTTPStatus.OK
    titles = [card["title"] for card in await _cards_in_column(client, board_id, limited["id"])]
    assert titles == ["Segunda", "Primera"]


# --- concurrencia real ------------------------------------------------------------
#
# Los dos tests siguientes gestionan sus propias conexiones y sesiones, y hacen
# COMMIT de verdad: la fixture `db_session` de conftest.py mete cada test en un
# SAVEPOINT que siempre se revierte, así que sobre ella dos corrutinas comparten
# transacción y no hay concurrencia que demostrar. Al terminar, limpian sus datos
# (primero el tablero — que arrastra columnas y tarjetas por CASCADE — y después el
# actor, en ese orden porque cards.created_by_actor_id es RESTRICT).


async def _seed_concurrency_board(
    engine: AsyncEngine, *, board_name: str, cards_in_origin: int, wip_limit: int | None
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Devuelve (actor_id, board_id, destination_column_id, card_ids)."""
    # Datos comprometidos de verdad, así que el email tiene que ser único por
    # ejecución: uno fijo colisionaría al repetir el test en local.
    unique_email = f"concurrencia-{uuid.uuid4().hex}@example.com"
    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor = await auth_service.create_person(
            session,
            email=unique_email,
            password="cualquier-cosa-larga-1234",
            display_name="Concurrencia",
        )
        board, _ = await boards_service.create_board(session, actor=actor, name=board_name)
        columns, _ = await columns_service.list_columns(
            session, actor=actor, board_id=board.id, limit=100, offset=0
        )
        origin, destination = columns[0], columns[-1]
        if wip_limit is not None:
            await columns_service.update_column(
                session,
                actor=actor,
                board_id=board.id,
                column_id=destination.id,
                name=destination.name,
                wip_limit=wip_limit,
            )
        card_ids = []
        for index in range(cards_in_origin):
            card = await cards_service.create_card(
                session,
                actor=actor,
                board_id=board.id,
                column_id=origin.id,
                title=f"Tarjeta {index}",
                description=None,
            )
            card_ids.append(card.id)
        return actor.id, board.id, destination.id, card_ids


async def _cleanup(engine: AsyncEngine, *, actor_id: uuid.UUID, board_id: uuid.UUID) -> None:
    async with engine.connect() as cleanup:
        await cleanup.execute(text("DELETE FROM boards WHERE id = :id"), {"id": board_id})
        await cleanup.execute(text("DELETE FROM actors WHERE id = :id"), {"id": actor_id})
        await cleanup.commit()


async def _move_in_own_session(
    engine: AsyncEngine,
    *,
    actor_id: uuid.UUID,
    board_id: uuid.UUID,
    card_id: uuid.UUID,
    column_id: uuid.UUID,
) -> None:
    async with AsyncSession(engine, expire_on_commit=False) as session:
        actor = await actors_repository.get_actor_by_id(session, actor_id)
        assert actor is not None
        await cards_service.move_card(
            session,
            actor=actor,
            board_id=board_id,
            card_id=card_id,
            column_id=column_id,
            position=0,
        )


async def test_movimientos_concurrentes_a_la_misma_columna_no_duplican_ni_pierden_tarjetas(
    engine: AsyncEngine,
) -> None:
    """Cuatro tarjetas se mueven **a la vez** al mismo hueco (índice 0) de la misma
    columna de destino, cada una en su propia sesión y su propia transacción.

    Sin el bloqueo de fila de la columna de destino, las cuatro leerían la columna
    vacía, calcularían la misma posición y chocarían contra el UNIQUE aplazado al
    hacer COMMIT. Con él, cada una calcula sobre lo que la anterior ya comprometió:
    ninguna falla, ninguna tarjeta se pierde y no hay dos posiciones iguales."""
    actor_id, board_id, destination_id, card_ids = await _seed_concurrency_board(
        engine, board_name="Carrera de movimientos", cards_in_origin=4, wip_limit=None
    )
    try:
        results = await asyncio.gather(
            *(
                _move_in_own_session(
                    engine,
                    actor_id=actor_id,
                    board_id=board_id,
                    card_id=card_id,
                    column_id=destination_id,
                )
                for card_id in card_ids
            ),
            return_exceptions=True,
        )
        assert [result for result in results if isinstance(result, BaseException)] == []

        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor = await actors_repository.get_actor_by_id(session, actor_id)
            assert actor is not None
            cards, total = await cards_service.list_cards(
                session,
                actor=actor,
                board_id=board_id,
                column_id=None,
                limit=100,
                offset=0,
            )
            assert total == len(card_ids)  # ninguna tarjeta perdida ni duplicada
            assert {card.id for card in cards} == set(card_ids)
            assert all(card.column_id == destination_id for card in cards)
            positions = [card.position for card in cards]
            assert len(set(positions)) == len(card_ids)  # ninguna posición repetida
    finally:
        await _cleanup(engine, actor_id=actor_id, board_id=board_id)


async def test_movimientos_concurrentes_no_superan_el_limite_wip(engine: AsyncEngine) -> None:
    """Dos movimientos simultáneos hacia una columna con un único hueco libre: uno
    entra y el otro se lleva el 409. Sin el bloqueo, los dos contarían cero tarjetas
    antes de escribir y los dos se colarían."""
    actor_id, board_id, destination_id, card_ids = await _seed_concurrency_board(
        engine, board_name="Carrera contra el WIP", cards_in_origin=2, wip_limit=1
    )
    try:
        results = await asyncio.gather(
            *(
                _move_in_own_session(
                    engine,
                    actor_id=actor_id,
                    board_id=board_id,
                    card_id=card_id,
                    column_id=destination_id,
                )
                for card_id in card_ids
            ),
            return_exceptions=True,
        )
        rejected = [result for result in results if isinstance(result, ConflictError)]
        succeeded = [result for result in results if result is None]
        assert len(succeeded) == 1, results
        assert len(rejected) == 1, results
        assert "ha alcanzado su límite de 1 tarjetas" in rejected[0].message

        async with AsyncSession(engine, expire_on_commit=False) as session:
            actor = await actors_repository.get_actor_by_id(session, actor_id)
            assert actor is not None
            _, total = await cards_service.list_cards(
                session,
                actor=actor,
                board_id=board_id,
                column_id=destination_id,
                limit=100,
                offset=0,
            )
            assert total == 1
    finally:
        await _cleanup(engine, actor_id=actor_id, board_id=board_id)
