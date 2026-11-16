# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `a007d66b70d5f6b96d2203cca90f65b9d70c4a82b424922c49486494bbbc29cb`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 2, 3604480 pasos efectivos (1800000 solicitados), 4663.25 s reales; entrenado con bloqueo=mixto. Modelo final: `models/m1b-i1-seed2/model.zip`. SHA-256: `692d03b71e53aaf69d148d1f2ab896abc23dbb384879883af9871c03735f3e94`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heuristic | normal | 100% | 115.858 ± 1.358 | 79.9 | 49.5 | 49.69 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 100% | 115.566 ± 1.414 | 84.0 | 51.8 | 51.91 | 0.0 | 0.0 | 3.0 |
| heuristic | blocked | 100% | 119.981 ± 1.283 | 103.1 | 72.2 | 67.93 | 0.0 | 0.0 | 3.0 |
| ppo | blocked | 96% | 107.482 ± 58.393 | 113.5 | 74.0 | 75.39 | 7.3 | 0.0 | 2.9 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| heuristic | 0.0 | 4.123 | 23.2 | 22.7 | 18.24 |
| ppo | -4.0 | -8.084 | 29.5 | 22.2 | 23.48 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 17635 episodios, con 17200 éxitos. El retorno medio de los primeros 10 fue 70.694 y el de los últimos 10 fue 117.068. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **100%**, 3.00 recogidas medias, finales {'success': 50}, conteos de acciones 0–7: {'0': 2592, '1': 392, '2': 278, '3': 186, '4': 150, '5': 50, '6': 275, '7': 275}.
- PPO en blocked: éxito **96%**, 2.96 recogidas medias, finales {'battery_depleted': 2, 'success': 48}, conteos de acciones 0–7: {'0': 4065, '1': 486, '2': 208, '3': 182, '4': 148, '5': 48, '6': 269, '7': 269}.
- En blocked, el heurístico funciona mejor que PPO en tasa de éxito.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
