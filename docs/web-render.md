# Web conectada a Render

Implementación en `dev/naomi`, según [contrato de Miguel, sección 9](https://github.com/angiedonatto/Warehouse-Rush/blob/dev/miguel-visor/docs/api-contrato.md#9-compatibilidad-con-el-visor-de-vercel-api).
La compatibilidad `/api/*` está en `dev/miguel-visor`; este cambio modifica la web,
sin copiar ni sustituir la implementación del backend de Miguel.

## Configuración

La variable pública de Vite es:

```env
VITE_API_BASE_URL=https://warehouse-rush-api.onrender.com
```

Debe tener origen HTTPS sin barra final, ruta ni credenciales. Vite incorpora el valor
durante la compilación. Lis o quien administre Vercel debe configurarla en los entornos
de destino y volver a compilar/publicar cuando el equipo decida hacerlo. No basta con
cambiar una variable después de compilar. Esta entrega no publica producción;
`vercel.json` mantiene desactivados los despliegues automáticos de `dev/naomi`.

Para verla en el Mac, desde la raíz:

```bash
npm ci --prefix web
VITE_API_BASE_URL=https://warehouse-rush-api.onrender.com npm run dev --prefix web
```

Abrir la dirección que imprima Vite. La API debe permitir ese origen mediante CORS.
Miguel ya permite `https://warehouse-rush-experiment-001.vercel.app` y
`https://warehouse-rush-psi.vercel.app`; cualquier dominio de preview nuevo u origen
local debe coordinarse con él. No desactivar la seguridad del navegador para probar.

Para una API local compatible de la rama de Miguel, iniciar su servidor con:

```bash
CORS_ORIGINS=http://127.0.0.1:5173 python -m uvicorn api._app:app --host 127.0.0.1 --port 7861 --workers 1
VITE_API_BASE_URL=http://127.0.0.1:7861 npm run dev --prefix web
```

Ejecutar cada proceso en su terminal. El primer comando requiere la implementación
`/api/*` de Miguel; el antiguo servidor `pipelines.cli view` no reemplaza esa API.
Para producción se exige HTTPS; HTTP local se admite en desarrollo o pruebas.

## Sesión y comportamiento

- Visor, catálogo y monitoreo comparten un cliente que usa la misma base de API.
  Los archivos estáticos (catálogos, GLB y curvas) siguen siendo de la web.
- `sessionStorage['warehouse-sesion:<origen API>']` guarda `X-Sesion`, obtenido de
  la cabecera de respuesta o del campo `sesion_id`. Cada petición lo envía con
  `credentials: 'omit'`. No se usan cookies para la partida.
- El primer acceso solicita estado y después el mapa de esa misma sesión.
- Una sesión desconocida (`sesion_no_encontrada`) detiene la reproducción y muestra
  un aviso persistente. Se inicia una misión nueva conservando modelo, semilla y
  ajustes. El avance y el inventario acumulado perdidos no se recuperan; vuelve el
  stock inicial. No se repite la última acción ni se reanuda sola la reproducción.
- Un reset que reemplaza una sesión también muestra el aviso. Un reset normal con
  una sesión vigente sigue las reglas de conservación de stock del servidor.
- Después de 2,5 segundos sin primera respuesta aparece «Despertando el servidor…»;
  en peticiones posteriores lentas aparece «Esperando respuesta del servidor…».
  El límite de espera es 90 segundos. Un error o timeout no reintenta automáticamente
  una petición que podría haber cambiado el estado.
- Se elimina el PPO genérico. Se utilizan identificadores concretos publicados por
  la API. Se conserva el modo histórico P1/P2 para revisar el escenario anterior.
- El control manual ofrece las ocho acciones del ambiente: avanzar, girar a cada
  lado, frenar, recoger, entregar, subir y bajar el elevador.

## Diagnóstico y evidencia

«Evaluar 10 episodios · diagnóstico no certificado» llama `/api/evaluate` y muestra
la nota del servidor. No sustituye las suites certificadas de `/evaluaciones`, ni
modifica las evaluaciones históricas, el test final, los pesos o el registro.
La posibilidad de ejecutar cada ficha depende de `evaluable_con_api`, no de estar
publicada como modelo activo.

Las pruebas del navegador usan una API compatible en otro origen y comparten su
identificador explícitamente, sin cookies. Para una compilación local de pruebas:

```bash
VITE_API_BASE_URL=http://127.0.0.1:7861 npm run build --prefix web -- --mode e2e
python -m http.server 8086 --bind 127.0.0.1 --directory web/dist
```

Permitir `http://127.0.0.1:8086` en el CORS del backend de prueba y, en otra terminal:

```bash
WAREHOUSE_TEST_URL=http://127.0.0.1:8086 WAREHOUSE_TEST_API_URL=http://127.0.0.1:7861 npm --prefix web test
```

Se verifican sesión tras recarga, aislamiento, pérdida de sesión sin repetir pasos,
aviso de espera, catálogo de productos, assets, elevador, empaque, cámaras,
modelos identificados, diagnóstico, comparación y monitoreo. Las pruebas de
reinicio simulan la respuesta de sesión perdida; no reinician el Render compartido.

## Verificación del 19 de noviembre de 2026

- Código de partida: `main` en `57e9ff7`, incorporado por avance directo en
  `dev/naomi`; se conserva el historial previo de Naomi y sus 27 productos.
- Backend de prueba aislado: `dev/miguel-visor` en `6a4a740`. Sus pruebas
  `tests/test_visor.py` y `tests/test_api.py`: **75 aprobadas y 1 omitida**.
  La omitida compara NumPy con SB3 y requiere pesos de DVC no descargados.
- Assets: 27 GLB y miniaturas válidos, con asociaciones anteriores y fallback.
- Web: **28 pruebas aprobadas** (26 en la revisión completa y 2 en repetición
  dirigida después de corregir comprobaciones antiguas del catálogo y el empaque).
  Incluye 9 pruebas del cliente y 4 de recuperación, sesión y espera. El catálogo
  prueba la descarga del GLB desde la web; el empaque observa una unidad que aún
  está en la cinta, sin suponer que la primera sigue allí durante toda la animación.
- Compilaciones de Vite para pruebas y para producción con la dirección HTTPS de
  Render: aprobadas. Se conserva el aviso existente sobre el tamaño del bundle.
- Render real, usando este cliente desde Node con TLS verificado: lectura de
  `/version`, creación de partida, mapa, paso con la misma sesión, carga de
  `m1b-i1-seed1-best` y diagnóstico de un episodio con `certificado:false`.
  La API informó `warehouse-v10` y commit
  `8b49d63313792fa5d677e902a624f5aeb85c8ee4`.
- Preflight CORS real aprobado para ambos dominios de Vercel indicados arriba,
  incluyendo `Content-Type` y `X-Sesion`.

La prueba completa del navegador usa la API local aislada. El navegador de este
entorno rechazó el certificado del proxy al intentar Render; no se desactivó TLS.
La comprobación real con Node y los preflight no equivalen a haber publicado ni
probado esta nueva interfaz en Vercel. La validación final del dominio publicado
corresponde al despliegue que realice el equipo.
