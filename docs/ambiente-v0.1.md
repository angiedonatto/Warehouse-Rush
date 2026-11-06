# Warehouse Rush — ficha del ambiente v0.1

## 1. Objetivo y misión

Un robot debe recoger paquetes identificados y entregarlos en una bodega antes de
agotar batería o tiempo. Nivel 1 (`--orders 1`): P1 → ENTREGA. Nivel 2
(`--orders 2`): P1 → ENTREGA → P2 → ENTREGA. Siempre comienza en BASE, mirando
al norte y detenido. Angie, Lis, Miguel y Naomi desarrollan el proyecto; esta
implementación se realiza en `dev/angie`.

Es una **aproximación cinemática discreta**, con celdas de 1 metro y pasos de 1
segundo. No modela dinámica, aceleración, masa, inercia ni frenado industrial.
La representación ASCII muestra el estado del simulador; no constituye una física
independiente ni un mapa decorativo.

## 2. Mapa, coordenadas y accesibilidad

La fuente única es [`configs/layout_v0.1.json`](../configs/layout_v0.1.json).
El paquete incluye un enlace al mismo archivo para distribuirlo en un wheel.
Dimensiones: 17 columnas × 13 filas. Origen (0,0) arriba a la izquierda, x crece
hacia el este, y hacia el sur. Perímetro cerrado.

```text
#################
# 1             #
#               #
#  RR  RR  RR   #
#  RR  RR  RR   #
#               #
#               #
#  RR  RR  RR 2 #
#  RR  RR  RR   #
#               #
####:####### ####
# B            D#
#################
```

`#` pared, `R` rack, `B` base, `1`/`2` recogidas, `D` entrega, `:` tramo
bloqueable abierto, `X` tramo bloqueado, `^>v<` robot. Al comenzar, el robot cubre
la letra B; el CLI también imprime las coordenadas de BASE.

| Elemento | Coordenadas / límites inclusivos |
|---|---|
| BASE | (2,11) |
| RECOGIDA 1 | (2,1) |
| RECOGIDA 2 | (14,7) |
| ENTREGA | (15,11) |
| R1, R2, R3 | [3,3]–[4,4]; [7,3]–[8,4]; [11,3]–[12,4] |
| R4, R5, R6 | [3,7]–[4,8]; [7,7]–[8,8]; [11,7]–[12,8] |
| Pasos en pared interior y=10 | x=4 y x=12 |
| Tramo que se cierra | (4,10), manteniendo libre (12,10) |

Las estaciones ocupan una celda física que no se atraviesa. La interacción se
realiza desde una celda cardinal adyacente, a 1 m del centro de la estación,
mirando hacia ella. BFS multiorigen calcula distancias a esas celdas de servicio.
`Layout.validate_routes()` verifica que BASE y todas las celdas de servicio
pertenecen al mismo componente conexo con y sin bloqueo, y que el bloqueo alarga
al menos una ruta desde BASE. El heurístico comprueba además la misión completa
con giros, frenado e interacción dentro del presupuesto real.

BFS medido: BASE→servicio P1 pasa de 13 celdas a 29 con bloqueo; hacia servicio
P2 permanece en 15 y hacia ENTREGA en 12. Son distancias de traslación, no
incluyen las acciones adicionales de orientación, frenado e interacción.

## 3. Estado del mundo

El estado interno (`WorldState`, `env.snapshot()`, `info["state"]`) es más amplio
que la observación. Las coordenadas y conjuntos internos se usan para diagnóstico
y para el baseline privilegiado; PPO no los recibe como entrada.

