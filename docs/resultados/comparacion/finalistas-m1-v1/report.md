# Comparación de finalistas `finalistas-m1-v1`

Suite `suite-m1-v1` (escenario normal), modelo final de cada run, PPO determinista. Cada semilla de entrenamiento es una unidad; el IC 95% es bootstrap de la media entre semillas.

## Por receta

| Receta | Semillas | Éxito medio ± sd | IC 95% | Semillas ≥ 50% | Choques/ep | Inválidas/ep | Pasos c/u | Minutos totales |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| c3 | 5 | 20% ± 44 | 0%–59% | 1/5 | 0.90 | 12.6 | 1 802 240 | 523.3 |
| e4 | 6 | 30% ± 47 | 0%–67% | 2/6 | 0.00 | 31.4 | 1 802 240 | 519.6 |
| c4 (referencia) | 4 | 0% ± 0 | 0%–0% | 0/4 | 0.00 | 1.9 | 1 802 240 | 355.4 |

## Por semilla

| Receta | Run | Éxito | Choques/ep | Inválidas/ep | Recogidas/ep | Entregas/ep | Pasos de los éxitos | Motivo de fin | Minutos |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| c3 | m1-c3-seed0 | 98% | 0.00 | 7.1 | 2.98 | 2.94 | 86.8 | success 49, time_limit 1 | 99.7 |
| c3 | m1-c3-seed1 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 104.3 |
| c3 | m1-c3-seed2 | 0% | 4.48 | 55.7 | 0.00 | 0.00 | — | battery_depleted 1, time_limit 49 | 104.2 |
| c3 | m1-c3-seed3 | 0% | 0.00 | 0.0 | 2.66 | 0.00 | — | time_limit 50 | 110.3 |
| c3 | m1-c3-seed4 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 104.8 |
| e4 | m1-e4x-seed0 | 0% | 0.00 | 117.9 | 0.00 | 0.00 | — | time_limit 50 | 74.9 |
| e4 | m1-e4x-seed1 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 74.8 |
| e4 | m1-e4x-seed2 | 80% | 0.00 | 63.8 | 2.68 | 2.40 | 91.8 | battery_depleted 2, success 40, time_limit 8 | 80.1 |
| e4 | m1-e4y-seed3 | 100% | 0.00 | 6.6 | 3.00 | 3.00 | 94.2 | success 50 | 103.0 |
| e4 | m1-e4y-seed4 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 94.1 |
| e4 | m1-e4y-seed5 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 92.7 |
| c4 | m1-c4-seed1 | 0% | 0.00 | 7.0 | 0.44 | 0.00 | — | battery_depleted 3, time_limit 47 | 87.5 |
| c4 | m1-c4-seed2 | 0% | 0.00 | 0.0 | 3.00 | 0.00 | — | time_limit 50 | 92.4 |
| c4 | m1-c4-seed3 | 0% | 0.00 | 0.0 | 0.00 | 0.00 | — | time_limit 50 | 87.1 |
| c4 | m1-c4-seed4 | 0% | 0.00 | 0.6 | 0.86 | 0.00 | — | time_limit 50 | 88.4 |

## Líneas base en la misma suite

| Política | Éxito | Choques/ep | Inválidas/ep | Pasos de los éxitos |
|---|---:|---:|---:|---:|
| random | 0% | 15.34 | 199.6 | — |
| heuristic | 100% | 0.00 | 0.0 | 79.9 |

## Decisión (regla pre-registrada)

- **Seleccionada: `c3`** — diferencia de 1 semilla(s) que alcanzan el umbral (<= 1): no distinguible; desempate por menos términos de recompensa ({'c3': 2, 'e4': 4}).
- Distinguible con estas semillas: no.

Curvas de entrenamiento (estocástica) y de evaluación (determinista) por run: `curvas/`.
