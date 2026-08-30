# Spec · TASK-07 · Frontend: sesión y armazón de la aplicación

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-07](plan-TASK-07.md) · **Tarea:** [TASK-07](../tasks/TASK-07-frontend-sesion.md)

## Backend

Sin cambios. `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`,
`GET /api/v1/auth/me` ya existen desde TASK-03 (ver
`docs/features/actores-y-autenticacion.md`). Único paso necesario:
`npm run gen:api` en `frontend/`, porque hasta ahora nadie lo había ejecutado con
estos endpoints presentes en `backend/openapi.json`.

## Contrato consumido

- `POST /api/v1/auth/login` — body `LoginRequest {email, password}` → `200
  ActorRead` + `Set-Cookie: kanbai_session` (httpOnly), o `401` con cuerpo
  `{"detail": "El email o la contraseña no son correctos."}`.
- `POST /api/v1/auth/logout` — sin body → `204`. Idempotente.
- `GET /api/v1/auth/me` — `200 ActorRead`, o `401` con cuerpo
  `{"detail": "No has iniciado sesión."}`.
- `ActorRead {id, kind, display_name, created_at}`.

Todos los tipos se importan de `components['schemas']` en
`src/api/schema.d.ts` tras `npm run gen:api`. Ninguna interfaz a mano.

## Frontend (`frontend/src/`)

### `lib/authEvents.ts` (nuevo)

Pub/sub mínimo, sin dependencias de React ni de TanStack Query, para desacoplar
`api/client.ts` (que no tiene acceso a la instancia de `QueryClient`, creada
dentro de `App` con `useState`) del resto de la aplicación:

```ts
type Listener = () => void

const listeners = new Set<Listener>()

export function onUnauthorized(listener: Listener): () => void {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

export function notifyUnauthorized(): void {
  for (const listener of listeners) listener()
}
```

### `api/client.ts` (editado)

- `createClient<paths>({ baseUrl, fetch, credentials: 'include' })`: sin esto el
  navegador no guarda ni reenvía la cookie httpOnly de sesión. Mismo origen en
  dev gracias al proxy de Vite, así que no hace falta CORS con credenciales.
- Middleware `onResponse`: si `response.status === 401`, llama a
  `notifyUnauthorized()`. Se dispara para **cualquier** endpoint (incluido
  `/auth/me`, que es la vía normal de detectar "no hay sesión"), no solo para
  endpoints futuros protegidos — es intencional y no tiene efecto adverso:
  volver a marcar la sesión como ausente cuando ya lo estaba es un no-op.

### `App.tsx` (editado)

Se suscribe una vez, con la instancia real de `QueryClient` creada por
`useState(createQueryClient)` (no se toca ese patrón, deliberado desde TASK-02
para aislar tests):

```ts
useEffect(
  () => onUnauthorized(() => queryClient.setQueryData(authKeys.me(), null)),
  [queryClient],
)
```

Rutas (React Router 8, `createBrowserRouter`):

```
/acceso                    → LoginPage (pública)
/  (ProtectedRoute)
  └─ (AppLayout)
       └─ index → HomePage
```

`ProtectedRoute` es el guardián (sin UI propia salvo carga/redirección);
`AppLayout` es el armazón visual (barra superior). Separados a propósito: uno
resuelve autorización, el otro solo pinta.

### `features/auth/api.ts` (nuevo)

- `export type Actor = components['schemas']['ActorRead']`.
- `authKeys = { all: ['auth'] as const, me: () => [...authKeys.all, 'me'] as const }`.
- `fetchCurrentActor(): Promise<Actor | null>` — `GET /auth/me`; `401` se
  interpreta como "no hay sesión" y devuelve `null` (no es un error de UI);
  cualquier otro fallo lanza `Error` con mensaje en español.
- `login(credentials): Promise<Actor>` — `POST /auth/login`; en `401` extrae
  `detail` del cuerpo de error (ya viene en español desde el backend) y lo lanza
  como `Error`; con `detail` ausente, mensaje de reserva en español.
- `logout(): Promise<void>` — `POST /auth/logout`; lanza `Error` en español si
  la respuesta no es `ok` (caso extremo: nunca debería fallar según el backend,
  pero la vista no debe quedar en blanco si ocurre).

### `features/auth/hooks.ts` (nuevo)

- `useCurrentActor()` — `useQuery({ queryKey: authKeys.me(), queryFn:
  fetchCurrentActor, retry: false })`. `retry: false` porque un `401` no es
  transitorio.
- `useLogin()` — `useMutation`; `onSuccess` escribe el actor devuelto
  directamente en caché con `queryClient.setQueryData(authKeys.me(), actor)`
  (evita un round-trip extra a `/me`).
- `useLogout()` — `useMutation`; `onSuccess` pone `authKeys.me()` a `null` en
  caché.

### `features/auth/components/LoginForm.tsx` (nuevo, + test)

Componente tonto con estado de formulario local (email, password — no son
estado de servidor, no van en TanStack Query) y la mutación de `useLogin` desde
fuera vía hook. HeroUI: `Form`, `TextField` + `Label` + `Input`, `Button`,
`Alert` para el error. Validación de formulario: si al enviar falta email o
contraseña, mensaje propio en español ("Introduce tu email y tu contraseña.")
sin llamar a la API — se evita depender de los mensajes de validación nativos
del navegador, que llegan en el idioma del sistema, no en español.

