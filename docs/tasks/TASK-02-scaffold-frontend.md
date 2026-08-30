# TASK-02 · Scaffold del frontend (Vite + React 19 + HeroUI + Bootstrap grid)

**Prioridad:** Alta · **Depende de:** TASK-01

## Objetivo

Dejar `frontend/` funcionando como una SPA React con el sistema de componentes
HeroUI v3 sobre Tailwind v4, la rejilla de Bootstrap para el layout, el cliente de
API tipado desde el OpenAPI del backend y la batería de calidad (eslint, tsc,
vitest) descritos en `CLAUDE.md`.

## Alcance

**Entra:**
- Proyecto Vite + React 19 + TypeScript con alias `@/` → `src/`.
- Tailwind v4 (`@tailwindcss/vite`) + `@heroui/react` + `@heroui/styles`.
- Bootstrap **solo la rejilla** (`bootstrap-grid.css`) en su propia cascade layer,
  por debajo de Tailwind (ver `CLAUDE.md` § Frontend).
- `npm run gen:api` → `src/api/schema.d.ts` generado con `openapi-typescript` desde
  el OpenAPI del backend, y cliente `openapi-fetch` tipado.
- TanStack Query configurado, React Router con una ruta raíz de prueba.
- Vitest + Testing Library con un test de humo.
- Proxy de `/api` al backend en `vite.config.ts` para desarrollo.

**No entra:**
- Pantallas del kanban y su estado de arrastrar/soltar.
- Pantalla de login.

## Criterios de aceptación

- [x] `npm run dev` levanta la app y renderiza una página con un componente HeroUI
      correctamente estilado (verifica que Tailwind y HeroUI cargan).
- [x] Una fila `.row` / `.col-*` de Bootstrap maqueta correctamente y **no** rompe
      los estilos de HeroUI (sin importar Reboot).
- [x] `npm run gen:api` regenera `src/api/schema.d.ts` con el backend levantado.
- [x] `npm run check` (eslint + tsc + vitest) pasa en verde.
- [x] `npm run build` produce un bundle sin errores ni warnings de TypeScript.

## Notas técnicas

- HeroUI v3 **no** necesita `<Provider>`; el orden de imports en el CSS global sí
  importa (`tailwindcss` antes que `@heroui/styles`).
- El tema (claro/oscuro) se controla con la clase de HeroUI en `<html>`.
