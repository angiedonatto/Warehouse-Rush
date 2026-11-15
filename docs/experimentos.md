# Experimentos (R2)

Hipótesis, resultados y decisiones. Cada afirmación debe rastrearse a un run, una suite y una semilla.

## Presupuesto real por run
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|

## Referencias (aleatoria, regla, baseline PPO)

## C0-C4: hipótesis, resultado, decisión

## Resultados N1 (2026-11-06, semilla 0, suite-n1-v1: 50 episodios, semillas 10000-10049, acciones deterministas)
Presupuesto pedido 200 000 pasos; efectivo 204 800 (múltiplo de 8 192 = 2048 × 4 entornos), ~4.0 min por run en CPU (~850 pasos/s).

| Run | Cambio | Éxito | Retorno medio | Pasos/ep | Batería usada | Estado MLflow |
|---|---|---:|---:|---:|---:|---|
| referencia aleatoria | - | 0% | -265.5 | 250 | 75.6 | referencia |
| referencia por regla (BFS) | - | 100% | +94.9 | 47 | 29.6 | referencia |
| n1-c0-seed0 (C0) | baseline PPO | 0% | -25.50 | 250 | 25.1 | candidato (baseline vigente) |
| n1-c1-seed0 (C1) | ent_coef 0.0 -> 0.01 | 0% | -25.36 | 250 | 33.1 | **rechazado** |

**Decisión C1:** no supera a C0 en ≥5 pp de éxito (0 pp), se rechaza según `configs/criterios.yaml`; el run y su evidencia se conservan. La hipótesis "más exploración sube el éxito en N1" **no se confirma** con este presupuesto y una semilla.

**Diagnóstico:** en ambos runs 0 éxitos en 816 episodios de entrenamiento. En los primeros ~10 episodios la política colapsa a quedarse quieta (retorno -270 -> -25): con una política aleatoria casi nunca llega a recoger (0.05 recogidas/episodio), no ve señal de éxito y moverse cuesta más (choques -5, inválidas -2, tiempo) que no hacer nada (-25.5 en 250 pasos). El crítico sí aprende (explained variance 0.89-0.93): el problema es exploración/diseño de recompensa, no capacidad. Los retornos solo se comparan dentro del mismo ambiente y recompensa; el retorno de C0/C1 es mejor que el aleatorio y aun así 0% de éxito.

**Siguiente hipótesis razonable (una dimensión):** ent_coef mayor (0.05-0.1) o más pasos; si no despega, cambio de recompensa (p. ej. suavizar penalizaciones al inicio) = decisión de R1, nueva versión `warehouse-v2` y nueva familia de modelos. No se ajusta la recompensa para aparentar éxito.

## Barrido de exploración en N1 (2026-11-06, semilla 0, mismo presupuesto 204 800 pasos, ~4.0 min por run)
| Run | ent_coef | Éxito (suite-n1-v1) | Retorno medio | Entrenamiento: éxitos / episodios | Estado |
|---|---:|---:|---:|---:|---|
| n1-c0-seed0 | 0.0 | 0% | -25.50 | 0 / 816 | candidato (baseline) |
| n1-c1-seed0 | 0.01 | 0% | -25.36 | 0 / 816 | rechazado |
| n1-c1b-seed0 | 0.05 | 0% | -24.93 | 0 / 816 | rechazado |
| n1-c1c-seed0 | 0.1 | 0% | -25.42 | 0 / 816 | rechazado |

**Conclusión:** la hipótesis "más exploración sube el éxito en N1" **se rechaza** en el rango 0.01-0.1 con 200 000 pasos y una semilla: ninguna configuración supera a C0 en ≥5 pp (todas 0%). Aun con ent_coef 0.1 la entropía de la política baja de ~1.6 (máximo ln 5 = 1.61) a ~1.2 y el retorno de entrenamiento se queda en -25 a -30, es decir, la política sigue prefiriendo quedarse quieta. Los 4 runs tienen cero éxitos durante el entrenamiento: sin ninguna entrega la señal de éxito nunca aparece, así que el coeficiente de entropía no puede corregirlo.

**Lectura:** el cuello de botella es la recompensa dispersa frente a penalizaciones que dominan al explorar (aleatoria: -265 por episodio vs -25.5 quieta), no un hiperparámetro de PPO. Antes de más barridos de PPO conviene una decisión de R1 sobre la recompensa (nueva versión `warehouse-v2`, nueva familia de modelos) o ayudar al descubrimiento (p. ej. nivel de arranque más cercano a la estación). Otras opciones sin cambiar el ambiente, de menor probabilidad: más pasos (1M), gamma 0.995, semillas distintas.

## C6: otro tipo de modelo, DQN (2026-11-06, mismo ambiente warehouse-v1 y misma recompensa)
Cambio de **algoritmo**, no de recompensa: DQN de Stable-Baselines3 (acciones Discrete(5), replay buffer 100 000, epsilon-greedy 1.0 -> 0.05 durante el 50% del presupuesto, lr 5e-4, batch 64, red [64, 64], target update 1000). Presupuesto 200 000 pasos exactos, 4.5 min en CPU (~740 pasos/s). Justificación (enunciado sec. 03): otros algoritmos se admiten si son compatibles con las acciones del mundo; PPO sigue siendo la referencia.

| Run | Algoritmo | Éxito (suite-n1-v1) | Retorno medio | Éxitos en entrenamiento | Estado |
|---|---|---:|---:|---:|---|
| n1-c0-seed0 | PPO | 0% | -25.50 | 0 / 816 | candidato (baseline) |
| n1-c6-seed0 | DQN | 0% | -25.22 | 0 / 800 | **rechazado** |

**Decisión:** no supera a C0 en ≥5 pp (0 pp); se rechaza según `configs/criterios.yaml` y se conserva la evidencia. La hipótesis "epsilon-greedy + replay evitan el colapso" **no se confirma**: tampoco hubo ninguna entrega durante el entrenamiento (con epsilon alto, ~250 pasos aleatorios por episodio), y la política final vuelve a FRENAR en 12 350 de 12 500 pasos evaluados.

**Lectura conjunta (6 runs, 2 algoritmos, 0% de éxito):** ni la exploración de PPO (ent_coef 0-0.1) ni la de DQN descubren la secuencia detenerse-orientarse-interactuar-ir a la entrega en 250 pasos: una política aleatoria hace 0.05 recogidas por episodio y ninguna entrega. El cuello de botella es el descubrimiento de la tarea, no el algoritmo ni sus hiperparámetros. Opciones sin tocar la recompensa: (a) clonar el comportamiento del heurístico BFS (demostraciones versionadas con DVC) y afinar con RL; (b) iniciar el episodio más cerca de la estación (cambio del ambiente: decisión de R1); (c) cambiar la recompensa (R1, `warehouse-v2`).


## M1 · Baseline PPO en `warehouse-v2` con 3 productos aleatorios (escrito antes de entrenar, 2026-11-13)
**Run:** `m1-c0-seed0` · config `configs/experiments/m1_c0_makeup3.yaml` · experimento MLflow `warehouse-m1` · tipo `candidato`.

**Qué cambia respecto de C0 (v1):** únicamente el ambiente. Modelo (PPO `MlpPolicy` [64,64]), hiperparámetros y presupuesto
(200 000 pasos) son idénticos a `c0_baseline_n1.yaml`. Ambiente `warehouse-v2`: observación `Box(27)` con posición propia y
del objetivo, acciones `Discrete(8)` con SUBIR/BAJAR/CARGAR/DESCARGAR, mapa 25 × 19, batería 180, 400 pasos.
Cada episodio sortea 3 SKU distintos de 1 unidad (stock repuesto al reiniciar).

**Hipótesis:** dar al agente su posición, la del objetivo y la elevación necesaria hace posible aprender la secuencia
navegar–detenerse–subir–cargar–bajar–descargar, y sortear los productos en cada episodio evita que memorice una ruta.
**Qué la refutaría:** 0% de éxito en `suite-m1-v1` o un comportamiento degenerado (quedarse quieto) como en v1.
**Referencias (misma suite):** política aleatoria y heurística BFS. **Comparación:** no se compara el retorno con v1
(otra misión y otro mapa); solo tasa de éxito, pasos, batería, colisiones e interacciones inválidas.
**Criterios (fijados antes, `configs/criterios.yaml`):** adoptar si supera al baseline vigente en ≥5 pp de éxito y sin subir
colisiones más de 10%. Al ser el primer run de la familia, se registra como `candidato` y las referencias fijan el techo y el piso.
**Limitaciones declaradas:** una sola semilla de entrenamiento, no hay finalistas ni 3 semillas todavía, y el modelo no ve el
SKU ni el nivel de la línea (solo la elevación objetivo).

### Presupuesto real por run (v2)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1-c0-seed0 | m1 | 204 800 (solicitados 200 000; múltiplo de 8 192 = 2048 × 4) | 7.9 (474.6 s, ~540 pasos/s) | candidato (baseline v2, no útil) |

### Resultados M1 (2026-11-13, semilla 0, `suite-m1-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, pasillo abierto)
Run MLflow `warehouse-m1/m1-c0-seed0` (id `f494073adf3d4b95ab512a81efe8e46a`), commit `b87876203c2764cfd8717d42c6264aa9ab3ae7c9` (limpio), tag de ambiente `env/warehouse-v2`,
config SHA-256 `cea7f1c9…c477`, modelo SHA-256 `5b2d734e…3c0c`. Manifiesto: `manifests/m1-c0-seed0.json`. Evidencia por episodio: `docs/resultados/eval/m1-c0-seed0/`.

| Política | Éxito | Retorno medio ± std | Pasos | Batería usada | Colisiones | Int. inválidas | Entregas | Recogidas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| aleatoria | 0% | −517.9 ± 35.0 | 400 | 96.1 | 15.3 | 199.6 | 0.0 | 0.0 |
| regla (BFS + secuencia SUBIR/CARGAR/BAJAR/DESCARGAR) | **100%** | +115.9 ± 1.4 | 79.9 | 49.7 | 0.0 | 0.0 | 3.0 | 3.0 |
| PPO `m1-c0-seed0` | **0%** | −41.0 ± 0.2 | 400 | 42.9 | 0.0 | 0.0 | 0.0 | 0.0 |

**Decisión:** primer run de la familia `warehouse-v2`, queda como `candidato` (baseline). No hay baseline vigente contra el cual aplicar
el criterio de ≥5 pp; **no es un modelo útil** y no se recomienda. Las referencias fijan el piso (0%) y el techo sin aprendizaje (100%).

**Hipótesis M1: no se confirma** con este presupuesto y una semilla. Dar la posición propia, la del objetivo y la elevación no bastó para descubrir la secuencia.

**Diagnóstico (hechos medidos):**
- 512 episodios de entrenamiento, 0 éxitos. El retorno medio de los primeros 10 fue −503.1 y el de los últimos 10 −72.8; la evaluación periódica (5 episodios cada 20 000 pasos) se queda en ≈ −40.8 desde los 40 000 pasos, que es el retorno de no hacer nada (−0.1 × 400 pasos más batería).
- En la evaluación final la política elige FRENAR en 18 677 de 20 000 pasos (93.4%), gira 1 306 veces y avanza 17; nunca usa SUBIR, BAJAR, CARGAR ni DESCARGAR. Se desplaza 0.3 m en promedio.
- La aleatoria hace 199.6 interacciones inválidas por episodio (−2 cada una) y 15.3 colisiones: explorar cuesta del orden de −500 por episodio frente a −41 por quedarse quieto, como en v1.

**Lectura (hipótesis de diagnóstico, no causa demostrada):** el problema de v1 reaparece en v2. Con una secuencia más larga (navegar, detenerse, orientarse, SUBIR 1–3 veces, CARGAR, BAJAR varias veces, ir a despacho, DESCARGAR) una política aleatoria casi nunca llega a la primera recogida, no ve señal positiva y las penalizaciones de explorar dominan. Más posición y objetivo no cambian eso. Opciones sin tocar la recompensa: clonar el comportamiento de la heurística BFS con demostraciones versionadas (DVC) y afinar con RL; más pasos o semillas; reducir la secuencia en un nivel previo (p. ej. un producto en balda 1). Cambiar la recompensa o el arranque del episodio es una decisión de R1 y una nueva versión (`warehouse-v3`). **No se ajustó la recompensa para aparentar éxito.**

**Limitaciones:** una semilla de entrenamiento; sin finalistas ni 3 semillas; sin suite de incidente (pasillo cerrado) para v2 todavía; el modelo no ve el SKU ni el nivel de la línea, solo la elevación objetivo; evaluación solo en pasillo abierto.


## Barrido de penalización por interacción inválida (escrito antes de entrenar, 2026-11-13)
**Contexto:** `m1-c0-seed0` (v2, 0% de éxito, FRENAR en 93% de los pasos). En la evaluación aleatoria, una interacción inválida cuesta −2 y ocurre
199.6 veces por episodio (≈ −399 de ≈ −518).

**Hipótesis (opción B, una dimensión):** bajar `invalid_interaction` hace que explorar acciones como CARGAR/SUBIR/BAJAR deje de ser mucho peor que
quedarse quieto (≈ −41), y el agente descubre la secuencia.
**Qué la refutaría:** que ningún run con penalización menor supere al control en ≥ 5 pp de éxito en `suite-m1-v1` (criterio de `configs/criterios.yaml`).
**Cuentas previas (aritmética, no resultados):** con −0.2 una política aleatoria pasaría de ≈ −518 a ≈ −160 por episodio y con −0.05 a ≈ −130;
ambas siguen por debajo de quedarse quieto (−41), de modo que no se garantiza que bajar solo esta penalización quite el colapso.

| Run | `invalid_interaction` | Cambio | Config |
|---|---:|---|---|
| m1-c0b-seed0 | −2 (por defecto) | control en warehouse-v3 | `m1_c0b_control_v3.yaml` |
| m1-r1-seed0 | −1 | única diferencia | `m1_r1_invalida_1.yaml` |
| m1-r2-seed0 | −0.2 | única diferencia | `m1_r2_invalida_02.yaml` |
| m1-r3-seed0 | −0.05 | única diferencia | `m1_r3_invalida_005.yaml` |

Igual en los cuatro: PPO, hiperparámetros de C0, 200 000 pasos, semilla 0, ambiente de 3 productos aleatorios, `suite-m1-v1` (50 episodios).
`m1-c0-seed0` (v2) queda como referencia histórica; el control v3 evita comparar entre versiones. Retornos no comparables entre runs
con coeficientes distintos: se compara éxito, pasos, batería, choques e inválidas.

### Presupuesto real por run (barrido)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1-c0b-seed0 | m1 | 204 800 | 10.0 (4 runs en paralelo, ~400-550 pasos/s cada uno) | candidato (control) |
| m1-r1-seed0 | m1 | 204 800 | 10.0 (4 runs en paralelo, ~400-550 pasos/s cada uno) | rechazado |
| m1-r2-seed0 | m1 | 204 800 | 10.1 (4 runs en paralelo, ~400-550 pasos/s cada uno) | rechazado |
| m1-r3-seed0 | m1 | 204 800 | 9.9 (4 runs en paralelo, ~400-550 pasos/s cada uno) | rechazado |

### Resultados del barrido (2026-11-13, semilla 0, `suite-m1-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, pasillo abierto)
Código: commit `30c34fb`, tag `env/warehouse-v3`. Los cuatro runs se entrenaron en paralelo (por eso ~10 min cada uno frente a 7.9 min del run solo). Manifiestos en `manifests/m1-{c0b,r1,r2,r3}-seed0.json`; evidencia por episodio en `docs/resultados/eval/<run>/`.
`git_dirty` figura `true` en los metadatos de r1–r3 solo porque las carpetas de salida de los runs hermanos aún no estaban versionadas; ningún archivo versionado cambió.

| Run | `invalid_interaction` | Éxito | Retorno medio | Retorno medio de los primeros 10 episodios de entrenamiento | FRENAR en la evaluación | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---:|---|
| m1-c0b-seed0 | −2 (control) | 0% | −41.0 | −503.1 | 93.4% | 0 / 512 | candidato (control) |
| m1-r1-seed0 | −1 | 0% | −40.0 | −302.3 | 98.5% | 0 / 512 | **rechazado** |
| m1-r2-seed0 | −0.2 | 0% | −40.2 | −141.6 | 99.2% | 0 / 512 | **rechazado** |
| m1-r3-seed0 | −0.05 | 0% | −40.0 | −111.5 | 98.3% | 0 / 512 | **rechazado** |

La heurística BFS obtiene 100% (retorno +115.9) bajo los cuatro conjuntos de coeficientes; los retornos entre runs con recompensas distintas no son comparables, la tasa de éxito sí.

**Decisión:** ningún run supera al control en ≥ 5 pp de éxito (todos 0 pp), así que r1, r2 y r3 se **rechazan** según `configs/criterios.yaml`; se conservan con su evidencia. **La hipótesis «bajar la penalización por interacción inválida permite descubrir la tarea» se rechaza** en el rango −1 a −0.05 con 200 000 pasos y una semilla.

**Hechos medidos:**
- **El control reproduce a `m1-c0-seed0` (v2) exactamente** (retorno −41.0, FRENAR 93.4%, 0 / 512): la comparación entre versiones es válida y el entrenamiento es determinista.
- Bajar la penalización **sí redujo el costo de explorar**: el retorno medio de los primeros 10 episodios pasó de −503 a −302, −142 y −112.
- Aun así, **la política colapsó más** hacia quedarse quieta: FRENAR pasó de 93.4% a 98.5%, 99.2% y 98.3%. Ningún run tuvo una sola entrega en entrenamiento y ninguno usó CARGAR, DESCARGAR, SUBIR ni BAJAR en la evaluación.
- Con −0.05, el retorno inicial (−111) sigue por debajo de quedarse quieto (−40): la diferencia (~−70) corresponde sobre todo a los choques (15.3 × −5 ≈ −77 en la política aleatoria).

**Lectura (hipótesis de diagnóstico, no causa demostrada):** las inválidas no eran el cuello de botella. Mientras ninguna conducta explorada produzca recompensa positiva, quedarse quieto (≈ −40, la penalización por tiempo) sigue siendo la mejor política y PPO converge a ella; reducir un costo de explorar no crea una señal que seguir. Quedan dos candidatos a probar, uno por experimento: (1) bajar el castigo de choques (−5), que es el costo restante; (2) **bonos por sub-pasos pagados una vez por línea** (llegar de frente al estante, alcanzar la altura correcta, bajar tras cargar), que dan señal positiva antes de la primera entrega y respetan la regla de «hitos una sola vez». La opción A (clonar la heurística y afinar con RL) sigue pendiente. No se tocaron modelo ni hiperparámetros.

**Limitaciones:** una semilla por configuración (sin medir la variación entre semillas), presupuesto de 200 000 pasos y evaluación solo con pasillo abierto.


## Barrido de penalización por choque con inválidas en −0.2 (escrito antes de entrenar, 2026-11-13)
**Contexto:** el barrido anterior (inválidas −1, −0.2, −0.05) dio 0% de éxito en los tres runs y la política colapsó a FRENAR (98–99%). Con inválidas en −0.05 la
exploración seguía ~70 por debajo de quedarse quieto, sobre todo por choques (15.3 × −5 ≈ −77). Instrucción del equipo: fijar `invalid_interaction` en **−0.2** y
probar distintas penalizaciones por choque.

**Hipótesis (una dimensión respecto de `m1-r2`):** bajar `collision` de −5 a valores menores hace que explorar deje de ser mucho peor que quedarse quieto y el agente
descubre la secuencia.
**Qué la refutaría:** que ningún run supere a `m1-r2` en ≥ 5 pp de éxito en `suite-m1-v1` (criterio de `configs/criterios.yaml`).
**Cuentas previas (aritmética con los conteos de la política aleatoria de `m1-c0`, no resultados):** retorno aleatorio por episodio ≈ −40 (inválidas −0.2 × 199.6) + 15.3 × `collision`
− 42 (tiempo y batería): −5 → ≈ −160; −2 → ≈ −113; −1 → ≈ −98; −0.5 → ≈ −90; −0.1 → ≈ −83. Todas siguen por debajo de quedarse quieto (≈ −41) porque las inválidas aportan ≈ −40
por sí solas: **bajar solo los choques no garantiza quitar el colapso**; lo que se mide es cuánto se acerca la exploración al piso de −41.

