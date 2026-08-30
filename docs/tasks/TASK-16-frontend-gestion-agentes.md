# TASK-16 · Frontend: gestión de agentes

**Prioridad:** Media · **Depende de:** TASK-07, TASK-09

## Objetivo

Dar a la persona el panel desde el que incorpora agentes a su equipo: darlos de alta,
entregarles su credencial, ver qué han estado haciendo y cortarles el acceso cuando
haga falta.

## Alcance

**Entra:**
- Listado de agentes propios con su última actividad.
- Alta de agente y **presentación de la API key una sola vez**, con aviso explícito de
  que no se volverá a mostrar y acción de copiar.
- Revocación de la key con confirmación mediante componente de HeroUI.
- Añadir un agente como miembro de un tablero desde la interfaz.
- Estados de carga, vacío y error; tests.

**No entra:**
- Métricas, cuotas o límites de uso por agente.
- Configuración del comportamiento del agente: kanbai no lo ejecuta.

## Criterios de aceptación

- [ ] Al crear un agente, la key se muestra una vez y la interfaz advierte de que no se
      podrá recuperar.
- [ ] Recargar la página ya no muestra la key por ninguna vía.
- [ ] Revocar pide confirmación y, tras hacerlo, el agente deja de poder operar.
- [ ] La lista vacía explica qué es un agente y cómo dar de alta el primero.
- [ ] `npm run check` en verde.

## Notas técnicas

- La confirmación se hace con el componente de HeroUI, **nunca** con `confirm()` del
  navegador.
- No guardes la key en `localStorage` ni la registres en ningún sitio del cliente.
