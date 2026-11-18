# Visor Three.js — Warehouse Rush v0.2

## Abrir

Desde el checkout del proyecto, con `.venv-rl` activo:

```bash
python -m warehouse_rush.cli view
```

El comando sirve la aplicación y abre `http://127.0.0.1:8080`. Ctrl+C detiene el
servidor. `--no-open` evita abrir otra pestaña; `--port 8081` cambia el puerto.
La primera ejecución usa `npm ci` y `npm run build` en `web/` si no existe un build.
Para cambios posteriores en JS/CSS: `npm run build --prefix web` y recargar página.

Node verificado: 24.17.0; Three.js 0.186.1, Vite 8.3.5. Las versiones resueltas
están fijadas en `web/package-lock.json`. Las dependencias Python no cambian.

## Funciones

- Escena real WebGL con racks, cartones, robot AMR, estaciones, marcas del suelo,
  paredes, luces, sombras y cierre señalizado. Los modelos son geometría procedural
  local; no requieren descargas de modelos o texturas de terceros.
- Cuatro cámaras: isométrica con órbita/zoom, primera persona, lateral que sigue al
  robot y detalle del objetivo. Las miniaturas representan la misma escena.
- Panel de posición, orientación, velocidad, batería, carga, objetivo, pasos,
  entregas, colisiones y retorno acumulado. Los valores proceden de Python.
- Minimap 2D del mapa JSON, con robot, estaciones, bloqueo y ruta de referencia.
- Iniciar/pausar, transición individual, reinicio, velocidad visual 0.5×–4×,
  políticas heurística/aleatoria/PPO/manual y misiones de uno o dos pedidos.
- Control manual: W/↑ avanzar, A/← girar izquierda, D/→ girar derecha,
  S/↓ frenar, E interactuar. Las mismas condiciones de frenado, orientación,
  batería y carga del CLI siguen aplicando.
- Mostrar/ocultar ocho sensores y ruta BFS. El botón de bloqueo inicia un episodio
  nuevo; no representa cierres inesperados durante la marcha.

## Correspondencia con el simulador

`viewer.py` sirve archivos estáticos y una pequeña API de biblioteca estándar:

| Ruta | Función |
|---|---|
| GET `/api/layout` | JSON canónico, hash y modelos PPO disponibles |
| GET `/api/state` | Estado, observación, eventos y ruta de referencia |
| POST `/api/reset` | Crear episodio con `orders`, `blocked`, `policy`, `seed` |
| POST `/api/step` | Ejecutar `env.step()` con la política elegida o acción manual |

No se entrena ni se modifica PPO al visualizarlo. El agente PPO sólo recibe las
22 observaciones; el BFS añadido para dibujar la ruta es una capa visual
independiente, identificada como `bfs_reference`. Una línea BFS no representa una
predicción de PPO ni prueba que vaya a seguir ese recorrido.

Cada transición equivale a 1 s simulado. La reproducción visual interpola entre
posiciones y ángulos discretos; la velocidad de reproducción no cambia consumo,
recompensa, tiempo ni decisiones. Durante pausa la cámara y las vistas siguen
funcionando. Pausar no revierte una petición que ya estuviera en curso.

El suelo tiene 17×13 celdas de 1 m; las seis huellas de racks, la pared interior,
el bloqueo y las posiciones se leen del mismo archivo que el entorno. Las paredes
frontales y la pared interior se muestran bajas para permitir observar el robot;
su altura visual no cambia las colisiones del simulador. No se añadieron obstáculos
físicos decorativos. La base es inicio, no una estación que recargue batería.

## Diseño y límites

La referencia adjunta guía la composición: escena grande, tarjetas de cámara,
panel lateral oscuro y acentos cian, verde, amarillo y rojo. Es una reconstrucción
procedural interactiva; no es una reproducción fotográfica exacta de los modelos
industriales de la referencia. La fuente usa Google Fonts y tiene fallback local
Arial si no hay red; los modelos y la simulación funcionan sin servicios externos.

El visor sirve una sesión compartida en este proceso local, enlazado sólo a
`127.0.0.1`. Dos pestañas no crean dos simulaciones independientes. No es un
servidor multiusuario ni una publicación en cloud. El visor requiere el checkout
con `web/`; el wheel del ambiente conserva su alcance de simulación Python.

El PPO entrenado con 20 000 pasos sigue teniendo 0% de éxito y se queda frenando.
La interfaz no oculta ese comportamiento. Para ver una misión completa, usar el
heurístico. PPO se deshabilita para misiones sin un modelo local guardado.

## Verificar

```bash
python -m pytest -q
npm run build --prefix web
# Con el visor escuchando en 8080, en otra terminal:
npm test --prefix web
```

Playwright usa Chrome instalado en macOS; en otros equipos preparar Chromium con
`cd web && npx playwright install chromium`. Las pruebas recorren navegador → API
→ entorno y verifican cámaras, controles, modo manual, entrega real y diseño móvil.
