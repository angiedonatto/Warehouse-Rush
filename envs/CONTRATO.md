# Contrato del ambiente · `warehouse-v3` (ficha 0.3.0)

Contrato congelado entre ambiente, entrenamiento, evaluación, API y web. Cualquier cambio de orden,
unidades, rangos, acciones, dt, física o recompensa **sube la versión** (`warehouse-v4`), abre una nueva
familia de modelos y se anota en `docs/decisiones.md`. Ficha completa: [docs/ambiente-v0.2.md](../docs/ambiente-v0.2.md) (base) y [docs/ambiente-v0.3.md](../docs/ambiente-v0.3.md) (cambio de v3: recompensa por run).

- Código: `envs/` (`ENV_VERSION = "warehouse-v3"`, `__version__ = "0.3.0"`). Fábrica: `envs.make_env(blocked, layout_path, orders, reward_overrides)`.
- Clase: `envs.missions.MakeupMissionEnv` (hereda `envs.env.WarehouseRushEnv`). **v2 solo ofrece el modo maquillaje.**
- Mapa por defecto: `configs/layout_v0.4.json` (25 × 19 celdas de 1 m).
- Paso de decisión: 1 acción = 1 s simulado. Una sola política decide en cada paso; la animación no cambia las reglas.
- Determinismo: mismo mapa, semilla y acciones reproducen las transiciones. `reset(seed=s)` genera el pedido de forma reproducible; `reset()` sin semilla lo sortea con el RNG del ambiente.

## Espacio de acciones: `Discrete(8)`

| Código | Acción | Precondición para tener efecto | Coste de batería |
|---:|---|---|---:|
| 0 | AVANZAR | bandeja abajo; celda libre | 0.8 |
| 1 | GIRAR_IZQUIERDA | bandeja abajo | 0.2 |
| 2 | GIRAR_DERECHA | bandeja abajo | 0.2 |
| 3 | FRENAR | siempre | 0.1 |
| 4 | CARGAR | detenido, mirando al estante objetivo, bandeja en la altura de la línea, cabe en la capacidad | 0.2 |
| 5 | DESCARGAR | detenido, mirando la cinta desde la celda de acceso, bandeja abajo, lleva carga | 0.2 |
| 6 | SUBIR | bandeja un puesto arriba; desde reposo exige detenido y mirando el estante objetivo | 0.1 + 0.8 por metro |
| 7 | BAJAR | bandeja un puesto abajo | 0.1 + 0.8 por metro |

- Posiciones de la bandeja: **0 = viaje (0.55 m)**, 1 = 0.99 m, 2 = 1.79 m, 3 = 2.60 m. Cada SUBIR/BAJAR mueve **una** posición; la balda 3 requiere 3 SUBIR desde reposo.
- Con la bandeja arriba el robot no avanza ni gira (queda detenido); la bandeja sigue arriba tras CARGAR y hay que bajarla.
- CARGAR, DESCARGAR, SUBIR o BAJAR sin cumplir su precondición cuentan como interacción inválida (−2, sin cambio de misión). Un AVANZAR contra un obstáculo es colisión (−5). AVANZAR/GIRAR con la bandeja arriba no se penalizan como inválidos: se bloquean (consumen tiempo y batería) y se cuentan en `blocked_lift_moves`.
- Las acciones fuera de `Discrete(8)` lanzan `ValueError` sin cambiar el estado.
- No se entrega máscara de acciones al agente.

## Espacio de observación: `Box(27,)`, `float32`, todo en [0, 1]

`wm = ancho − 1 = 24`, `hm = alto − 1 = 18`.

