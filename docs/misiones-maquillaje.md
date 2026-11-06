# Misiones de maquillaje — dev/angie

El visor local (`warehouse-rush view --no-open`) inicia pedidos automáticos de 1–3 SKUs temporales. «Generar pedido» crea y reserva otro pedido usando la semilla visible y el stock disponible; no repone inventario. Las seis estanterías conservan posición, geometría y colisiones. Seleccionar una etiqueta E01–E06 o el selector muestra los tres niveles y sus existencias. El checklist consume cantidades confirmadas por Python; no permite marcar manualmente las líneas.

## Modelo y operaciones

`inventory.py` contiene el catálogo provisional, separado de Three.js. Cada nivel tiene un SKU temporal de cinco unidades iniciales. `Inventory.reserve` valida todas las líneas bajo un bloqueo y reserva todo o rechaza todo. Un ID repetido con las mismas líneas devuelve la orden existente; con otro contenido se rechaza. `pick` exige cantidades exactas, descuenta una vez, y libera reserva. `deliver` confirma sin descontar. Repetir recogida/entrega no genera eventos ni movimientos adicionales. Cancelación/fallo libera lo no recogido y registra `pending_return` para carga no entregada. No hay reposición implícita ni eliminación del historial.

El generador devuelve directamente la orden reservada, con eventos GENERATED y RESERVED (o REJECTED para solicitudes directas sin stock). El estado IN_TRANSIT corresponde a carga en el robot; PICKING indica que quedan líneas después de una descarga; DELIVERED requiere todas las líneas entregadas. CANCELLED/FAILED/REJECTED cierran la orden. Eventos incluyen tiempo simulado; ID UUID independiente de la semilla, líneas reproducibles para igual stock y semilla.

`MakeupMissionEnv` añade estaciones de interacción sobre la cara norte de los racks y valida su accesibilidad con y sin bloqueo. No añade obstáculos ni permite atravesarlos. Interactuar exige adyacencia, orientación correcta y velocidad cero. La transferencia se realiza con una bandeja de rodillos sobre una plataforma telescópica; sólo puede recoger a la altura del nivel solicitado y baja antes de desplazarse. Capacidad predeterminada: 3 unidades; el generador limita cada línea a esa capacidad. El robot reúne varias líneas en los estantes antes de ir a despacho mientras quepan en su capacidad; si no caben, descarga y continúa con las líneas pendientes. `cargo_lines` contiene los SKUs y cantidades físicas transportadas. La recompensa de entrega se aplica una vez por interacción de descarga, aunque descargue varias líneas; no cambia la función ni sus coeficientes.

La invariancia comprobada es: stock inicial = stock físico restante + unidades recogidas acumuladas; reservas <= stock físico; entregadas <= recogidas <= solicitadas. La carga pendiente de devolución sigue fuera del estante. No se implementó una operación de devolución física.

El inventario se mantiene en la sesión local, incluido al generar pedidos sucesivos. Reiniciar el proceso inicia un almacén nuevo: no hay persistencia durable. El adaptador stateless conserva el libro por visitante en cookie comprimida y firmada; no representa stock compartido entre visitantes. Conserva cookies legacy. Al exceder su límite de 3800 caracteres falla explícitamente, sin truncar trazabilidad. Para producción con historial extenso o stock compartido hará falta almacenamiento servidor; no se incorpora una base externa en esta tarea.

## Compatibilidad — Lis / Naomi

`WarehouseRushEnv` y el entrenamiento no cambian. El modo legacy sigue disponible desmarcando «Pedidos de maquillaje»; la API usa `makeup: true` para solicitar el nuevo modo. PPO recibe únicamente el mismo vector de 22 valores y las mismas cinco acciones. En maquillaje cambian la distribución de objetivos a estanterías y el progreso de entregas se normaliza por líneas (1–3); no se añaden observaciones de SKU, nivel ni cantidad. Los coeficientes de recompensa y el presupuesto de batería/pasos son los existentes; el elevador añade consumo físico, penalizado con el mismo coeficiente de batería. No se entrenó ni reentrenó ningún modelo. Los checkpoints legacy pueden cargarse, pero no se garantiza su rendimiento en estos nuevos objetivos. La ruta BFS visual no elige acciones PPO.

Naomi puede sustituir el catálogo provisional cuando entregue productos y assets. No se añadieron imágenes comerciales ni se reconstruyeron sus modelos; las etiquetas y el panel de inventario son capas de interfaz.

