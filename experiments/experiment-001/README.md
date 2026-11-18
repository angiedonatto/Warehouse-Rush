# Experimento 001 — Warehouse Rush

Primera integración ejecutada: ambiente Gymnasium v0.1, misiones de uno/dos
pedidos, baselines Random/BFS, PPO y visor Three.js v0.2.

Entrenamiento principal: un pedido, sin bloqueo, semilla 42, **20 000 pasos
efectivos**, CPU, 118.10 s. PPO obtuvo **0% de éxito** en los dos escenarios;
el heurístico obtuvo **100%**. El modelo final permanece frenando en BASE.
No se ajustaron las recompensas para aparentar éxito.

El archivo `ppo-orders1-seed42.zip` es el modelo final real (aprox. 170 KiB).
Este único snapshot pequeño se versiona explícitamente para reproducir la
inferencia desplegada. Los checkpoints y modelos posteriores continúan ignorados
en `artifacts/models/`. El visor utiliza el modelo local si existe; en un checkout
nuevo o despliegue utiliza este snapshot para la misión de un pedido.

- [Métricas por episodio y configuración](../../results/evaluation.json).
- [Informe](../../results/report.md).
- [Entrenamiento y metadatos](../../results/training/ppo_level1_seed42_20k/metadata.json).
- [Ficha del ambiente](../../docs/ambiente-v0.1.md).
- [Visor](../../docs/visor-v0.2.md).

`manifest.json` registra hashes del mapa y modelo, semillas y resultados. Los
datos son medidos, no generados como demostración.