| Variable | Tipo | Unidad | Rango / significado |
|---|---|---|---|
| x, y | int | m/celda | 0–16, 0–12; en operación sólo celdas transitables |
| theta | int | dirección | 0 norte, 1 este, 2 sur, 3 oeste |
| v | float | m/s discretos | 0 detenido, 1 movimiento |
| bateria | float | unidades de energía | 0–100 por defecto |
| carga | str o None | identificador | None, P1 o P2; máximo un paquete |
| pedido_actual | int | índice desde 0 | 0–orders; orders indica misión completa |
| etapa | str | categoría | recoger, entregar, completada |
| objetivo | str o None | estación | P1, P2, DELIVERY o None |
| tiempo | int | s/pasos | 0–max_steps |
| tiempo_restante | int | s | 0–max_steps |
| entregas | int | paquetes | 0–orders |
| colisiones | int | intentos | 0–max_steps |
| interacciones_invalidas | int | intentos | 0–max_steps |
| pasillo_bloqueado | bool | condición | fijo por episodio, configurable al reset |
| distancia | float | m | 0–max_steps; sólo avances exitosos |
| recompensa_total | float | retorno | suma de componentes emitidos |
| paquetes_recogidos | set[str] | identidades | subconjunto de {P1,P2}, monotónico |
| paquetes_completados | set[str] | identidades | subconjunto de recogidos, monotónico |

Los conjuntos se serializan como listas ordenadas. El entorno mantiene además
configuración, cachés de obstáculos/distancias, indicador de finalización y razón
de cierre. El tiempo y la batería son observables para distinguir los presupuestos.

## 4. Observación del agente

`spaces.Box(low, high, shape=(22,), dtype=np.float32)`. Todos los valores están
en [0,1], excepto las dos componentes relativas del objetivo en [-1,1].

| Índices | Señal | Normalización |
|---|---|---|
| 0–7 | rayos N, NE, E, SE, S, SO, O, NO, en ejes del mundo | distancia / alcance (8 m) |
| 8–9 | objetivo menos posición: dx, dy | dx/16, dy/12 |
| 10–13 | orientación N,E,S,O | one-hot de 4 componentes |
| 14 | velocidad | 0 o 1 |
| 15 | batería disponible | batería / capacidad |
| 16 | transporta paquete | 0 o 1 |
| 17–19 | etapa recoger, entregar, completada | one-hot de 3 componentes |
| 20 | tiempo restante | restante / max_steps |
| 21 | progreso de pedidos | entregas / orders |

Los rayos prueban celdas discretas y retornan metros al centro del primer obstáculo
o el alcance máximo. En diagonales, cada incremento mide √2 m. Detectan paredes,
racks, estaciones y el bloqueo activo. No son un modelo óptico de LiDAR ni incluyen
ruido u oclusión continua en esquinas.

El objetivo observado es el centro de la estación; la recompensa de progreso mide
distancia transitable a una celda de interacción. No se incluyen rutas, distancias
BFS, acciones heurísticas, mapa global ni un indicador privilegiado de bloqueo.
Esto puede producir observaciones ambiguas lejos del cierre. Cada observación se
comprueba en ejecución con `isfinite` y `observation_space.contains`, incluyendo
estados terminales. No se aplica un clip para ocultar errores.

## 5. Acciones y reglas de transición

`spaces.Discrete(5)`:

| Código | Acción | Posición / orientación / velocidad |
|---|---|---|
| 0 | AVANZAR | 1 celda en theta si está libre; v=1 |
| 1 | GIRAR_IZQUIERDA | theta=(theta−1) mod 4; posición y v se conservan |
| 2 | GIRAR_DERECHA | theta=(theta+1) mod 4; posición y v se conservan |
| 3 | FRENAR | posición y orientación se conservan; v=0 |
| 4 | INTERACTUAR | intenta la operación; no frena automáticamente |

La velocidad es un indicador discreto persistente: girar no desplaza al robot y
no lo detiene. Para interactuar después de avanzar hay que frenar. Un choque
impide el desplazamiento, deja v=0 y aumenta colisiones. No hay diagonales ni
desplazamiento pasivo entre acciones. Todas las acciones consumen un segundo y
energía, incluso choques e interacciones inválidas.

