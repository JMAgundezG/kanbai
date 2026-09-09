# TASK-08 · Frontend: vista del tablero con arrastrar y soltar

**Prioridad:** Alta · **Depende de:** TASK-06, TASK-07
**Estado:** Completada · **Cerrada:** 2026-09-09

## Objetivo

La pantalla que da nombre al producto: columnas con sus tarjetas, y la capacidad de
mover una tarjeta arrastrándola. Es la vista donde, más adelante, la persona verá
moverse solas las tarjetas que gestiona un agente.

## Alcance

**Entra:**
- Feature `board`: `api.ts`, hooks y componentes, sin importar de otras features.
- Render de columnas y tarjetas con HeroUI sobre la rejilla de Bootstrap.
- Arrastrar y soltar **accesible**, operable también con teclado.
- Mutación optimista del movimiento con reversión si la API falla, e invalidación de
  las claves de TanStack Query afectadas.
- Estados de carga, tablero vacío y error, explícitos.
- Tests sobre lo que ve el usuario (roles y texto), incluido el movimiento por teclado.

**No entra:**
- Detalle de tarjeta (TASK-15) y tiempo real (TASK-14).
- Crear o editar columnas desde la interfaz, si no lo exige la spec.

## Criterios de aceptación

- [x] Arrastrar una tarjeta a otra columna persiste el cambio y sobrevive a recargar.
- [x] La misma operación se puede completar **solo con teclado**.
- [x] Si la API falla, la tarjeta vuelve visualmente a su sitio y se avisa al usuario.
- [x] Un tablero sin tarjetas muestra un estado vacío con sentido, no una columna en
      blanco.
- [x] Una fila `.row` / `.col-*` maqueta las columnas sin romper los estilos de HeroUI.
- [x] `npm run check` en verde.
- [x] Un 404 al mover revierte la tarjeta y muestra un error genérico.

## Notas técnicas

- La librería de arrastrar y soltar se justifica en la spec (`AGENTS.md` § 7);
  preferencia por una que conviva con React Aria, en la que se apoya HeroUI.
- Componentes tontos + hooks con la lógica: el componente de tarjeta no llama a la API.
