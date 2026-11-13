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
| m1-c0-seed0 | m1 | (pendiente) | (pendiente) | en curso |
