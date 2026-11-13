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
| m1o-c0-seed0 | m1o | (pendiente) | (pendiente) | en curso |
| m1o-d1-seed0 | m1o | (pendiente) | (pendiente) | en curso |
| m1o-d2-seed0 | m1o | (pendiente) | (pendiente) | en curso |
| m1o-d3-seed0 | m1o | (pendiente) | (pendiente) | en curso |