## Ejecutar

```sh
cd /workspace/Warehouse-Rush
source .venv/bin/activate
npm --prefix web ci
npm --prefix web run build
warehouse-rush view --no-open
```

En otra terminal, con el visor ejecutándose:

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m pytest tests/test_inventory_missions.py -k full_lip -s
CHROMIUM_PATH=/usr/bin/chromium npm --prefix web test
```

El repositorio no define un script de lint. El build de Vite comprueba el bundle; pytest valida contratos legacy, inventario, bloqueo, idempotencia, cookies y misiones integrales. Los tests de navegación incluyen 24 combinaciones de semilla/bloqueo con presupuesto explícito de 300 de batería y 600 pasos para cubrir tres viajes sin alterar defaults. La prueba de aceptación Labios usa el presupuesto normal y capacidad explícita 4: inicial 5, reserva 4, recogida 4, entrega 4, final 1.

La escena usa el fondo azul oscuro original. En modo maquillaje se ocultan las estaciones legacy P1/P2 y sus paquetes; el despacho empieza vacío. Cada unidad temporal aparece sobre su nivel y desaparece únicamente cuando el inventario confirma su recogida. Los mismos SKUs se muestran sobre el robot durante el transporte y sobre la zona de despacho al entregar. No se usan cajas decorativas como inventario.


## Alcance vertical y decisiones de viaje

Se eligió un elevador telescópico con bandeja de rodillos en lugar de un brazo: los productos tienen ubicaciones fijas y no hay modelos de agarre ni pesos definitivos. El mecanismo añade alcance vertical, no una pinza universal. La transferencia horizontal sobre la bandeja sigue siendo una operación automática simplificada (el estante debe estar preparado para entregarla); no simula dedos, agarre ni empaquetado. Es una simulación logística, no una validación mecánica de hardware.

Las tres baldas de almacenamiento son las tres superiores de la geometría existente: alturas de transferencia 0.99, 1.79 y 2.60 m. La balda de base queda como soporte estructural. La plataforma viaja a 0.55 m; velocidad vertical 0.40 m por paso de 1 s; consumo 0.80 unidades de batería por metro vertical, tanto al subir como al bajar. La plataforma sólo inicia el ciclo con el robot detenido, adyacente y orientado hacia el estante. Se bloquean avance y giro durante subida, transferencia y bajada. INTERACTUAR inicia la elevación y, cuando alcanza la altura, confirma la recogida. No se descuenta stock antes. FRENAR mientras está lista permite abortar y bajar sin recoger. No se puede descargar con la plataforma levantada.

Cada ciclo registra LIFT_START, LIFT_READY, PICK, LIFT_LOWERING y LIFT_STOWED con tiempo simulado. `state.lift` incluye altura, destino vertical, fase, energía, movimientos bloqueados y número real de visitas a despacho. Se conserva al recargar mediante el adaptador firmado, incluso a mitad de elevación. La visualización interpola la altura confirmada sin adelantar recogidas.

El despachador de misiones ordena candidatos por distancia navegable más pasos de elevación, respetando capacidad. Antes de recoger estima desplazamiento al producto y a despacho, ciclos verticales, bajada pendiente, 12 pasos de margen para orientación/transferencia y reserva de 5 unidades de batería. Se reevalúa tras cada recogida. Si lleva carga y no cabe otro producto, vuelve por capacidad; si no queda margen estimado de batería/tiempo, vuelve con lo recogido. Si está vacío y no puede iniciar un viaje de ida y vuelta según ese presupuesto, termina con `insufficient_budget` y libera reservas; no repone batería mágicamente. No se ha implementado estación de carga. La estimación es conservadora y no garantiza retorno de una política aleatoria o PPO que se desvíe. No busca una solución global óptima al problema de rutas.

Estas decisiones del despachador y el enclavamiento del elevador son reglas explícitas del entorno, no decisiones aprendidas por PPO. La heurística espera con FRENAR durante subida/bajada; Random y PPO conservan sus acciones propias y se someten al mismo bloqueo físico. El entrenamiento sigue intacto y el vector legacy sigue teniendo 22 valores. Para Lis: el modo maquillaje ahora tiene tiempos de servicio, consumo extra e inhibición de movimiento mientras se eleva; altura/fase no están en el vector legacy, por lo que el modelo existente no observa todo ese estado. Un experimento PPO específico debe decidir si amplía observaciones y versiona el checkpoint; no se entrenó ni se modificó su entrenamiento aquí.
