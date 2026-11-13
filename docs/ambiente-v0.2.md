# Warehouse Rush — ficha del ambiente v0.2 (`warehouse-v2`)

Sustituye a [ambiente-v0.1.md](ambiente-v0.1.md) como ambiente de entrenamiento. La v0.1 (`warehouse-v1`) se conserva
como historia: sus modelos y resultados siguen siendo válidos para su propia familia. El contrato congelado
(orden, unidades, rangos, acciones) está en [`envs/CONTRATO.md`](../envs/CONTRATO.md); esta ficha explica el porqué.

## 1. Qué cambia respecto de v0.1 y por qué

| Aspecto | v0.1 · `warehouse-v1` | v0.2 · `warehouse-v2` |
|---|---|---|
| Misión | llevar P1 (y P2) a la entrega | atender un pedido de productos de estantería y entregarlo en la cinta de despacho |
| Mapa | 17 × 13, `layout_v0.1.json` | 25 × 19, `layout_v0.4.json` (cinta y caja) |
| Presupuesto | batería 100, 250 pasos | batería 180, 400 pasos |
| Carga | 1 paquete | hasta 3 unidades |
| Elevador | no existe | bandeja telescópica con 4 posiciones, controlada por el agente |
| Acciones | `Discrete(5)`: …, INTERACTUAR | `Discrete(8)`: INTERACTUAR se divide en CARGAR y DESCARGAR; se añaden SUBIR y BAJAR |
| Observación | `Box(22)`: dirección relativa al objetivo | `Box(27)`: posición propia, posición del objetivo, mira objeto, elevación y elevación objetivo |
| Inventario | no existe | stock total / reservado / disponible, pedidos y eventos (`envs/inventory.py`) |
| Modos | un solo modo | **solo maquillaje**; el modo v0.1 ya no se entrena ni se evalúa |

Motivos (instrucción del equipo, 2026-11-13): (1) dar al agente su posición y la del objetivo en lugar de una dirección
relativa; (2) que sepa si tiene enfrente algo con lo que interactuar; (3) que controle la bandeja con acciones propias en
lugar de que el ambiente la suba sola; (4) separar cargar de descargar, dos operaciones distintas; (5) incluir la altura
que necesita cada producto, porque sin ella el agente no puede saber en qué posición detener la bandeja.

## 2. Mapa y elementos (fuente: `configs/layout_v0.4.json`)

25 columnas × 19 filas, celdas de 1 m, origen arriba a la izquierda, x al este, y al sur. Perímetro cerrado.
BASE (3,16) mirando al norte. Seis estanterías de 2 × 2 celdas (E01–E06) en [4,4]–[5,5], [11,4]–[12,5], [18,4]–[19,5],
[4,10]–[5,11], [11,10]–[12,11], [18,10]–[19,11]. Muro interior en y = 14 con un paso permanente en x = 20 y uno
cerrable en x = 6. Despacho: cinta en (22,16)–(23,16), caja en (23,16), celda de acceso (21,16) mirando al este.
El mapa v0.1 sigue disponible en el repositorio (`configs/layout_v0.1.json`) para v1.

Cada estantería tiene 3 niveles de almacenamiento (alturas de transferencia 0.99, 1.79 y 2.60 m) con un SKU
temporal de 5 unidades (18 SKU, 90 unidades). La balda inferior es estructura, no almacenamiento.

## 3. Qué decisión nueva debe tomar el agente y cómo se mide la dificultad

- **Decisión nueva:** en cada estante debe llevar la bandeja a la altura correcta (SUBIR/BAJAR en el número justo de
  pasos), cargar, bajar la bandeja antes de moverse y, con varias líneas, decidir cuándo ir a despacho.
- **Dificultad medible:** pasos por pedido, batería usada, número de SUBIR/BAJAR necesarios (1, 2 o 3 por línea),
  distancia recorrida, colisiones e interacciones inválidas. La heurística BFS completa un pedido de 3 productos en
  76–105 pasos y 46–69 de batería (semillas 0–9); ese es el piso de pasos que cualquier política aprendida debe igualar.
