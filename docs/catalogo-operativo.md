# Catálogo operativo Trendy 27 · v1

Distribución aprobada por Naomi tras consultar a Angie. El JSON canónico es
`configs/products.json`; Python y Three.js leen la misma definición.

- Stock inicial fijo de 5 a 10 unidades por SKU, 202 en total. Es una cantidad de simulación.
- Cada kit cuenta como una unidad completa, sin multiplicar sus componentes.
- E01: Rostro abajo, Labios en medio, Ojos/Cejas arriba. E03-L3 queda libre.
- Se mantienen mapa, alturas (0.99 / 1.79 / 2.60 m), elevador, capacidad, batería,
  acciones/observaciones y recompensas. No se entrena PPO ni se modifican checkpoints.
- Los pedidos reservan y recogen SKU TRD; las cuatro representaciones visuales
  (estante, robot, retrato y caja) comparten la misma identidad y cantidades.
- Cada referencia tiene su espacio dentro del nivel. La geometría se escala para
  evitar superposiciones y se apoya en la altura física que usa el elevador.

| SKU | Producto | Subcategoría | Estante/nivel | Stock inicial | Unidad |
|---|---|---|---|---:|---|
| TRD-01-10 | Base | Rostro | E01-L1 | 7 | unidad |
| TRD-01-11 | Corrector | Rostro | E01-L1 | 8 | unidad |
| TRD-01-12 | Polvos compactos | Rostro | E01-L1 | 9 | unidad |
| TRD-01-04 | Kit x8 Labiales | Labios | E01-L2 | 5 | kit |
| TRD-01-05 | Kit x6 delineadores | Labios | E01-L2 | 7 | kit |
| TRD-01-06 | Gloss | Labios | E01-L2 | 10 | unidad |
| TRD-01-01 | Lápiz retráctil | Cejas | E01-L3 | 8 | unidad |
| TRD-01-02 | Fijador de cejas | Cejas | E01-L3 | 6 | unidad |
| TRD-01-03 | Kit depilador de cejas | Cejas | E01-L3 | 5 | kit |
| TRD-01-07 | Delineador de ojos | Ojos | E01-L3 | 9 | unidad |
| TRD-01-08 | Kit Pestañina + fortalecedor | Ojos | E01-L3 | 5 | kit |
| TRD-01-09 | Paleta de sombras | Ojos | E01-L3 | 6 | unidad |
| TRD-02-01 | Crema | Corporal | E02-L1 | 8 | unidad |
| TRD-02-02 | Exfoliante | Corporal | E02-L1 | 6 | unidad |
| TRD-02-03 | Splash | Corporal | E02-L2 | 7 | unidad |
| TRD-02-04 | Mascarilla | Facial | E02-L3 | 10 | unidad |
| TRD-03-01 | Brocha polvos | Brochas individuales | E03-L1 | 8 | unidad |
| TRD-03-02 | Esponja | Esponjas | E03-L2 | 10 | unidad |
| TRD-04-02 | Cosmetiquera viajera | Cosmetiqueras | E04-L1 | 6 | unidad |
| TRD-04-01 | Tarjetero | Bolsos y monederos | E04-L2 | 7 | unidad |
| TRD-04-03 | Pegante de pestañas | Pestañas | E04-L3 | 9 | unidad |
| TRD-05-02 | Kit Peinillas | Accesorios para el cabello | E05-L1 | 7 | kit |
| TRD-05-01 | Pinzas | Accesorios para el cabello | E05-L2 | 10 | unidad |
| TRD-05-03 | Caimán mariposa | Accesorios para el cabello | E05-L3 | 5 | unidad |
| TRD-06-01 | Rubor Lotso | Toy Story 5 | E06-L1 | 8 | unidad |
| TRD-06-02 | Cadena Stitch | Stitch | E06-L2 | 6 | unidad |
| TRD-06-03 | Brillo Ansiedad | Intensamente 2 | E06-L3 | 10 | unidad |

## Compatibilidad y sesiones

`CATALOG` es TRD-27. `LEGACY_CATALOG` conserva los 18 TMP y sus metadatos anteriores.
Cada libro de inventario utiliza un único catálogo, seleccionado por sus identificadores;
no se aceptan mezclas ni equivalencias implícitas entre TMP y TRD.

Al cargar una cookie antigua, el pedido, reservas, carga, mapa, alturas y mecanismo
continúan con su inventario TMP. Su siguiente pedido tampoco lo repone ni lo renombra;
la interfaz indica «Catálogo anterior conservado». Para usar TRD, iniciar una sesión
nueva/privada; en el visor local, reiniciar el proceso crea un libro nuevo. Esta
separación deliberada evita perder trazabilidad o atribuir stock antiguo a productos
distintos. No se borra ni se recorta el historial para hacer caber una cookie.

La cookie sigue firmada y limitada a 3800 caracteres. El inventario continúa siendo
por sesión, sin persistencia durable. Mantener cantidades históricas entre reinicios
o visitantes requeriría almacenamiento, fuera de este cambio.

## Verificación

- Recogida y entrega de cada uno de los 27 SKU, con y sin bloqueo, usando su stock inicial.
- Reserva, idempotencia, conservación de stock, capacidad, batería y alturas.
- Sesión TMP recargada durante elevación, sin convertir identificadores ni reponer stock.
- Modelos apoyados y sin superposición entre unidades de una misma balda.
- Pedidos con nombres, checklist, cinta, caja, recarga y vista móvil.

Para reproducir una demostración de tres líneas y tres unidades, usar semilla **24**
y política heurística. Las semillas 42 y 10000 también se verifican con el presupuesto
normal; no son resultados de entrenamiento PPO.

La publicación se mantiene sólo en `dev/naomi`; el despliegue automático de esa rama
permanece desactivado. No se cambia producción.


## Resultados de la implementación

- 185 casos Python distintos aprobados por grupos: catálogo, 54 misiones individuales,
  transacciones, mecanismo, mapas, API, compatibilidad y contratos Gymnasium anteriores.
- 12 pruebas de navegador compartido aprobadas. El caso de aislamiento por visitante
  se omite en ese servidor y se aprobó por separado en el adaptador stateless local.
- Comprobación de 27 GLB/miniaturas y 27 geometrías operativas, con soporte de 12
  asociaciones visuales antiguas. Build Vite aprobado.
- La prueba visual verifica apoyo y ausencia de superposiciones entre unidades de
  las baldas, incluyendo las seis referencias de E01-L3.
- Sin cambios a pesos PPO, recompensas, observaciones, acciones ni resultados históricos.
