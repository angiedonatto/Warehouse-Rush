# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 2 pedido(s); 20 episodios por combinación. Semillas emparejadas 10000–10019. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `5aefdbc89459bd5f72833e2cb37e64c17670e5db89e6b881d1756baeb18102a6`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| random | normal | 0% | -255.751 ± 49.240 | 250.0 | 23.1 | 74.54 | 26.3 | 49.2 | 0.0 |
| heuristic | normal | 100% | 136.032 ± 0.000 | 75.0 | 48.0 | 43.40 | 0.0 | 0.0 | 2.0 |
| random | blocked | 0% | -269.831 ± 36.631 | 250.0 | 20.2 | 74.54 | 29.2 | 49.3 | 0.0 |
| heuristic | blocked | 100% | 138.976 ± 0.000 | 91.0 | 64.0 | 56.20 | 0.0 | 0.0 | 2.0 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| random | 0.0 | -14.080 | 0.0 | -2.9 | 0.00 |
| heuristic | 0.0 | 2.944 | 16.0 | 16.0 | 12.80 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos


## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 22 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
