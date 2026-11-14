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
