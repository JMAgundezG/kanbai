# TASK-09 · Agentes como actores: alta y API keys

**Prioridad:** Alta · **Depende de:** TASK-03

## Objetivo

La tarea que convierte a kanbai en lo que dice ser. Un agente se da de alta como actor,
recibe una API key y, a partir de ahí, **usa exactamente los mismos endpoints que una
persona** con los mismos permisos que quien lo creó. Ninguna ruta nueva de dominio:
solo una segunda forma de identificarse.

## Alcance

**Entra:**
- Datos propios del actor de tipo agente (nombre, descripción, persona propietaria).
- Emisión de API key: se guarda **hasheada**, el valor en claro se devuelve una sola vez.
- Autenticación por `Authorization: Bearer <key>` integrada en `CurrentActor`, junto a
  la sesión de personas.
- Revocación de keys y endpoints de gestión bajo `/api/v1/agents`.
- Migración revisada y tests: key válida, key revocada, key inexistente, alcance de
  permisos.

**No entra:**
- Cola de trabajo y endpoints pensados para consumo automático (TASK-13).
- Reclamación de tarjetas (TASK-10).
- Interfaz de gestión de agentes (TASK-16).
- Límite de peticiones por key.

## Criterios de aceptación

- [ ] Con una key válida, un agente llama a los endpoints de tableros y tarjetas y las
      acciones quedan atribuidas a él como actor.
- [ ] Una key revocada o inexistente devuelve `401`.
- [ ] La key en claro se devuelve **solo** en la respuesta de creación y no aparece en
      ningún log, traza ni otra respuesta.
- [ ] Un agente solo ve los tableros de los que es miembro; el resto, **404**.
- [ ] Un agente no puede acceder a nada a lo que su persona propietaria no llegue.
- [ ] Ningún servicio ni router ramifica por el tipo de actor para funcionar.
- [ ] `uv run poe check` en verde.

## Notas técnicas

- El hash de la key debe permitir búsqueda eficiente: la spec define el esquema
  (prefijo identificador en claro + secreto hasheado, o equivalente).
- Es el momento de verificar la invariante de `CLAUDE.md` § 0 sobre todo lo construido
  en TASK-04 a TASK-06.