Una recogida requiere la estación del pedido pendiente, frente correcto, v=0,
carga vacía e identidad nunca recogida/completada. Una entrega requiere esas
condiciones geométricas en DELIVERY y llevar exactamente el paquete pendiente.
Después se vacía carga, se completa el pedido y se selecciona el siguiente.
`_move()`, `_interact()` y `WorldState` separan responsabilidades.

## 6. Configuración y unidades

Los valores por defecto residen en el JSON. `--layout archivo.json` permite usar
otra configuración en mapa, juego, entrenamiento y evaluación. Python permite
inyectar `SimulationConfig` y `RewardConfig` sin cambiar la lógica.

| Parámetro | Por defecto | Unidad / dominio |
|---|---:|---|
| orders | 1 | entero en {1,2}, argumento CLI |
| blocked | false | booleano, argumento CLI/reset |
| battery_capacity | 100 | energía, >0 |
| max_steps | 250 | entero, ≥1 |
| forward_cost | 0.8 | energía por intento de avance, >0 |
| turn_cost | 0.2 | energía por giro, >0 |
| brake_cost | 0.1 | energía por frenado, >0 |
| interact_cost | 0.2 | energía por intento de interacción, >0 |
| sensor_range | 8 | metros, entero ≥1 |
| step_seconds | 1 | s; fijo en esta versión |
| interaction_radius | 1 | m; fijo en esta versión |
| cell_meters | 1 | m; geometría de esta versión |
| render delay | 0.1 | segundos reales por transición; CLI `--delay`, ≥0 |

Si la energía disponible es menor que el coste de la última acción, se descuenta
lo disponible y se termina tras esa transición. Nunca se genera batería negativa.
Los parámetros iniciales de misión, batería y penalizaciones se conservaron.

## 7. Recompensas y prevención de abuso

Para una transición con objetivo anterior g, posición p→p', consumo e y distancia
mínima transitable d a una celda de servicio de g:

```text
r = 10·recogida + 30·entrega + 50·misión_completa
    + 0.3·(d(p,g) − d(p',g)) − 0.1 − 0.02·e
    − 5·colisión − 2·interacción_inválida
```

Todos los eventos son indicadores de esa transición. El objetivo g se mantiene
fijo para calcular progreso aunque una interacción cambie de etapa; cambiar de
destino no genera recompensa artificial. Distanciarse produce progreso negativo.
Permanecer cerca, girar, frenar o interactuar no reduce distancia y paga tiempo
y batería. Un ciclo espacial completo sin eventos tiene progreso neto cero y
retorno estrictamente negativo. Es shaping por diferencia de distancia sin
descuento, no una garantía de invariancia de política bajo gamma<1.

Entre escenarios, una ruta bloqueada puede tener retorno mayor aunque cueste más:
al crecer la distancia inicial, crece el progreso total premiado. Por eso la
robustez se interpreta mediante éxito, pasos, distancia y energía, junto al retorno.

`info["reward_components"]` contiene siempre `pickup`, `delivery`, `completion`,
`progress`, `time`, `battery`, `collision`, `invalid_interaction`; su suma es reward.
Los cuatro premios y progreso son no negativos; tiempo es estrictamente negativo
y el resto de penalizaciones no positivas. Se rechazan valores no finitos y signos
que convertirían una interacción inválida en premio.

No se puede ganar recogiendo/soltando el mismo paquete: no hay acción de soltar,
cada identidad tiene premio de recogida único, entregar exige carga real correcta,
los pedidos completados son permanentes y no se pueden reabrir. Una interacción
inválida no mueve al robot ni cambia la misión y su retorno es negativo. Tras el
fin, `step()` exige `reset()` y no vuelve a emitir el premio de completar misión.

## 8. Episodios y reproducibilidad

- `reset(seed, options)` devuelve `(observation, info)` y usa `super().reset(seed)`.
- `step()` devuelve `(observation, reward, terminated, truncated, info)`.
- Éxito: todas las entregas → terminated=True, razón `success`.
- Fracaso: batería agotada o destino sin ruta → terminated=True,
  `battery_depleted` o `unreachable_target`.