| Run | `invalid_interaction` | `collision` | Config |
|---|---:|---:|---|
| m1-r2-seed0 (control, ya entrenado) | −0.2 | −5 (por defecto) | `m1_r2_invalida_02.yaml` |
| m1-r4-seed0 | −0.2 | −2 | `m1_r4_choque_2.yaml` |
| m1-r5-seed0 | −0.2 | −1 | `m1_r5_choque_1.yaml` |
| m1-r6-seed0 | −0.2 | −0.5 | `m1_r6_choque_05.yaml` |
| m1-r7-seed0 | −0.2 | −0.1 | `m1_r7_choque_01.yaml` |

Igual en todos: PPO, hiperparámetros de C0, 200 000 pasos, semilla 0, 3 productos aleatorios, código `env/warehouse-v3`, `suite-m1-v1` (50 episodios).
`m1-r2` es el control porque comparte código, semilla y todo lo demás; la prueba `test_collision_sweep_configs_change_one_dimension_from_r2` lo verifica en los YAML.
Retornos solo comparables entre runs con los mismos coeficientes; se compara éxito, pasos, batería, choques e inválidas.

### Presupuesto real por run (barrido de choques)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1-r4-seed0 | m1 | 204 800 | 10.0 (4 runs en paralelo, ~550 pasos/s cada uno) | rechazado |
| m1-r5-seed0 | m1 | 204 800 | 10.1 (4 runs en paralelo, ~550 pasos/s cada uno) | rechazado |
| m1-r6-seed0 | m1 | 204 800 | 10.1 (4 runs en paralelo, ~550 pasos/s cada uno) | rechazado |
| m1-r7-seed0 | m1 | 204 800 | 10.0 (4 runs en paralelo, ~550 pasos/s cada uno) | rechazado |

### Resultados del barrido de choques (2026-11-13, semilla 0, `suite-m1-v1`, 50 episodios, semillas 10000–10049, acciones deterministas)
Código: commit `423a014`. `git_dirty` figura `true` en r6 y r7 (y en `m1-r2`, del barrido anterior) solo por carpetas de salida de runs hermanos sin versionar; ningún archivo versionado cambió.
Todos con `invalid_interaction` = −0.2. Control: `m1-r2` (`collision` −5).

| Run | `collision` | Éxito | Retorno medio | Retorno medio de los primeros 10 episodios de entrenamiento | FRENAR en la evaluación | Choques / episodio (evaluación) | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| m1-r2-seed0 (control) | −5 | 0% | −40.2 | −141.6 | 99.2% | 0.0 | 0 / 512 | rechazado (barrido anterior) |
| m1-r4-seed0 | −2 | 0% | −38.4 | −105.6 | 97.3% | 0.0 | 0 / 512 | **rechazado** |
| m1-r5-seed0 | −1 | 0% | −39.3 | −93.6 | 98.2% | 0.0 | 0 / 512 | **rechazado** |
| m1-r6-seed0 | −0.5 | 0% | −40.0 | −87.6 | 84.6% | 4.0 | 0 / 512 | **rechazado** |
| m1-r7-seed0 | −0.1 | 0% | −38.8 | −82.8 | 94.4% | 9.6 | 0 / 512 | **rechazado** |

**Decisión:** ningún run supera al control en ≥ 5 pp de éxito (todos 0 pp); r4–r7 se **rechazan** según `configs/criterios.yaml` y se conservan con su evidencia. **La hipótesis «bajar la penalización por choque (con inválidas en −0.2) permite descubrir la tarea» se rechaza** en el rango −2 a −0.1 con 200 000 pasos y una semilla.

**Hechos medidos:**
- Bajar el castigo de choques redujo el costo inicial de explorar de forma monótona: retorno medio de los primeros 10 episodios −141.6 → −105.6 → −93.6 → −87.6 → −82.8, como predecían las cuentas previas (≈ −160 a ≈ −83). Seguían por debajo de quedarse quieto (≈ −41), como se advirtió.
- Con choques baratos la política **se mueve más** (FRENAR baja a 84.6% en r6) pero sin rumbo: **0 recogidas y 0 entregas en todos los runs**, 0 éxitos en 512 episodios de entrenamiento cada uno, y ninguna acción de CARGAR, DESCARGAR, SUBIR o BAJAR en la evaluación.
- **Efecto secundario:** con −0.5 y −0.1, en la semilla de evaluación 10033 la política quedó atascada contra un muro (199 y 219 choques) hasta agotar la batería (`battery_depleted`, 329 y 230 pasos). Un choque casi gratis no es rentable (el retorno sigue siendo negativo) pero es una trampa de comportamiento y termina el episodio como fallo.

**Lectura (hipótesis de diagnóstico):** tras dos barridos de penalizaciones (inválidas y choques), 8 runs con castigos menores dieron 0% de éxito. El costo de explorar ya no es el cuello de botella; falta una **señal positiva** accesible antes de la primera entrega. Quedan dos caminos: bonos por sub-pasos pagados una vez por línea (llegar de frente al estante, alcanzar la altura correcta, bajar tras cargar), y clonación de comportamiento desde la heurística (opción A). No se recomienda seguir bajando penalizaciones: con −0.1 aparece el atasco contra muros.

**Limitaciones:** una semilla por configuración; presupuesto de 200 000 pasos; solo pasillo abierto.


## Barrido de penalización por distancia Manhattan en mapa abierto (escrito antes de entrenar, 2026-11-13)
**Contexto:** ocho runs con penalizaciones menores (inválidas y choques) dieron 0% de éxito; el costo de explorar dejó de ser el cuello de botella y falta una señal que premie acercarse al
destino. Instrucción del equipo: dejar `collision` en **−1**, mantener `invalid_interaction` en **−0.2**, añadir una **penalización por la distancia Manhattan** al destino por paso
(mayor cuanto más lejos) y probarla en un **mapa sin muros interiores ni pasos estrechos**.

**Hipótesis (una dimensión respecto del control `m1o-c0`):** penalizar la distancia Manhattan al objetivo hace que quedarse quieto o vagar lejos cueste más que acercarse al estante, y esa señal permite
descubrir la secuencia hasta la primera recogida y la entrega.
**Qué la refutaría:** que ningún run con término de distancia supere a `m1o-c0` en ≥ 5 pp de éxito en `suite-m1o-v1`.
**Retornos de referencia medidos antes de entrenar** (20 episodios, semillas 10000–10019, mapa abierto, `invalid` −0.2, `collision` −1; no son resultados del modelo):

| `distance` | quieto (FRENAR) | aleatoria | heurística BFS |
|---:|---:|---:|---:|
| 0 (control) | −40.8 | −89.3 | +114.9 |
| −0.005 | −62.5 | −109.6 | +112.7 |
| −0.01 | −84.2 | −129.9 | +110.5 |
| −0.02 | −127.6 | −170.5 | +106.0 |

La heurística sigue siendo la mejor política con los tres coeficientes (100% de éxito). El término hace quedarse quieto en la base 22–87 puntos peor que en el control, mientras que llegar al estante lo
reduce (≈ −0.02 × 10 celdas por paso ahorrados). Quedan por debajo de la aleatoria en el mismo orden de magnitud, de modo que **no se garantiza** que el término baste: la recogida sigue exigiendo
detenerse, SUBIR 1–3 veces y CARGAR sin señal intermedia propia, y al cambiar de objetivo la penalización por estado salta.

| Run | `invalid_interaction` | `collision` | `distance` | Config |
|---|---:|---:|---:|---|
| m1o-c0-seed0 (control) | −0.2 | −1 | 0 | `m1o_c0_control.yaml` |
| m1o-d1-seed0 | −0.2 | −1 | −0.005 | `m1o_d1_distancia_0005.yaml` |
| m1o-d2-seed0 | −0.2 | −1 | −0.01 | `m1o_d2_distancia_001.yaml` |
| m1o-d3-seed0 | −0.2 | −1 | −0.02 | `m1o_d3_distancia_002.yaml` |

Igual en todos: PPO, hiperparámetros de C0, 200 000 pasos, semilla 0, 3 productos aleatorios, mapa `configs/layout_v0.5.json`, código `env/warehouse-v4`, `suite-m1o-v1` (50 episodios, semillas 10000–10049).
Retornos solo comparables entre runs con los mismos coeficientes; se compara éxito, pasos, batería, choques e inválidas.

### Presupuesto real por run (barrido de distancia)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-c0-seed0 | m1o | 204 800 | 10.7 (4 runs en paralelo, ~540 pasos/s cada uno) | candidato (control) |
| m1o-d1-seed0 | m1o | 204 800 | 10.4 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |
| m1o-d2-seed0 | m1o | 204 800 | 10.4 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |
| m1o-d3-seed0 | m1o | 204 800 | 10.3 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |

### Resultados del barrido de distancia (2026-11-13, semilla 0, `suite-m1o-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, mapa abierto)
Código: commit `1b82ca9` (tag `env/warehouse-v4`). `git_dirty` figura `true` en c0 y d3 solo por carpetas de salida de runs hermanos sin versionar; ningún archivo versionado cambió.
`invalid_interaction` −0.2 y `collision` −1 en todos. Manifiestos en `manifests/m1o-*-seed0.json`; evidencia por episodio en `docs/resultados/eval/m1o-*/`.

| Run | `distance` | Éxito | Retorno medio | Episodios con una recogida | Dist. Manhattan final al primer objetivo (media) | Terminó a ≤ 2 celdas | FRENAR | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| m1o-c0-seed0 (control) | 0 | 0% | −37.1 | **7 / 50** | 1.4 | 48 / 50 | 61.2% | candidato |
| m1o-d1-seed0 | −0.005 | 0% | −46.6 | 0 / 50 | 3.5 | 32 / 50 | 86.2% | **rechazado** |
| m1o-d2-seed0 | −0.01 | 0% | −46.8 | 0 / 50 | 1.8 | 45 / 50 | 8.0% (GIRAR 90%) | **rechazado** |
| m1o-d3-seed0 | −0.02 | 0% | −62.5 | 0 / 50 | 2.9 | 38 / 50 | 80.8% | **rechazado** |

La heurística BFS logra 100% en 71 pasos bajo los tres coeficientes (retorno +115.1, +112.7, +110.3, +105.5 según `distance`); los retornos entre runs con coeficientes distintos no son comparables, el éxito sí.

**Decisión:** ningún run con término de distancia supera al control del mismo mapa en ≥ 5 pp de éxito (todos 0 pp) y ninguno logra una sola recogida, mientras el control sí; d1–d3 se **rechazan** según `configs/criterios.yaml` y se conservan con su evidencia. **La hipótesis «penalizar la distancia Manhattan permite descubrir la tarea» se rechaza** en el rango −0.005 a −0.02 con 200 000 pasos y una semilla. Por la regla fijada antes de entrenar (solo continuar si algún run era favorable), **no se entrenó la versión con muros interiores con el término de distancia**.

**Hechos medidos:**
- El término sí cambia la conducta: d2 y d3 terminan cerca del primer objetivo (45 y 38 de 50 episodios a ≤ 2 celdas) con retornos mucho mejores que quedarse quieto en la base (−84 y −128 según las referencias previas), pero ese acercamiento no se convierte en recogidas.
- **El control es la política más avanzada hasta ahora** (ningún run anterior recogió nada): en el mapa abierto, con `collision` −1 e `invalid_interaction` −0.2, llega a ≤ 2 celdas del primer objetivo en 48/50 episodios y completa la secuencia navegar–detenerse–SUBIR–CARGAR en 7/50 (≈ 23 pasos; son episodios cuyo primer producto está en E05, nivel 1 o 2). La comparación pertinente es con `m1-r5-seed0` (mismos coeficientes, mapa con muro): 0 recogidas y FRENAR 98.2%. Las únicas diferencias entre ambos son el mapa y la versión del código (término `distance` por defecto 0). Es un solo run por configuración.
- **Dónde se atasca:** tras el primer CARGAR la bandeja queda arriba (0.99 m) y el robot no puede moverse hasta bajarla. En las semillas 10002, 10014, 10015 y 10020 la política nunca usa BAJAR (1 sola vez en 4 episodios; 0.0% en la evaluación) y pasa los ~377 pasos restantes girando y frenando con la carga puesta: **no ha descubierto que debe bajar la bandeja**.

**Lectura (hipótesis de diagnóstico, no causa demostrada):** quitar el muro y los pasos estrechos (junto con los castigos menores) facilita aprender la navegación, pero la penalización de distancia no aporta nada sobre eso y empeora el resultado; el siguiente cuello de botella es BAJAR tras cargar, que no tiene ninguna señal propia. Candidato siguiente: bono único por línea al bajar la bandeja tras cargar (y por llegar a la altura correcta), sobre el mapa abierto. También queda la clonación de comportamiento. No se ha probado por qué el término de distancia no ayuda.

**Limitaciones:** una semilla por configuración; presupuesto de 200 000 pasos; evaluación en mapa abierto (sin incidente de pasillo); la comparación control frente a `m1-r5` mezcla mapa y versión de código.

### Diagnóstico del control y de d2/d3 (2026-11-13; repetición determinista de las 50 semillas de `suite-m1o-v1`, acción = la más probable, con las probabilidades de la política)
**Control `m1o-c0` (sin término de distancia):**
- Navegación: llega a una celda de acceso del primer objetivo en 48/50 episodios (mediana: paso 12) y queda mirando al estante en 27/50 (mediana: paso 13). Finales: 20 con la bandeja arriba sin carga, 7 con la bandeja arriba y carga, 15 en una celda de acceso sin mirar al estante, 8 sin llegar.
- Parado y mirando al estante con la bandeja abajo elige SUBIR (27 de 27 veces; probabilidad media 0.50) y sube la bandeja en 27/50 episodios.
- Por nivel que exige el primer producto: nivel 1 → 21 episodios, 12 llegan a la altura, 4 cargan; nivel 2 → 16 episodios, 12 llegan a la altura, 3 cargan; nivel 3 → 13 episodios, ninguno llega a la altura 3 (máximo nivel 2) y ninguno carga.
- Con la bandeja **exactamente** a la altura correcta y mirando al estante, la acción más probable es GIRAR_IZQUIERDA (probabilidad media 0.31; con la bandeja arriba el giro está bloqueado y es una acción vacía) y CARGAR solo 0.16: elige CARGAR 7 veces en total (los 7 casos de recogida).
- Con la bandeja por debajo de la altura necesaria casi siempre elige FRENAR (1 131 de 1 146 pasos; SUBIR 15): no sigue subiendo.
- Tras cargar (bandeja arriba) elige BAJAR 1 vez en 2 636 pasos (probabilidad media 0.045) y pasa el resto girando (acción bloqueada) y frenando.

**d2 y d3 (con `distance`):**
- Llegan y miran al estante pronto (d2: 38/50 episodios, mediana paso 8; d3: 12/50, mediana paso 13), pero parados y mirando con la bandeja abajo **no eligen SUBIR**: d2 elige GIRAR_IZQUIERDA en 864 de 870 pasos (probabilidad de SUBIR 0.26) y d3 GIRAR_DERECHA en 528 de 528 (probabilidad de SUBIR 0.001). Giran sobre la celda de acceso y dejan de mirar al estante (32 y 35 episodios terminan en una celda de acceso sin mirar). La bandeja se sube en 6/50 episodios en d2 y en 0/50 en d3; nunca se carga.
- Medición del incentivo (recompensas con la heurística guionizada, 20 semillas, mapa abierto): tras la primera recogida el siguiente objetivo queda a ≈ 10.1 celdas Manhattan y la bandeja arriba bloquea el movimiento. Retorno de «acercarse al estante y quedarse» frente a «recoger el primer producto y quedarse»: `distance` 0 → −38.0 / −28.0 (recoger gana +10); −0.005 → −40.3 / −47.7; −0.01 → −42.5 / −67.4; −0.02 → −47.1 / −106.7. Con el término, **recoger el primer producto empeora el retorno** salvo que el robot también baje la bandeja y recorra la distancia (completar el pedido da +106 a +115). Esa recompensa solo aparece tras una secuencia larga que ninguna política exploró.
- Lectura: con el término, la señal empuja a quedarse cerca del estante y **en contra** de la recogida; además, en el estado clave (parado, mirando, bandeja abajo) todas las acciones cuestan casi lo mismo, así que nada favorece SUBIR. Es una medición del incentivo, no una prueba de que esa sea la única causa; no se ha probado una variante que lo corrija.


## Barrido de diferencia de distancia + penalización por altura (escrito antes de entrenar, 2026-11-13)
**Contexto:** `m1o-d1`–`d3` (distancia Manhattan por estado) dieron 0% y 0 recogidas. El diagnóstico midió que ese término hacía peor recoger el primer producto que quedarse junto al estante
y que, en el estado clave (parado, mirando, bandeja abajo), todas las acciones costaban casi lo mismo. Instrucción del equipo: (1) la penalización por distancia pasa a ser una **diferencia**; (2) se añade una **penalización
mientras la distancia al destino es 0 (celda de interacción) pero la altura de la bandeja es distinta**. Mapa abierto, `collision` −1, `invalid_interaction` −0.2. Código `env/warehouse-v5`.

**Hipótesis:** la diferencia de distancia (sin salto al cambiar de objetivo) y la penalización por altura distinta en la celda de interacción hacen que subir la bandeja hasta la altura correcta y cargar sea la conducta mejor
pagada, y el agente supera al control del mismo mapa (`m1o-c0`).
**Qué la refutaría:** que ningún run supere a `m1o-c0` en ≥ 5 pp de éxito en `suite-m1o-v1`.

**Retornos de referencia medidos antes de entrenar** (conductas guionizadas, 15 semillas 10000–10014, mapa abierto; no son resultados del modelo):

| Conjunto de coeficientes | quieto en la base | aleatoria | ir al estante y quedarse | subir a la altura y quedarse | recoger el 1.º y quedarse | completar el pedido |
|---|---:|---:|---:|---:|---:|---:|
| control `m1o-c0` | −40.8 | −88.9 | −38.1 | −38.1 | −28.1 | +115.0 |
| e1: Manhattan 0.3 | −40.8 | −88.6 | −35.3 | −35.3 | −25.3 | +127.8 |
| e2: altura −0.1 | −40.8 | −89.2 | −105.9 | −38.8 | −31.3 | +113.2 |
| e3: ambos 0.3 / −0.1 | −40.8 | −88.9 | −103.1 | −35.9 | −28.5 | +126.0 |
| e4: ambos 0.3 / −0.02 | −40.8 | −88.7 | −48.9 | −35.4 | −26.0 | +127.4 |

- **Corregido respecto de v4:** con los cinco conjuntos «recoger el primer producto» rinde más que «ir al estante y quedarse» (en v4 con −0.02 era 60 puntos peor). En e2–e4 el orden es ir y quedarse < subir a la altura < recoger < completar: hay gradiente en el estado clave.
- **Riesgo de evitación (medido):** en e2 y e3 quedarse en el estante con la altura equivocada (−106, −103) es **peor que no ir** (−40.8); solo compensa si el agente sube la bandeja. En e4 la diferencia es pequeña (−48.9). Una política podría aprender a evitar el estante; los runs lo dirán.
- **Límite declarado:** el término de altura no empuja a BAJAR la bandeja tras cargar (el objetivo pasa al siguiente estante). Solo la diferencia Manhattan paga cuando el robot puede volver a moverse.

| Run | `manhattan_progress` | `height_mismatch` | Config |
|---|---:|---:|---|
| m1o-c0-seed0 (control, ya entrenado en v4) | 0 | 0 | `m1o_c0_control.yaml` |
| m1o-e1-seed0 | 0.3 | 0 | `m1o_e1_manhattan_dif.yaml` |
| m1o-e2-seed0 | 0 | −0.1 | `m1o_e2_altura_01.yaml` |
| m1o-e3-seed0 | 0.3 | −0.1 | `m1o_e3_ambos_01.yaml` |
| m1o-e4-seed0 | 0.3 | −0.02 | `m1o_e4_ambos_002.yaml` |

(En los cinco: `invalid_interaction` −0.2, `collision` −1, sin `distance`.) Igual en todos: PPO, hiperparámetros de C0, 200 000 pasos, semilla 0, 3 productos aleatorios, mapa `layout_v0.5`, `suite-m1o-v1` (50 episodios).
El control se entrenó con el código v4; su recompensa es idéntica y los términos nuevos valen 0 por defecto (verificado por prueba). Se reentrenó el mismo control bajo v3→v4 con resultado idéntico en el barrido anterior (`m1-c0b` = `m1-c0`).
Son cuatro runs porque el término de distancia y el de altura se separan (e1, e2) además de combinarse (e3, e4), para saber cuál aporta.

