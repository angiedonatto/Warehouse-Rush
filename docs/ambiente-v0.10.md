# Warehouse Rush — ficha del ambiente v0.10 (`warehouse-v10`)

Cambios respecto de [ambiente-v0.9.md](ambiente-v0.9.md): un parámetro nuevo de recompensa, `potential_nav` (≥ 0, por defecto 0.40 = idéntico a v9, verificado por prueba): el peso de la parte de **navegación** dentro de φ. Con 0 la navegación se quita y φ se renormaliza. Observación `Box(27)`, acciones `Discrete(8)`, mapas, presupuesto y pedidos no cambian. Contrato: [`envs/CONTRATO.md`](../envs/CONTRATO.md). `env/warehouse-v9` conserva el código anterior.

## Por qué
Los 10 runs con potencial completo (p1, p2, q1, q2) no llegaron nunca a la celda de interacción; el control `m1-c1`/`m1-c2` mostró que el código v9 y la parada de estancamiento no rompen la línea base (`progress` 0.3 llega al estante en 2 de 3 semillas), así que el fallo es del potencial. Para aislar si lo que falla es su parte de navegación hay que poder quitarla y dejar el resto de etapas encima de `progress`.

## Cambio
`φ = (w_stow·stow + w_nav·nav + w_face·face + w_tray·tray) / (w_stow + w_nav + w_face + w_tray)`, con `w_stow` 0.10, `w_face` 0.20, `w_tray` 0.30 y `w_nav` = `potential_nav` (0.40 por defecto: los pesos suman 1 y φ es la de v9). Con `potential_nav` = 0 los pesos suman 0.60 y φ ∈ [0,1] queda como: bandeja guardada 1/6, mirar la estación 1/3, altura de la bandeja 1/2. Φ = (K + φ)/(2n) y el reward `W(γΦ' − Φ)` no cambian; la invarianza del shaping basado en potencial se conserva con cualquier φ función del estado.

## Medición previa (mapa con muro, 8 semillas, retorno descontado γ = 0.99, recompensa de m1-c1: invalid −0.2, collision −1, `progress` 0.3; potencial 30.0 con `potential_nav` 0)
| Conducta | sin potencial (c1) | con etapas (s1) |
|---|---:|---:|
| quieto en la base | −10.0 | −10.8 |
| ir, mirar el estante y quedarse | −6.6 | −7.3 |
| recoger el 1.º y quedarse | 1.7 | 0.9 |
| pedido completo | 59.9 | 72.1 |
El orden no cambia (invarianza): sin zona de evitación nueva; `progress` ya vuelve rentable ir y mirar frente a quedarse en la base.

## Límites conocidos
- Los pesos 0.10/0.20/0.30 siguen sin ajustarse con resultados.
- Con `progress` y potencial a la vez, la parte de navegación depende solo de `progress`, que no es potencial (tiene el sesgo habitual: no se conserva la política óptima en teoría); el potencial solo cubre las etapas.

## Pruebas
`tests/test_reward_config.py` (sección v10): valor por defecto 0.40 con retorno idéntico a v9 (ambos mapas), signo validado y, con 0, Φ inicial = (1/6)/(2n), constante mientras se navega y 1 al terminar con éxito.