- Tiempo máximo → truncated=True, `time_limit`; no es una terminación física.
- Si coinciden, éxito tiene prioridad; luego agotamiento/sin ruta; luego tiempo.

`info` registra éxito, fracaso físico, razón, pasos, segundos simulados, distancia,
energía consumida, entregas, colisiones, interacciones inválidas, retorno, estado,
componentes y hash del mapa. El límite temporal es un truncamiento sin fracaso
físico, pero cuenta como episodio no exitoso al calcular success rate.

Mapa y reinicio son deterministas; semillas controlan Random y las bibliotecas de
PPO. Igual semilla/acciones reproduce las transiciones. Entrenamiento usa semilla
42; comparación final usa 10000–10019 y evaluaciones periódicas parten de 20000.
CPU de un hilo y algoritmos deterministas de PyTorch reducen variación, sin
prometer identidad binaria entre arquitecturas y versiones.

## 9. Baselines, entrenamiento y métricas

Random elige uniformemente una de cinco acciones. El heurístico busca con BFS en
(x,y,theta), incorporando avance y giros; al llegar, frena e interactúa. Conoce
mapa, bloqueo y estado: es una referencia privilegiada. PPO (`MlpPolicy`) sólo
accede al vector numérico con `model.predict` y nunca llama al heurístico.

PPO usa dos redes de 64×64, learning_rate=0.0003, gamma=0.99,
gae_lambda=0.95, clip_range=0.2, ent_coef=0.01, vf_coef=0.5,
max_grad_norm=0.5, 10 épocas, rollout=500 y batch=100; CPU, un hilo.
Primero se ejecuta una integración de 128 pasos (rollout 64, batch 32); después
20 000 pasos sobre un pedido sin bloqueo. SB3 puede redondear al completar
rollouts: se registran pasos solicitados y efectivos. El experimento principal
usa un múltiplo de 500 para obtener exactamente 20 000.

Monitor guarda episodios; `progress.csv` guarda pérdidas, entropía y métricas PPO;
callbacks guardan checkpoints y evalúan 5 episodios cada 5000 pasos. El modelo
final y el mejor de evaluación se conservan separados. La comparación utiliza
**el modelo final**, identificado por hash. No se entrena con acciones BFS.

Las métricas se calculan a partir de episodios completos:

| Métrica | Cálculo |
|---|---|
| Success rate | episodios con todas las entregas / total |
| Mean reward y Reward std | media y desviación poblacional del retorno sin descuento |
| Mean steps | número de acciones; coincide con segundos simulados |
| Mean distance | avances exitosos × 1 m |
| Battery used | capacidad inicial menos energía final |
| Collisions | intentos de avance contra obstáculos |
| Invalid interactions | intentos que no cumplen reglas |
| Deliveries | paquetes entregados por episodio |

La evaluación compara las tres políticas en el mismo mapa, misión, reglas y
semillas, con y sin bloqueo. Reporta además bloqueo−normal, recogidas medias,
distribución de acciones y razones de cierre para apoyar el diagnóstico.

## 10. Cinco transiciones ejecutadas

Se generan con `python -m pipelines.cli demo-transitions --steps 5`, semilla
42. El JSON completo en [`transitions-v0.1.json`](transitions-v0.1.json) contiene
Observación → Acción → Estado → Recompensa y componentes → Nueva observación.
Los siguientes datos se extraen de `step()`, sin construir trayectorias ficticias.

