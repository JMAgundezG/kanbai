# Spec · TASK-02 · Scaffold del frontend (Vite + React 19 + HeroUI + Bootstrap grid)

**Estado:** Completada · **Fase:** Cerrada · **Creada:** 2026-08-30 · **Cerrado:** 2026-08-30
**Plan:** [plan-TASK-02](plan-TASK-02.md) · **Tarea:** [TASK-02](../tasks/TASK-02-scaffold-frontend.md)

## Decisiones cerradas

| Decisión | Resolución | Por qué |
|----------|------------|---------|
| Versión de TypeScript | **`~6.0.3`**, no la 7 | `typescript-eslint@8.68` declara `typescript >=4.8.4 <6.1.0`. Con TS 7 el linter queda fuera de juego, y `npm run check` sin lint no es una puerta |
| Origen del OpenAPI | `../backend/openapi.json` (commiteado por TASK-01) | `npm run gen:api` no necesita servidor ni base de datos, ni en local ni en CI |
| Mock de red en tests | `vi.spyOn(globalThis, "fetch")`, **sin MSW** | Hay un endpoint. `CLAUDE.md` § 7: preferimos lo que ya está antes que una dependencia nueva. Si el mockeo crece, MSW se justifica en su propia tarea |
| Router | `createBrowserRouter` + `RouterProvider` (data router) | Verificado que React Router 8.3 mantiene esta API; es la que soporta *loaders* si más adelante hacen falta |

---

## Árbol de archivos a crear

```
frontend/
├── .env.example              # VITE_API_BASE_URL
├── .gitignore
├── eslint.config.js          # flat config
├── index.html
├── package.json
├── package-lock.json         # se commitea
├── tsconfig.json / tsconfig.app.json / tsconfig.node.json
├── vite.config.ts            # plugins, alias, proxy, config de Vitest
└── src/
    ├── main.tsx              # QueryClientProvider + RouterProvider
    ├── App.tsx               # layout raíz
    ├── vite-env.d.ts
    ├── setupTests.ts         # jest-dom
    ├── styles/global.css     # capas: bootstrap → tailwind → heroui
    ├── api/
    │   ├── schema.d.ts       # GENERADO — no se edita a mano
    │   └── client.ts         # openapi-fetch tipado con schema.d.ts
    ├── lib/queryClient.ts
    ├── components/AppLayout.tsx
    ├── features/health/
    │   ├── api.ts            # llamada + queryKey
    │   ├── hooks.ts          # useBackendStatus()
    │   └── components/BackendStatusCard.tsx
    │   └── components/BackendStatusCard.test.tsx
    └── routes/HomePage.tsx
```

---

## Dependencias

**Producción:** `react@^19.2`, `react-dom@^19.2`, `@heroui/react@^3.2`,
`@heroui/styles@^3.2`, `tailwindcss@^4.3`, `bootstrap@^5.3`,
`@tanstack/react-query@^5.102`, `react-router@^8.3`, `openapi-fetch@^0.17`.

**Desarrollo:** `vite@^8.2`, `@vitejs/plugin-react@^6.1`, `@tailwindcss/vite@^4.3`,
`typescript@~6.0.3`, `typescript-eslint@^8.68`, `eslint@^10.9`,
`eslint-plugin-react-hooks`, `vitest@^4.1`, `jsdom@^30`,
`@testing-library/react@^16.3`, `@testing-library/jest-dom@^7`,
`@testing-library/user-event`, `openapi-typescript@^7.13`, `@types/node`,
`@types/react`, `@types/react-dom`.

HeroUI declara como *peer* `react-aria`, `react-aria-components@^1.20` y tres paquetes
`@react-aria/*`. npm los instala solo, pero **hay que confirmarlo con `npm ls
react-aria-components`**: si faltaran, los componentes fallan en tiempo de ejecución con
errores poco descriptivos.

---

## Configuración

### `src/styles/global.css` — el archivo de más riesgo de la tarea

El orden es lo único que impide que Bootstrap pise a HeroUI:

