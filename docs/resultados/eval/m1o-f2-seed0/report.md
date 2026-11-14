# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `0bd1788a5daf4cd0857d62ef86ed48a4b2145ea6f2e050aa37eb901845e4bbca`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 0, 606208 pasos efectivos (600000 solicitados), 2100.79 s reales; entrenado con bloqueo=False. Modelo final: `models/m1o-f2-seed0/model.zip`. SHA-256: `e7b4d327e13b52ee602d8011f7b9559a0ed8b9278ed8f8bcb3dc12bb486478e2`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heuristic | normal | 100% | 120.164 ± 2.192 | 71.3 | 43.6 | 44.46 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 44% | 24.491 ± 85.275 | 251.4 | 37.2 | 73.06 | 0.0 | 27.4 | 1.3 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 1813 episodios, con 479 éxitos. El retorno medio de los primeros 10 fue -127.732 y el de los últimos 10 fue 109.810. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **44%**, 2.70 recogidas medias, finales {'battery_depleted': 2, 'success': 22, 'time_limit': 26}, conteos de acciones 0–7: {'0': 2220, '1': 432, '2': 2974, '3': 4616, '4': 527, '5': 22, '6': 416, '7': 1362}.
- En normal, el heurístico funciona mejor que PPO en tasa de éxito.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
