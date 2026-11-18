# Warehouse Rush: visor local 3D
Referencia principal: imagen adjunta por la usuaria, consola de simulación industrial azul noche, escena 3D isométrica grande a la izquierda, tarjetas de cámaras debajo, columna derecha de telemetría, leyenda y minimapa. Reproducir esta composición, no una landing page.

Colores: fondo #07131e, paneles #0c1d2a, bordes #3c5264, texto #f1f6fa, texto secundario #91a9bb, acento cian #42ddf5, amarillo entrega #ffbd23, verde base #5bea6e y rojo cierre #ff5555. Sans industrial (Arial/Inter), títulos compactos en mayúsculas; telemetría monoespaciada. Bordes finos, esquinas 6px, reflejos discretos, no gradientes decorativos grandes.

Escena Three.js real, suelo de hormigón cuadriculado, seis racks de acero gris con vigas naranja y cajas de cartón, paredes modulares, robot blanco/negro de cuatro ruedas con luces cian y paquete cuando corresponde. BASE verde, P1/P2 cian, D amarilla, bloqueo rojo rayado. Etiquetas flotantes ancladas al mundo. Mapa 17x13 desde JSON existente; nunca cambiar geometría para decoración.

Header WAREHOUSE RUSH y VISUALIZACIÓN 3D · SIMULACIÓN EN VIVO. Controles reproducir/pausar, un paso, reiniciar, agente (BFS, aleatorio, PPO, manual), pedidos 1/2, bloqueo y velocidad. Cámaras isométrica, primera persona, lateral, detalle estación; selección funcional. Sidebar ESTADO DEL ROBOT: posición, orientación, velocidad, batería, carga, objetivo, pasos y entregas reales. LEYENDA y VISTA SUPERIOR (MINIMAPA) sincronizado.

Sin métricas ficticias: el backend Python ejecuta el WarehouseRushEnv existente; la UI interpola visualmente entre estados discretos. Cualquier ruta BFS dibujada es referencia, nunca una predicción atribuida a PPO. El PPO disponible se frena en BASE y hay que mostrarlo honestamente. Controles accesibles, diseños responsive con sidebar debajo en móvil. Evitar React y servicios cloud; interfaz local en el mismo repositorio.
