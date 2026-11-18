# Warehouse Rush — ficha del ambiente v0.4 (`warehouse-v4`)

Cambios respecto de [ambiente-v0.3.md](ambiente-v0.3.md): (1) la recompensa tiene un **término de distancia Manhattan** al objetivo y (2) existe un **mapa abierto**.
Observación `Box(27)`, acciones `Discrete(8)`, mecánica de la bandeja, presupuesto (batería 180, 400 pasos) y pedidos de 3 productos aleatorios no cambian.
Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md).

## Por qué se sube la versión
Agregar un término a la función de recompensa es un cambio de recompensa, y la regla de versionado del proyecto exige subir la versión. Con el coeficiente por defecto
(`distance = 0.0`) el comportamiento es idéntico a v3; la etiqueta `env/warehouse-v3` sigue apuntando al código que produjo los barridos anteriores.

## Término de distancia
`distance_term = c_dist · (|x − x_obj| + |y − y_obj|)` por paso, con `c_dist ≤ 0`. La distancia es **Manhattan** (suma de diferencias absolutas, sin euclidiana ni camino real) entre el robot
después del paso y la estación del objetivo anterior al paso (estante `E0x` o `DELIVERY`). Cuanto más lejos del destino, mayor la penalización; acercarse la reduce. Es un castigo por estado,
distinto del término de progreso (que premia la reducción de distancia por BFS). Aparece en `info["reward_components"]["distance"]` y se valida `≤ 0`, de modo que nunca sea rentable.
Efecto esperado: quedarse quieto lejos del objetivo deja de ser la política más barata; llegar al estante y quedarse cerca cuesta mucho menos.

## Mapa abierto `configs/layout_v0.5.json`
Misma bodega 25 × 19 de v0.4 (seis estanterías, base (3,16), cinta de despacho (22,16)–(23,16), celda de acceso (21,16)) **sin el muro interior en y = 14** y sin sus dos pasos
(uno cerrable). Se mantiene el perímetro y las estanterías, que son las estaciones. `Layout.validate_routes` solo exige que el bloqueo altere una ruta cuando existe un paso cerrable.
Medido con la heurística BFS (20 semillas, 3 productos): 100% de éxito en ≈ 71 pasos (con el muro: ≈ 80). El nivel `m1o` (`configs/niveles.yaml`) y las suites `dev-m1o-v1` / `suite-m1o-v1`
usan este mapa; las semillas son las mismas que en `m1`, con otro mapa, por eso son suites nuevas (las suites son inmutables).

## Simplificaciones
La distancia Manhattan ignora estanterías: en el mapa abierto aproxima bien el camino, en el mapa con muro puede subestimarlo. El término no tiene en cuenta el nivel de la bandeja. El mapa abierto
quita la incidencia de pasillo cerrado (N3), por lo que no sirve para medir degradación.