### Presupuesto real por run (barrido v5)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-e1-seed0 | m1o | 204 800 | 10.6 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |
| m1o-e2-seed0 | m1o | 204 800 | 10.2 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |
| m1o-e3-seed0 | m1o | 204 800 | 10.3 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |
| m1o-e4-seed0 | m1o | 204 800 | 10.7 (4 runs en paralelo, ~540 pasos/s cada uno) | rechazado |

### Resultados del barrido v5 (2026-11-13, semilla 0, `suite-m1o-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, mapa abierto)
Código: commit `2b80031` (tag `env/warehouse-v5`). `git_dirty` figura `true` en e1, e2 y e4 solo por carpetas de salida de runs hermanos sin versionar; ningún archivo versionado cambió.
`invalid_interaction` −0.2 y `collision` −1 en todos. Manifiestos en `manifests/m1o-e*-seed0.json`; evidencia por episodio en `docs/resultados/eval/m1o-e*/`.

| Run | `manhattan_progress` | `height_mismatch` | Éxito | Recogidas (media/ep) | Inválidas/ep | CARGAR / SUBIR / BAJAR (% de pasos) | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---|---:|---|
| m1o-c0-seed0 (control, v4) | 0 | 0 | 0% | 0.14 | 0.0 | 0.0 / 0.2 / 0.0 | 0 / 512 | candidato |
| m1o-e1-seed0 | 0.3 | 0 | 0% | 0.00 | 26.6 | 5.2 / 1.8 / 0.0 | 0 / 512 | **rechazado** |
| m1o-e2-seed0 | 0 | −0.1 | 0% | 0.00 | 0.0 | 0.0 / 0.0 / 0.0 | 0 / 512 | **rechazado** |
| m1o-e3-seed0 | 0.3 | −0.1 | 0% | 0.00 | 0.0 | 0.0 / 0.0 / 0.0 | 0 / 512 | **rechazado** |
| m1o-e4-seed0 | 0.3 | −0.02 | 0% | **0.30** | 159.4 | **28.6 / 16.5 / 4.3** | **1 / 512** (3 entregas) | **rechazado** (criterio) |

**Decisión:** ningún run supera al control en ≥ 5 pp de éxito (todos 0 pp); e1–e4 se **rechazan** según `configs/criterios.yaml` y se conservan con su evidencia. **La hipótesis «diferencia de distancia + penalización por altura permite superar al control» se rechaza** con 200 000 pasos y una semilla. e4 es, sin embargo, el run **más avanzado** hasta ahora (ver abajo).

**Diagnóstico (repetición determinista de las 50 semillas, acción más probable):**
- **e2 y e3: evitación del estante, como se advirtió antes de entrenar.** En 0/50 episodios llegan a una celda de interacción. e3 termina a ≈ 3.0 celdas Manhattan del primer estante (recompensa de acercamiento pero sin entrar en la zona penalizada); e2 se queda cerca de la base (≈ 5.2 celdas) girando (GIRAR_DERECHA 97.7%). Con −0.1 por puesto de bandeja, estar en la celda de interacción con la altura equivocada rinde −103 a −106 frente a −41 de no ir (medido antes de entrenar): la política aprendió a no ir.
- **e1 (solo diferencia Manhattan): llega y sube, pero no carga.** Llega y mira al estante en 49/50 episodios (mediana: paso 15) y sube la bandeja en 41/50, pero con la bandeja por debajo de la altura exigida elige CARGAR (1 038 pasos, inválida) o FRENAR, y con la bandeja a la altura correcta elige FRENAR (11 192 pasos; probabilidad media de CARGAR 0.17). Cero cargas. No aprende a subir hasta la altura ni a cargar.
- **e4 (ambos, altura −0.02): primera conducta con la cadena casi completa.** Llega al estante en 35/50 episodios, sube la bandeja en 27/50, carga en **12/50** (15 productos; 3 episodios con 2 productos) y baja la bandeja por completo tras cargar en 6/50 (BAJAR 4.3% de los pasos; es la primera vez que un run usa BAJAR). Tuvo **un episodio de entrenamiento con éxito (3 entregas)**: la tarea completa es alcanzable con esta recompensa. Pero en evaluación nunca intenta DESCARGAR en la etapa de entrega y no completa ningún pedido; 3 episodios terminan por batería agotada.
- Lo que falla en e4: con la bandeja por debajo de la altura exigida elige CARGAR (2 156 pasos, inválida) más que SUBIR (559); a la altura correcta elige BAJAR (354) en vez de CARGAR (12; probabilidades 0.36 frente a 0.34): oscila entre subir y bajar. Tras cargar mezcla casi uniformemente giros bloqueados, SUBIR, BAJAR y CARGAR. Esto da 159 inválidas por episodio (≈ −32 de retorno) y un retorno medio de −70.5, peor que el control aunque la conducta sea más avanzada: el retorno no mide el avance.

**Lectura (hipótesis, no causa demostrada):** el término de altura débil (−0.02) funciona como gradiente sin crear una zona prohibida; el fuerte (−0.1) la crea. La diferencia Manhattan sola no basta (e1). Falta señal directa para los pasos intermedios (subir exactamente hasta la altura, cargar, bajar). Candidatos: (a) el mismo e4 con más pasos y 3 semillas (e4 es el único con un éxito en entrenamiento; con una semilla no se sabe cuánto varía), (b) bonos únicos por línea al alcanzar la altura correcta y al bajar tras cargar, (c) una penalización de altura intermedia (−0.05) para ver el punto entre −0.02 y −0.1.

**Limitaciones:** una semilla por configuración; presupuesto de 200 000 pasos; el control se entrenó bajo el código v4 con recompensa idéntica; evaluación en mapa abierto; el éxito en entrenamiento de e4 es un único episodio.


## e4 con más pasos y 3 semillas, y penalización de altura intermedia (escrito antes de entrenar, 2026-11-13)
**Contexto:** en el barrido v5 todos los runs dieron 0% de éxito, pero `m1o-e4` (diferencia Manhattan 0.3, altura −0.02) fue el más avanzado: recogió en 12/50 episodios, bajó la bandeja en 6/50 y tuvo 1/512 episodios de entrenamiento con 3 entregas.
Instrucción del equipo: (1) repetir e4 con más pasos y 3 semillas; (3) probar una penalización de altura intermedia (−0.05). Código `env/warehouse-v5` sin cambios.

### Experimento 1: e4 con 3 veces los pasos y 3 semillas
- **Hipótesis:** con 600 000 pasos la política de e4 completa la cadena (subir hasta la altura, cargar, bajar, entregar) y supera al control del **mismo presupuesto**.
- **Control del mismo presupuesto:** `m1o-c0l` (recompensa base `invalid` −0.2 y `collision` −1, sin términos v4/v5), 600 000 pasos, semilla 0. Sin él no se distingue el efecto de los pasos extra del de la recompensa. Solo una semilla de control.
- **Criterio (fijado ahora, antes de ver resultados):** adoptar si el éxito **medio de las 3 semillas** de `m1o-e4l` en `suite-m1o-v1` supera al de `m1o-c0l` en ≥ 5 pp; si no, rechazar. Se reportan la media, la desviación y cada semilla.
- **Qué la refutaría:** media de éxito de las 3 semillas < control + 5 pp.
- **Métricas secundarias descriptivas (no deciden):** recogidas por episodio, entregas por episodio, episodios con la bandeja bajada tras cargar, inválidas por episodio, episodios de entrenamiento con éxito.

### Experimento 3: altura −0.05 con 200 000 pasos
- **Hipótesis:** −0.05 mantiene el gradiente de e4 (−0.02) sin crear la zona a evitar de e2/e3 (−0.1) y supera al control `m1o-c0` (200 000 pasos).
- **Medición previa (conductas guionizadas, 10 semillas, mapa abierto; no son resultados del modelo):**

| `height_mismatch` | quieto en la base | ir al estante y quedarse | subir a la altura y quedarse | recoger el 1.º y quedarse | completar el pedido |
|---:|---:|---:|---:|---:|---:|
| −0.02 (e4) | −40.8 | −49.5 | −35.6 | −26.3 | +127.6 |
| −0.05 (e5) | −40.8 | −70.6 | −35.8 | −27.7 | +127.0 |
| −0.10 (e2/e3) | −40.8 | −105.8 | −36.1 | −30.0 | +126.0 |

  Con −0.05 ir al estante y quedarse sigue costando ≈ 30 más que quedarse en la base (con −0.02: ≈ 9; con −0.1: ≈ 65), de modo que **queda un riesgo moderado de evitación**.
- **Criterio:** éxito en `suite-m1o-v1` ≥ 5 pp por encima de `m1o-c0`; si no, rechazar.
- **Métricas secundarias descriptivas:** episodios que llegan a una celda de interacción (e2/e3: 0/50; e4: 35/50), recogidas por episodio (e4: 0.30), uso de SUBIR/CARGAR/BAJAR.

| Run | Pasos pedidos | Semilla | `manhattan_progress` | `height_mismatch` | Config |
|---|---:|---:|---:|---:|---|
| m1o-e4l-seed0 | 600 000 | 0 | 0.3 | −0.02 | `m1o_e4l_seed0.yaml` |
| m1o-e4l-seed1 | 600 000 | 1 | 0.3 | −0.02 | `m1o_e4l_seed1.yaml` |
| m1o-e4l-seed2 | 600 000 | 2 | 0.3 | −0.02 | `m1o_e4l_seed2.yaml` |
| m1o-c0l-seed0 (control 600k) | 600 000 | 0 | 0 | 0 | `m1o_c0l_control_600k.yaml` |
| m1o-e5-seed0 | 200 000 | 0 | 0.3 | −0.05 | `m1o_e5_altura_005.yaml` |

Igual en todos: PPO, hiperparámetros de C0, `invalid_interaction` −0.2, `collision` −1, 3 productos aleatorios, mapa `layout_v0.5`, `suite-m1o-v1` (50 episodios), código `env/warehouse-v5`.
Con 600 000 pasos pedidos el presupuesto efectivo será 606 208 (múltiplo de 8 192).

### Presupuesto real por run (e4l, c0l, e5)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-e4l-seed0 | m1o | 606 208 | 25.8 (5 runs en paralelo, ~525 pasos/s cada uno) | candidato |
| m1o-e4l-seed1 | m1o | 606 208 | 23.5 (5 runs en paralelo, ~525 pasos/s cada uno) | candidato |
| m1o-e4l-seed2 | m1o | 606 208 | 26.0 (5 runs en paralelo, ~525 pasos/s cada uno) | candidato |
| m1o-c0l-seed0 | m1o | 606 208 | 25.6 (5 runs en paralelo, ~525 pasos/s cada uno) | candidato |
| m1o-e5-seed0 | m1o | 204 800 | 8.0 (5 runs en paralelo, ~530 pasos/s cada uno) | rechazado |

### Resultado del experimento 3: altura −0.05 (`m1o-e5-seed0`, 2026-11-13, `suite-m1o-v1`, 50 episodios, acciones deterministas)
Código `env/warehouse-v5`, commit `835cf68`. Manifiesto: `manifests/m1o-e5-seed0.json`. 200 000 pasos pedidos (204 800 efectivos), 8.0 min.

| Run | `height_mismatch` | Éxito | Recogidas/ep | Llegan a una celda de interacción | FRENAR | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---:|---|
| m1o-c0 (control) | 0 | 0% | 0.14 | 48/50 | 61.2% | 0 / 512 | candidato |
| m1o-e4 | −0.02 | 0% | 0.30 | 35/50 | 7.4% | 1 / 512 | rechazado |
| **m1o-e5** | **−0.05** | **0%** | **0.00** | **0/50** | **98.6%** | **0 / 512** | **rechazado** |
| m1o-e3 / e2 | −0.1 | 0% | 0.00 | 0/50 | 22.2% / 0.0% | 0 / 512 | rechazado |

**Decisión:** no supera al control en ≥ 5 pp (0 pp); se **rechaza** y se conserva la evidencia. **La hipótesis «−0.05 mantiene el gradiente de e4 sin crear la zona a evitar» se rechaza**: con −0.05 aparece la evitación.
**Hechos medidos:** la política avanza ≈ 5.6 celdas desde la base (la distancia Manhattan media al primer estante baja de 10.7 a 5.1, es decir, a la mitad del camino) y se queda frenando; los 50 episodios terminan «sin llegar» y ninguno entra en una celda de interacción. Cobra la recompensa por acercarse y se detiene antes de la zona donde la altura equivocada cuesta, como se había advertido (ir y quedarse −70.6 frente a −40.8).
**Lectura (hipótesis):** el punto de transición entre gradiente útil y zona a evitar está entre −0.02 y −0.05 en este diseño; e4 (−0.02) queda en el lado útil. Una penalización que se aplica solo dentro de la celda de interacción castiga estar donde hay que estar; un diseño distinto (p. ej. premiar el acierto de altura en lugar de castigar el error) no tiene ese efecto, pero sería otra versión.

### Resultados del experimento 1: e4 con 600 000 pasos y 3 semillas (`m1o-e4l`), con control del mismo presupuesto (2026-11-13, `suite-m1o-v1`, 50 episodios, semillas 10000–10049, acciones deterministas)
Código `env/warehouse-v5`, commit `835cf68`. Presupuesto efectivo 606 208 pasos por run (23.5–26.0 min con 5 runs en paralelo). Manifiestos `manifests/m1o-e4l-seed{0,1,2}.json` y `m1o-c0l-seed0.json`; evidencia por episodio en `docs/resultados/eval/<run>/`.

| Run | Semilla | Éxito | Entregas/ep | Recogidas/ep | Pasos | Choques | Inválidas/ep | Entrenamiento: episodios con 3 entregas | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| m1o-e4l-seed0 | 0 | **92%** (46/50) | 2.76 | 2.92 | 95 | 0.0 | 3.8 | **2 395 / 3 278** | candidato |
| m1o-e4l-seed1 | 1 | 0% | 0.00 | 0.00 | 400 | 0.0 | 258.3 | 0 / 1 512 | candidato (evidencia) |
| m1o-e4l-seed2 | 2 | 0% | 0.00 | 2.42 | 397 | 0.0 | 20.1 | 2 / 1 515 | candidato (evidencia) |
| **e4l, media ± desv. (3 semillas)** | | **30.7% ± 43.4 pp** (desviación poblacional, ddof = 0) | | | | | | | |
| m1o-c0l-seed0 (control, 606 208 pasos) | 0 | 0% | 0.00 | 1.68 | 394 | 0.0 | 31.4 | 0 / 1 513 | candidato (control) |

La heurística BFS logra 100% en ≈ 71 pasos en este mapa.

**Decisión según el criterio fijado antes de entrenar** (adoptar si el éxito medio de las 3 semillas de e4l supera al control del mismo presupuesto en ≥ 5 pp, sin que los choques suban más de 10%): **se cumple** (30.7% − 0% = +30.7 pp; choques 0.0 frente a 0.0). La hipótesis «con 3 veces los pasos la política de e4 completa la cadena y supera al control» **se confirma en promedio**.
**Cuidado con la lectura:** el promedio lo sostiene **una sola semilla de tres** (92%, 0%, 0%); la desviación entre semillas es de 43 pp y el control tiene una sola semilla. No es evidencia de que la configuración sea robusta; es evidencia de que **es alcanzable** (la semilla 0 lo logra con regularidad: 73% de éxito en entrenamiento). No se promueve ningún run a `recomendado` (el ciclo exige finalistas, más semillas y la suite final reservada); los tres e4l quedan `candidato`.

**Diagnóstico (repetición determinista de las 50 semillas de evaluación):**
- **e4l-seed0:** llega a la celda de interacción del primer estante en 50/50 episodios; primera recogida a mediana del paso 16; 46 episodios completan el pedido con la bandeja abajo y vacía. Los 4 fallos (semillas 10020, 10025, 10027, 10040) terminan con 2 productos cargados, 0 entregados y la bandeja arriba (3 por tiempo, 1 por batería agotada). Usa AVANZAR 44.1%, GIRAR 17.2%, FRENAR 14.9%, CARGAR 7.1%, SUBIR 8.0%, BAJAR 7.8%, DESCARGAR 1.0%: la cadena completa.
- **e4l-seed1:** solo 10/50 episodios llegan a la celda de interacción y ninguno recoge; elige DESCARGAR (inválida) en 64.6% de los pasos (258 inválidas por episodio): colapso a una acción inválida, distinto de los colapsos a FRENAR anteriores.
- **e4l-seed2:** llega al estante en 50/50 y recoge 2.42 productos por episodio (como seed0, primera recogida mediana en el paso 16), pero no entrega: 49/50 episodios terminan cargando (38 con la bandeja arriba) y gira en el sitio (GIRAR 83.5%). Tuvo 2 episodios de entrenamiento con éxito.
- **Control c0l (más pasos, sin términos v4/v5):** también aprende a llegar y recoger (1.68 productos por episodio, 50/50 llegan al estante) pero **nunca entrega** (0 entregas): terminan 46/50 con carga (33 con la bandeja arriba). Es decir, más pasos por sí solos dan recogidas pero no entregas en este run; la recompensa de e4 es lo que permite entregar en la semilla 0.
- Patrón común de los fallos (c0l, seed2, y los 4 fallos de seed0): tras cargar, la política se queda con la carga y no completa el trayecto a la cinta con la bandeja abajo.

**Lectura (hipótesis):** la recompensa e4 más presupuesto bastan para resolver el problema en al menos una semilla, y las otras dos se atascan en puntos distintos (no llegar y spam de DESCARGAR; cargar y no entregar). Antes de afirmar que la configuración funciona hay que replicar con más semillas y presupuesto; los puntos de fallo sugieren bonos únicos por línea al bajar tras cargar y al llegar a la cinta con la bandeja abajo (nueva versión).
**Limitaciones:** una semilla por control; 3 semillas por configuración; mapa abierto; 606 208 pasos; no se usó la suite final reservada.

### Curva de e4l-seed0 por pasos de entrenamiento (2026-11-13, `suite-m1o-v1`, 50 episodios, acciones deterministas)
Pregunta del equipo: ¿qué habría pasado con la semilla 0 con el presupuesto original (200 000 pasos)? Ya existe ese run: `m1o-e4-seed0` (misma recompensa, hiperparámetros y semilla; 204 800 pasos) dio **0%** de éxito y 0.30 recogidas por episodio. Como el entrenamiento es determinista (`m1-c0b` reproduce `m1-c0`), repetirlo daría el mismo modelo; en su lugar se evaluaron los 30 checkpoints (uno cada 20 000 pasos) del run de 606 208 pasos. Datos: `docs/resultados/eval/m1o-e4l-seed0-curve.json`.

| Pasos | Éxito | Entregas/ep | Recogidas/ep | Pasos/ep | Inválidas/ep |
|---:|---:|---:|---:|---:|---:|
| 20 000 | 0% | 0.00 | 0.00 | 400 | 0.0 |
| 100 000 | 0% | 0.00 | 0.00 | 400 | 0.0 |
| 200 000 | 0% | 0.00 | 0.06 | 400 | 155.9 |
| 280 000 | 0% | 0.00 | 0.92 | 385 | 53.1 |
| 340 000 | 10% | 0.30 | 1.14 | 388 | 134.7 |
| 380 000 | 26% | 0.78 | 1.60 | 337 | 133.3 |
| 420 000 | 32% | 0.96 | 1.90 | 292 | 51.1 |
| 460 000 | 48% | 1.44 | 2.20 | 249 | 10.4 |
| 480 000 | 76% | 2.28 | 2.68 | 151 | 44.2 |
| 500 000 | 88% | 2.64 | 2.86 | 117 | 25.3 |
| 560 000 | 92% | 2.76 | 2.92 | 96 | 3.2 |
| 600 000 | 90% | 2.70 | 2.88 | 102 | 13.4 |
| 606 208 (modelo final) | 92% | 2.76 | 2.92 | 95 | 3.8 |

**Hechos medidos:**
- Hasta los ≈ 120 000 pasos la política no hace nada útil (400 pasos, 0 recogidas, 0 inválidas): colapso a quedarse quieto, como en los runs de 200 000 pasos.
- A los 200 000 pasos casi no recoge (0.06 por episodio; el run `m1o-e4` de 204 800 pasos recogió 0.30, porque el checkpoint de 200 000 aún no incorpora la última actualización) y dispara las inválidas (156 por episodio): explora acciones nuevas.
- Entre 200 000 y 340 000 pasos las recogidas suben de 0.06 a 1.14 por episodio sin ninguna entrega; el **primer éxito aparece a los 340 000 pasos (10%)**, 76% a los 480 000 y ≈ 88–94% desde los 500 000, con irregularidades (78% a los 540 000).
- Por tanto el presupuesto original quedaba **a mitad de camino**: la política aprendía a recoger pero aún no a entregar. El 3× del presupuesto no es un detalle: la curva solo despega pasado el doble del presupuesto original.

