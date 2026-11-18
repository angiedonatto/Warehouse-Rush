# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `a007d66b70d5f6b96d2203cca90f65b9d70c4a82b424922c49486494bbbc29cb`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ppo | normal | 80% | 78.729 ± 71.818 | 151.1 | 47.6 | 64.86 | 0.0 | 51.5 | 2.4 |
| ppo | blocked | 74% | 63.516 ± 88.910 | 191.8 | 64.8 | 84.39 | 0.0 | 92.4 | 2.2 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|
| ppo | -6.0 | -15.213 | 40.7 | 17.1 | 19.53 |

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

- PPO en normal: éxito **80%**, 2.78 recogidas medias, finales {'battery_depleted': 1, 'success': 40, 'time_limit': 9}, conteos de acciones 0–7: {'0': 2382, '1': 823, '2': 711, '3': 168, '4': 2712, '5': 40, '6': 365, '7': 356}.
- PPO en blocked: éxito **74%**, 2.52 recogidas medias, finales {'battery_depleted': 2, 'success': 37, 'time_limit': 11}, conteos de acciones 0–7: {'0': 3238, '1': 429, '2': 184, '3': 150, '4': 4747, '5': 37, '6': 414, '7': 391}.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
