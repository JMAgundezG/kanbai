# Plan · TASK-02 · Scaffold del frontend (Vite + React 19 + HeroUI + Bootstrap grid)

**Estado:** Completada · **Fase:** Cerrada · **Iniciado:** 2026-08-30 · **Cerrado:** 2026-08-30 · **Responsable:** Claude
**Tarea:** [TASK-02](../tasks/TASK-02-scaffold-frontend.md)

> **Desbloqueada:** TASK-01 se cerró el 2026-08-30 y dejó `backend/openapi.json`
> commiteado, que es justo lo que esta tarea necesita para generar tipos. El plan se
> escribió por adelantado y se ha revisado al arrancar: sigue siendo válido; los puntos
> 3 y 2 de "riesgos" quedan resueltos en la spec.

## Objetivo

Dejar `frontend/` como una SPA React 19 ejecutable y verificable, con HeroUI v3 sobre
Tailwind v4 como sistema de componentes, la rejilla de Bootstrap para maquetar, el
cliente de API **tipado desde el OpenAPI del backend** y la puerta de calidad
`npm run check` en verde. No implementa pantallas de producto: implementa el esqueleto
que las features consumirán.

## Enfoque

Igual que en el backend, un esqueleto **vertical y demostrado**: una ruta que llama de
verdad a `GET /health` a través del cliente generado y de TanStack Query, y la renderiza
con componentes HeroUI dentro de una rejilla Bootstrap. Si eso funciona, están probadas
de una vez las cuatro piezas de riesgo (tipos generados, capa de datos, estilos y
rejilla).

Decisiones de partida y por qué:

- **Tailwind v4 vía plugin de Vite** (`@tailwindcss/vite`), no PostCSS: es la vía
  recomendada en v4 y evita un `postcss.config` que nadie más necesita.
- **Orden de CSS explícito con cascade layers**, tal y como fija `CLAUDE.md` § 5:
  `@layer bootstrap, theme, base, components, utilities;` primero, luego
  `bootstrap-grid.css` dentro de `layer(bootstrap)`, luego `tailwindcss` y por último
  `@heroui/styles`. Bootstrap queda **por debajo** y no puede pisar a HeroUI.
- **Solo `bootstrap-grid.css`**: sin Reboot (chocaría con el preflight de Tailwind) y
  sin utilidades (duplicarían a Tailwind con otro vocabulario).
- **Contrato generado, no escrito**: `openapi-typescript` produce `src/api/schema.d.ts`
  y `openapi-fetch` da un cliente tipado con ese esquema. Cero interfaces a mano.
- **TanStack Query** para todo el estado de servidor, con las claves jerárquicas de
  `CLAUDE.md`. El `QueryClient` se crea en `main.tsx`.
- **Vitest + Testing Library** con entorno jsdom; el test de humo comprueba lo que ve el
  usuario, con la API mockeada en la capa de red (MSW o un mock del cliente, se decide
  en la spec).
- **Proxy `/api` → `:8000` en `vite.config.ts`**, para que en desarrollo no haya CORS ni
  URLs absolutas repartidas por el código.
- HeroUI v3 **no lleva `<Provider>`**; el único punto de configuración global es el CSS
  y el tema en `<html>`.

Alternativas descartadas: Bootstrap completo (rompe HeroUI, ver `CLAUDE.md` § 5),
escribir a mano los tipos de la API (se desincroniza en la primera semana), y usar
`fetch` + `useEffect` en lugar de TanStack Query.

## Alcance

- **Frontend (`frontend/`)** — todo el trabajo está aquí:
  - Proyecto Vite (plantilla `react-ts`), `tsconfig` en `strict`, alias `@/` → `src/`.
  - `src/styles/global.css` con el orden de capas de `CLAUDE.md` § 5.
  - `src/api/` — `schema.d.ts` (generado) y `client.ts` (`openapi-fetch` tipado).
  - `src/main.tsx` / `App.tsx` — `QueryClientProvider`, router y layout base.
  - `src/routes/` — una ruta raíz que muestra el estado del backend.
  - `src/features/`, `src/components/`, `src/lib/` — creados con la convención fijada.
  - Scripts `dev`, `build`, `lint`, `typecheck`, `test`, `check`, `gen:api`.
  - eslint (flat config) + configuración de Vitest y Testing Library.
- **Backend:** no se toca. Solo se **consume** su OpenAPI.
- **Contrato:** esta tarea es la que estrena el flujo
  `response_model → /openapi.json → npm run gen:api → schema.d.ts → tsc`.

## Criterios de aceptación

- [x] `npm run dev` levanta la app y renderiza una página con un componente HeroUI
      correctamente estilado (verifica que Tailwind y HeroUI cargan).
- [x] Una fila `.row` / `.col-*` de Bootstrap maqueta correctamente y **no** rompe los
      estilos de HeroUI (sin importar Reboot).
- [x] `npm run gen:api` regenera `src/api/schema.d.ts` con el backend levantado.
- [x] `npm run check` (eslint + tsc + vitest) pasa en verde.
- [x] `npm run build` produce un bundle sin errores ni warnings de TypeScript.

## Plan de verificación

- `npm run gen:api` contra el backend de TASK-01 y `git diff` sobre `schema.d.ts` para
  comprobar que el archivo se genera entero y no se toca a mano.
- `npm run check` desde `frontend/`, con la salida real pegada en el reporte.
- `npm run build` para confirmar que no hay errores solo visibles en producción.
- **Verificación visual obligatoria** (es el riesgo principal de la tarea): con
  `npm run dev` levantado, comprobar en el navegador que un `Button` de HeroUI tiene su
  aspecto propio y que una rejilla `.row`/`.col-6` reparte el ancho. Un fallo de capas
  CSS no lo detecta ningún test automático.

## Riesgos / decisiones abiertas

1. **El choque Bootstrap ↔ Tailwind/HeroUI es el riesgo real de esta tarea.** La receta
   de capas de `CLAUDE.md` § 5 está pensada para evitarlo, pero hay que confirmarla en
   el navegador. Si aun así aparecen conflictos, la salida es reducir Bootstrap a las
   clases de rejilla que de verdad se usen, no relajar HeroUI.
2. **Versiones mayores recientes**: React Router 8 y Vite 8 son saltos de major
   recientes; en la spec se fijan versiones concretas y se revisa su guía de migración
   antes de escribir código.
3. **`gen:api` con backend levantado vs. archivo volcado**: si TASK-01 incluye
   `poe openapi` (ver su plan, punto 4), este script leerá el archivo y no necesitará el
   servidor. Queda a expensas de esa decisión.
4. **Mock de red en los tests**: MSW da más fidelidad, un mock del cliente es menos
   dependencia. Se decide en la spec.
5. **Tema claro/oscuro**: se deja el conmutador para una tarea de producto; aquí solo se
   fija dónde vive la clase de tema en `<html>`.