**Cuidado:** es una sola semilla y la curva se evaluó con la suite de comparación (`suite-m1o-v1`); no debe usarse para escoger un checkpoint (sería ajustar sobre la suite). Los checkpoints están solo en local (`models/` ignorado por Git).


## Penalización de tiempo −0.2 y bono por bajar la bandeja camino al despacho (escrito antes de entrenar, 2026-11-13)
**Contexto:** `m1o-e4l-seed0` (92%) completa la misión, pero sus episodios exitosos duran 71.8 pasos de media (máximo 83), lo mismo que la heurística (71.3), y la media de 95.1 pasos del run viene de 4 fallos
(3 por límite de tiempo a 400 pasos, 1 por batería a 251) que no entregaron nada. Las semillas 1 y 2 de e4l dieron 0%. Instrucción del equipo: subir la penalización de tiempo, añadir un bono por bajar la bandeja
cuando la distancia al despacho es > 0 y la bandeja no está en 0, y comprobar que tras recoger todo el objetivo (x, y y distancia) apunta al despacho (ya era así; fijado por prueba). Código `env/warehouse-v6`.

**Cambio (dos dimensiones, pedidas juntas; la ablación las separa):** `time` −0.1 → −0.2 y `lower_bonus` 0 → 1.0 (por puesto de bandeja bajado, una vez por tramo y puesto). Resto igual a e4l: Manhattan 0.3, altura −0.02,
collision −1, invalid −0.2, mapa abierto `layout_v0.5`, PPO de C0, 606 208 pasos efectivos (600 000 pedidos), `suite-m1o-v1`.

**Hipótesis:** (1) el bono da señal directa al paso «bajar la bandeja tras cargar», donde fallan las semillas 1 y 2, y más semillas completan la misión; (2) `time` −0.2 reduce los pasos por episodio. **Qué la refutaría:** que el éxito medio de las 3 semillas de `f1`
no supere al de e4l (30.7%) en ≥ 5 pp, o que los choques suban > 10% (criterio de `configs/criterios.yaml`, sin cambios). Métricas secundarias (descriptivas): pasos de los episodios exitosos (e4l-seed0: 71.8), nº de fallos por límite de tiempo, inválidas por episodio, entregas y recogidas por episodio,
BAJAR con objetivo DELIVERY y distancia > 0, retorno (no comparable con e4l: cambia la escala).

**Retornos de referencia medidos antes de entrenar** (conductas guionizadas, 15 semillas 10000–10014, mapa abierto; no son resultados del modelo):

| Conducta | e4 (control) | time −0.2 | bono 1.0 | time −0.2 + bono 1.0 | time −0.3 + bono 1.0 |
|---|---:|---:|---:|---:|---:|
| quieto en la base | −40.8 | −80.8 | −40.8 | −80.8 | −120.8 |
| ir al estante y quedarse | −48.9 | −88.9 | −48.9 | −88.9 | −128.9 |
| recoger el 1.º y quedarse | −26.0 | −66.0 | −26.0 | −66.0 | −106.0 |
| recoger todo, bandeja arriba, quieto | 5.4 | −34.6 | 5.4 | −34.6 | −74.6 |
| recoger todo, bajar la bandeja, quieto lejos | 5.4 | −34.6 | 7.3 | −32.7 | −72.7 |
| completar el pedido | 127.4 | 120.3 | 129.3 | 122.1 | 115.0 |

- El orden de las conductas no cambia con `time` −0.2: recoger sigue rindiendo más que ir al estante y que quedarse, y completar rinde +122 frente a −81 de no hacer nada (el control: +127 frente a −41). No aparece zona de evitación nueva por este término.
- Elegimos −0.2 (no −0.3): el hueco entre completar e idle pasa de 168 a 203 puntos en términos absolutos, pero el retorno de un episodio exitoso baja de 127 a 122 (−0.3 lo baja a 115); un tiempo más caro reduce la ventaja neta de terminar.
- El bono vale 1.9 puntos de media en el tramo guionizado (la última recogida suele estar en la balda 1–3): es una señal pequeña frente a los hitos (10/30/50), pensada como gradiente y no como premio.
- Probado que el bono no es explotable: SUBIR/BAJAR repetidos en el tramo de entrega pagan como máximo 1 bono por puesto (`test_raising_and_lowering_on_the_way_to_delivery_is_not_farmable`).
- **Límite declarado:** el bono solo actúa con objetivo DELIVERY; la bajada tras una recogida intermedia no cobra bono.

| Run | `time` | `lower_bonus` | Semilla | Config |
|---|---:|---:|---:|---|
| m1o-e4l-seed0/1/2 (control, v5, ya entrenados) | −0.1 | 0 | 0, 1, 2 | `m1o_e4l_seed{0,1,2}.yaml` |
| m1o-f1-seed0/1/2 | −0.2 | 1.0 | 0, 1, 2 | `m1o_f1_tiempo_bono_seed{0,1,2}.yaml` |
| m1o-f2-seed0 (ablación) | −0.2 | 0 | 0 | `m1o_f2_tiempo_seed0.yaml` |
| m1o-f3-seed0 (ablación) | −0.1 | 1.0 | 0 | `m1o_f3_bono_seed0.yaml` |

El control es e4l: con `lower_bonus` 0 y `time` −0.1 v6 reproduce el retorno de v5 (prueba `test_v6_with_new_terms_off_matches_v5_returns`) y el entrenamiento es determinista, así que no se reentrena. El bloque `ppo:` de los cinco configs es idéntico al de e4l (verificado con `diff`).

### Presupuesto real por run (f1–f3)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-f1-seed0 | m1o | 606 208 | 35.0 (5 runs en paralelo más pruebas y guiones corriendo a la vez) | rechazado |
| m1o-f1-seed1 | m1o | 606 208 | 33.4 | rechazado |
| m1o-f1-seed2 | m1o | 606 208 | 31.1 | rechazado |
| m1o-f2-seed0 | m1o | 606 208 | 35.0 | rechazado (criterio; 44% de éxito) |
| m1o-f3-seed0 | m1o | 606 208 | 35.4 | rechazado |

(Más lento que los 24–26 min de e4l porque la suite completa de pruebas y el guion de retornos corrían a la vez.)


### Resultados de `f1`–`f3` (2026-11-13, `suite-m1o-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, mapa abierto)
Código: commit `cc968ff` (tag `env/warehouse-v6`). Manifiestos `manifests/m1o-f*.json`; evidencia en `docs/resultados/eval/m1o-f*/`. Choques: 0 en todos.

| Run | `time` | `lower_bonus` | Éxito | Recogidas/ep | Entregas/ep | Inválidas/ep | Fin de episodio | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| m1o-e4l-seed0 (control) | −0.1 | 0 | 92% | 2.92 | 2.76 | 3.8 | 46 éxito, 3 tiempo, 1 batería | 2 395 / 3 278 | candidato |
| m1o-e4l-seed1 / seed2 (control) | −0.1 | 0 | 0% / 0% | 0.00 / 2.42 | 0 / 0 | 258 / – | tiempo | 0 / 1 512, 2 / 1 515 | candidato |
| m1o-f1-seed0 | −0.2 | 1.0 | 0% | 2.50 | 0 | 44.3 | 49 tiempo, 1 batería | 0 / 1 525 | **rechazado** |
| m1o-f1-seed1 | −0.2 | 1.0 | 0% | 0.82 | 0 | 128.4 | 50 tiempo | 0 / 1 514 | **rechazado** |
| m1o-f1-seed2 | −0.2 | 1.0 | 0% | 0.00 | 0 | 0.0 | 50 tiempo | 0 / 1 512 | **rechazado** |
| m1o-f2-seed0 | −0.2 | 0 | **44%** | 2.70 | 1.32 | 27.4 | 22 éxito, 26 tiempo, 2 batería | 479 / 1 813 | **rechazado** (criterio) |
| m1o-f3-seed0 | −0.1 | 1.0 | 0% | 2.38 | 0 | 57.4 | 50 tiempo | 0 / 1 516 | **rechazado** |

**Decisión:** el éxito medio de `f1` (3 semillas) es 0% frente a 30.7% de e4l: no supera al control en ≥ 5 pp, así que `f1` se **rechaza** con el criterio fijado antes; la hipótesis «el bono y el tiempo −0.2 hacen que más semillas completen la misión» se rechaza con este presupuesto. `f2` (solo tiempo) y `f3` (solo bono) también se rechazan frente a e4l-seed0 (92%): −48 pp y −92 pp.
Los criterios no se cambiaron tras ver los resultados.

**Diagnóstico** (`trace_policy.py`, repetición determinista de las 50 semillas):
- **El bono hizo lo que se esperaba en el paso que buscaba:** `f1-seed0` y `f3` suben, cargan y **bajan la bandeja** en 50/50 episodios (35/50 y 47/50 terminan con bandeja abajo y carga). Pero después **no avanzan al despacho**: giran en el sitio (f1-seed0: GIRAR_DERECHA 2 587 y GIRAR_IZQUIERDA 1 634 pasos en el estado posterior a cargar; f3: GIRAR_DERECHA 825) y terminan por límite de tiempo con carga. Ningún episodio de entrenamiento de f1/f3 (7 600 en total) entregó nada. El cuello de botella se movió de «bajar la bandeja» a «recorrer el camino al despacho con la carga».
- **f1-seed1:** llega al estante en 50/50 pero solo carga en 35/50; se queda en FRENAR y CARGAR inválido (128 inválidas por episodio). **f1-seed2:** nunca llega a una celda de interacción (0/50): estas dos semillas reproducen los fallos de e4l-seed1/seed2 y el bono no las rescata.
- **f2 (solo time −0.2) aprende la cadena completa** (479 episodios de entrenamiento exitosos; 44% en la suite), pero menos que e4l-seed0 con −0.1 (92%): 26/50 episodios terminan por tiempo con carga, 2 por batería. Sus 22 éxitos duran **73.6 pasos de media** (máximo 82) frente a 71.8 de e4l-seed0: **subir la penalización de tiempo no acortó los episodios exitosos** (ya estaban al nivel de la heurística, 71.3), y el único efecto medible fue menos éxito.
- Sobre la duración de los episodios: la causa del largo medio es el fallo (400 pasos), y con `time` −0.2 hay más fallos, no menos.

**Lectura (hipótesis, no causa demostrada):** (a) el bono por bajar es una señal correcta pero insuficiente: el siguiente tramo (recorrer ~10–30 celdas con carga hasta el despacho) sigue sin señal propia más allá de la diferencia Manhattan; (b) `time` −0.2 duplica el costo de explorar y puede dificultar el descubrimiento de la cadena (f2 pierde 48 pp respecto a −0.1); no se probó una causa; (c) con una semilla por ablación no se puede separar efecto de la penalización de la varianza entre semillas (e4l dio 92/0/0).

**Limitaciones:** una semilla por ablación; tres para `f1`; presupuesto de 606 208 pasos; el control (e4l) se entrenó con código v5 con recompensa idéntica en los términos no nuevos (verificado por prueba, no reentrenado); el bono solo actúa con objetivo DELIVERY; las duraciones de entrenamiento incluyen carga concurrente de otras tareas.

**Siguiente (no iniciado):** si se quiere acortar episodios, atacar el fallo: (1) volver a `time` −0.1 y probar un bono por avanzar con carga hacia el despacho (diferencia Manhattan ya existe; falta un hito, por ejemplo una vez al cruzar la mitad de la distancia al despacho tras bajar la bandeja); (2) replicar e4l en más semillas antes de seguir afinando recompensa, porque 92/0/0 no distingue efectos de recompensa de la varianza.


## Hito de la mitad del camino al despacho con la carga (`g1`, escrito antes de entrenar, 2026-11-13)
**Contexto:** en f1–f3 (v6) el bono por bajar la bandeja logró que el agente subiera, cargara y bajara la bandeja en 50/50 episodios (f1-seed0, f3), pero **ninguno entregó** (0 entregas en ≈ 7 600 episodios de entrenamiento): tras bajarla gira en el sitio
(GIRAR_DERECHA 2 587 / 825 pasos) en lugar de avanzar al despacho. `time` −0.2 (f2) no acortó los éxitos (73.6 frente a 71.8 pasos) y bajó el éxito de 92% a 44% en la semilla 0. Instrucción del equipo: retirar `lower_bonus` y pagar un hito en el tramo con carga. Código `env/warehouse-v7`.

**Cambio (una dimensión frente a e4l):** `carry_milestone` 0 → 5.0 (una vez por tramo de entrega, al llegar a la mitad o menos de la distancia BFS inicial al despacho). Se vuelve a `time` −0.1 y no hay `lower_bonus`. Resto igual a e4l: Manhattan 0.3, altura −0.02, collision −1, invalid −0.2,
mapa abierto `layout_v0.5`, PPO de C0, 606 208 pasos efectivos (600 000 pedidos), semillas 0–2, `suite-m1o-v1`.

**Hipótesis:** una señal única en el tramo con carga hace que los agentes que ya bajan la bandeja y no avanzan lleguen al despacho y entreguen, y suben el éxito medio de las 3 semillas frente a e4l (30.7%; 92/0/0).
**Qué la refutaría:** que el éxito medio de las 3 semillas no supere al de e4l en ≥ 5 pp, o que los choques suban > 10% (criterio de `configs/criterios.yaml`, sin cambios). Métricas secundarias (descriptivas): entregas y recogidas por episodio, episodios de entrenamiento con entrega,
pasos de los éxitos (e4l-seed0: 71.8), fallos por límite de tiempo, inválidas por episodio, y la acción elegida tras cargar con la bandeja abajo (giros en el sitio frente a AVANZAR).

**Retornos de referencia medidos antes de entrenar** (conductas guionizadas, 15 semillas 10000–10014, mapa abierto; no son resultados del modelo):

| Conducta | e4l (control, v5) | g1: hito 5.0 | hito 10.0 |
|---|---:|---:|---:|
| quieto en la base | −40.8 | −40.8 | −40.8 |
| ir al estante y quedarse | −48.9 | −48.9 | −48.9 |
| recoger el 1.º y quedarse | −26.0 | −26.0 | −26.0 |
| recoger todo, bandeja arriba, quieto | 5.4 | 5.4 | 5.4 |
| recoger todo, bajar la bandeja, quieto lejos | 5.4 | 5.4 | 5.4 |
| llevar la carga a la mitad del camino y quedarse | 9.7 | 14.7 | 19.7 |
| completar el pedido | 127.4 | 132.4 | 137.4 |

- El hito no altera ninguna conducta anterior a la mitad del camino (columnas idénticas) y añade exactamente su valor a las que llegan a ella: el orden de las conductas no cambia y no aparece zona de evitación. Se eligió 5.0 (no 10.0) para que sea un gradiente y no domine los hitos de 10/30/50.
- No es explotable: se paga una vez por tramo (`test_carry_milestone_is_not_farmable_by_oscillating`); el retorno máximo extra por pedido es 5.0 por tramo.
- **Límite declarado:** el hito solo actúa con objetivo DELIVERY; si el atasco es de política (giros en el sitio) y no de señal, 5 puntos pueden no bastar.

| Run | `time` | `carry_milestone` | Semilla | Config |
|---|---:|---:|---:|---|
| m1o-e4l-seed0/1/2 (control, v5, ya entrenados) | −0.1 | 0 | 0, 1, 2 | `m1o_e4l_seed{0,1,2}.yaml` |
| m1o-g1-seed0/1/2 | −0.1 | 5.0 | 0, 1, 2 | `m1o_g1_hito_seed{0,1,2}.yaml` |

El control es e4l: con el hito en 0 v7 reproduce el retorno de v5 (prueba `test_v7_with_milestone_off_matches_v5_returns`) y el entrenamiento es determinista, así que no se reentrena. El bloque `ppo:` de los tres configs es idéntico al de e4l (comprobado por prueba).

### Presupuesto real por run (g1)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-g1-seed0 | m1o | 606 208 | 30.8 (3 runs en paralelo, nada más corriendo) | rechazado |
| m1o-g1-seed1 | m1o | 606 208 | 28.0 | rechazado |
| m1o-g1-seed2 | m1o | 606 208 | 30.4 | rechazado |


### Resultados de `g1` (2026-11-13, `suite-m1o-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, mapa abierto)
Código: commit `c152c42` (tag `env/warehouse-v7`). Manifiestos `manifests/m1o-g1-seed*.json`; evidencia en `docs/resultados/eval/m1o-g1-seed*/`. Choques: 0 en todos.

| Run | `carry_milestone` | Éxito | Recogidas/ep | Entregas/ep | Inválidas/ep | Pasos de los éxitos | Éxitos en entrenamiento | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| m1o-e4l-seed0 (control) | 0 | 92% | 2.92 | 2.76 | 3.8 | 71.8 | 2 395 / 3 278 | candidato |
| m1o-g1-seed0 | 5.0 | **94%** | 2.94 | 2.82 | 0.8 | 72.4 | 2 184 / 3 120 | **rechazado** (criterio) |
| m1o-e4l-seed1 (control) | 0 | 0% | 0.00 | 0 | 258.3 | – | 0 / 1 512 | candidato |
| m1o-g1-seed1 | 5.0 | 0% | 0.00 | 0 | 258.3 | – | 0 / 1 512 | **rechazado** |
| m1o-e4l-seed2 (control) | 0 | 0% | 2.42 | 0 | 20.1 | – | 2 / 1 515 | candidato |
| m1o-g1-seed2 | 5.0 | 0% | 2.44 | 0 | 104.0 | – | 268 / 1 673 | **rechazado** |

**Decisión:** el éxito medio de `g1` es **31.3%** (94 / 0 / 0) frente a **30.7%** de e4l (92 / 0 / 0): **+0.7 pp**, por debajo de los 5 pp exigidos; los choques no suben (0 en ambos). La hipótesis «un hito en el tramo con carga hace que más semillas entreguen» se **rechaza** con el criterio fijado antes, que no se cambió. Los tres g1 quedan `rechazado` y se conservan con su evidencia.

**Diagnóstico** (`trace_policy.py`, repetición determinista de las 50 semillas):
- **seed 0:** 47/50 éxitos, 72.4 pasos de media (máximo 83), igual que e4l-seed0; los 3 fallos tienen la bandeja arriba con carga. El +2 pp (47 frente a 46 éxitos) no es distinguible de la variación entre episodios con 50 semillas de evaluación; menos inválidas por episodio (0.8 frente a 3.8).
- **seed 1: resultado idéntico bit a bit al de e4l-seed1** (retorno −88.8, 258.3 inválidas, 0/50 miran al estante). El agente nunca llega a cargar, así que el hito, que solo existe tras la última recogida, nunca se paga y la trayectoria de entrenamiento es la misma (el entrenamiento es determinista). Este tipo de semilla no puede mejorar con ningún término que actúe tras cargar.
- **seed 2:** carga en 50/50 y baja la bandeja, pero con la carga **gira en el sitio** (GIRAR_IZQUIERDA 1 819, GIRAR_DERECHA 1 197 pasos) y no entrega en evaluación determinista. En entrenamiento (política estocástica) **268/1 673 episodios sí tuvieron éxito** (e4l-seed2: 2/1 515): el hito sí cambió algo, pero la política determinista aprendida no completa el tramo. Es el mismo patrón que f1/f3 (bajan la bandeja y giran).
- Los fallos de seed 0 y los de seed 2 son de tipo distinto: en seed 0 la bandeja queda arriba (no se baja), en seed 2 queda abajo y no se avanza.

**Lectura (hipótesis, no causa demostrada):** (a) el hito mueve algo en la semilla que ya cargaba (seed 2: de 2 a 268 éxitos de entrenamiento) pero no basta para que la política **determinista** avance; la acción más probable tras cargar sigue siendo girar (probabilidad media ≈ 0.24 por giro frente a ≈ 0.01 de AVANZAR), de modo que evaluar con la acción más probable esconde que una política estocástica sí completa el tramo; (b) la varianza entre semillas es mayor que cualquier efecto de recompensa probado hasta ahora (92/0/0 en e4l, 94/0/0 en g1): para atribuir un efecto hacen falta más semillas; (c) el límite declarado se cumple: el hito solo actúa tras la última recogida y no puede ayudar a una semilla que nunca llega a cargar (seed 1).