| Paso | Acción | (x,y,theta,v) | Batería | Recompensa | Evento |
|---|---|---|---:|---:|---|
| 1 | AVANZAR | (2,11,0,0.0) | 99.2 | -5.116 | time=-0.100, battery=-0.016, collision=-5.000 |
| 2 | GIRAR_DERECHA | (2,11,1,0.0) | 99.0 | -0.104 | time=-0.100, battery=-0.004 |
| 3 | AVANZAR | (3,11,1,1.0) | 98.2 | 0.184 | progress=0.300, time=-0.100, battery=-0.016 |
| 4 | FRENAR | (3,11,1,0.0) | 98.1 | -0.102 | time=-0.100, battery=-0.002 |
| 5 | INTERACTUAR | (3,11,1,0.0) | 97.9 | -2.104 | time=-0.100, battery=-0.004, invalid_interaction=-2.000 |

## 11. Resultados experimentales y verificaciones

Resultados principales y sus limitaciones:
[`resultados/report.md`](resultados/report.md),
[`resultados/evaluation.csv`](resultados/evaluation.csv),
[`resultados/evaluation.json`](resultados/evaluation.json) y
[`resultados/training_curve.png`](resultados/training_curve.png).
Los datos de entrenamiento, hiperparámetros, versiones y duración están en
`docs/resultados/training/`; los modelos locales en `models/` (ignorados por git).

Experimento principal ejecutado: **20 000 pasos efectivos**, semilla 42, un pedido,
CPU, **118.10 s** reales de entrenamiento y evaluaciones periódicas. Ochenta
episodios de entrenamiento terminaron sin una misión exitosa. El retorno medio
de los primeros diez fue −181.835 y el de los últimos diez −25.735.

En evaluación final (20 episodios por combinación, semillas 10000–10019), PPO
obtuvo **0% de éxito tanto normal como bloqueado**: eligió FRENAR las 250 veces,
sin moverse ni recoger paquetes, con retorno −25.500 y consumo 25.0. Random
también obtuvo 0%. El heurístico funciona mejor que PPO en tasa de éxito:
**100% en ambos escenarios**, 47/63 pasos, 34/50 m y 29.6/42.4 de energía para
normal/bloqueado. Este resultado demuestra integración del ciclo RL, sin
demostrar que PPO haya aprendido la misión. No se alteraron las recompensas
iniciales para aparentar éxito.

La prueba de ambos pedidos se conserva adicionalmente en
[`resultados/level2/report.md`](resultados/level2/report.md).
El heurístico completó los dos pedidos en 75/91 pasos y 48/64 m, también con 100%
de éxito en las 20 semillas por escenario. No se entrenó un modelo PPO de nivel 2.
`python -m pipelines.cli validate` ejecuta `check_env`, búsqueda de rutas y
toda la suite pytest. La suite cubre sensores, contabilidad, observaciones,
acciones, colisiones, reglas de carga, pedidos permanentes, fin de episodio,
desvíos, reproducibilidad, ciclos improductivos y exportación de errores reales.

## 12. Limitaciones y siguiente versión

Esta v0.1 no incluye 3D, interfaz web, servicios, bases de datos, cloud, inventario,
varios robots, dinámica continua, incertidumbre de sensores ni cierres durante la
marcha. `--blocked` es una perturbación conocida por el simulador desde reset;
PPO debe detectarla mediante sus observaciones locales. La secuencia de pedidos
es fija, sin generación estocástica. Veinte semillas no equivalen a veinte mapas
independientes y no justifican inferencias de generalización amplia.

Los resultados de un entrenamiento corto no prueban convergencia ni superioridad
de PPO. Próximos pasos: más pasos y semillas, analizar exploración e interacciones,
entrenar el nivel 2 y ensayar mapas fuera de entrenamiento. Cualquier curriculum,
ajuste de recompensa o cambio de mapa requiere un experimento separado. MLflow
puede añadirse después al registro JSON/CSV existente.

Referencias de API: [Gymnasium Env](https://gymnasium.farama.org/api/env/),
[semántica de terminated/truncated](https://farama.org/Gymnasium-Terminated-Truncated-Step-API)
y [rollouts de Stable-Baselines3](https://stable-baselines3.readthedocs.io/en/master/guide/algos.html).