- Los efectos gráficos (cinta, caja, rótulos) solo representan el estado; no añaden complejidad evaluable.

## 4. Mecanismo de la bandeja

La bandeja ocupa 4 posiciones: 0 = viaje (0.55 m) y 1–3 = baldas. Cada SUBIR/BAJAR avanza **una** posición.
SUBIR desde reposo exige estar detenido, mirando el estante del producto en curso y en la etapa de recoger.
CARGAR solo recoge si la bandeja está exactamente en la altura de la línea; el stock se descuenta en ese momento.
Con la bandeja arriba el robot no puede avanzar ni girar. DESCARGAR exige bandeja en reposo. La energía vertical
(0.8 por metro) se descuenta de la batería y se penaliza con el coeficiente de batería (−0.02).

## 5. Sensores, estado y observación

Ver tabla de 27 señales en `envs/CONTRATO.md`. La observación **no** incluye mapa, rutas, SKU, nivel, inventario,
fase de la bandeja ni máscara de acciones. El estado interno (`WorldState`, `snapshot()`, `info["state"]`) es más amplio
y sirve para diagnóstico y para la heurística privilegiada.

## 6. Pedido, nivel `m1` y reproducibilidad

Un pedido es un conjunto de líneas (SKU, cantidad) con reserva atómica. En el nivel de entrenamiento `m1` cada episodio
sortea **3 SKU distintos de 1 unidad** y repone el stock al reiniciar, para que el modelo aprenda la tarea general de
reunir paquetes y no una sola ruta. `reset(seed=s)` reproduce el mismo pedido (evaluación); `reset()` sin semilla lo sortea
con el RNG del ambiente (entrenamiento, reproducible a partir de la semilla del run). Los niveles `n1`–`n3` de
`configs/niveles.yaml` describen la familia v1 y se conservan; `m1` es el primer nivel de v2.

## 7. Recompensa, terminación y truncamiento

Coeficientes idénticos a v0.1 (ver §7 de la ficha v0.1 y `envs/CONTRATO.md`): +10 recogida, +30 entrega, +50 misión,
0.3 por celda de progreso, −0.1 tiempo, −0.02 por unidad de batería, −5 choque, −2 interacción inválida.
`terminated` = éxito, batería agotada, objetivo inalcanzable o `insufficient_budget`; `truncated` = 400 pasos.
No se modificó la recompensa porque el cambio de v2 es de interfaz (observación y acciones); cualquier ajuste de
recompensa será un experimento separado y una nueva versión.

## 8. Simplificaciones y limitaciones

- Cada SUBIR/BAJAR dura 1 s y mueve la bandeja una posición completa, aunque la distancia entre posiciones sea de
  0.44 a 0.81 m. Esto ignora el límite de 0.40 m/s de la ficha del elevador anterior: es una simplificación de
  decisión discreta, no una validación mecánica.
- Un pedido de varias líneas requiere recorrer estantes distintos en un orden que el agente debe decidir solo
  con la dirección y posición del objetivo actual; el ambiente fija el orden de visita mediante su despachador.
- Sin estación de carga, sin reposición de stock dentro del episodio, un solo robot.
- Con 3 líneas de 1 unidad la capacidad (3) nunca obliga a un viaje extra; el caso de capacidad se prueba por separado.
- Los modelos v1 no se pueden evaluar con v2.

## 9. Verificaciones ejecutadas (2026-11-13)

- `python -m pytest tests -q`: informe JUnit en `docs/resultados/pytest-warehouse-v2.xml`.
- La heurística BFS completó 10/10 pedidos de 3 productos aleatorios sin colisiones ni interacciones inválidas
  (semillas 0–9, 76–105 pasos).
- Pruebas específicas: `tests/test_lift.py` (una posición por acción, acciones inválidas, pedidos aleatorios y reposición),
  `tests/test_env.py` (contrato Gymnasium con `check_env`, observaciones finitas y acotadas, recompensas y terminaciones),
  `tests/test_inventory_missions.py`, `tests/test_packing.py` y `tests/test_layouts.py`.
