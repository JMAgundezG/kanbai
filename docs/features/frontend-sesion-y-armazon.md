# Frontend: sesión y armazón de la aplicación

**Introducida por:** [TASK-07](../tasks/TASK-07-frontend-sesion.md) · **Última actualización:** 2026-08-30

Consume el contrato de autenticación de
[`actores-y-autenticacion.md`](actores-y-autenticacion.md) (`POST /auth/login`,
`POST /auth/logout`, `GET /auth/me`, sesión por cookie httpOnly) para dar acceso
a personas, proteger rutas y pintar el armazón visual común (barra superior)
sobre el que TASK-08 monta el tablero.

## Estructura

```
features/auth/
  api.ts         → authKeys, fetchCurrentActor, login, logout
  hooks.ts       → useCurrentActor, useLogin, useLogout
  components/
    LoginForm.tsx

components/
  ProtectedRoute.tsx   → guardián de rutas, sin UI propia
  AppLayout.tsx        → barra superior (actor + salir), contenedor Tailwind

routes/
  LoginPage.tsx         → pública, /acceso
  HomePage.tsx           → protegida (TASK-02)

lib/
  authEvents.ts         → pub/sub para el 401 centralizado
```

`ProtectedRoute` y `AppLayout` se anidan (guardián primero, armazón visual
después) para que uno resuelva autorización y el otro solo pinte:

```
/acceso                    → LoginPage (pública)
/  (ProtectedRoute)
  └─ (AppLayout)
       └─ index → HomePage
```

## Sesión: fuente de verdad única

`useCurrentActor()` (`useQuery(['auth','me'])`, `retry: false`) es la única
fuente de verdad de "quién ha entrado" — nunca se duplica en `useState`.
`fetchCurrentActor` trata un `401` de `/auth/me` como el estado normal "no hay
sesión" (`null`, no un error de React Query); cualquier otro fallo sí es un
error real (`isError`), para que `ProtectedRoute` pueda distinguir "no hay
sesión → a /acceso" de "el backend no responde → mostrar un aviso", sin
redirigir a ciegas cuando el problema es otro.

`useLogin`/`useLogout` escriben el resultado directamente en la caché
(`queryClient.setQueryData(authKeys.me(), …)`) en vez de invalidar: la
respuesta del propio endpoint ya es el dato que hace falta, así que no hay
razón para otro viaje a `/me`.

## Envío de la cookie de sesión

`api/client.ts` crea el cliente de `openapi-fetch` con `credentials:
'include'`. Sin esto el navegador nunca guarda ni reenvía `kanbai_session`
(httpOnly). En desarrollo todo pasa por el proxy `/api` de Vite → mismo
origen, sin necesidad de CORS con credenciales.

## 401 centralizado

Cualquier respuesta `401` de la API dispara un aviso global, para que ninguna
vista tenga que manejar "la sesión ha caducado" por su cuenta — el criterio
explícito de la tarea.

El obstáculo: `api/client.ts` es un módulo sin componentes React, y la
instancia de `QueryClient` vive dentro de `App` creada con `useState` (deliberado
desde TASK-02, para aislar tests de un singleton de módulo) — así que
`api/client.ts` no tiene ninguna instancia a la que escribir directamente.

Solución: `lib/authEvents.ts` es un pub/sub mínimo sin dependencias de React.
Un middleware de `openapi-fetch` (`onResponse`) llama a `notifyUnauthorized()`
en cualquier `401`; `App` se suscribe una vez, con su propia instancia de
`QueryClient`, y en cada aviso pone `authKeys.me()` a `null`. Cualquier
componente que consulte `useCurrentActor()` (incluido `ProtectedRoute`)
reacciona solo, sin lógica de sesión repartida por las vistas.

## Formulario de acceso

`LoginForm` (HeroUI `Form` + `TextField`/`Label`/`Input` + `Button` + `Alert`)
valida a mano que ambos campos estén rellenos antes de llamar a la API —
deliberadamente sin `isRequired`/validación nativa del navegador, cuyos
mensajes llegan en el idioma del sistema operativo, no en español. El error
del backend en un login inválido (`401`, cuerpo `{"detail": "..."}`) ya viene
en español y se muestra tal cual en un `Alert`.

Tras un acceso correcto, `ProtectedRoute` guarda en el estado de la
navegación la ruta de la que rebotó (`state: { from: location }`); `LoginPage`
lee ese estado y vuelve ahí en vez de ir siempre a `/`.

## No entra en esta feature

Vista del tablero (TASK-08), detalle de tarjeta (TASK-15), gestión de agentes
(TASK-16), registro público de personas, recuperación de contraseña o perfil.
