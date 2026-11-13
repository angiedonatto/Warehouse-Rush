# Integración rosa en dev/naomi

Naomi autorizó integrar su commit `df7c28b` con `e4fea61` y subir el resultado a
`dev/naomi`, sin reemplazar el historial remoto ni publicar en producción.

## Qué se conserva

- Los 27 productos del PDF, sus modelos estilizados, miniaturas y GLB descargables.
- Catálogo con buscador, filtro por categoría y vista 3D orbitable.
- Interfaz y materiales rosas, conservando placas físicas y detalles en el lateral.
- Todas las funcionalidades de Angie: mapa v0.4, elevador con bloqueo de movimiento,
  capacidad/planificación, stock real, cuatro representaciones de existencias,
  cinta, empaque idempotente, cookies y compatibilidad con mapas anteriores.
- Los checkpoints y las observaciones, acciones y recompensas de Gymnasium.

## Identificadores y alcance del catálogo

El inventario operativo mantiene **18 SKU TMP**, sus alturas y asociaciones de
categoría/nivel. No se migran pedidos guardados a los **27 identificadores TRD**,
que se conservan como propuestas de producto y assets visuales del PDF.

`web/src/product-visuals.js` declara 12 asociaciones visuales compatibles por
categoría/subcategoría; para los seis niveles sin equivalente en el PDF se conserva
el marcador provisional. La asociación no cambia nombres comerciales del pedido,
no crea existencias y no repone stock. Los 27 modelos se pueden consultar y descargar
en el catálogo, incluso cuando no tienen asociación con un SKU operativo.

Los modelos asociados se usan en estante, robot, retrato y despacho, compartiendo
geometría instanciada. Se normalizan a la envolvente del marcador anterior y a su
plano de apoyo: las mismas alturas de transferencia siguen siendo válidas.
Incorporar los 27 productos como inventario definitivo requerirá una migración de
SKU coordinada; esta integración no la ejecuta implícitamente.

## Publicación

El commit debe contener el remoto existente y el commit visual original como
ancestros. Se sube sólo `dev/naomi`, sin force push y sin modificar `main` o
`dev/angie`. `git.deploymentEnabled.dev/naomi=false` evita desplegar automáticamente
esta rama mediante la integración Git de Vercel; otras ramas conservan su política.
No se ejecutan comandos de despliegue ni se modifican secretos.

Referencia de esa opción: https://vercel.com/docs/project-configuration/git-configuration

## Verificar y abrir

```sh
npm ci --prefix web
node web/scripts/check-product-assets.mjs
npm run build --prefix web
python -m pytest -q
python -m warehouse_rush.cli view --no-open
# En otra terminal, con el servidor activo:
npm --prefix web test
```

En Linux, añadir `CHROMIUM_PATH=/usr/bin/chromium` a las pruebas de navegador.
La prueba de aislamiento de visitantes se ejecuta aparte contra el adaptador
stateless local (`python -m warehouse_rush.cloud`) usando un único contexto con cookies.
El visor compartido y el stateless representan modelos de sesión diferentes.

En el Mac, abrir http://127.0.0.1:8080 después de iniciar el visor. El catálogo
está en «Explorar los 27 productos». Para probar mecanismos: «Pedidos de maquillaje»,
«Generar pedido», «Iniciar» y «Ver despacho».

## Validación de esta integración

- 162 pruebas Python aprobadas, incluidos contratos anteriores y navegación de cada SKU operativo.
- 12 casos distintos de navegador compartido aprobados; el de sesiones por visitante se omite en ese modo y pasó por separado en el adaptador stateless local.
- Catálogo, descarga de GLB, asociaciones y pivotes, control manual, móvil, elevador, stock y cinta/caja verificados.
- La primera ejecución concurrente de Playwright tuvo un error de escritura de trazas compartidas; el caso afectado pasó al repetirlo con una carpeta de salida aislada. No se retiró ninguna aserción funcional.
- Build Vite y comprobación de los 27 GLB/miniaturas aprobados. Permanecen advertencias de dependencias y tamaño del bundle, sin errores de construcción.
- Capturas históricas de `results/` conservadas; las evidencias nuevas quedaron fuera de los archivos versionados.
