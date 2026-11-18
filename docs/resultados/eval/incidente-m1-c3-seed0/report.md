# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `a007d66b70d5f6b96d2203cca90f65b9d70c4a82b424922c49486494bbbc29cb`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 0, 1802240 pasos efectivos (1800000 solicitados), 5980.36 s reales; entrenado con bloqueo=False. Modelo final: `models/m1-c3-seed0/model.zip`. SHA-256: `b6034b3396a676d8d9edd27c4229be239f8d0cf9b3ccd712bb0437c67d76b9a7`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| random | normal | 0% | -97.290 ± 6.818 | 400.0 | 36.4 | 96.12 | 15.3 | 199.6 | 0.0 |
| heuristic | normal | 100% | 115.858 ± 1.358 | 79.9 | 49.5 | 49.69 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 98% | 111.234 ± 28.043 | 93.0 | 51.9 | 52.80 | 0.0 | 7.1 | 2.9 |
| random | blocked | 0% | -96.824 ± 7.076 | 400.0 | 35.7 | 96.12 | 16.0 | 199.6 | 0.0 |
| heuristic | blocked | 100% | 119.981 ± 1.283 | 103.1 | 72.2 | 67.93 | 0.0 | 0.0 | 3.0 |
| ppo | blocked | 0% | -99.047 ± 49.888 | 382.7 | 30.2 | 85.97 | 21.6 | 220.1 | 0.0 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| random | 0.0 | 0.466 | 0.0 | -0.6 | 0.00 |
| heuristic | 0.0 | 4.123 | 23.2 | 22.7 | 18.24 |
| ppo | -98.0 | -210.281 | 289.7 | -21.8 | 33.17 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 11123 episodios, con 2040 éxitos. El retorno medio de los primeros 10 fue -35.323 y el de los últimos 10 fue 101.786. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **98%**, 2.98 recogidas medias, finales {'success': 49, 'time_limit': 1}, conteos de acciones 0–7: {'0': 2597, '1': 381, '2': 264, '3': 311, '4': 149, '5': 49, '6': 628, '7': 273}.
- En normal, el heurístico funciona mejor que PPO en tasa de éxito.
- PPO en blocked: éxito **0%**, 0.00 recogidas medias, finales {'battery_depleted': 5, 'time_limit': 45}, conteos de acciones 0–7: {'0': 2590, '1': 2754, '2': 2645, '3': 141, '4': 0, '5': 344, '6': 10663, '7': 0}.
- En blocked, el heurístico funciona mejor que PPO en tasa de éxito.
- El entrenamiento ejecutado no resolvió la misión. Las señales densas de distancia no garantizan descubrir la secuencia detenerse–orientarse–interactuar; ésta es una hipótesis de diagnóstico, no una causa demostrada. No se cambiaron las recompensas para mejorar la cifra.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