| Índices | Señal | Normalización |
|---|---|---|
| 0–7 | 8 rayos N, NE, E, SE, S, SO, O, NO (ejes del mundo) | metros al primer obstáculo ÷ 8 m (alcance); diagonales miden √2 m por celda |
| 8–9 | posición propia (x, y) | x ÷ wm, y ÷ hm |
| 10–11 | posición del objetivo (x, y) | x ÷ wm, y ÷ hm (celda de la estación: estante `E01–E06` o `DELIVERY`); sin objetivo = posición propia |
| 12–15 | orientación N, E, S, O | one-hot |
| 16 | velocidad | 0 detenido, 1 en movimiento |
| 17 | batería | batería ÷ 180 |
| 18 | carga | unidades transportadas ÷ capacidad (3) |
| 19–21 | etapa recoger, entregar, completada | one-hot |
| 22 | tiempo restante | pasos restantes ÷ 400 |
| 23 | progreso del pedido | entregas ÷ líneas del pedido |
| 24 | mira un objeto interactuable | 1 si la celda de enfrente es la celda de servicio de un estante, o la cinta de despacho abordada desde su celda de acceso |
| 25 | elevación de la bandeja | (altura − 0.55) ÷ (2.60 − 0.55) |
| 26 | elevación objetivo | igual, para la altura de la línea en curso; 0 al entregar o al terminar |

No hay recorte (clip) que oculte errores: cada observación se valida con `isfinite` y `observation_space.contains`.
**No se entrega al agente:** mapa, rutas BFS, SKU/nivel/cantidad de la línea, inventario, fase de la bandeja,
máscara de acciones, bloqueo del pasillo ni recompensa del paso. La heurística BFS sí conoce el estado completo
(referencia privilegiada, no política aprendida).

## Recompensa (v3: coeficientes como parámetro versionado del run)

`r = 10·recogida + 30·entrega + 50·misión + 0.3·(d_antes − d_después) − 0.1 − 0.02·batería − 5·choque − 2·inválida`

- Hitos una sola vez por línea; recompensa de entrega una vez por acción DESCARGAR aunque descargue varias líneas.
- La energía vertical de la bandeja se descuenta como batería y se penaliza con el mismo coeficiente (−0.02).
- El progreso usa la distancia transitable a una celda de acceso del objetivo anterior (no se paga por cambiar de objetivo).
- **v3:** los coeficientes de arriba son los **valores por defecto** (los del mapa, idénticos a v1/v2). Un experimento puede cambiar
  uno o más con el bloque `recompensa:` de su YAML (`envs.reward_config`); el bloque entra en `config_sha256`, en los metadatos del
  entrenamiento (`reward_overrides`, `rewards`) y en el tag MLflow `recompensa`. Se rechazan claves desconocidas, premios negativos,
  tiempo ≥ 0 y penalizaciones positivas, de modo que repetir acciones inválidas nunca sea rentable.
- Los retornos solo se comparan entre runs con **los mismos coeficientes**; entre recompensas distintas se compara la tasa de éxito. No son comparables con `warehouse-v1`.

## Episodio

- `terminated`: éxito (`success`) o fallo (`battery_depleted`, `unreachable_target`, `insufficient_budget`).
- `truncated`: límite de 400 pasos (`time_limit`). Se registran ambos y cuentan como no exitoso al calcular la tasa de éxito.
- Presupuesto: batería 180, 400 pasos. Capacidad: 3 unidades. Sin estación de carga.

## Pedido y nivel de entrenamiento `m1`

Cada pedido se compone de `orders` SKU **distintos** del catálogo provisional (18 SKU `TMP-E##-L#`, 5 unidades cada uno).
En `m1` son 3 productos de 1 unidad, sorteados en cada episodio, y el stock se repone al reiniciar.

## Compatibilidad

Los modelos `warehouse-v2` comparten observación y acciones con v3 y se cargan, pero se entrenaron con la recompensa por defecto. `warehouse-v1` (Box(22), Discrete(5)) **no es compatible**: sus checkpoints (`experiment-001`, `n1-c*`) siguen siendo
historia y no se cargan con v2. Un modelo declara su `environment_version` y su recompensa efectiva en el manifiesto.
Etiquetas de código del ambiente: `env/warehouse-v2`, `env/warehouse-v3`.
