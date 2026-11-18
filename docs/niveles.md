# Niveles del enunciado (N1, N2, N3) y su correspondencia en el proyecto

El enunciado (sec. 06) pide tres niveles: **N1 base** (líneas base, primer modelo, evaluación), **N2 más decisiones**
(hipótesis, candidato, comparación) y **N3 exigente** (degradación, intervención, recuperación). Los perfiles viven en
`configs/niveles.yaml`; cada nivel tiene su suite fija en `configs/suites/`. Todos usan la misma misión (3 productos
aleatorios por episodio, bandeja a 3 alturas, entrega en la cinta de despacho), la misma observación `Box(27)` y las
mismas acciones `Discrete(8)` (`envs/CONTRATO.md`). Las recompensas de niveles o versiones distintas no se comparan:
se comparan éxito, choques, inválidas y pasos.

| Nivel del enunciado | Nivel del proyecto | Mapa y escenario | Suite fija | Qué demuestra |
|---|---|---|---|---|
| **N1 base** | `m1o` | mapa abierto sin muro interior (`configs/layout_v0.5.json`) | `suite-m1o-v1` (50 semillas, 10000–10049) | líneas base, primer modelo PPO, evaluación por episodio |
| **N2 más decisiones** | `m1` | mapa con muro interior y dos pasos (`configs/layout_v0.4.json`), paso (6,14) abierto | `suite-m1-v1` (mismas semillas) | hipótesis de recompensa y presupuesto, comparación de finalistas × semillas, selección y test final |
| **N3 exigente** | `m1b` | mismo mapa con el paso (6,14) **cerrado** (incidente) | `suite-m1b-v1` (mismas semillas, paso cerrado) | degradación medida, intervención, recuperación y vuelta atrás |

La familia `warehouse-v1` (`n1`, `n2`, `n3`: 1–2 pedidos, otra observación `Box(22)` y acciones `Discrete(5)`) se
conserva como historia (`docs/experimento-001.md`) y **no es compatible** con los modelos actuales.

## Líneas base por nivel (`warehouse-v10`, 50 episodios, recompensa base)

Corridas el 2026-11-15 con `pipelines.evaluate` (`docs/resultados/eval/lineas-base-<suite>/`). La heurística es una
referencia **privilegiada** (BFS sobre el mapa completo); PPO solo ve el vector observado.

| Nivel | Suite | Aleatoria: éxito | choques/ep | inválidas/ep | Heurística: éxito | pasos |
|---|---|---:|---:|---:|---:|---:|
| N1 `m1o` | `suite-m1o-v1` | 0% | 7.5 | 199.3 | 100% | 71.3 |
| N2 `m1` | `suite-m1-v1` | 0% | 15.3 | 199.6 | 100% | 79.9 |
| N3 `m1b` | `suite-m1b-v1` | 0% | 16.0 | 199.6 | 100% | 103.1 |

El muro sube el camino de la heurística un 12% (71.3 → 79.9 pasos) y el incidente otro 29% (79.9 → 103.1).

## N1: mapa abierto (`m1o`)

- **Primer modelo:** `m1o-c0-seed0` (`warehouse-v4`, 204 800 pasos): 0%. A 204 800 pasos ningún run del mapa abierto completa la misión.
- **Mejor PPO puro:** `m1o-e4l-seed0` (`warehouse-v5`, 606 208 pasos) **92%**, con las semillas 1 y 2 en 0%. `m1o-g1` (v7) 94/0/0%, rechazado.
- **Otras líneas:** `m1o-h0` (clonación de la heurística, v7) 100% en 3 semillas: referencia, no evidencia de RL. `m1o-h1` (PPO desde h0) 88/92/100%, rechazado por 6.7 choques/ep en la semilla 0.
- **Compatibilidad:** estos modelos se entrenaron con `warehouse-v4` a `v7`; se cargan solo con su versión de ambiente (manifiesto `environment_version` y `runtime_ref`).
- Detalle: `docs/experimentos.md` (secciones `m1o`).

## N2: mapa con muro (`m1`)

- **Hipótesis registradas (≥ 4):** recompensas `c0`–`c4`, `e4`, `j1`–`j3`, `p1`/`p2`, `q1`/`q2`, `r1`–`r7`, `s1`, cada una escrita antes de entrenar con su criterio (`configs/experiments/`, `docs/experimentos.md`). Las fallidas y rechazadas se conservan con su manifiesto y su etiqueta MLflow `estado`.
- **Comparación de finalistas × semillas:** `c3` (5 semillas) frente a `e4` (6 semillas), 1 802 240 pasos cada una (`docs/resultados/comparacion/finalistas-m1-v1/`). Éxito medio 20% frente a 30%; 1 de 5 frente a 2 de 6 semillas que funcionan; diferencia no distinguible con estas semillas → se elige `c3` por tener menos términos de recompensa.
- **Modelo `recomendado` del nivel:** `m1-c3-seed0`, elegido por regla declarada y validado una vez en `test-final-m1-v1`: **100/100, 0 choques, 0 inválidas, 90.6 pasos**.
- **Limitación medida:** el entrenamiento desde cero es poco fiable (3 de 15 semillas completan la misión a 1.8 M pasos).

## N3: incidente en el mapa con muro (`m1b`)

1. **Degradación medida:** con el paso (6,14) cerrado, `m1-c3-seed0` cae de 98% a **0%** (21.6 choques/ep); la heurística sigue en 100% (+23 pasos). El modelo había memorizado una ruta.
2. **Intervención:** `m1b-i1`, ajuste fino de `m1-c3-seed0` con el paso cerrado en la mitad de los ambientes, 3 semillas. Abierto 94/98/100%, cerrado 90/90/96%; **receta rechazada** por el criterio fijado antes (2.43 choques/ep de media con el paso cerrado, todos de la semilla 2).
3. **Recuperación:** por una selección declarada aparte, el mejor checkpoint de la semilla 1 (`m1b-i1-seed1-best`) pasa el test final reservado `test-final-m1b-v1`: **100/100 abierto y 100/100 cerrado, 0 choques, 0 inválidas** → `recomendado` para `m1b` y modelo de producción.
4. **Vuelta atrás (rollback):** `m1-c3-seed0` sigue registrado como `recomendado` para `m1`, con pesos en DVC (`models/m1-c3-seed0.dvc`). La prueba automática de rollback del catálogo y la API corresponde a R3 (pendiente).

## Curvas

Cada run nuevo escribe `docs/resultados/training/<run>/learning_curves.png` con dos paneles separados: entrenamiento
(política estocástica, con exploración) y evaluación periódica (política determinista, ambiente aparte, 5 episodios
cada 20 000 pasos). Para runs anteriores: `python -m pipelines.compare --curves <run> ...` (`docs/resultados/curvas/`).
