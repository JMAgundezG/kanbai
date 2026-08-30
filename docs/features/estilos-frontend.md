# Estilos del frontend: HeroUI + Tailwind + Bootstrap

**Introducida por:** [TASK-02](../tasks/TASK-02-scaffold-frontend.md) · **Última actualización:** 2026-08-30

Tres sistemas de estilos en la misma página. Lo que sigue **está medido en un navegador**,
no deducido: cada afirmación se comprobó con `getComputedStyle` durante TASK-02.

## El orden de capas

```css
/* src/styles/global.css */
@layer theme, base, bootstrap, components, utilities;

@import "bootstrap/dist/css/bootstrap-grid.css" layer(bootstrap);
@import "tailwindcss";
@import "@heroui/styles";
```

Dos restricciones lo fijan, y son opuestas:

1. **`bootstrap` va DESPUÉS de `base`.** El *preflight* de Tailwind incluye
   `*, ::before, ::after { margin: 0; padding: 0 }`. El orden de capas manda sobre la
   especificidad, así que con `bootstrap` declarada antes de `base` ese reset **borra el
   padding de `.container` y todos los gutters de `.col-*`**. Medido con la capa mal
   puesta: `paddingLeft: 0px`, `marginLeft: 0px`. Bien puesta: columnas de 564 px con
   `paddingLeft: 12px`.
2. **`bootstrap` va ANTES de `components` y `utilities`.** Así los componentes de HeroUI
   y las utilidades de Tailwind ganan cualquier conflicto contra Bootstrap.

Y `tailwindcss` se importa **antes** que `@heroui/styles`, como exige HeroUI.

## Qué se usa de cada uno

| Sistema | Para qué | Qué NO |
|---------|----------|--------|
| HeroUI | Todo componente interactivo: botones, inputs, modales, tablas, chips, alerts | Reimplementarlos a mano |
| Tailwind | Espaciado, tipografía, color, flexbox, **y el contenedor de página** | — |
| Bootstrap | **Solo `.row` y `.col-*`** | `.container*`, utilidades, Reboot, el JS |

### Por qué el contenedor NO es el de Bootstrap

Tailwind v4 define su propia utilidad `.container`, y la capa `utilities` gana siempre.
El nombre está efectivamente tomado: usar el `.container` de Bootstrap no funciona. El
contenedor de página se hace con Tailwind (`mx-auto w-full max-w-6xl px-4`).

### Trampas de HeroUI

`className` sobre un slot compuesto (`Card.Content`) **no** sustituye a los estilos del
propio slot: HeroUI trae su `flex-direction`, y una utilidad de `display` no lo deshace.
El layout propio va en un `div` dentro del slot.

## Cómo verificarlo

Un fallo de capas CSS no lo detecta ningún test. Con `npm run dev` levantado:

```bash
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
"$CHROME" --headless --disable-gpu --window-size=1280,760 \
  --virtual-time-budget=8000 --screenshot=/tmp/home.png http://localhost:5173/
```

Comprobar que un componente de HeroUI tiene su aspecto propio, que una `.row` con dos
`.col-md-6` reparte el ancho al 50 % **con separación** entre columnas, y que el
contenedor no pega al borde de la ventana.