**Limitaciones:** una configuración, tres semillas; presupuesto de 606 208 pasos; el control (e4l) se entrenó con código v5 con recompensa idéntica (verificado por prueba y, en seed 1, por el resultado idéntico); evaluación solo determinista.

**Siguiente (no iniciado):** (1) replicar e4l y g1 en más semillas (3–7) para estimar la tasa real de semillas que funcionan; (2) evaluar g1-seed2 con política estocástica en la suite para ver si el éxito de entrenamiento (268/1 673) se reproduce; (3) para semillas como la 1 (nunca cargan) hace falta señal antes de la recogida, por ejemplo un hito al llegar a una celda de interacción del primer estante.


### Diagnóstico de g1 con política estocástica (2026-11-13, post hoc; no sustituye a la evaluación oficial)
**Por qué:** la suite oficial evalúa con la acción más probable. g1-seed2 tuvo 268/1 673 éxitos de entrenamiento (política estocástica) pero 0% determinista. Se evalúa cada modelo muestreando acciones (`deterministic=False`) en las mismas 50 semillas de la suite (10000–10049), con 3 semillas de muestreo distintas
(script `.claude/skills/warehouse-rush/scripts/eval_stochastic.py`; salida en `docs/resultados/eval/<run>/stochastic.json`). Se decidió **después** de ver el resultado oficial, así que es exploratorio.

| Run | Éxito determinista (oficial) | Éxito estocástico (3 repeticiones) | Pasos de los éxitos (estocástico) | Choques/ep (estocástico) |
|---|---:|---|---:|---:|
| m1o-e4l-seed0 | 92% | 96 / 96 / 96% | 77–78 | 0.1–0.2 |
| m1o-g1-seed0 | 94% | 96 / 96 / 96% | 78–79 | 0.0–0.3 |
| m1o-e4l-seed1 | 0% | (no evaluado) | – | – |
| m1o-g1-seed1 | 0% | 0 / 0 / 0% | – | 0.1 |
| m1o-e4l-seed2 | 0% | 4 / 0 / 0% | 277 (2 éxitos) | 0.1–0.3 |
| m1o-g1-seed2 | 0% | **94 / 94 / 94%** | 108–119 | 0.2–0.4 |

**Hallazgos:**
- **El hito sí funcionó en la semilla 2.** Con muestreo, g1-seed2 completa la misión en 47/50 episodios en las tres repeticiones; e4l-seed2 casi nunca (2/150). La política determinista de g1-seed2 gira con carga, pero la estocástica avanza: la acción más probable tras cargar es un giro, y los giros y el avance están cerca en probabilidad (≈ 0.24 por giro, AVANZAR ≈ 0.01 en estado de carga medio), de modo que el muestreo basta para salir del giro y el argmax no.
- **La evaluación determinista esconde esto.** Con los números estocásticos el éxito medio de 3 semillas sería ≈ 63% (96 / 94 / 0) para g1 frente a ≈ 32% (96 / 0 / 1.3) para e4l (el seed 1 de e4l no se midió: se usó 0%, su valor determinista).
- **Pero los éxitos de seed2 son lentos:** 108–119 pasos frente a 72–79 de seed0. El objetivo original (episodios más cortos) no se cumple en esa semilla; el hito ayuda a entregar, no a entregar rápido.
- Seed1 sigue en 0% con muestreo: nunca carga, el hito no puede actuar.
- Con muestreo aparecen choques (0.1–0.4 por episodio); en determinista eran 0.

**Decisión:** el **resultado oficial no cambia**: el criterio fijado antes es determinista y g1 sigue `rechazado` (+0.7 pp). Reetiquetarlo ahora con una métrica elegida tras ver los datos sería cambiar el criterio a posteriori. Lo que sí queda registrado es que (a) la evaluación determinista subestima políticas cuyas probabilidades están repartidas y
(b) g1 podría ser mejor que e4l bajo una evaluación estocástica. Para afirmarlo haría falta un criterio **nuevo, escrito antes**, con política estocástica y semillas de evaluación no usadas aquí, y más semillas de entrenamiento. Es una decisión del equipo (el criterio vive en `configs/criterios.yaml`, que no se toca).

**Limitaciones:** exploratorio y decidido después de ver los resultados; las mismas 50 semillas de episodio de la suite; 3 muestreos por modelo no son semillas de entrenamiento (la variación entre semillas de entrenamiento sigue sin medirse); e4l-seed1 no se evaluó.


## Más semillas de e4l y g1 (escrito antes de entrenar, 2026-11-13)
**Contexto:** con 3 semillas (0–2) e4l dio 92 / 0 / 0% y g1 94 / 0 / 0% en la suite determinista: la varianza entre semillas de entrenamiento (la mayoría de las semillas no funcionan) es mayor que cualquier efecto de recompensa medido, y con muestreo g1-seed2 sí completa la misión (94%) mientras e4l-seed2 no (≈ 1%).
Con tres semillas no se puede estimar con qué frecuencia funciona cada recompensa. Se entrenan las semillas **3–7 (no vistas)** de ambas, con el mismo presupuesto (606 208 pasos), el mismo PPO, el mismo mapa y `suite-m1o-v1`. Código `env/warehouse-v7` (e4l = `carry_milestone` 0, equivalente a v5 por prueba).

**Hipótesis:** (1) el hito `carry_milestone` 5.0 sube el éxito medio frente a e4l; (2) aumenta la fracción de semillas que completan la misión (≥ 50% de éxito), pero no puede ayudar a las que nunca cargan (como seed 1).
**Criterio principal (fijado antes de entrenar, sobre las 5 semillas nuevas 3–7, evaluación **determinista** oficial en `suite-m1o-v1`):** g1 supera a e4l si el éxito medio de las 5 semillas es ≥ 5 pp mayor y los choques por episodio no suben más de 0.1 (con 0 choques en e4l un porcentaje no tiene sentido). Si no, se rechaza.
**Métricas secundarias, descriptivas (no deciden):** (a) las 8 semillas juntas (0–7); (b) fracción de semillas con ≥ 50% de éxito determinista (k/8, con intervalo de Wilson al 95%); (c) pasos de los éxitos; (d) entregas por episodio; (e) **evaluación estocástica** de los 16 modelos (3 muestreos) en las semillas de episodio **20000–20049**,
que no son parte de ninguna suite oficial ni de la suite reservada `test-final`; es un diagnóstico exploratorio y no cambia el criterio principal. Si el resultado oficial y el estocástico discrepan, se informan ambos y la decisión sigue el principal.
**Lo que lo refutaría:** que la media de las 5 semillas nuevas de g1 no supere a la de e4l en ≥ 5 pp.

| Run | `carry_milestone` | Semillas | Config |
|---|---:|---|---|
| m1o-e4l-seed3…7 (control, nuevas) | 0 | 3, 4, 5, 6, 7 | `m1o_e4l_seed{3..7}.yaml` |
| m1o-g1-seed3…7 | 5.0 | 3, 4, 5, 6, 7 | `m1o_g1_hito_seed{3..7}.yaml` |
| m1o-e4l-seed0/1/2, m1o-g1-seed0/1/2 (ya entrenados) | 0 / 5.0 | 0, 1, 2 | solo para las métricas secundarias |

Se entrena en dos tandas de 5 runs en paralelo (g1 primero, luego e4l) por memoria (7.6 GB). Tras cada run: evaluación oficial, traza y evaluación estocástica; manifiestos al final.

### Presupuesto real por run (semillas 3–7)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1o-g1-seed3…7, m1o-e4l-seed3…7 | m1o | (pendiente) | (pendiente) | (pendiente) |

### Cancelado: más semillas de e4l y g1 (2026-11-13)
Por instrucción del equipo se detuvieron las 5 corridas de `g1` (semillas 3–7) al ≈ 50% de los pasos (≈ 300 000 de 606 208) para probar antes el arranque con clonación de comportamiento. **No hay resultados ni evaluación** de ese experimento, y las `e4l` 3–7 nunca se lanzaron.
El criterio escrito arriba nunca se aplicó. Los runs `m1o-g1-seed3`…`7` quedan con estado MLflow `interrumpido` (detenidos con SIGTERM; `sin_checkpoint`: solo hay checkpoints intermedios en `models/<run>/checkpoints`, no modelo final) y sus carpetas parciales en `docs/resultados/training/` no se versionan.
Los configs `m1o_{e4l,g1_hito}_seed{3..7}.yaml` siguen en el repositorio por si se retoma.


## Arranque con clonación de comportamiento + ajuste fino con PPO (`h0` / `h1`, escrito antes de entrenar, 2026-11-13)
**Contexto:** con la recompensa de e4l, 2 de 3 semillas nunca descubren la tarea (92 / 0 / 0%); g1 (hito) tampoco rescata la semilla 1 (nunca carga). La heurística de referencia completa el 100% de la suite en ≈ 71 pasos. Ninguna recompensa probada hace que *todas* las semillas arranquen; se prueba cambiar la **inicialización**.
Sin cambio de ambiente ni de recompensa (`warehouse-v7`, `carry_milestone` 0 = e4l; no hay subida de versión).

**Método:** (1) `pipelines/bc.py`: la heurística genera 1000 episodios de demostración en el mapa abierto (semillas 40000–40999; la mitad con ruido de 25% de acciones al azar, etiquetadas con lo que haría la heurística en ese estado); una red idéntica a la de PPO ([64,64], actor y crítico separados) se entrena por entropía cruzada (actor) y regresión de los retornos descontados (crítico). Validación: 100 episodios (semillas 50000–50099).
Ninguna semilla de demostración coincide con la suite (10000–10049), dev (1000–1009), la evaluación periódica (20000) ni el diagnóstico estocástico (20000–20049) (prueba `test_demo_seeds_do_not_overlap_the_evaluation_suites`). (2) `h1`: PPO desde ese modelo (`parent_run_id`) con exactamente el PPO y la recompensa de e4l, 600 000 pasos (606 208 efectivos).
**Cambia solo la inicialización frente a e4l.** Parámetros de BC fijados antes: 30 épocas, lr 1e-3, lote 256.

**Regla de ajuste de BC (fijada antes):** los parámetros de BC se pueden ajustar **solo** con la precisión de validación sobre las demostraciones de validación (nunca con la suite ni con resultados de h1). Si la precisión de validación en estados limpios es < 90%, se duplican las épocas (máximo dos veces) y se registra cada intento.
Es la única repetición permitida; los intentos se anotan abajo.

**Hipótesis:** (1) el modelo BC solo (`h0`, referencia descriptiva) ya completa la misión en una fracción apreciable de episodios de la suite; (2) el ajuste fino (`h1`) mantiene o mejora eso y funciona en **las tres semillas** (no solo en la 0), de modo que el éxito medio supera al de e4l.
**Criterio principal (sin cambios, `configs/criterios.yaml`):** h1 gana si el éxito medio de las 3 semillas en `suite-m1o-v1` (evaluación determinista oficial) es ≥ 5 pp mayor que el de e4l (30.7%: 92 / 0 / 0) y los choques por episodio no suben más de 0.1 (e4l: 0). Si no, se rechaza.
**Métricas secundarias, descriptivas:** éxito de `h0` en la suite; precisión del actor y varianza explicada del crítico en validación; pasos de los éxitos (e4l-seed0: 71.8; heurística: 71.3); entregas y recogidas por episodio; éxito en entrenamiento durante el ajuste fino (¿se degrada la política al empezar PPO?); evaluación estocástica en 20000–20049 (exploratoria).
**Lo que lo refutaría:** que la media de h1 no supere a e4l en ≥ 5 pp.

**Límites declarados antes de entrenar:**
- **Experto privilegiado:** la heurística usa estado interno del ambiente (BFS por pose, alturas por línea). El modelo resultante solo usa la observación `Box(27)` al decidir, pero lo que imita no sale de la observación; si la observación no basta para reproducirla, la precisión de validación será baja.
- **Presupuesto no idéntico:** h1 recibe 600 000 pasos de PPO como e4l **más** ≈ 85 000 pasos de demostración (≈ 14%) en la fase BC. Se declara y se reporta; no se compensa restando pasos de PPO.
- **Desplazamiento de distribución:** las demostraciones vienen de la trayectoria de la heurística (más ruido); el modelo fallará en estados que ni la heurística ni el ruido visitan. El ajuste fino con PPO debe corregirlo.
- **Crítico con retornos de la trayectoria ruidosa** (valor de la política con ruido, no de la heurística): aproximación; se reporta su varianza explicada.
- **Datos:** las demostraciones se regeneran de forma determinista con el script y las semillas (hash SHA-256 en `metadata.json`); no se versionan (DVC sin remoto).

| Run | Qué es | Semilla | Config |
|---|---|---:|---|
| m1o-e4l-seed0/1/2 (control, ya entrenados) | PPO desde cero, recompensa e4l | 0, 1, 2 | `m1o_e4l_seed{0,1,2}.yaml` |
| m1o-h0-seed0/1/2 | solo imitación de la heurística (0 pasos de PPO) | 0, 1, 2 | `m1o_h0_bc_seed{0,1,2}.yaml` |
| m1o-h1-seed0/1/2 | PPO 600 000 pasos desde h0 de la misma semilla | 0, 1, 2 | `m1o_h1_bcppo_seed{0,1,2}.yaml` |

### Presupuesto real por run (h0 / h1)
| Run | Nivel | Pasos de PPO | Minutos | Estado |
|---|---|---|---|---|
| m1o-h0-seed0 | m1o | 0 (≈ 84 000 pasos de demostración) | 10.2 (generación de demostraciones y ajuste) | candidato (referencia) |
| m1o-h0-seed1 | m1o | 0 | 9.9 | candidato (referencia) |
| m1o-h0-seed2 | m1o | 0 | 9.9 | candidato (referencia) |
| m1o-h1-seed0 | m1o | 606 208 | 34.9 (3 runs en paralelo) | rechazado (criterio: choques) |
| m1o-h1-seed1 | m1o | 606 208 | 34.4 | rechazado (criterio: choques) |
| m1o-h1-seed2 | m1o | 606 208 | 34.9 | rechazado (criterio: choques) |


### Resultados de h0 / h1 (2026-11-14, `suite-m1o-v1`: 50 episodios, semillas 10000–10049, acciones deterministas, mapa abierto)
Código: commit `d1d91c9` (+ parche del metadato de h0, ver límites). Los parámetros de BC no se ajustaron: la precisión de validación en estados limpios fue 100% en las tres semillas (regla: ajustar solo si < 90%). Manifiestos `manifests/m1o-h{0,1}-seed*.json`; evidencia en `docs/resultados/eval/m1o-h*/`.

| Run | Éxito | Pasos de los éxitos | Entregas/ep | Choques/ep | Inválidas/ep | Fin de episodio | Estado |
|---|---:|---:|---:|---:|---:|---|---|
| m1o-e4l-seed0 / 1 / 2 (control) | 92 / 0 / 0% (media 30.7%) | 71.8 / – / – | 2.76 / 0 / 0 | 0 / 0 / 0 | 3.8 / 258 / 20 | – | candidato |
| m1o-h0-seed0 / 1 / 2 (solo imitación) | 100 / 100 / 100% | 71.3 | 3.00 | 0 / 0 / 0 | 0 | 50 éxito | candidato (referencia) |
| m1o-h1-seed0 (PPO desde h0) | 88% | 74.8 | 2.64 | **6.74** | 30.3 | 44 éxito, 4 tiempo, 2 batería | **rechazado** |
| m1o-h1-seed1 | 92% | 110.7 (máx. 395) | 2.80 | 0 | 0 | 46 éxito, 3 tiempo, 1 presupuesto | **rechazado** |
| m1o-h1-seed2 | **100%** | 79.8 (máx. 124) | 3.00 | 0 | 0 | 50 éxito | **rechazado** |

**Decisión según el criterio fijado antes (`h1` frente a e4l):** (1) éxito medio de h1 **93.3%** (88 / 92 / 100) frente a 30.7%: **+62.7 pp**, supera los 5 pp. (2) Choques por episodio: media de h1 **2.25** frente a 0 de e4l, y el límite era +0.1 por episodio: **no se cumple**.
El criterio exige ambas condiciones, así que **h1 se rechaza**, aunque el éxito sea mucho mayor. Todo el exceso de choques viene de la semilla 0 (6.74 por episodio; las semillas 1 y 2 tienen 0). No se cambió el criterio: si el equipo considera que la condición de choques debe medirse de otra forma, es una decisión del equipo y no afecta a este veredicto.

**Hallazgos:**
- **La imitación sola completa la misión en las 3 semillas** (h0: 100%, 71.3 pasos, 0 choques, 0 inválidas: el mismo desempeño que la heurística). La observación `Box(27)` contiene lo necesario para decidir bien; el cuello de botella de e4l/g1 era **el descubrimiento de la tarea por exploración**, no la capacidad de la red ni la observación.
- **El ajuste fino con PPO empeoró al imitador.** La evaluación periódica (5 episodios deterministas en la semilla 20000) arranca con el retorno de la heurística (≈ 127) en h0, pero ya en el primer punto de h1 (20 000 pasos) cae a 6 / 1 / −19, y oscila durante los 600 000 pasos entre ≈ 127 y valores negativos (seed0: 126 en 100 000 pasos, −113 en 540 000, 81 al final).
  El modelo final es solo el estado en que se detuvo el entrenamiento. Causa probable (no demostrada): el crítico llega con varianza explicada de solo 0.38–0.40 y lr 3e-4 con `ent_coef` 0 mueve el actor con ventajas ruidosas; PPO desarma una política buena antes de ajustar el crítico.
- **Los éxitos de h1 son más lentos que los de h0** (74.8 / 110.7 / 79.8 pasos frente a 71.3) y h1-seed0 y -seed1 fallan 6 y 4 episodios que h0 no falla.
- **Evaluación estocástica exploratoria** (semillas 20000–20049, 3 muestreos): h1 100 / 100 / 100% en las tres semillas, 77–81 pasos, ≤ 0.42 choques por episodio. La política muestreada es mejor que la determinista oficial (88 / 92 / 100% en 10000–10049); las dos evaluaciones usan semillas de episodio distintas, así que no son directamente comparables.
- **Trazas (determinista):** h1-seed0 se queda en CARGAR repetido en el estado de carga con la bandeja a la altura (1 440 pasos, probabilidad media de CARGAR 0.71 en ese estado) y por eso acumula inválidas y choques; h1-seed1 gira en el estado de subida (GIRAR_IZQUIERDA 453 pasos, probabilidad 0.45).

**Lectura (hipótesis, no causa demostrada):** (a) arrancar desde la heurística resuelve el problema de las semillas que no descubren la tarea; (b) el paso de PPO, tal como está configurado, es perjudicial desde el primer punto, no una mejora: para conservar la política hay que cambiar el ajuste fino (lr menor, calentar el crítico sin tocar el actor, KL objetivo, o quedarse con el mejor punto de la evaluación periódica); (c) como todas las semillas de h0 son idénticas en éxito (100%), con esta suite h0 no se distingue de la heurística.

**Limitaciones y avisos:**
- **h0 es una copia de un controlador privilegiado.** La heurística usa estado interno del ambiente; h0 solo usa la observación al decidir, pero no demuestra aprendizaje por refuerzo. Se registra como referencia, no como finalista, y no se recomienda.
- **Presupuesto no idéntico:** h1 tuvo 606 208 pasos de PPO más ≈ 84 000 de demostración (≈ 14%).
- **Parche de metadatos:** `bc.py` se ejecutó sin escribir `layout_sha256`, `simulation` y `rewards` en el `metadata.json` de h0 (el evaluador los exige); se añadieron después con el mismo ambiente y se dejó constancia en el campo `patched_fields`. El modelo no cambia; el código se corrigió para los runs siguientes.
- 3 semillas; la media de choques de h1 la determina una sola semilla; evaluación oficial determinista con 50 episodios; el diagnóstico estocástico es exploratorio y usa otras semillas de episodio.

**Siguiente (no iniciado):** (1) ajuste fino que no destruya la política: lr menor (p. ej. 3e-5), calentamiento del crítico con el actor congelado durante los primeros pasos o `target_kl`; criterio fijado antes y 3 semillas; (2) guardar y evaluar el mejor punto de la evaluación periódica (`models/<run>/best`) además del último; (3) decidir con el equipo si una política copiada de la heurística es un resultado aceptable para el proyecto o solo una referencia.

