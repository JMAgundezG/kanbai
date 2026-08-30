# Plan · TASK-07 · Frontend: sesión y armazón de la aplicación

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-07](../tasks/TASK-07-frontend-sesion.md)

## Objetivo

Que una persona pueda entrar en kanbai (pantalla de acceso con email/contraseña),
que la sesión se mantenga entre recargas, que las rutas protegidas redirijan al
acceso cuando no hay sesión, y que exista un armazón visual común (barra superior
con el actor actual y salir) sobre el que TASK-08 montará el tablero.

## Enfoque

Backend ya resuelto (TASK-03): cookie httpOnly `kanbai_session`, endpoints
`POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
Este frontend solo consume ese contrato, generado con `npm run gen:api`.

Patrón de feature ya establecido por `features/health/` (TASK-02):
`api.ts` (fetch tipado + query keys) + `hooks.ts` (TanStack Query) +
`components/` (componente tonto) + `*.test.tsx`. Se replica igual para
`features/auth/`.

Puntos de diseño:
- **Envío de cookies**: `openapi-fetch` no añade `credentials: 'include'` por
  defecto; hay que pasarlo explícito en `createClient` (`api/client.ts`) para que
  el navegador guarde y reenvíe `kanbai_session`. En dev todo va por el proxy de
  Vite (`/api` → `:8000`), mismo origen, así que `credentials: 'include'` basta
  (no hace falta CORS con `Access-Control-Allow-Credentials`).
- **401 centralizado**: un `middleware` de `openapi-fetch` (`onResponse`) detecta
  cualquier 401 de la API y notifica a un pequeño store fuera de React (o invalida
  `['auth','me']` y deja que `ProtectedRoute` reaccione). Se decide el mecanismo
  exacto en la spec; el criterio es que ninguna vista deba manejar el 401 a mano.
- **Sesión con TanStack Query**: `useQuery(['auth','me'])` es la única fuente de
  verdad de "quién ha entrado"; sin duplicarlo en `useState`. `retry: false` (un
  401 no se reintenta) y sin sesión el resultado es simplemente "no autenticado",
  no un error de UI.
- **Rutas protegidas**: un componente `ProtectedRoute` (o `RequireAuth`) que
  envuelve las rutas privadas con React Router, consulta `['auth','me']` y
  redirige a `/acceso` si no hay actor, contemplando el estado de carga inicial
  (para no parpadear a `/acceso` mientras `/auth/me` resuelve la primera vez).
- **Armazón**: se amplía `AppLayout.tsx` existente con una barra superior HeroUI
  que muestra `display_name` del actor y un botón "Salir" (mutación de logout que
  invalida `['auth','me']` y navega a `/acceso`).

## Alcance

- Backend (`backend/src/kanbai/`): **no se toca nada**. TASK-03 ya lo dejó
  completo y probado.
- Frontend (`frontend/src/`):
  - `api/client.ts`: `credentials: 'include'` + middleware de 401.
  - `features/auth/api.ts`, `features/auth/hooks.ts`,
    `features/auth/components/LoginForm.tsx` (+ test).
  - `components/AppLayout.tsx`: barra superior con actor + salir.
  - `components/ProtectedRoute.tsx` (o ubicación equivalente en `routes/`).
  - `routes/LoginPage.tsx`.
  - `App.tsx`: nuevas rutas (`/acceso` pública, resto protegidas).
- Contrato: no cambia el OpenAPI (los endpoints de auth ya existen desde TASK-03)
  pero **sí hay que regenerar** `frontend/src/api/schema.d.ts`, porque hasta ahora
  nunca se ha ejecutado `npm run gen:api` con los endpoints de `auth` presentes
  (la feature de TASK-03 lo dejó anotado explícitamente como pendiente).

## Criterios de aceptación

- [x] Un acceso correcto navega a la vista principal y la sesión sobrevive a recargar.
- [x] Credenciales inválidas muestran el mensaje de error en español, sin pantalla
      en blanco.
- [x] Entrar a una ruta protegida sin sesión redirige al acceso.
- [x] Todos los tipos de datos de la API vienen de `src/api/schema.d.ts`: ninguna
      `interface` escrita a mano que refleje una respuesta.
- [x] `npm run check` en verde.

## Plan de verificación

- Frontend: `npm run check` desde `frontend/` (eslint + tsc + vitest) y
  `npm run build`.
- End-to-end: backend real levantado (`uv run poe dev`), una persona de prueba
  creada vía `auth_service.create_person` (mismo patrón que
  `backend/tests/test_auth.py`), navegador headless (Chrome) verificando acceso,
  persistencia de sesión tras recargar, y logout.
- Verificación visual de capas CSS (`docs/features/estilos-frontend.md`): captura
  headless de `/acceso` y de la vista protegida, comprobando aspecto propio de
  HeroUI y que el contenedor no pega al borde.

## Riesgos / decisiones abiertas

- Mecanismo exacto del "manejo centralizado del 401" (evento global vs.
  invalidación de query vs. `QueryCache` `onError`): se fija en la spec.
- Nombre y ubicación exacta de `ProtectedRoute` (`components/` vs. `routes/`): se
  fija en la spec, siguiendo la regla de que solo lo compartido entre features
  vive en `components/`.
