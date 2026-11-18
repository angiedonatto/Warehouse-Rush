# Warehouse Rush — ficha del ambiente v0.5 (`warehouse-v5`)

Cambios respecto de [ambiente-v0.4.md](ambiente-v0.4.md): la recompensa gana **dos términos** (ambos por defecto 0, es decir, v5 sin ellos se comporta como v4).
Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos de 3 productos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md).
La etiqueta `env/warehouse-v4` conserva el código de los barridos de distancia por estado.

## Por qué
El diagnóstico de `m1o-d2`/`d3` (ver `docs/experimentos.md`) midió que el término de distancia por estado de v4 hacía **peor** recoger el primer producto que quedarse junto al estante:
tras la recogida el siguiente objetivo queda a ≈ 10 celdas Manhattan y la bandeja arriba bloquea el movimiento, así que la penalización por paso salta. Además, en el estado clave
(parado, mirando, bandeja abajo) todas las acciones costaban casi lo mismo y nada favorecía SUBIR.

## Término 1: diferencia de distancia Manhattan (`manhattan_progress`, ≥ 0)
`c_man · (M_antes − M_después)`, con M = |dx| + |dy| (Manhattan, sin obstáculos) al **mismo** objetivo antes y después del paso. Acercarse paga, alejarse cobra, una ida y vuelta suma cero y,
al usar el mismo objetivo en ambos extremos, **no hay salto cuando el objetivo cambia** (la recogida no cambia la posición, luego aporta 0). Es el análogo en Manhattan del progreso por BFS que ya existe
(0.3 por celda), por lo que con `c_man = 0.3` el empuje total hacia el objetivo se duplica en el mapa abierto, donde ambas distancias casi coinciden.

## Término 2: penalización por altura distinta en la celda de interacción (`height_mismatch`, ≤ 0)
Si el robot está en una celda de interacción del objetivo (distancia BFS 0 a la estación, es decir, a una celda desde la que podría interactuar) y la bandeja no está en la posición que el objetivo exige, cada paso cuesta
`c_alt · |posición de la bandeja − posición exigida|`. La posición exigida es la de la balda del producto en curso (1–3) o 0 en el despacho. Como depende de la diferencia de puestos, cada SUBIR correcto reduce
la penalización y se anula al llegar a la altura. No exige estar mirando al estante.

## Límites conocidos (declarados antes de entrenar)
- El término de altura solo actúa en la celda de interacción del objetivo **actual**. Tras cargar, el objetivo pasa al siguiente estante y el robot ya no está en una celda de interacción de él, así que **no empuja a BAJAR
  la bandeja**; solo la diferencia Manhattan paga una vez que el robot pueda moverse de nuevo (para lo cual primero debe bajarla). Es el punto donde se atascó el control `m1o-c0`.
- Riesgo de evitación: si estar en la celda de interacción con la altura equivocada cuesta, una política podría quedarse una celda más allá y no pagar nada. Se mide en los runs.
- Retornos solo comparables entre runs con los mismos coeficientes; entre conjuntos distintos se compara éxito, pasos, batería, choques e inválidas.

## Pruebas
`tests/test_reward_config.py`: términos apagados por defecto; signos validados; ida y vuelta suma cero; sin salto al cambiar de objetivo; penalización de altura solo en la celda de interacción y proporcional
a los puestos de diferencia (se anula al subir); en el despacho con la bandeja arriba; subir y bajar en el estante nunca es rentable; los configs `e1`–`e4` cambian solo los términos nuevos.