Tras un login correcto, navega (React Router `useNavigate`) a la ruta de la que
venía (`location.state.from`, si `ProtectedRoute` redirigió aquí) o a `/`.

### `components/ProtectedRoute.tsx` (nuevo, + test)

```tsx
export function ProtectedRoute() {
  const { data: actor, isPending } = useCurrentActor()
  const location = useLocation()

  if (isPending) return <estado de carga centrado, Spinner de HeroUI>
  if (!actor) return <Navigate to="/acceso" replace state={{ from: location }} />
  return <Outlet />
}
```

### `components/AppLayout.tsx` (editado)

Se añade a la barra superior existente: `display_name` del actor (de
`useCurrentActor`) y un botón "Salir" (HeroUI `Button`, variante secundaria)
que dispara `useLogout().mutate()` y, en `onSuccess`, navega a `/acceso`.
El contenedor de página sigue siendo el de Tailwind (`estilos-frontend.md`), no
`.container` de Bootstrap.

### `routes/LoginPage.tsx` (nuevo)

Contenedor centrado (Tailwind) con `<LoginForm />` dentro de una `Card` de
HeroUI, título "Acceder a kanbai".

## Casos límite y errores

- **Recarga con sesión activa**: `useCurrentActor` vuelve a pedir `/me` al
  montar `App`; la cookie httpOnly va sola en la petición (`credentials:
  'include'`), sin estado en `localStorage`. Sesión "sobrevive a recargar" por
  construcción, no por persistencia manual.
- **Backend caído en `/me`**: `fetchCurrentActor` lanza (no es `401`, es un
  fallo real) → `useCurrentActor` queda en `isError`. `ProtectedRoute` debe
  distinguir "cargando" / "sin sesión" (`data === null`) / "error real"
  (`isError`) para no redirigir a ciegas cuando el problema es que el backend
  no responde: en ese caso se muestra un `Alert` de error en vez de redirigir
  (evita el bucle "backend caído → parece que no hay sesión → a por el login →
  el login también falla" sin explicación).
- **Doble submit del formulario**: botón deshabilitado mientras
  `loginMutation.isPending`.
- **Logout con sesión ya caída** (cookie expiró entre que se pintó la barra y
  que se pulsó "Salir"): el backend responde `204` igualmente (idempotente);
  el frontend no necesita distinguir el caso.
- **`ProtectedRoute` sin sesión, ruta profunda** (`/tableros/1`, futura): se
  guarda `location` completa en el estado de la navegación para poder volver
  tras el login.

## Plan de tests

`frontend/src/**/*.test.tsx` con Testing Library, siguiendo el patrón de
`BackendStatusCard.test.tsx` (mock de `globalThis.fetch`, sin red real):

- `features/auth/components/LoginForm.test.tsx`:
  - Acceso correcto: `fetch` responde `200` con un `ActorRead`; tras enviar el
    formulario, se llama a la navegación (se puede envolver en
    `MemoryRouter`/mock de `useNavigate`) — o, más simple, verificar que
    `authKeys.me()` queda con el actor en la caché de un `QueryClient` de
    prueba tras el submit.
  - Credenciales inválidas: `fetch` responde `401` con
    `{"detail": "El email o la contraseña no son correctos."}`; se ve ese
    texto exacto en pantalla, sin pantalla en blanco.
  - Validación local: enviar con campos vacíos muestra el mensaje propio y no
    llama a `fetch`.
- `components/ProtectedRoute.test.tsx`:
  - Sin sesión (`fetch` a `/me` responde `401`): se redirige a `/acceso`
    (usando `MemoryRouter` con rutas `/` protegida y `/acceso`, comprobando
    que el contenido de `/acceso` es el que se renderiza).
  - Con sesión (`fetch` a `/me` responde `200`): se renderiza el `Outlet`
    (contenido protegido visible).
- Verificación end-to-end manual (fuera de Vitest): backend real levantado,
  persona de prueba creada con `auth_service.create_person` (mismo patrón que
  `backend/tests/test_auth.py`), navegador headless.

## Desviaciones respecto al plan

- El plan dejaba abierto el mecanismo del 401 centralizado entre "evento
  global" e "invalidación de query". Se resuelve como **evento global**
  (`lib/authEvents.ts`) precisamente porque `api/client.ts` no tiene, ni debe
  tener, una referencia a la instancia de `QueryClient` (que vive dentro de
  `App` vía `useState`, no como singleton de módulo) — mantiene el patrón de
  aislamiento de tests que TASK-02 dejó documentado en el propio `App.tsx`.
- `ProtectedRoute` se ubica en `components/`, no en `routes/`, porque no es una
  página: no tiene URL propia ni contenido visible; es infraestructura de
  enrutado compartida, igual que `AppLayout`.
- **Encontrado en code review:** el middleware de `api/client.ts` no debe
  disparar `notifyUnauthorized()` para un `401` de `POST /auth/login` — ese
  `401` es "credenciales incorrectas", no "la sesión ha caducado", y
  dispararlo igualmente borraría de la caché una sesión real y válida de
  quien lo intenta (p. ej. una persona ya autenticada en otra pestaña que
  navega a `/acceso` por error y teclea mal la contraseña). Se excluye por
  `schemaPath === '/api/v1/auth/login'`; test de regresión en
  `api/client.test.ts`.
