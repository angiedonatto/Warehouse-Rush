# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `a007d66b70d5f6b96d2203cca90f65b9d70c4a82b424922c49486494bbbc29cb`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 0, 3604480 pasos efectivos (1800000 solicitados), 4676.59 s reales; entrenado con bloqueo=mixto. Modelo final: `models/m1b-i1-seed0/model.zip`. SHA-256: `0ef17ec7a0c8d6508db7eaff9f08ed493088fdfc63c5b135eb2cbbef05c615c1`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heuristic | normal | 100% | 115.858 ± 1.358 | 79.9 | 49.5 | 49.69 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 94% | 107.542 ± 31.402 | 94.4 | 48.8 | 58.70 | 0.0 | 0.0 | 2.8 |
| heuristic | blocked | 100% | 119.981 ± 1.283 | 103.1 | 72.2 | 67.93 | 0.0 | 0.0 | 3.0 |
| ppo | blocked | 90% | 105.960 ± 40.928 | 122.9 | 69.9 | 80.31 | 0.0 | 0.0 | 2.7 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.0 | 4.123 | 23.2 | 22.7 | 18.24 |
| ppo | -4.0 | -1.582 | 28.5 | 21.2 | 21.61 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 17670 episodios, con 17316 éxitos. El retorno medio de los primeros 10 fue 115.593 y el de los últimos 10 fue 115.890. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **94%**, 2.86 recogidas medias, finales {'battery_depleted': 3, 'success': 47}, conteos de acciones 0–7: {'0': 2439, '1': 421, '2': 281, '3': 179, '4': 143, '5': 47, '6': 606, '7': 605}.
- En normal, el heurístico funciona mejor que PPO en tasa de éxito.
- PPO en blocked: éxito **90%**, 2.74 recogidas medias, finales {'battery_depleted': 5, 'success': 45}, conteos de acciones 0–7: {'0': 3497, '1': 451, '2': 182, '3': 174, '4': 137, '5': 45, '6': 832, '7': 826}.
- En blocked, el heurístico funciona mejor que PPO en tasa de éxito.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
