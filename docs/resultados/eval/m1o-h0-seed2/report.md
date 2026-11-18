# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 3 pedido(s); 50 episodios por combinación. Semillas emparejadas 10000–10049. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `0bd1788a5daf4cd0857d62ef86ed48a4b2145ea6f2e050aa37eb901845e4bbca`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO (clonación de comportamiento): semilla 2, 0 pasos efectivos (0 solicitados), 593.28 s reales; entrenado con bloqueo=False. Modelo final: `models/m1o-h0-seed2/model.zip`. SHA-256: `a3f48db7029bf9f66ddb02881c550434545ea3407d8f90390df4faaf65abe0e9`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| heuristic | normal | 100% | 127.296 ± 2.723 | 71.3 | 43.6 | 44.46 | 0.0 | 0.0 | 3.0 |
| ppo | normal | 100% | 127.296 ± 2.723 | 71.3 | 43.6 | 44.46 | 0.0 | 0.0 | 3.0 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

- PPO en normal: éxito **100%**, 3.00 recogidas medias, finales {'success': 50}, conteos de acciones 0–7: {'0': 2182, '1': 191, '2': 257, '3': 186, '4': 150, '5': 50, '6': 275, '7': 275}.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 27 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