```css
@layer bootstrap, theme, base, components, utilities;

/* Solo la rejilla. bootstrap.css completo trae Reboot y rompe HeroUI. */
@import "bootstrap/dist/css/bootstrap-grid.css" layer(bootstrap);

@import "tailwindcss";
@import "@heroui/styles";
```

`tailwindcss` **antes** que `@heroui/styles` (lo exige la documentación de HeroUI), y
Bootstrap en una capa declarada primero, que por las reglas de cascade layers pierde
frente a todo lo posterior. Nada de `bootstrap.css`, `bootstrap-reboot.css`,
`bootstrap-utilities.css` ni el JS de Bootstrap.

### `vite.config.ts`

- Plugins: `react()` y `tailwindcss()` (el plugin de Vite, no PostCSS).
- `resolve.alias`: `@` → `./src`, con el `paths` equivalente en `tsconfig.app.json`.
- `server.proxy`: `/api` → `http://localhost:8000`, `changeOrigin: true`. Evita CORS y
  URLs absolutas en el código.
- Bloque `test` (se importa `defineConfig` de `vitest/config`): `environment: "jsdom"`,
  `globals: true`, `setupFiles: ["./src/setupTests.ts"]`, `css: false`.

### `package.json` — scripts

| Script | Comando |
|--------|---------|
| `dev` | `vite` |
| `build` | `tsc --noEmit && vite build` |
| `lint` | `eslint .` |
| `typecheck` | `tsc --noEmit` |
| `test` | `vitest run` |
| `check` | `npm run lint && npm run typecheck && npm run test` |
| `gen:api` | `openapi-typescript ../backend/openapi.json -o src/api/schema.d.ts` |

### `tsconfig.app.json`

`strict: true`, `noUnusedLocals`, `noUnusedParameters`,
`noFallthroughCasesInSwitch`, `verbatimModuleSyntax`, `jsx: "react-jsx"`,
`moduleResolution: "bundler"`, `baseUrl: "."` + `paths: {"@/*": ["src/*"]}`.

### `eslint.config.js`

Flat config: `js.configs.recommended`, `tseslint.configs.recommendedTypeChecked`,
`react-hooks` (`recommended-latest`) y `react-refresh`. `src/api/schema.d.ts` se
**ignora**: es generado y no tiene sentido lintarlo.

---

## Frontend (`frontend/src/`)

### Tipos

Todo lo que venga de la API se tipa desde `src/api/schema.d.ts`, generado con
`npm run gen:api`. Ni una `interface` escrita a mano que refleje una respuesta.

```ts
// src/api/client.ts
import createClient from "openapi-fetch";
import type { paths } from "@/api/schema";

// Cadena vacía en desarrollo: las rutas salen del mismo origen y el proxy de Vite
// las manda al backend. En un despliegue con dominios distintos se fija la variable.
export const apiClient = createClient<paths>({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "",
});
```

### Capa de datos (`features/health/`)

```ts
// api.ts
export const healthKeys = {
  all: ["health"] as const,
  readiness: () => [...healthKeys.all, "ready"] as const,
};

export type Readiness =
  paths["/api/v1/health/ready"]["get"]["responses"][200]["content"]["application/json"];

export async function fetchReadiness(): Promise<Readiness> { … }
```

`fetchReadiness` usa `apiClient.GET("/api/v1/health/ready")`. **Detalle que importa:**
readiness responde 503 con cuerpo válido cuando la base de datos está caída;
`openapi-fetch` devuelve `{data, error}` sin lanzar, así que la función lanza un `Error`
explícito si no hay `data`, para que TanStack Query lo trate como error de verdad.

```ts
// hooks.ts
export function useBackendStatus() {
  return useQuery({ queryKey: healthKeys.readiness(), queryFn: fetchReadiness });
}
```

Solo se consume `/api/v1/health/ready`. `/health` (liveness) existe en el OpenAPI pero
**no se llama desde la UI**: está fuera de `/api`, el proxy no lo cubre, y es una sonda
para el orquestador, no información de producto.

### UI

- `components/AppLayout.tsx` — cabecera + `<main>` con `.container` de Bootstrap y un
  `<Outlet />`.