## e4l en el mapa con muro interior (`m1-e4l`, escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1o-e4l-seed0` (92%) y `m1o-h0` (100%) fallan por completo en el mapa con muro (`layout_v0.4`): evaluados sin reentrenar dieron 0/50 en `suite-m1`-semillas 10000–10049 (40–52 choques por episodio, 0 entregas), mientras la heurística da 50/50. Los modelos nunca vieron el muro. Instrucción del usuario: entrenar la misma configuración de e4 en el mapa con muro.
- **Cambio (una dimensión):** mapa `layout_v0.4` y nivel `m1` en vez de `layout_v0.5` / `m1o`. Recompensa (`manhattan_progress` 0.3, `height_mismatch` −0.02, `collision` −1, `invalid_interaction` −0.2), PPO (bloque idéntico a `m1o_e4l_seed*.yaml`, verificado con `diff`) y 600 000 pasos iguales. Código `env/warehouse-v7` (e4l original corrió en v5; `carry_milestone` vale 0 por defecto, así que la recompensa efectiva es la misma). Sin cambio de ambiente ni de versión.
- **Hipótesis:** la recompensa de e4 también permite completar el pedido con el muro y supera a la referencia de recompensa de choque/inválida sin términos de progreso (`m1-r5`, 200 000 pasos, 0%).
- **Criterio (fijado ahora, antes de ver resultados):** adoptar si el éxito **medio de las 3 semillas** en `suite-m1-v1` supera en ≥ 5 pp a `m1-r5` (0%) sin que los choques por episodio suban > 10%; si no, rechazar. Se reportan media, desviación y cada semilla.
- **Qué la refutaría:** media de éxito < 5%.
- **Limitación conocida:** no hay control del mismo presupuesto en el mapa con muro (`m1-r5` usa 200 000 pasos); si la media es positiva, un control `c0l` a 600 000 pasos en `m1` distinguiría el efecto de los pasos del de la recompensa.
- **Riesgo anticipado:** en el mapa abierto la política llegó al estante en línea recta; con el muro en y=14 (paso en x=20) la distancia Manhattan al objetivo no es monótona a lo largo de la ruta, así que `manhattan_progress` puede premiar acercarse al muro y quedarse atrapado.
- **Métricas secundarias descriptivas (no deciden):** recogidas y entregas por episodio, choques e inválidas por episodio, pasos de los éxitos, episodios de entrenamiento con éxito.

| Run | Pasos pedidos | Semilla | Config |
|---|---:|---:|---|
| m1-e4l-seed0 | 600 000 | 0 | `m1_e4l_seed0.yaml` |
| m1-e4l-seed1 | 600 000 | 1 | `m1_e4l_seed1.yaml` |
| m1-e4l-seed2 | 600 000 | 2 | `m1_e4l_seed2.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real (m1-e4l)
| Run | Nivel | Pasos | Minutos | Estado |
|---|---|---|---|---|
| m1-e4l-seed0 | m1 | 606 208 | 34.3 (3 runs en paralelo) | rechazado |
| m1-e4l-seed1 | m1 | 606 208 | 34.5 (3 runs en paralelo) | rechazado |
| m1-e4l-seed2 | m1 | 606 208 | 37.0 (3 runs en paralelo) | rechazado |

### Resultados (m1-e4l, `suite-m1-v1`, determinista, semillas 10000–10049)
| Run | Éxito | Recogidas/ep | Entregas/ep | Inválidas/ep | Choques/ep | Episodios de entrenamiento con éxito |
|---|---:|---:|---:|---:|---:|---:|
| m1-e4l-seed0 | 0% | 0.00 | 0.00 | 63.0 | 0.0 | 0 / 1 512 |
| m1-e4l-seed1 | 0% | 0.00 | 0.00 | 0.0 | 0.0 | 0 / 1 512 |
| m1-e4l-seed2 | 0% | 1.94 | 0.00 | 113.7 | 0.0 | 0 / 1 516 |
Referencias en el mismo mapa: heurística 100% (80 pasos), `m1-r5` 0%.
- **Decisión por el criterio fijado antes:** media 0% < 0% + 5 pp → **hipótesis refutada, los 3 runs `rechazado`** (se conservan como evidencia).
- **Diagnóstico (`trace_policy.py`):** seed0 y seed1 llegan a una celda de interacción en 21/50 y 29/50 episodios pero nunca miran al estante ni cargan (se quedan quietos o giran). seed2 es la más avanzada: en los 50 episodios llega al estante, sube la bandeja y carga (1.94 recogidas/ep), pero no entrega: tras cargar gira a la derecha (prob. media 0.46) y casi nunca avanza (0.01), 31 episodios acaban con la bandeja arriba y 19 abajo. Mismo tipo de atasco que e4l-seed2/g1 en el mapa abierto antes de `carry_milestone`.
- **Observación sobre el riesgo anticipado:** los choques son 0.0 por episodio en las tres semillas, así que no hay atasco contra el muro; el fallo no es el trampa del muro sino que no se descubre o no se completa la cadena de carga y entrega.
- **Limitaciones:** 3 semillas y un único presupuesto (606 208); sin control del mismo presupuesto en `m1` (`c0l`), por lo que no se separa el efecto de pasos y recompensa. La curva de aprendizaje (e4l-seed0 abierto: primer éxito a 340 000 pasos) sugiere que 600 000 pasos puede ser insuficiente con el muro; no probado.
- **Evidencia no tocada:** `m1-r5` se reevaluó por error con la salida por defecto y se restauró desde Git; sus archivos de evaluación no cambiaron.

## Control sin términos e4 y e4 con 3x pasos en el mapa con muro (`m1-c0l`, `m1-e4x`, escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1-e4l` (600 000 pasos, mapa con muro) dio 0/0/0%. Instrucción del usuario: enfoque de RL puro; primero un control del mismo presupuesto, luego e4 con más pasos, y después evaluar la función de recompensa para hacerla más robusta. Sin cambio de ambiente (`warehouse-v7`). Todo con PPO de C0 (bloque `ppo:` idéntico, verificado con `diff`), 3 productos aleatorios, `layout_v0.4`, `suite-m1-v1`.

### Experimento 1: control `m1-c0l` (600 000 pasos, semillas 0–2)
- **Cambio frente a `m1-e4l`:** se quitan `manhattan_progress` y `height_mismatch`; queda `invalid_interaction` −0.2 y `collision` −1.
- **Pregunta:** ¿la recompensa de e4 aporta algo en el mapa con muro frente a los pasos solos? Control descriptivo, sin adopción: se reporta media y cada semilla frente a `m1-e4l` (0%) y `m1-r5` (200 000 pasos, 0%). En el mapa abierto el control a 600 000 pasos aprendió a recoger (1.68/ep) pero no a entregar.
- **Qué lo haría informativo:** si `m1-c0l` > 0% con e4l = 0%, los términos e4 dañan con el muro; si ambos 0%, no se separan a este presupuesto.

### Experimento 2: `m1-e4x` (e4, 1 800 000 pasos, semillas 0–2)
- **Cambio frente a `m1-e4l`:** solo el presupuesto (3x).
- **Hipótesis:** con el muro el descubrimiento es más lento (en el mapa abierto la primera victoria llegó a ≈340 000 pasos) y con 1 800 000 pasos la política completa la cadena.
- **Criterio (fijado ahora):** adoptar si el éxito medio de las 3 semillas en `suite-m1-v1` supera en ≥ 5 pp al de `m1-e4l` (0%) sin que los choques por episodio suban > 10%. Se reporta cada semilla.
- **Qué la refutaría:** media < 5%.
- **Limitación conocida:** no hay control de 1 800 000 pasos sin términos e4; la comparación con `m1-c0l` es a otro presupuesto.
- **Métricas secundarias descriptivas:** recogidas/entregas por episodio, inválidas, choques, pasos de los éxitos, primer punto de la curva (checkpoints cada 20 000) con éxito, episodios de entrenamiento con éxito.

| Run | Pasos pedidos | Semilla | Config |
|---|---:|---:|---|
| m1-c0l-seed0/1/2 | 600 000 | 0/1/2 | `m1_c0l_seed{0,1,2}.yaml` |
| m1-e4x-seed0/1/2 | 1 800 000 | 0/1/2 | `m1_e4x_seed{0,1,2}.yaml` |

Presupuesto efectivo 606 208 / 1 802 240 (múltiplo de 8 192; el 1 810 432 anotado antes era un error de cálculo). Se lanzaron 6 runs en paralelo.

### Presupuesto real (m1-c0l, m1-e4x)
| Run | Pasos | Minutos | Estado |
|---|---:|---:|---|
| m1-c0l-seed0/1/2 | 606 208 | 30.5 / 30.4 / 31.6 (6 runs en paralelo) | candidato (control) |
| m1-e4x-seed0/1/2 | 1 802 240 | 74.9 / 74.8 / 80.1 | candidato |

### Resultados (`suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Éxito | Recogidas/ep | Entregas/ep | Inválidas/ep | Choques/ep | Entrenamiento con éxito |
|---|---:|---:|---:|---:|---:|---:|
| m1-c0l-seed0 | 0% | 0.00 | 0 | 0.0 | 0 | 0 / 1 821 |
| m1-c0l-seed1 | 0% | 0.00 | 0 | 0.0 | 0 | 0 |
| m1-c0l-seed2 | 0% | 1.00 | 0 | 11.9 | 0 | 0 |
| m1-e4x-seed0 | 0% | 0.00 | 0 | 117.9 | 0 | 0 |
| m1-e4x-seed1 | 0% | 0.00 | 0 | 0.0 | 0 | 0 |
| m1-e4x-seed2 | **80%** (40/50) | 2.68 | 2.40 | 63.8 | 0 | 8 322 |
- **Experimento 1 (control):** 0/0/0%, media 0%, igual que `m1-e4l` (0%): a 600 000 pasos la recompensa de e4 no se distingue de la base. c0l-seed2 aprende a cargar (como e4l-seed2) pero no entrega; las otras dos quedan en idle.
- **Experimento 2 (criterio fijado antes): cumplido.** Media de las 3 semillas 26.7% (desv. poblacional 37.7 pp) ≥ 0% + 5 pp, choques 0.0 (sin subir). **Lo lleva una semilla de tres** (seed0 y seed1 0%), igual que pasó con e4l en el mapa abierto: los 3 runs quedan `candidato`, ninguno `recomendado`.
- **e4x-seed2:** primer modelo que completa la misión en el mapa con muro. Éxitos en 91.8 pasos de media (heurística 80); 7 de los 10 fallos terminan con carga y la bandeja arriba (el mismo atasco tras cargar), 2 por batería. Curva en la suite intermedia (`dev-m1-v1`, 10 episodios, checkpoints cada 20 000 pasos): retorno ≈ −40 hasta ≈ 660 000, primer retorno positivo a 700 000, ≈ 125 desde 1 060 000 pero irregular (29 a 1.22M, 18 a 1.70M, 95 al final). El modelo final es el de 1 802 240 pasos, no el mejor checkpoint.
- **e4x-seed0** acaba en DESCARGAR/inválidas (117.9/ep) sin llegar a celdas de interacción; **seed1** se queda quieto o gira (30/50 llegan a una celda, 1/50 mira al estante).
- **Limitaciones:** sin control de 1 802 240 pasos sin términos e4: no se separa recompensa de pasos a ese presupuesto (a 600 000 pasos el control y e4l coinciden en 0%); 3 semillas, una sola exitosa; el modelo depende de la semilla, lo que apunta a que el descubrimiento de la cadena es la parte frágil de la recompensa.

## Tres ajustes de la recompensa/PPO, uno por experimento, en el mapa con muro (`m1-j1`, `m1-j2`, `m1-j3`, escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1-e4x` (1 800 000 pasos) dio 0/0/80%: solo una semilla descubre la cadena. Instrucción del usuario: probar los tres ajustes a 600 000 pasos, **cada uno en su propio experimento (no combinados), una corrida cada uno**. Se usa la **semilla 0**, que fracasó en e4l (0%), c0l (0%) y e4x (0%), para que un éxito no pueda atribuirse a una semilla favorable. Línea base común: `m1-e4l-seed0` (600 000 pasos, misma semilla, 0%).
Código `env/warehouse-v8` (nuevo término `face_bonus`, por defecto 0; ver `docs/ambiente-v0.8.md`). Los experimentos j2 y j3 no cambian código (j2 usa `carry_milestone` de v7). PPO de C0 salvo en j3.

| Run | Cambio frente a `m1-e4l-seed0` | Config |
|---|---|---|
| m1-j1-seed0 | `face_bonus` 10.0 (llegar a la celda de interacción mirando a la estación, una vez por estación y episodio) | `m1_j1_cara_seed0.yaml` |
| m1-j2-seed0 | `carry_milestone` 5.0 (hito a mitad del camino al despacho con la carga) | `m1_j2_hito_seed0.yaml` |
| m1-j3-seed0 | `ent_coef` 0.01 (recompensa idéntica a e4l) | `m1_j3_entropia_seed0.yaml` |

