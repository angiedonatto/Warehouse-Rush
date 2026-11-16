# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `a007d66b70d5f6b96d2203cca90f65b9d70c4a82b424922c49486494bbbc29cb`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 1, 3604480 pasos efectivos (1800000 solicitados), 4625.13 s reales; entrenado con bloqueo=mixto. Modelo final: `models/m1b-i1-seed1/model.zip`. SHA-256: `569b0fdd1539c8c2b0ff61766346da3287750288c02eaed66df52bb79e9b480a`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heuristic | normal | 100% | 115.858 ± 1.358 | 79.9 | 49.5 | 49.69 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 98% | 112.282 ± 19.473 | 95.5 | 51.0 | 52.31 | 0.0 | 0.0 | 2.9 |
| heuristic | blocked | 100% | 119.981 ± 1.283 | 103.1 | 72.2 | 67.93 | 0.0 | 0.0 | 3.0 |
| ppo | blocked | 90% | 105.584 ± 42.456 | 136.7 | 71.3 | 70.40 | 0.0 | 0.0 | 2.7 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.0 | 4.123 | 23.2 | 22.7 | 18.24 |
| ppo | -8.0 | -6.698 | 41.2 | 20.3 | 18.09 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 18018 episodios, con 17712 éxitos. El retorno medio de los primeros 10 fue 98.792 y el de los últimos 10 fue 117.569. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **98%**, 2.96 recogidas medias, finales {'success': 49, 'time_limit': 1}, conteos de acciones 0–7: {'0': 2548, '1': 363, '2': 257, '3': 865, '4': 148, '5': 49, '6': 273, '7': 273}.
- En normal, el heurístico funciona mejor que PPO en tasa de éxito.
- PPO en blocked: éxito **90%**, 2.80 recogidas medias, finales {'success': 45, 'time_limit': 5}, conteos de acciones 0–7: {'0': 3564, '1': 449, '2': 179, '3': 1939, '4': 140, '5': 45, '6': 260, '7': 260}.
- En blocked, el heurístico funciona mejor que PPO en tasa de éxito.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
