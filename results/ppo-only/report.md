# Warehouse Rush v0.1 — evaluación real

## Configuración experimental

Estado: **completada**. Misión de 1 pedido(s); 20 episodios por combinación. Semillas emparejadas 10000–10019. PPO se evalúa con acciones deterministas; Random usa un generador independiente por semilla.

Mapa SHA-256: `5aefdbc89459bd5f72833e2cb37e64c17670e5db89e6b881d1756baeb18102a6`. Mismo JSON, acciones, recompensas, batería y límite de tiempo en todas las políticas. El bloqueo se fija al iniciar el episodio.

PPO: semilla 42, 20000 pasos efectivos (20000 solicitados), 118.10 s reales; entrenado con bloqueo=False. Modelo final: `artifacts/models/ppo_orders1_seed42.zip`. SHA-256: `ec31412af8828b90d4404db92bd2760cb1af13184782b5186a38b48b8ce95531`. Los hiperparámetros y versiones completos están en `evaluation.json`.

## Hechos medidos

| Política | Escenario | Éxito | Reward ± std | Pasos | Distancia m | Batería | Colisiones | Int. inválidas | Entregas |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| ppo | normal | 0% | -25.500 ± 0.000 | 250.0 | 0.0 | 25.00 | 0.0 | 0.0 | 0.0 |

La desviación estándar es poblacional (ddof=0). CSV contiene un registro por episodio; JSON conserva configuración, agregados, acciones y errores.

## Robustez: bloqueo menos normal

| Política | Δ éxito (pp) | Δ recompensa | Δ pasos | Δ distancia m | Δ batería |
|---|---:|---:|---:|---:|---:|

La recompensa total puede aumentar con bloqueo aunque aumenten pasos y consumo: el cierre eleva la distancia inicial al objetivo y, por tanto, el progreso total recompensado. Evaluar robustez con éxito, pasos, distancia y batería; una recompensa mayor entre escenarios no demuestra mayor eficiencia.

## Interpretación basada en datos

En entrenamiento se completaron 80 episodios, con 0 éxitos. El retorno medio de los primeros 10 fue -181.835 y el de los últimos 10 fue -25.735. Mejor retorno por sí solo no acredita haber aprendido a recoger y entregar.

- PPO en normal: éxito **0%**, 0.00 recogidas medias, finales {'time_limit': 20}, conteos de acciones 0–4: {'0': 0, '1': 0, '2': 0, '3': 5000, '4': 0}.
- La política final elige FRENAR en todos los pasos, permanece en BASE y evita penalizaciones mayores sin cumplir la misión. Es el comportamiento observado en esta evaluación determinista.
- El entrenamiento ejecutado no resolvió la misión. Las señales densas de distancia no garantizan descubrir la secuencia detenerse–orientarse–interactuar; ésta es una hipótesis de diagnóstico, no una causa demostrada. No se cambiaron las recompensas para mejorar la cifra.

## Limitaciones

- Una semilla de entrenamiento y un mapa fijo. Las 20 semillas no crean 20 mapas: la dinámica es determinista; heurística y PPO determinista repiten la trayectoria.
- La evaluación prueba perturbación fija al inicio, no cierres inesperados durante la navegación.
- BFS usa mapa y estado completos: es una referencia privilegiada, no una política aprendida. PPO sólo usa 22 observaciones normalizadas y no recibe rutas ni acciones de BFS.
- Cinemática discreta de 1 m y 1 s: no representa inercia, frenado industrial, ruido ni carga física.
- Siguientes experimentos: más pasos y semillas de entrenamiento, análisis de exploración y entrenamiento de dos pedidos. Comparar cualquier ajuste con esta configuración fija.