- **Hipótesis:** (j1) el primer paso, llegar y mirar al estante, no tiene señal y por eso 2 de 3 semillas no despegan; (j2) el atasco tras cargar se reduce con un hito en el tramo con carga; (j3) el colapso temprano a una acción casi determinista impide descubrir la cadena.
- **Medición previa (conductas guionizadas, mapa con muro, 20 semillas):** quieto en la base −40.8; ir al estante y mirarlo y quedarse −47.8 sin bonus, −42.8 con 5, **−37.8 con 10**; pedido completo 128.8 / 147.8 / 166.8. Por eso se usa 10.0 y no 5.0.
- **Criterio (fijado ahora, antes de ver resultados), idéntico para los tres:** el ajuste *muestra señal* si el éxito en `suite-m1-v1` es ≥ 5% (≥ 3/50) frente a e4l-seed0 (0%) y los choques por episodio no suben > 10%; si no, se rechaza. Con una sola semilla un resultado positivo **no basta para adoptar**: pide repetir con semillas 1 y 2 (donde también falló e4l/e4x).
- **Qué los refutaría:** éxito < 5% o choques que suben > 10%.
- **Limitaciones declaradas:** una semilla por ajuste (la variación entre semillas fue enorme: 0/0/80% en e4x), sin control de ablación; no se sabe cuánto de un resultado positivo es del ajuste y cuánto de la semilla. Una diferencia en la conducta (llega al estante, carga, entrega) es evidencia descriptiva.
- **Métricas secundarias descriptivas:** episodios que llegan a la celda de interacción / miran al estante / suben la bandeja / cargan (`trace_policy.py`), recogidas y entregas por episodio, inválidas, choques, episodios de entrenamiento con éxito.

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (j1–j3, `suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Minutos | Éxito | Llegan a celda / miran al estante / suben bandeja / cargan (de 50) | Inválidas/ep | Choques/ep | Estado |
|---|---:|---:|---|---:|---:|---|
| m1-e4l-seed0 (base) | 34.3 | 0% | 21 / 0 / 0 / 0 | 63.0 | 0.0 | rechazado |
| m1-j1-seed0 (`face_bonus` 10) | 28.7 | 0% | 40 / **40** / 0 / 0 | 0.0 | **2.56** | rechazado |
| m1-j2-seed0 (`carry_milestone` 5) | 28.1 | 0% | 21 / 0 / 0 / 0 | 63.0 | 0.0 | rechazado |
| m1-j3-seed0 (`ent_coef` 0.01) | 28.4 | 0% | 22 / 0 / 0 / 0 | 8.0 | 0.0 | rechazado |
Entrenamiento con éxito: 0 en los tres (0 / ≈1 512 episodios).
- **Decisión por el criterio fijado antes:** los tres con 0% < 5% → `rechazado` (evidencia conservada). Con una sola semilla no descartan la idea.
- **j1 (`face_bonus`):** el único que cambia la conducta como se predijo: 40/50 episodios llegan a la celda y miran al estante (base: 0/50). Pero ninguno sube la bandeja ni carga: se queda quieto mirando, que es lo que anticipaba la medición guionizada (ir, mirar y quedarse −37.8 > quieto −40.8, < recoger el 1.º y quedarse −26.3) y además sube los choques a 2.56/ep (condición de choques también incumplida). El cuello de botella pasa al siguiente paso: subir la bandeja con la penalización `height_mismatch` −0.02 acumulándose por paso mientras está mirando con la bandeja a otra altura.
- **j2 (`carry_milestone`):** **pesos idénticos a los de `m1-e4l-seed0`** (verificado tensor a tensor): como la política nunca carga, el hito no se cobra jamás y el entrenamiento sigue la misma trayectoria (mismo fenómeno que g1-seed1 en el mapa abierto). La prueba no era informativa para una semilla que no carga; el hito solo puede ayudar a semillas que ya cargan (seed2 de e4l/c0l/e4x).
- **j3 (`ent_coef` 0.01):** sin cambio útil (22/50 llegan a una celda, 0 miran, 8 inválidas/ep): la entropía por sí sola no descubre el primer paso.
- **Limitaciones:** una semilla por ajuste y semilla 0 elegida por ser la más difícil; j2 no probó el hito donde sí cargan; j1 no se probó con una recompensa para subir la bandeja.
- **Código:** `env/warehouse-v8` (suite 175/176 en la primera pasada; el fallo, un test que fijaba v7, se corrigió y pasa; reporte `docs/resultados/pytest-warehouse-v8.xml` conserva el fallo original).


## Shaping solo por potencial y parada por estancamiento (`m1-p1`, `m1-p2`, escrito antes de entrenar, 2026-11-14)
**Contexto:** j1 (`face_bonus`) hizo llegar y mirar al estante en 40/50 episodios pero se quedó mirando; el shaping acumulaba términos (≈ 40% del retorno de una misión perfecta, con `progress` y `manhattan_progress` midiendo lo mismo). Instrucción del usuario: probar **solo shaping basado en potencial** y acortar los episodios en el entrenamiento para que tarde menos. Código `env/warehouse-v9` (ver `docs/ambiente-v0.9.md`).
- **Cambio:** se quitan `progress` (0), `manhattan_progress`, `height_mismatch`, `face_bonus` y `carry_milestone`; queda `potential` 30.0 (Φ por etapas, γ 0.99) más las recompensas de la tarea (pickup, delivery, completion), `time`, `battery`, `invalid_interaction` −0.2 y `collision` −1. PPO y mapa (`layout_v0.4`, `m1`) iguales a `m1-e4l`; 600 000 pasos. **Dos cambios a la vez** (potencial y parada por estancamiento de 100 pasos solo en entrenamiento), por instrucción del usuario; por eso hay ablación.
- **Medición previa (conductas guionizadas, retorno descontado, 10 semillas):** quieto −10.0 → −11.4; ir, mirar y quedarse −10.2 → −11.6; recoger el 1.º y quedarse −2.0 → −3.3; pedido completo 50.6 → 62.4 (W = 0 → 30). El orden no cambia: no hay zona de evitación nueva. Brecha máxima sin mejorar Φ (parada): heurística 2, éxitos de e4x-seed2 con acciones muestreadas 49 (p95 30), episodios atascados ≈ 384 → ventana 100.
- **Hipótesis:** un único potencial por etapas da señal para toda la cadena sin las zonas de evitación de los términos sueltos, y la parada multiplica los episodios por paso, de modo que más semillas despegan.
- **Criterio (fijado ahora):** `m1-p1` se adopta como *señal* si el éxito medio de las 3 semillas en `suite-m1-v1` es ≥ 5% (referencia `m1-e4l`: 0%) sin que los choques por episodio suban > 10%. Se reporta cada semilla; con 3 semillas, un resultado llevado por una sola sigue siendo `candidato`, no `recomendado`.
- **Qué la refutaría:** media < 5% o choques que suben > 10%.
- **Ablación `m1-p2`** (semilla 0, potencial sin parada): atribuye el efecto. Se compara con `m1-p1-seed0` y con `m1-e4l-seed0` (0%).
- **Métricas secundarias descriptivas:** episodios que llegan / miran / suben la bandeja / cargan, recogidas y entregas por episodio, episodios de entrenamiento (con la parada son más), inválidas, choques, minutos de entrenamiento.
- **Sobre el tiempo:** los pasos por segundo no cambian (el presupuesto sigue siendo de 606 208 pasos); la parada reduce el tiempo por episodio, no el tiempo del run. Si p1 funciona, el siguiente paso es recortar el presupuesto de pasos.
- **Limitaciones:** retorno sin descontar de evaluación no comparable con v8 (fuga del potencial); pesos internos de φ sin ajustar; la parada y el potencial vienen juntos salvo en la semilla 0 de p2.

| Run | Pasos | Semilla | Parada | Config |
|---|---:|---:|---|---|
| m1-p1-seed0/1/2 | 606 208 | 0/1/2 | 100 pasos sin mejorar Φ | `m1_p1_potencial_seed{0,1,2}.yaml` |
| m1-p2-seed0 | 606 208 | 0 | ninguna | `m1_p2_potencial_sinparada_seed0.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (p1, p2; `suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Minutos | Éxito | Llegan a celda / miran / suben / cargan (de 50) | Inválidas/ep | Choques/ep | Episodios de entrenamiento (éxitos) | Acciones: FRENAR | Estado |
|---|---:|---:|---|---:|---:|---:|---:|---|
| m1-e4l-seed0 (base) | 34.3 | 0% | 21 / 0 / 0 / 0 | 63.0 | 0.0 | 1 512 (0) | 72% | rechazado |
| m1-p1-seed0 | 27.8 | 0% | 0 / 0 / 0 / 0 | 8.0 | 0.0 | 5 455 (0) | 95% | rechazado |
| m1-p1-seed1 | 28.0 | 0% | 0 / 0 / 0 / 0 | 0.0 | 0.0 | 5 633 (0) | 100% | rechazado |
| m1-p1-seed2 | 27.7 | 0% | 0 / 0 / 0 / 0 | 0.0 | 0.0 | 5 745 (0) | idle | rechazado |
| m1-p2-seed0 (sin parada) | 27.5 | 0% | 0 / 0 / 0 / 0 | 53.2 | 0.0 | 1 512 (0) | 85% | rechazado |
- **Decisión por el criterio fijado antes:** media 0% < 5% → hipótesis refutada, los 4 runs `rechazado` (evidencia conservada). Peor que la base (m1-e4l-seed0 llegaba a la celda en 21/50): ninguna semilla se acerca al estante.
- **Diagnóstico:** las políticas colapsan a FRENAR (idle), como en los primeros runs (v1/v2). El shaping de navegación de `potential` 30.0 vale `30·0.40/(6·d_max)` ≈ **0.08 por celda** (d_max ≈ 25), unas **8 veces menos** que `manhattan_progress` + `progress` de e4 (0.6 por celda) y por debajo del coste de moverse (batería y exploración con inválidas/choques); quedarse quieto cuesta lo mismo en tiempo. La invarianza de la política óptima no dice nada sobre la magnitud de la señal: con W = 30 el shaping total de una misión (≈ 30) es pequeño frente a la dificultad de descubrir la cadena. Es una explicación coherente con la medición, **no probada** (no se corrió W mayor).
- **Atribución (ablación p2 frente a p1-seed0):** misma conducta sin parada (0/50, idle), así que el fallo es del potencial con ese W, no de la parada. La parada hizo lo previsto en mecánica: **3.6–3.8 veces más episodios** de entrenamiento (5 455–5 745 frente a 1 512) con los mismos pasos y los mismos minutos (≈ 28 en ambos); no acorta el run.
- **Limitaciones:** un solo valor de W (30), elegido para que el shaping total fuera una unidad; pesos internos de φ sin ajustar; `p2` con una semilla.
- **Siguiente paso propuesto (no hecho):** subir W (por ejemplo 100–200) y/o concentrar la navegación, con la medición guionizada del shaping por celda antes de entrenar; criterio: ≥ 5%.

## Potencial con la recompensa de la tarea ×5 (`m1-q1`, escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1-p1`/`p2` (potencial W = 30) dieron 0% con política idle (FRENAR 85–100%); el shaping de navegación valía 0.08 por celda (e4: 0.6), por debajo del coste de moverse. Instrucción del usuario: W mayor con las recompensas de la tarea proporcionalmente mayores. Sin cambio de código (`warehouse-v9`); solo configs.
- **Cambio frente a `m1-p1`:** `pickup` 50, `delivery` 150, `completion` 250 y `potential` 150 (×5); `invalid_interaction` −0.2, `collision` −1, `time` y `battery` sin escalar. Parada de estancamiento 100, 600 000 pasos, mapa con muro, semillas 0–2, PPO idéntico (verificado con `diff` y una prueba).
- **Equivalencia (declarada antes):** SB3 normaliza las ventajas, así que escalar todo por igual no cambiaría nada; escalar solo los términos positivos equivale a dividir por 5 las penalizaciones: colisión efectiva −0.2, inválida −0.04, tiempo −0.02, batería −0.004. **Riesgo:** la trampa de choques vista con colisión −0.5/−0.1 (`m1-r6`, `r7`; 200 000 pasos, sin shaping, ver `experiment-log`). Si los choques por episodio suben, es la señal.
- **Medición previa:** shaping de navegación por celda 0.08 (×1) → **0.40** (×5) (d_max ≈ 25; e4: 0.6). Retornos guionizados descontados, 8 semillas, mapa con muro, ×1 → ×5: quieto −11.4 → −17.2; ir, mirar y quedarse −11.6 → −17.1; recoger el 1.º y quedarse −3.3 → +24.2; pedido completo 61.0 → 330.6. El orden se conserva (invarianza) y recoger y quedarse ahora supera a quedarse quieto por ≈ 41.
- **Hipótesis:** con el shaping de navegación por encima del coste de moverse la política se acerca al estante y descubre el resto de etapas del potencial; más semillas despegan.
- **Criterio (fijado ahora):** éxito medio de las 3 semillas en `suite-m1-v1` ≥ 5% (base `m1-e4l` 0%) y choques por episodio sin subir > 10% frente a `m1-e4l` (0). Se reporta cada semilla; un resultado llevado por una semilla es `candidato`.
- **Qué la refutaría:** media < 5% o choques que suben > 10%.
- **Métricas secundarias descriptivas:** episodios que llegan / miran / suben / cargan, entregas por episodio, choques, inválidas, fracción de FRENAR.
- **Limitaciones:** un solo factor (×5), sin barrido; el retorno de evaluación no es comparable con v8 ni con p1; no se separa el efecto del factor del de «penalizaciones más baratas» (son lo mismo).

| Run | Pasos | Semilla | Config |
|---|---:|---:|---|
| m1-q1-seed0/1/2 | 606 208 | 0/1/2 | `m1_q1_escala5_seed{0,1,2}.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (q1; `suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Minutos | Éxito | Llegan a celda (de 50) | Choques/ep | Inválidas/ep | Acciones | Episodios de entrenamiento (éxitos) | Estado |
|---|---:|---:|---:|---:|---:|---|---:|---|
| m1-e4l-seed0 (base) | 34.3 | 0% | 21 | 0.0 | 63.0 | 72% FRENAR | 1 512 (0) | rechazado |
| m1-p1-seed0 (×1) | 27.8 | 0% | 0 | 0.0 | 8.0 | 95% FRENAR | 5 455 (0) | rechazado |
| m1-q1-seed0 (×5) | 26.9 | 0% | 0 | **98.8** | 0.0 | 25% AVANZAR, 0% giros, 75% FRENAR | 5 786 (0) | rechazado |
| m1-q1-seed1 (×5) | 26.7 | 0% | 0 | **39.9** | 0.0 | 12% AVANZAR, 0% giros, 88% FRENAR | 5 797 (0) | rechazado |
| m1-q1-seed2 (×5) | 26.7 | 0% | 0 | 0.0 | 19.4 | 92% FRENAR, 8% CARGAR | 5 327 (0) | rechazado |
- **Decisión por el criterio fijado antes:** media 0% < 5% y los choques suben de 0 a 0/39.9/98.8 por episodio → hipótesis refutada, los 3 runs `rechazado` (evidencia conservada).
- **El riesgo declarado antes se materializó:** dos de tres semillas caen en la **trampa de choques** (conducción contra obstáculos sin giros, luego frenado), la misma conducta que `m1-r6`/`r7` con colisión barata. Con ×5 y penalizaciones sin escalar, la colisión efectiva (−0.2) y la invalidación (−0.04) quedaron baratas frente a un shaping de 0.40 por celda; la semilla 2 sigue en idle.
- **Lectura de los dos factores:** ×1 (p1) → idle por señal débil; ×5 (q1) → trampa de choques y un idle. Subir todo por igual no mueve nada (SB3 normaliza ventajas); lo que decide es la razón entre el shaping por celda y el coste de los contactos (colisión −1, inválida −0.2) y de moverse. No probado: **escalar también `collision` e `invalid_interaction` ×5** (−5 y −1, que son los valores por defecto del ambiente) mantendría la razón shaping/colisión de p1 y subiría la razón shaping/tiempo ×5.
- **Limitaciones:** un solo factor; sin ablación de las penalizaciones; la parada (100) está activa en todas, aunque p2 mostró que no es la causa del idle; el potencial navega con BFS (consciente del muro), por lo que el choque contra obstáculos no lo explica el potencial sino la exploración barata.


## Potencial con todo ×3, incluidas las penalizaciones de contacto (`m1-q2`, escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1-p1` (×1) → idle por señal débil (0.08 por celda); `m1-q1` (×5, penalizaciones sin escalar) → trampa de choques en 2 de 3 semillas (98.8 y 39.9 choques por episodio) y un idle. Instrucción del usuario: factor menor (×3) y que `collision` e `invalid_interaction` escalen con él. Sin cambio de código (`warehouse-v9`).
- **Cambio frente a `m1-p1`:** `pickup` 30, `delivery` 90, `completion` 150, `potential` 90, `collision` −3, `invalid_interaction` −0.6 (todo ×3); `time` y `battery` sin escalar. Parada 100, 600 000 pasos, mapa con muro, semillas 0–2, PPO idéntico (`diff` y prueba).
- **Razón de diseño (medida):** coste de una colisión en celdas de shaping de navegación — p1 12.6, q1 **2.5**, q2 **12.6**. q2 conserva la razón de p1 (que no chocó) y sube la señal frente a `time`/`battery` ×3 (0.24 por celda frente a 0.08).
- **Medición previa (retornos guionizados descontados, 8 semillas, mapa con muro):** quieto −14.3; ir, mirar y quedarse −14.3; recoger el 1.º y quedarse **+10.4**; pedido completo **195.8** (×1: −11.4 / −11.6 / −3.3 / 61.0; ×5: −17.2 / −17.1 / +24.2 / 330.6). Recoger y quedarse supera a quedarse quieto por ≈ 25.
- **Hipótesis:** con la señal ×3 y los contactos igual de caros en proporción, la política avanza y gira hacia el estante sin chocar y descubre las demás etapas del potencial; más semillas despegan.
- **Criterio (fijado ahora):** éxito medio de las 3 semillas en `suite-m1-v1` ≥ 5% (base `m1-e4l` 0%) y choques por episodio sin subir > 10% frente a `m1-e4l` (0). Se reporta cada semilla; un resultado llevado por una semilla es `candidato`.
- **Qué la refutaría:** media < 5% o choques que suben > 10%.
- **Métricas secundarias descriptivas:** episodios que llegan / miran / suben / cargan, entregas por episodio, choques, inválidas, mezcla de acciones.
- **Limitaciones:** un solo factor; la razón shaping/colisión está igualada con la de p1 por construcción, pero la razón shaping/(tiempo+batería) solo mejora ×3; si falla, no se sabe si falta señal o sobran contactos caros. El potencial no premia orientarse hacia el objetivo (solo distancia BFS), por lo que los giros no tienen señal propia.

| Run | Pasos | Semilla | Config |
|---|---:|---:|---|
| m1-q2-seed0/1/2 | 606 208 | 0/1/2 | `m1_q2_escala3_seed{0,1,2}.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (q2; `suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Minutos | Éxito | Llegan a celda (de 50) | Choques/ep | Inválidas/ep | Acciones | Episodios de entrenamiento (éxitos) | Estado |
|---|---:|---:|---:|---:|---:|---|---:|---|
| m1-q2-seed0 | 27.1 | 0% | 0 | 0.0 | 0.0 | 99% FRENAR | 4 678 (0) | rechazado |
| m1-q2-seed1 | 27.0 | 0% | 0 | 1.6 | 39.4 | 90% FRENAR, 6% SUBIR, 3% BAJAR | 5 018 (0) | rechazado |
| m1-q2-seed2 | 27.1 | 0% | 0 | 0.0 | 7.1 | 97% FRENAR | 5 176 (0) | rechazado |
- **Decisión por el criterio fijado antes:** media 0% < 5% → hipótesis refutada, los 3 runs `rechazado`. Los choques no suben (la trampa de q1 no reaparece: razón colisión/shaping igual a la de p1), pero las tres políticas vuelven a **idle**.
- **Patrón en los 10 runs con potencial** (p1 ×3, p2, q1 ×3, q2 ×3; factores ×1, ×3, ×5, con y sin parada, penalizaciones escaladas o no): **0/10 llegan siquiera a la celda de interacción** (0/50 episodios en cada uno), mientras e4l y c0l llegaban en 21/50, 29/50 y 50/50 en la mitad de sus semillas (seed0: 21 y 29, seed2: 50; seed1: 29 y 0). Dos modos de fallo: idle (señal débil o contactos caros) y trampa de choques (contactos baratos).
- **Diagnóstico de la señal (retorno descontado del término de shaping, 20 episodios, mapa con muro):** acciones aleatorias vs quieto — `progress` 0.3: +0.04 vs 0.00; potencial W = 90: −4.19 vs −4.20; W = 30: −1.40 vs −1.40. Con ambos, explorar al azar apenas rinde más que no hacer nada; la diferencia entre el potencial y `progress` no se ve en esta medición, por lo que **la causa de que ninguna semilla despegue no está establecida** (candidatas sin probar: la fuga γ del potencial en estados con Φ alto, la combinación con `time`/`battery`, o la varianza entre semillas).
- **Control propuesto, no hecho (pruebas de ambiente antes que del modelo):** `m1-c0l` (progress 0.3, sin potencial) con el código v9 y la parada de 100, 3 semillas. Si vuelve a llegar al estante en ≈ la mitad de las semillas, el potencial es el problema; si da 0/3, el cambio de código o la parada rompen la línea base.
- **Limitaciones:** el potencial se probó con pesos internos de φ fijos (0.10/0.40/0.20/0.30) y tres factores; los giros no tienen señal propia; solo se mide la señal por la política aleatoria, no la dificultad real de exploración.


## Control de regresión de v9: `m1-c0l` con el código v9 (`m1-c1`, `m1-c2`, escrito antes de entrenar, 2026-11-14)
**Contexto:** 10 runs con `potential` (p1, p2, q1, q2; ×1, ×3, ×5) dieron 0/50 episodios que llegan a la celda de interacción, mientras `m1-c0l` (recompensa base con `progress` 0.3, `warehouse-v7`) y `m1-e4l` llegaban en la mitad de las semillas. Instrucción del usuario: correr el control. Sin cambio de código.
- **`m1-c1` (3 semillas):** receta de `m1-c0l` (invalid −0.2, collision −1, `progress` 0.3 por defecto, sin `potential`), código `warehouse-v9` y `parada_estancamiento` 100. 600 000 pasos, mapa con muro. Referencia `m1-c0l`: llegan a la celda 29/50, 0/50 y 50/50 (semillas 0, 1, 2); éxito 0% en las tres.
- **`m1-c2` (semilla 0):** exactamente la config de `m1-c0l-seed0` pero con `environment_version: warehouse-v9` y **sin parada**. El entrenamiento es determinista (`m1-c0b` reprodujo a `m1-c0`): si v9 no cambia la dinámica ni la recompensa con `potential` = 0, los **pesos deben ser idénticos** a los de `m1-c0l-seed0`.
- **Qué se concluye (fijado ahora):**
  - `m1-c2` con pesos idénticos → el código v9 no rompe la línea base; si difieren → hay una regresión en v9 y se investiga antes de cualquier otro experimento.
  - `m1-c1` reproduce el patrón de `c0l` (al menos 1 de 3 semillas con ≥ 10/50 episodios que llegan a la celda) → el fallo de los 10 runs es del potencial y no de la parada; si da 0/3 con `c2` idéntico → la parada rompe la línea base.
- **Qué la refutaría / limitaciones:** con 3 semillas y probabilidad de llegar ≈ 2/3 por semilla en la línea base, ver 0/3 por azar con la parada inocua tiene probabilidad ≈ 4%, no cero; el control es una señal fuerte, no una prueba. `c2` solo cubre la semilla 0.
- **Métricas secundarias descriptivas:** episodios que llegan / miran / suben / cargan, mezcla de acciones, episodios de entrenamiento.

| Run | Pasos | Semilla | Parada | Config |
|---|---:|---:|---|---|
| m1-c1-seed0/1/2 | 606 208 | 0/1/2 | 100 | `m1_c1_control_v9_seed{0,1,2}.yaml` |
| m1-c2-seed0 | 606 208 | 0 | ninguna | `m1_c2_repro_v9_seed0.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (c1, c2; `suite-m1-v1`, determinista, semillas 10000–10049)
| Run | Minutos | Éxito | Llegan a celda / miran / suben / cargan (de 50) | Inválidas/ep | Recogidas/ep | Episodios de entrenamiento | Estado |
|---|---:|---:|---|---:|---:|---:|---|
| m1-c0l-seed0 (ref. v7) | 30.5 | 0% | 29 / 0 / 0 / 0 | 0.0 | 0.00 | 1 821 | candidato |
| m1-c0l-seed1 (ref. v7) | 30.4 | 0% | 0 / 0 / 0 / 0 | 0.0 | 0.00 | — | candidato |
| m1-c0l-seed2 (ref. v7) | 31.6 | 0% | 50 / 50 / 50 / 49 | 11.9 | 1.00 | — | candidato |
| m1-c1-seed0 (v9 + parada) | 26.1 | 0% | **49 / 41 / 41 / 19** | 132.1 | 0.44 | 3 577 | candidato |
| m1-c1-seed1 (v9 + parada) | 25.8 | 0% | 0 / 0 / 0 / 0 | 0.0 | 0.00 | 4 341 | candidato |
| m1-c1-seed2 (v9 + parada) | 25.7 | 0% | 21 / 0 / 0 / 0 | 0.0 | 0.00 | 4 310 | candidato |
| m1-c2-seed0 (v9, sin parada) | 25.4 | 0% | 29 / 0 / 0 / 0 | 0.0 | 0.00 | 1 512 | candidato |
- **`m1-c2`: pesos idénticos a `m1-c0l-seed0` (verificado tensor a tensor).** El código v9 con `potential` = 0 no cambia el entrenamiento: no hay regresión del ambiente ni de la recompensa.
- **`m1-c1`: reproduce el patrón de la línea base** (2 de 3 semillas llegan a la celda: 49/50 y 21/50; la semilla 1 no, igual que `c0l`). Con la parada de 100 pasos, la receta base sigue llegando al estante; la semilla 0 incluso sube la bandeja en 41/50 episodios y carga en 19/50 (la línea base, seed0: 0 cargan), pero con una semilla por celda esto es descriptivo, no atribuible a la parada (el camino de aprendizaje cambia al cambiar la parada).
- **Conclusión por el criterio fijado antes:** `c2` idéntico y `c1` con ≥ 1 de 3 semillas que llega a la celda ⇒ **el fallo de los 10 runs con potencial (0/50 llegan a la celda) es del potencial, no del código v9 ni de la parada.** Éxito 0% en los siete runs de la tabla: la línea base tampoco entrega con 600 000 pasos.
- **Qué no se sabe:** por qué el potencial no despega mientras `progress` 0.3 sí en la mitad de las semillas. La medición de señal con política aleatoria no lo distinguía (ver q2). Una diferencia que no se ha aislado: `progress` paga la diferencia de BFS sin descuento y sin términos extra, mientras el potencial usa `γΦ' − Φ` con la fuga (γ−1)Φ y reparte el peso entre cuatro partes de φ.
- **Limitaciones:** una semilla por celda en las comparaciones entre runs; `c0l` y `c1` no son comparables semilla a semilla (la parada cambia el camino).



## `progress` 0.3 + etapas del potencial sin navegación (`m1-s1`, escrito antes de entrenar, 2026-11-14)
**Contexto:** el control `m1-c1`/`c2` mostró que el fallo de los 10 runs con potencial es del potencial (no del código v9 ni de la parada). Instrucción del usuario: dejar `progress` 0.3 y añadir solo las etapas del potencial encima. Código `env/warehouse-v10` (`potential_nav`, ver `docs/ambiente-v0.10.md`).
- **Cambio frente a `m1-c1` (misma semilla, mismo código salvo el parámetro):** `potential` 30.0 y `potential_nav` 0.0; el resto idéntico (invalid −0.2, collision −1, `progress` 0.3 por defecto, parada 100, PPO, mapa con muro, 600 000 pasos, semillas 0–2). Las semillas son pareables con `m1-c1` (v9, mismo resto): `potential` en 0 y `potential_nav` en 0.40 reproducen v9 por prueba.
- **Hipótesis:** con la navegación de `progress` y las etapas del potencial encima (bandeja guardada, mirar, altura, avance por recoger/entregar), las semillas que llegan al estante pasan a subir la bandeja, cargar, bajarla y entregar. `m1-c1-seed0` llegaba 49/50, subía 41/50, cargaba 19/50 y nunca entregaba; la línea base no entrega con 600 000 pasos.
- **Medición previa (conductas guionizadas, retorno descontado, 8 semillas):** quieto −10.0 → −10.8; ir, mirar y quedarse −6.6 → −7.3; recoger el 1.º y quedarse 1.7 → 0.9; pedido completo 59.9 → 72.1 (c1 → s1). El orden se conserva.
- **Criterio (fijado ahora):** éxito medio de las 3 semillas en `suite-m1-v1` ≥ 5% (base 0%) y episodios que llegan a la celda sin caer frente a `m1-c1` (49 / 0 / 21 de 50 en las semillas 0 / 1 / 2). Se reporta cada semilla y las etapas alcanzadas (llegan / miran / suben / cargan / entregan).
- **Qué la refutaría:** media < 5% de éxito, o pérdida de la llegada al estante.
- **Qué se aprende aunque el éxito sea 0%:** si suben las etapas alcanzadas (cargan, entregan) frente a `m1-c1`, las etapas ayudan; si bajan las llegadas, el potencial interfiere con `progress`.
- **Limitaciones:** una semilla por celda; `progress` más potencial no conserva en teoría la política óptima (solo la parte de potencial lo hace); pesos internos de φ sin ajustar.

| Run | Pasos | Semilla | Config |
|---|---:|---:|---|
| m1-s1-seed0/1/2 | 606 208 | 0/1/2 | `m1_s1_etapas_seed{0,1,2}.yaml` |

Presupuesto efectivo 606 208 pasos por run.

### Presupuesto real y resultados (s1; `suite-m1-v1`, determinista, semillas 10000–10049)
| Run | Minutos | Éxito | Llegan a celda (de 50) | Referencia `m1-c1` (misma semilla) | Inválidas/ep | Choques/ep | Episodios de entrenamiento (éxitos) | Estado |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| m1-s1-seed0 | 23.7 | 0% | 0 | 49 | 0.0 | 0.0 | 6 024 (0) | rechazado |
| m1-s1-seed1 | 23.5 | 0% | 0 | 0 | 3.6 | 0.0 | 6 060 (0) | rechazado |
| m1-s1-seed2 | 23.8 | 0% | 0 | 21 | **210.0** | 0.0 | 6 026 (0) | rechazado |
- **Decisión por el criterio fijado antes:** media 0% < 5% y las llegadas a la celda caen de 49/0/21 a 0/0/0 → hipótesis refutada, los 3 runs `rechazado`. Con `progress` 0.3 intacto, añadir solo las etapas del potencial hace perder la llegada al estante en las dos semillas que la tenían.
- **Confusión de diseño, descubierta al analizar (mía):** la parada de estancamiento usa `env.potential()` para decidir si hubo progreso. Con `potential_nav` = 0 Φ no sube mientras el robot navega, así que en s1 la parada pasó a ser «100 pasos sin avanzar en mirar/altura/recoger», distinta de la de `m1-c1` (donde Φ incluía la navegación). s1 difiere de c1, por tanto, en **dos** cosas (el término de recompensa y la señal de la parada) y el resultado no permite atribuir el fallo solo al término. Lo que sí se mantiene: p2 (potencial completo, **sin parada**) también dio 0/50 y `m1-c2` (sin parada, v9) reproduce la línea base, así que la parada no explica los 10 runs anteriores.
- **Curvas de entrenamiento (`progress.csv`, semillas 0 y 1):** la varianza explicada del crítico de s1 sube más rápido (0.95 a 60 000 pasos frente a 0.78 en c1-seed0) y la pérdida del valor cae a ≈ 0 hacia 120 000 pasos: el crítico predice bien un retorno casi constante (política idle), compatible con el colapso, pero no es un diagnóstico de la causa.
- **Conclusión acumulada (13 runs con `potential` > 0: p1 ×3, p2, q1 ×3, q2 ×3, s1 ×3):** ninguno llega a la celda de interacción en ningún episodio de evaluación; los runs sin potencial (e4l, c0l, c1, c2, e4x, j1–j3) llegan en la mayoría de las semillas. La causa **no está establecida**. Lo descartado con evidencia: el código v9 (c2 idéntico), la parada (p2 y c2), la magnitud sola (×1, ×3, ×5), la trampa de choques (q2) y la navegación del potencial como único culpable (s1, con la salvedad de la parada).
- **Siguiente paso razonable (no hecho):** abandonar la línea del potencial por ahora y volver a la receta que sí llega al estante (`progress` 0.3 / e4) para atacar la carga y la entrega con otra palanca (presupuesto de 1 800 000 pasos con parada, o repetir `e4x` con más semillas), en lugar de seguir variando el potencial.
- **Limitaciones:** una semilla por celda; confusión de la parada en s1; sin ablación del `K` del potencial (recoger/entregar) ni de la renormalización.


## `e4x` en semillas nuevas con parada y `c1` con 3× pasos (`m1-e4y`, `m1-c3`, escrito antes de entrenar, 2026-11-14)
**Contexto:** 13 runs con potencial no llegaron nunca a la celda de interacción; se abandona esa línea por ahora. Instrucción del usuario: probar las dos opciones propuestas. Sin cambio de código (`warehouse-v10`, `potential` en 0); solo configs, todas con 1 800 000 pasos (1 802 240 efectivos), mapa con muro (`layout_v0.4`), `suite-m1-v1`, PPO de C0.

### Experimento A: `m1-e4y` (receta de `m1-e4x`, semillas 3, 4 y 5, con parada 100)
- **Cambio frente a `m1-e4x`:** semillas nuevas (3–5) y parada de estancamiento de 100 pasos (e4x corrió sin parada). Recompensa e4 (manhattan 0.3, altura −0.02, invalid −0.2, collision −1, `progress` 0.3 por defecto) y PPO idénticos (prueba que lo fija).
- **Pregunta:** ¿cuán fiable es el 80% de `m1-e4x-seed2` (0/0/80% en las semillas 0–2)? e4y no separa el efecto de las semillas del de la parada (cambian las dos); si sale bien o mal con la parada, esto no atribuye la diferencia a la parada.
- **Hipótesis:** con 1 800 000 pasos y la parada, al menos una de las 3 semillas nuevas completa la misión. **Criterio (fijado ahora):** éxito medio de las 3 semillas en `suite-m1-v1` ≥ 5% (base `m1-e4l` 0%) y choques por episodio sin subir > 10% frente a `m1-e4l` (0). Se reporta además cuántas semillas tienen éxito > 0 (e4x: 1 de 3).
- **Qué la refutaría:** media < 5% o choques que suben > 10%.

### Experimento B: `m1-c3` (receta de `m1-c1-seed0`, 1 800 000 pasos, semilla 0, con parada 100)
- **Cambio frente a `m1-c1-seed0`:** solo el presupuesto (3×).
- **Motivo:** con 600 000 pasos `m1-c1-seed0` llegaba a la celda en 49/50, subía la bandeja en 41/50 y cargaba en 19/50 pero no entregaba. **Hipótesis:** con más pasos completa la cadena sin los términos de e4. **Criterio:** éxito en `suite-m1-v1` ≥ 5% (c1-seed0 a 600 000 pasos: 0%). **Qué la refutaría:** < 5%.
- **Métricas secundarias descriptivas (ambos):** episodios que llegan / miran / suben / cargan / entregan, entregas por episodio, choques, inválidas, curva de la evaluación intermedia (primer punto con retorno positivo), episodios de entrenamiento con éxito, minutos.
- **Limitaciones:** una semilla en B (la variación entre semillas fue enorme); en A no se separa la parada de las semillas; un control de e4 sin parada en las semillas 3–5 costaría 3 runs más de ≈ 80 minutos.

| Run | Pasos | Semilla | Parada | Config |
|---|---:|---:|---|---|
| m1-e4y-seed3/4/5 | 1 802 240 | 3/4/5 | 100 | `m1_e4y_seed{3,4,5}.yaml` |
| m1-c3-seed0 | 1 802 240 | 0 | 100 | `m1_c3_largo_seed0.yaml` |

Presupuesto efectivo 1 802 240 pasos por run. Los 4 runs corrieron en paralelo; **92.7–103.0 minutos** cada uno (el estimado de ≈ 80 minutos se quedó corto: mis pruebas y perfilados compartieron la CPU).

### Presupuesto real y resultados (`suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%, 79.9 pasos)
| Run | Minutos | Éxito | Recogidas / entregas por ep | Llegan / miran / suben / cargan (de 50) | Inválidas/ep | Choques/ep | Pasos de los éxitos | Entrenamiento: éxitos / episodios | Estado |
|---|---:|---:|---|---|---:|---:|---:|---:|---|
| **m1-e4y-seed3** | 103.0 | **100%** (50/50) | 3.00 / 3.00 | 50 / 50 / 50 / 50 | 6.6 | 0.0 | 94.2 | 2 575 / 10 767 | candidato |
| m1-e4y-seed4 | 94.1 | 0% | 0.00 / 0 | 22 / 0 / 0 / 0 | 0.0 | 0.0 | — | 0 / 13 814 | candidato |
| m1-e4y-seed5 | 92.7 | 0% | 0.00 / 0 | 22 / 21 / 0 / 0 | 0.0 | 0.0 | — | 0 / 14 145 | candidato |
| **m1-c3-seed0** | 99.7 | **98%** (49/50) | 2.98 / 2.94 | 50 / 50 / 50 / 50 | 7.1 | 0.0 | 86.8 | 2 040 / 11 123 | candidato |
- **Experimento A (criterio fijado antes): cumplido.** Media de las 3 semillas nuevas 33.3% (desv. poblacional 47.1 pp) ≥ 5%, choques 0.0 (sin subir). **Lo lleva una semilla de tres** (seed3 100%; seed4 y seed5 0%), exactamente como `m1-e4x` (0/0/80%): 1 de 3 semillas con éxito en ambos grupos. La parada no aumentó la fracción de semillas que despegan (1/3 frente a 1/3 con 3 semillas por grupo; no hay potencia para ver una diferencia). e4y-seed3 hizo 10 767 episodios de entrenamiento (e4x ≈ 4 000–5 000) con 2 575 éxitos.
- **Experimento B (criterio fijado antes): cumplido con holgura.** `m1-c3-seed0` 98% (49/50) frente a 0% de `m1-c1-seed0` a 600 000 pasos. **Con la receta base, sin ningún término e4** (invalid −0.2, collision −1, `progress` 0.3 por defecto) más la parada: 2.94 entregas por episodio, 0 choques, éxitos en 86.8 pasos (heurística 79.9). El único fallo agota el tiempo con carga y la bandeja abajo. Primer retorno positivo de la evaluación intermedia a 1 620 000 pasos, casi al final del presupuesto: con menos pasos no habría despegado.
- **Lectura conjunta:** un modelo de RL puro (sin heurística ni imitación) completa la misión en el mapa con muro en dos runs distintos (e4y-seed3 100%, c3-seed0 98%, además de e4x-seed2 80%). Lo que falta no es la recompensa e4 (c3 funciona sin ella) sino **robustez entre semillas**: 2 de 3 semillas de e4y fracasan y e4x también; de c3 solo se corrió una semilla. El presupuesto largo es necesario (c1 con 600 000 pasos dio 0%).
- **Lo que NO se puede afirmar:** que la receta base sea fiable (una semilla); que la parada ayude (confusión con las semillas); que 98–100% sea el rendimiento esperado: las semillas se eligieron por convocatoria, y la suite de comparación (10000–10049) es la misma con la que se decide, no el test final reservado.
- **Notas de trazabilidad:** los runs se lanzaron con el commit `750e99f`; después se hizo la mejora de rendimiento de `Layout.distance_field` (`1cffbc0`), que no cambia resultados (equivalencia probada) y que los runs en curso no importaron. Tres manifiestos registran `git_dirty: true` por carpetas de salida de runs hermanos sin versionar.
- **Siguiente paso razonable (no hecho):** repetir `c3` en las semillas 1 y 2 (y/o 3–5) con la misma parada para medir la fiabilidad de la receta base; elegir finalistas con tres semillas y reservar el test final.

## Fiabilidad de la receta base: `m1-c3` en las semillas 1–4 (escrito antes de entrenar, 2026-11-14)
**Contexto:** `m1-c3-seed0` (receta base: invalid −0.2, collision −1, `progress` 0.3 por defecto, parada 100, 1 802 240 pasos, mapa con muro) dio 98% (49/50), mientras `m1-e4x`/`m1-e4y` solo despegaron en 1 de 3 semillas. Instrucción del usuario: repetirla en más semillas. Sin cambio de código (`warehouse-v10`).
- **Cambio:** solo la semilla (1, 2, 3 y 4); el resto idéntico a `m1-c3-seed0` (prueba que lo fija). 4 runs en paralelo; sin otra carga en la CPU para que el tiempo sea comparable (≈ 80–90 minutos esperados).
- **Hipótesis:** la receta base con 1 800 000 pasos y parada completa la misión en la mayoría de las semillas.
- **Criterio (fijado ahora):** candidata a finalista si **al menos 3 de las 5 semillas (0–4, contando `m1-c3-seed0`) alcanzan ≥ 50% de éxito en `suite-m1-v1` con choques sin subir > 10% frente a `m1-e4l` (0)**. **Se refuta** si como máximo 1 de las 4 semillas nuevas alcanza ≥ 50%. Se reportan éxito, entregas, choques y etapas de cada semilla, y la media y desviación de las 5.
- **Métricas secundarias descriptivas:** pasos de los éxitos, primer punto de la evaluación intermedia con retorno positivo, episodios de entrenamiento con éxito.
- **Limitaciones:** 5 semillas dan una estimación gruesa de la fiabilidad (un intervalo exacto al 95% para 3 de 5 va de ≈ 15% a ≈ 95%); sin control de la receta base sin parada en el mismo presupuesto (no se separa el efecto de la parada); todas las semillas se evalúan en la misma suite de comparación, no en el test final reservado.

| Run | Pasos | Semilla | Config |
|---|---:|---:|---|
| m1-c3-seed1/2/3/4 | 1 802 240 | 1/2/3/4 | `m1_c3_largo_seed{1,2,3,4}.yaml` |

Presupuesto efectivo 1 802 240 pasos por run; 4 runs en paralelo sin otra carga: **104.2–110.3 minutos** cada uno (≈ 270 pasos/s; la estimación de 80–90 minutos se quedó corta también sin carga externa).

### Presupuesto real y resultados (`suite-m1-v1`, determinista, semillas 10000–10049; heurística 100%)
| Run | Minutos | Éxito | Recogidas / entregas por ep | Llegan / miran / suben / cargan (de 50) | Inválidas/ep | Choques/ep | Entrenamiento: éxitos / episodios | Estado |
|---|---:|---:|---|---|---:|---:|---:|---|
| m1-c3-seed0 (previo) | 99.7 | **98%** | 2.98 / 2.94 | 50 / 50 / 50 / 50 | 7.1 | 0.0 | 2 040 / 11 123 | candidato |
| m1-c3-seed1 | 104.3 | 0% | 0 / 0 | 0 / 0 / 0 / 0 | 0.0 | 0.0 | 0 / 14 249 | candidato |
| m1-c3-seed2 | 104.2 | 0% | 0 / 0 | 42 / 15 / 0 / 0 | 55.7 | 4.48 | 0 / 13 731 | candidato |
| m1-c3-seed3 | 110.3 | 0% | 2.66 / 0 | 50 / 50 / 50 / 50 | 0.0 | 0.0 | 0 / 9 454 | candidato |
| m1-c3-seed4 | 104.8 | 0% | 0 / 0 | 22 / 22 / 0 / 0 | 0.0 | 0.0 | 0 / 14 096 | candidato |
- **Decisión por el criterio fijado antes: refutada.** 0 de las 4 semillas nuevas alcanza ≥ 50% (el umbral de refutación era ≤ 1); en total **1 de 5 semillas** (seed0) completa la misión. Media de las 5: 19.6% (desv. poblacional 39.2 pp). La receta base **no es candidata a finalista** con esta evidencia; los 5 runs quedan `candidato` como evidencia.
- **Patrón:** las semillas se reparten en tres conductas finales: idle sin llegar al estante (seed1), llegar y mirar sin subir la bandeja (seed2, seed4; seed2 además choca 4.48/ep y hace 55.7 inválidas/ep), y cargar sin entregar (seed3: 2.66 recogidas/ep, 42/50 episodios acaban con carga y la bandeja abajo, es decir, **ya puede moverse** y aun así no va al despacho). Solo seed0 completa la cadena. seed3 tuvo su primer retorno positivo en la evaluación intermedia a 1 400 000 pasos: con más presupuesto podría haber despegado, pero eso no se probó.
- **Fiabilidad acumulada del RL puro en el mapa con muro a 1 802 240 pasos:** e4x 1/3, e4y 1/3, c3 1/5 → **3 de 11 semillas** completan la misión (27%), con y sin los términos e4, con y sin parada. La recompensa (e4 frente a base) y la parada no cambian esa fracción de forma visible con estas muestras; la variable que decide es la semilla, es decir, si la exploración temprana encuentra la cadena completa antes de que la política se cierre.
- **Lo que esto cambia:** el problema no es la forma de la recompensa (tres recetas distintas dan la misma tasa) sino la **exploración**: la mayoría de las semillas se estanca en una etapa (idle, mirar, cargar) y PPO con `ent_coef` 0 no sale de ahí. Las palancas no probadas que atacan eso: (a) más presupuesto para las semillas que ya cargan (seed3 iba subiendo), (b) `ent_coef` > 0 con el presupuesto largo (j3 solo lo probó a 600 000 pasos), (c) currículo de posiciones iniciales o de pedidos de 1 línea, (d) elegir entre varias semillas con una suite de desarrollo y validar la elegida en el test final reservado (legítimo si la selección se declara).
- **Limitaciones:** 5 semillas; sin control sin parada al mismo presupuesto; la suite de comparación es la misma con la que se decide; la selección de seed0 como «el modelo que funciona» es posterior a ver el resultado.


## Bono de entropía con el presupuesto largo (`m1-c4`, escrito antes de entrenar, 2026-11-14)
**Contexto:** a 1 802 240 pasos el RL puro completa la misión en 3 de 11 semillas (e4x 1/3, e4y 1/3, c3 1/5), con y sin términos e4, con y sin parada. Las semillas que fallan se estancan en una etapa distinta (idle, mirar sin subir, cargar sin entregar). `j3` probó `ent_coef` 0.01 solo a 600 000 pasos, donde ninguna receta funciona. Instrucción del usuario: opción 1 (entropía con presupuesto largo). Sin cambio de código (`warehouse-v10`).
- **Cambio frente a `m1-c3`:** solo `ent_coef` 0.0 → 0.01 (prueba que fija el resto del bloque `ppo` y del config). Semillas 1–4: las cuatro en que `m1-c3` dio 0%, así cada run tiene su par directo.
- **Hipótesis:** el bono de entropía mantiene la exploración el tiempo suficiente para que más semillas descubran la cadena completa dentro del presupuesto.
- **Criterio (fijado ahora):** muestra señal si **≥ 2 de las 4 semillas alcanzan ≥ 50%** de éxito en `suite-m1-v1` con choques ≤ 0.1 por episodio (`m1-c3` en esas semillas: 0 de 4). **Se refuta si 0 de 4.** 1 de 4 es inconcluyente (coincide con la tasa base ≈ 27%). Se reportan éxito, etapas alcanzadas, choques e inválidas por semilla, y la entropía de la política al final (`train/entropy_loss`).
- **Qué más se aprende:** si las semillas estancadas avanzan de etapa frente a su par de `c3` (por ejemplo seed3 entrega algo) aunque no lleguen al 50%, la entropía mueve el cuello de botella; si suben las inválidas o los choques, el coste de explorar más.
- **Limitaciones:** no se corre seed0 (el único éxito de c3), así que no se sabe si la entropía la perjudica; 4 semillas; mismo presupuesto y parada que c3, sin ablación de la parada; ≈ 105 minutos por run en paralelo.

| Run | Pasos | Semilla | `ent_coef` | Config |
|---|---:|---:|---:|---|
| m1-c4-seed1/2/3/4 | 1 802 240 | 1/2/3/4 | 0.01 | `m1_c4_entropia_seed{1,2,3,4}.yaml` |

Presupuesto real: (pendiente).