- `routes/HomePage.tsx` — una `.row` con dos `.col-md-6`: una columna con
  `<BackendStatusCard />` y otra con texto de bienvenida. La rejilla existe para
  demostrar que Bootstrap maqueta sin romper nada.
- `features/health/components/BackendStatusCard.tsx` — componente tonto: recibe el
  resultado del hook y solo renderiza. Los tres estados que exige `CLAUDE.md` § 5:

| Estado | Componente HeroUI |
|--------|-------------------|
| Cargando | `Spinner` |
| Error | `Alert` con tono de error y texto en español |
| Con datos | `Card` (`Card.Header` / `Card.Content`) con un `Chip` verde/rojo |

Componentes verificados en el paquete: `button`, `card`, `chip`, `alert`, `spinner`,
`empty-state`, `skeleton` y otros 60. HeroUI v3 **no lleva `<Provider>`**: basta con el
CSS. El tema claro/oscuro se controla en `<html>` y se deja para una tarea de producto.

### `main.tsx`

`QueryClientProvider` (con el `QueryClient` de `lib/queryClient.ts`) envolviendo un
`RouterProvider` con `createBrowserRouter([{ path: "/", element: <AppLayout />,
children: [{ index: true, element: <HomePage /> }] }])`. `React.StrictMode` activo.

---

## Contrato API

Esta tarea **no cambia el backend**: consume el contrato que TASK-01 dejó cerrado.

```
GET /api/v1/health/ready  →  200 {"status":"ok","database":"ok"}
                          →  503 {"status":"error","database":"error"}
```

`src/api/schema.d.ts` se genera desde `../backend/openapi.json` y **no se edita jamás**.
Si `tsc` se queja de un campo, la respuesta correcta es mirar el backend, no tocar el
archivo generado.

---

## Casos límite y errores

| Caso | Comportamiento esperado |
|------|-------------------------|
| Backend apagado | La tarjeta muestra `Alert` de error en español, no una pantalla en blanco |
| Base de datos caída (503 con cuerpo válido) | Se trata como **error**, no como dato: `fetchReadiness` lanza si no hay `data` |
| `schema.d.ts` desactualizado | `npm run typecheck` falla; se arregla con `npm run gen:api`, nunca a mano |
| Build de producción | El proxy de Vite **no existe** fuera de `npm run dev`: hay que fijar `VITE_API_BASE_URL` o servir front y API en el mismo origen. Documentado en `.env.example` |
| Reintentos de TanStack Query en tests | El wrapper de test crea el `QueryClient` con `retry: false`; si no, el estado de error tarda segundos en aparecer |
| `StrictMode` en desarrollo | Doble render de efectos; no debe provocar doble petición visible (TanStack Query deduplica) |

---

## Plan de tests

`src/features/health/components/BackendStatusCard.test.tsx`, con un helper que renderiza
dentro de un `QueryClientProvider` con `retry: false` y `fetch` interceptado con
`vi.spyOn(globalThis, "fetch")`:

| Test | Comprueba |
|------|-----------|
| `muestra el estado cuando la API responde` | Tras resolver, aparece el texto del estado "ok" (por rol y texto, no por clase CSS) |
| `muestra un aviso de error si la API falla` | Con `fetch` rechazando, aparece el `Alert` con mensaje en español |
| `muestra el indicador de carga mientras espera` | Antes de resolver, el `Spinner` es visible |

Nada de snapshots grandes ni de aserciones sobre clases de Tailwind: se prueba lo que ve
el usuario (`getByRole`, `getByText`).

### Verificación no automatizable

Un fallo de capas CSS **no lo detecta ningún test**. Por eso, con `npm run dev`
levantado y el backend en marcha, hay que comprobar en el navegador:

1. Un `Button` de HeroUI tiene su aspecto propio (si Tailwind o `@heroui/styles` no
   cargan, se ve un botón del sistema sin estilo).
2. La `.row` con dos `.col-md-6` reparte el ancho al 50 % y colapsa en móvil.
3. La tarjeta muestra `database: ok`; parando la base de datos (`docker compose stop
   db`) pasa al estado de error sin pantalla en blanco.

---

## Desviaciones respecto al plan

1. **TypeScript queda en `~5.9.3`**, no en `~6.0.3` como decía esta spec. Al instalar
   aparece una segunda restricción que no había visto: `openapi-typescript@7.13` exige
   `typescript@^5.x` (en **todas** sus versiones publicadas). Cruzada con
   `typescript-eslint` (`>=4.8.4 <6.1.0`), la única familia que satisface a las dos es
   la 5.x. Se sube cuando `openapi-typescript` soporte TS 6.
   *Observación:* el template oficial de Vite 8 pinea `typescript ~6.0.2`, así que este
   choque lo hereda cualquiera que añada `openapi-typescript` a un proyecto Vite nuevo.
2. **MSW descartado** en favor de espiar `fetch`. El plan lo dejaba abierto.
3. **`gen:api` lee el archivo commiteado**, no el servidor: TASK-01 incluyó `poe openapi`
   y dejó `backend/openapi.json` versionado, lo que resuelve el punto 3 de los riesgos
   del plan.
4. **La UI no consume `/health`**, solo `/api/v1/health/ready`. Liveness está fuera de
   `/api`, el proxy no lo cubre y no es información de producto.
5. **El template de Vite 8 ya no trae eslint, sino `oxlint`.** Se ha mantenido eslint +
   typescript-eslint porque lo fijan `CLAUDE.md` § 5 y esta spec; cambiar de linter es
   una decisión de spec, no de implementación. Queda anotado por si se quiere revisar.

## Hallazgos de la implementación

Cinco cosas que solo aparecieron al ejecutar, tres de ellas **correcciones a lo que la
spec y el `CLAUDE.md` daban por bueno**:

| # | Qué pasó | Corrección |
|---|----------|------------|
| 1 | **El orden de capas de `CLAUDE.md` § 5 rompe la rejilla.** Con `@layer bootstrap, theme, base, …`, el preflight de Tailwind (`*{margin:0;padding:0}`, capa `base`) gana por orden de capa y **borra el padding del contenedor y los gutters de Bootstrap**. Medido en navegador: `paddingLeft: 0px`, `marginLeft: 0px` | `@layer theme, base, bootstrap, components, utilities;` — Bootstrap después del preflight, antes de componentes y utilidades. Verificado: `col` de 564px con `paddingLeft: 12px` |
| 2 | **`.container` es un nombre que Tailwind v4 también define**, y la capa `utilities` gana siempre. Usar el de Bootstrap es imposible | El contenedor de página pasa a ser de Tailwind (`mx-auto w-full max-w-6xl px-4`). De Bootstrap se usan **solo** `.row` y `.col-*` |
| 3 | `className="flex"` sobre `Card.Content` no basta: HeroUI trae su propio `flex-direction`, y una utilidad de `display` no lo deshace | El layout va en un `div` propio dentro de `Card.Content` |
| 4 | En jsdom, `new Request('/api/…')` **lanza** ("Failed to parse URL"): undici no tiene URL base. El cliente funcionaba en navegador y reventaba en tests | `baseUrl` se resuelve a `globalThis.location.origin` cuando no hay `VITE_API_BASE_URL` |
| 5 | `openapi-fetch` captura `globalThis.fetch` al crear el cliente, antes de que el test instale el espía, así que los mocks no interceptaban nada | El cliente recibe `fetch: (request) => globalThis.fetch(request)`, resuelto en cada llamada |

## Riesgos que siguen abiertos

- **Vite 8 + `@vitejs/plugin-react` 6**: el plugin declara peers nuevos
  (`oxc-transform-react`, `@rolldown/plugin-babel`). Si `npm install` deja avisos de
  peers, se resolverán instalándolos explícitamente y se anotará en la implementación.
- **La convivencia de capas CSS está razonada pero no probada** en este proyecto: es lo
  primero que hay que mirar en el navegador, y si falla, la salida es recortar Bootstrap
  a las clases que de verdad se usen, nunca relajar HeroUI.
