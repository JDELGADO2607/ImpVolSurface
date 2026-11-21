# Auditoría cuantitativa independiente de R3 — ImpVolSurface

**Commit auditado** `3d81ff18cae3a9f8dc74c174015fed17031a8da8`  
**Referencia R2** `855eb1cfbd300ddf488bd02d348883f5eac756b8`  
**Rama auditada** `fix/quant-audit-2026-11` · **PR principal** [#1](https://github.com/JDELGADO2607/ImpVolSurface/pull/1)  
**Estado** `AUDIT_COMPLETE_AWAITING_HUMAN_REVIEW`

Gemini identificó el SHA congelado y GitHub confirmó el mismo HEAD. La auditoría usó tres extracciones Git del commit, una de lectura y dos desechables para el pipeline y pytest. El diff introduce 35 cambios de archivo. Afecta principalmente a la superficie, contratos de datos, estrategias, HAR-RV, capital del stress, pruebas y documentación. La implementación de tipos de interés conserva la curva de R2. [Diff de R3](https://github.com/JDELGADO2607/ImpVolSurface/compare/855eb1cfbd300ddf488bd02d348883f5eac756b8...3d81ff18cae3a9f8dc74c174015fed17031a8da8) · [Informe de Gemini](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/docs/audits/GEMINI_REMEDIATION_R3.md) · [Auditoría R2](https://github.com/JDELGADO2607/ImpVolSurface/blob/209d309066fffd7c3ae505d0c3a0904b266098da/docs/audits/CODEX_AUDIT_855eb1c.md)

## Resumen ejecutivo

**Dictamen provisional · Mantener el PR #1 en revisión.** Los dos contraejemplos de calls de R2 y el put de 14,75 USD mejoran en los puntos repetidos. Se encontraron mariposas negativas nuevas en zonas que el evaluador marca productivas, incluida una transición que incorpora el corte de tres días. El motor estricto acepta esa transición, la frontera de soporte se calcula por interpolación y el ajuste de varianza todavía depende de alas extrapoladas. El supuesto holdout 2D usa otra ruta de calibración y evaluación. La tabla y la documentación deben corregirse antes de afirmar capacidad predictiva del evaluador de producción.

| BLOCKER | HIGH | MEDIUM | LOW |
| ---: | ---: | ---: | ---: |
| 1 | 4 | 4 | 2 |

El recuento agrupa problemas relacionados. Incluye defectos nuevos y defectos persistentes de R2 según la matriz.

## Matriz de R2

| ID | Estado | Resultado de la repetición independiente |
| --- | --- | --- |
| B1 | `PARTIALLY_RESOLVED` | Las mallas de 27,5 y 612 días vuelven a tener curvatura positiva. En estricto, 612 días queda excluido. Nuevas mariposas negativas sobreviven al refinamiento en puntos que la interfaz autoriza. |
| H1 | `UNRESOLVED` | 430d/K=5 queda en IV 57,03724%, frente a 55,69978% cruda. 31d/K=10 queda en 56,19164%, frente a 50,99585%. Ambos desplazamientos se gobiernan por alas fuera del soporte del corte anterior. |
| H2 | `PARTIALLY_RESOLVED` | LEAPS se recalibra filtrando K=3 y se marca en cuarentena. Estricto rechaza >430d. La API por defecto y la comparación de modelos siguen consumiendo sus valores. |
| H3 | `UNRESOLVED` | La exclusión de call y put existe. El holdout duplica una ruta con malla y umbrales distintos a producción, no reproduce sus predicciones y vuelve a publicar su CSV como LOO por corte. |
| H4 | `PARTIALLY_RESOLVED` | Los contrafactuales del straddle ya desactivan su exportación. Las pruebas de cartera y stress todavía ejecutan funciones que escriben en rutas oficiales. Ver control de hashes. |
| H5 | `RESOLVED` | En K=14,75 el put EDP sube de 2,50691 a 2,53646 USD. CRR confirma el signo a 1.000, 2.000 y 4.000 pasos. Es el cierre del contraejemplo específico. |
| M1 | `PARTIALLY_RESOLVED` | Diagnóstico de tres días con dos strikes deja la convexidad en NaN y marca cuarentena. El mismo corte sigue activo en consultas y se etiqueta productivo en K=12,5. |
| M2 | `PARTIALLY_RESOLVED` | Se rechazan columnas explícitamente requeridas y figuras ausentes. Pasan nulos parciales, columnas solo listadas como finitas, resultados anteriores y una figura de un byte. |
| M3 | `RESOLVED` | Con 120 observaciones y ventana de 55 se omiten fechas prematuras y el pronóstico queda invariante al modificar datos posteriores al origen. La historia aún más corta exhibe un fallo de interfaz nuevo. |
| L1 | `RESOLVED` | Las dos cifras del escenario Base largo de R2 ya concilian. El informe nuevo contiene cifras inconsistentes en otras tablas. |
| L2 | `PARTIALLY_RESOLVED` | Reparado el salto artificial de varianza en t≈0⁺. Persisten quiebres de pendiente, inconsistencia algebraica en vecindades de nodos y entrada de plazo negativo. |

## Hallazgos demostrados

### B-R3-1 · BLOCKER · Nuevas mariposas negativas por alas recortadas

La metodología aplica un desplazamiento escalar de nivel por tenor, recorta k en cada corte y mezcla linealmente varianza total entre nodos. Si el orden en w se cumple en ambos extremos, la interpolación lineal preserva orden temporal para ese k. Una combinación convexa de **precios normalizados** convexos preservaría la convexidad transversal en la coordenada de strike forward común. Combinar w no permite trasladar esa prueba a los precios, porque la aplicación de Black–Scholes es no lineal. Incluso una w afín en k puede producir densidad negativa. Con w(0)=0,02, w′=0,4 y w″=0, la expresión g(0)=1−(0,4²/4)(1/0,02+1/4)=−1,01. Se necesita además la condición de ala de la formulación aplicable. La implementación agrega un máximo local en interpolación y usa clipping con derivada discontinua. [Gatheral y Jacquier, §2 y §5.3](https://www.ma.imperial.ac.uk/~ajacquie/index_files/GJ%20-%20NoArbSVI.pdf) · [Evaluación de cortes](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L555) · [Interpolación final](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L688)

- **Replicación R2.** Calls a 27,5d en K∈[10,15] con 121/241/481 puntos tienen mínimos de curvatura +0,06227/+0,06131/+0,06083. A 612d en K∈[5,30] salen +0,00519/+0,00512/+0,00508 en consulta exploratoria. No queda punto productivo a 612d. En esas mismas mallas irregulares de 227 puntos se conserva el signo.
- **Búsqueda nueva.** Con grillas irregulares en intervalos declarados de soporte y evaluaciones a 0%, 37,1%, 71,3% y 100% de los tramos, 151/409/1.001 strikes por corte revelan 13/28/34 tripletes estrictamente bajo −0,0001 y marcados productivos. Los recuentos incluyen bordes repetidos de intervalos. No representan probabilidades ni frecuencias de mercado.
- **Dentro del horizonte documentado.** Una búsqueda separada de 10 a 430 días dio 38 y 63 tripletes negativos con mallas irregulares de 301 y 911 strikes. A 290,476d, los strikes 9,6643924, 9,6836856 y 9,7029760 dan curvatura −2,63682 y prima de mariposa ponderada −0,00049068 USD por acción. Los tres se aceptan en modo estricto y quedan marcados productivos. A 21,991d aparece otro mínimo de −2,60521. Los mismos tripletes reproducen concavidad en puts con EDP y CRR a 1.000, 2.000 y 4.000 pasos. A 290,476d, EDP y CRR 4.000 dan −2,61846 y −2,71802. La propia malla publicada también marca simultáneamente `is_production_ready=True` e `is_convex=False` a 17d/K=10,5, con curvatura −0,01140.
- **Causa localizada.** A 5,597d, en K*=11,648738261 USD se cruza el recorte del corte de 3d, k_min−0,03. Para K*+h·(−1,0,1,15), con h=0,005, las pendientes de call caen de −0,821940 a −0,834220. La curvatura es −2,28463 USD por USD². Al bajar h de 0,02 a 0,001 pasa de −0,33643 a −12,67348. EDP y CRR de 4.000 pasos también detectan pérdida de convexidad de put alrededor del corte, con −2,64544 y −1,48611 a h=0,005. El signo en calls se prueba con CDF independiente y no depende del motor de puts. Los tres strikes se aceptan bajo `strict` y se marcan productivos, pese a encontrarse por debajo del mínimo temporal de 10 días declarado.
- **Controles favorables.** En el núcleo exacto de 31 y 59 días, K=11–15, 901 puntos por corte dan curvaturas mínimas de call +0,06196 y +0,07168. En la grilla irregular de 1.001 puntos, las calls respetaron monotonía y cotas BS de valor intrínseco descontado y spot. No se infiere una garantía en todo el continuo.

**Aceptación.** Acotar un dominio coherente que excluya contribuciones no aptas, o reconstruir precios con restricciones de strike y de calendario simultáneas, comprobar la factibilidad y usar un interpolador que preserve esas restricciones. Una mezcla afín de curvas convexas y ordenadas de calls normalizadas puede ser más simple que imponer un ajuste de w, con un costo en suavidad temporal. Verificar también puts americanos con ejercicio coherente, vecinos de puntos de recorte, sensibilidad de curvatura y efecto sobre el ajuste.

### H-R3-1 · HIGH · Las alas extrapoladas todavía desplazan cortes observados

Recalculé, en los mismos 50 puntos que usa la calibración, el máximo de `(t/u)^0.22*w_prev − w_raw`. En 31d el máximo se obtiene en k=0,212245, fuera del soporte del corte de 24d [−0,212142; 0,193324], y aumenta w de toda la sonrisa en 0,004730035. A 430d, el máximo se obtiene en k=−0,519938, por fuera del intervalo del corte de 395d [−0,482179; 0,434112], con alza 0,017763185. Los resultados en K=10 y 5, respectivamente, conservan calidad soportada y el campo dominante apunta al tenor consultado. Este campo identifica el corte evaluado, pero no identifica la fuente del desplazamiento.

**Aceptación.** Limitar restricciones a pares de puntos con soporte conjunto o etiquetar la contribución extrapolada y excluirla del dominio certificado. Exportar tenor y coordenada que fijaron cada desplazamiento. Evaluar cardinalidad y coste numérico antes de sustituir un cambio escalar por una optimización más compleja. [Armonización](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L479)

### H-R3-2 · HIGH · La cuarentena difiere entre metadatos, API y consumidores

`strict` rechaza 612 y 794 días. El argumento por defecto es `allow`, y la evaluación solo usa el techo temporal para rechazar en modo estricto. A 3d/K=12,5 los dos modos devuelven IV 49,54683% y `is_production_ready=True`. La calibración utiliza ese mismo corte para el tramo siguiente. Un consumidor con el valor por defecto recibe también las IV LEAPS. La comparación de modelos aplica el evaluador al total de 201 contratos y cubre 17 filas de enero de 2029. El metadato de producción no comprueba restricciones de precios ni la pertenencia de las dos fuentes al soporte común. La documentación afirma modo estricto predeterminado y horizonte desde 10 días.

**Aceptación.** Unificar dominio, rutas y diagnósticos en una decisión aplicada por defecto a cada consumidor. Validar explícitamente plazo mínimo, soporte de ambos extremos y cuarentena. Separar la comparación productiva de la exploratoria conservando coberturas y motivos de rechazo. [Política](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L588) · [Consumidor](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/model_comparison.py#L64) · [Dominio declarado](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/docs/SURFACE_RELEASE_STATUS.md#L24)

### H-R3-3 · HIGH · El holdout nunca evalúa el producto 2D

Quité el grupo completo (vencimiento, strike) de la tabla y construí `VolatilitySurface(train)`. La predicción publicada para el put 31d/K=10 es 58,121% y 0,0936 USD. Con el evaluador final de esa calibración queda 55,41969% y 0,07840 USD, marcado extrapolado. En 31d/K=12, el holdout publicado asigna 50,950% y 0,9197/0,5492 USD (C/P), frente a 51,03319% y 0,92090/0,55032 con la reconstrucción final, ambos soportados. A 59d/K=13, coinciden aproximadamente (47,119% publicado frente a 47,11821% reconstruido). A 794d/K=3, las dos IV pasan de 69,219% en el CSV a 57,42466% en reevaluación exploratoria y quedan rechazadas por horizonte en política estricta. Los resultados muestran divergencia según el fold, no ausencia de exclusión del strike hermano.

El holdout clona la calibración completa, opera en la intersección con 30 puntos y usa un umbral mínimo de cuatro strikes. Producción usa 50 puntos sobre soporte extendido y otro criterio SVI. El holdout predice directamente desde el corte y no usa el recorte, la cuarentena ni la función pública. A 794d tampoco aplica la regla de filtrado de producción al entrenar folds de otros strikes. Las dos tablas de validación son idénticas. No hay una validación de interpolación temporal que retire tenores completos.

**Cobertura nominal:** 197/201 = 98,01%. Cuatro contratos del tenor de 3d se omiten por número de strikes. El CSV incluye 17 contratos LEAPS y no registra rechazos por política. Sus 115 calls tienen MAE/RMSE de precio 0,05122/0,07615 USD e IV 3,22317/5,19426 pp. Sus 82 puts dan 0,06349/0,08493 USD e IV 4,32799/5,61437 pp. Excluir solo LEAPS dejaría 180/201 = 89,55% del total como techo preliminar, antes de examinar los folds de frontera. El MAE publicado no es una estimación de precisión del producto apto para uso.

**Aceptación.** Recalibrar mediante la misma función de producción con cada conjunto de entrenamiento. Capturar razones de rechazo, tipo, vencimiento y moneyness. Comparar errores sobre el conjunto común y reportar cobertura en paralelo. Añadir una evaluación de vencimientos retenidos completos. [Holdout](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L951)

### H-R3-4 · HIGH · Las tasas atribuidas al 17-nov conservan entradas de R2

El diff de `market_data.py` cambia solo encabezado documental. La fila oficial de CMT del 17-nov muestra, para 1M/2M/3M/4M/6M/1Y, 4,09/4,26/4,33/4,32/4,41/4,60%. El código tiene 4,10/4,27/4,34/4,35/4,43/4,62%, desvíos de 1–3 pb. Varios coinciden con otros días, lo que prueba ausencia de concordancia con la fecha declarada. El historial de precios del repo contiene cierre 12,329999923706055 el 17-nov, compatible con spot 12,33. Sin evidencia del minuto exacto de disponibilidad de la curva oficial, no puede certificarse una reconstrucción estrictamente ex ante al cierre. El Tesoro obtiene cotizaciones alrededor de 15:30 ET y documenta la disponibilidad habitual hacia 18:00 ET. [CMT oficial de noviembre](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve) · [Metodología del Tesoro](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology) · [Entradas del código](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/market_data.py#L21)

Para t≤0,5 se aplica capitalización simple, y para t>0,5 conversión de frecuencia semiannual sobre un **yield par**. Se interpola r linealmente en t y se extrapola r plana. Las identidades D=exp(−rt) y F=S exp((r−q)t) sí se cumplen. Convertir frecuencia no reconstruye una curva cero con cupones y distintos factores de descuento. Al reconstruir bonos par nocionales con cupones semestrales de las propias entradas, obtengo precio 100,01122 a 2 años y 100,26233 a 10 años para nominal 100. A 1 año, con el cupón oficial 4,60%, obtengo 99,98276. Esto no pretende reproducir los bonos cotizados línea a línea. No se aportaron cotizaciones de esos instrumentos ni datos intradía de publicación. En valoración americana, el uso de r(T) constante por contrato es una aproximación adicional a una dinámica común con curva temporal.

**Aceptación.** Fijar procedencia y timestamp de las tasas, guardar la fila consumida y distinguir aproximación de bootstrap. Si se reconstruye de cupones, repricing explícito, convenciones y regla de interpolación sobre D o forwards. Regenerar los resultados dependientes desde insumos versionados. Cuantificar el impacto separadamente del nuevo ajuste de superficie.

### M-R3-1 · MEDIUM · Los contratos de datos permiten éxito con salidas antiguas o corruptas

Quité `our_iv_decimal` y el contrato lo rechazó. Una fila nula de la misma columna pasó. Borrar `strike` de `options_audit.csv` también pasó, porque figura solo en `finite_cols` y el validador omite columnas ausentes. Sustituí las siete etapas por funciones vacías en un directorio temporal con tablas publicadas. El pipeline devolvió 0. Con una figura requerida reducida a un byte también devolvió 0. Borrarla sí lanzó `FileNotFoundError`. `model_comparison_detailed.csv` figura en el contrato, pero no se incluye en los artefactos que comprueba la etapa 4.

**Aceptación.** Directorio por ejecución, publicación atómica o verificación de procedencia, esquema con nulabilidad explícita y decodificación de PNG. Ejecutar casos negativos sobre pasos que no escriben, escrituras parciales, datos obsoletos, valores nulos y salida requerida omitida. [Validación](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/run_all.py#L132) · [Validación de figuras](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/run_all.py#L312)

### M-R3-2 · MEDIUM · La suite sigue escribiendo artefactos de cartera y stress

Las llamadas de straddle con forecasts contrafactuales ahora pasan `export_artifacts=False`. En cambio `tests/test_portfolio_and_stress.py` llama a las funciones sin directorio temporal. Esas funciones exportan cartera, tablas de estrés y figuras. La prueba unitaria de hashes de Gemini cubre dos archivos del straddle y puede omitir las aserciones si faltan los archivos. La ejecución independiente dejó 45/45 archivos con hashes idénticos, pero las marcas de tiempo detectaron siete reescrituras. Son la cartera, las dos tablas y figuras de stress y las dos tablas de holdout/LOO. La identidad de hashes tras una reescritura determinista no implica ausencia de escritura. El uso de rutas oficiales expone resultados parciales a consumidores concurrentes. [Pruebas de cartera y stress](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/tests/test_portfolio_and_stress.py#L23) · [Prueba específica del straddle](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/tests/test_no_lookahead.py#L220)

**Aceptación.** Usar `tmp_path` en todos los tests que escriben, conservar hashes y verificar ausencia de escrituras a rutas oficiales durante toda la suite. El camino `analyze_strategy_1_straddle(forecast_vol_pct=None,export_artifacts=False)` todavía delega en `run_forecast_pipeline()` con exportación predeterminada. Incluirlo en el control.

### M-R3-3 · MEDIUM · El capital y la revaloración consumen carteras diferentes

La fórmula dinámica reproduce 5.370,82 USD. En el camino real de stress, inyecté cambios a la cartera retornada por `build_hypothetical_portfolio`. Subir en un centavo la prima del corto de cinco contratos eleva el capital en 5 USD. Agregar un contrato corto de put lo eleva 276,60 USD. Sustituir el corto de K=14 por el de K=13 y su prima observada eleva el capital en 130 USD. A pesar de esos cambios, el motor ejecuta P&L con `PORTFOLIO_LEGS`, y conserva el símbolo previo y los mismos P&L. Este control mantiene la cobertura fija para aislar el efecto.

El algoritmo suma prima larga, prima corta más 20% del spot por unidad corta, y 50% del nocional de acciones. Es una aproximación académica. El tratamiento regulatorio de opciones cortas depende, entre otros aspectos, de OTM, mínimos, compensaciones y configuración de cuenta. El motor usa primas y cantidades iniciales y su capital es constante entre escenarios. [Capital y bucle de P&L](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/stress_testing.py#L151) · [FINRA 4210](https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210)

**Aceptación.** Una cartera única con contratos, cantidades, multiplicadores y cobertura debe alimentar ambos pasos. Conciliar capital y P&L tras los tres cambios. Identificar el denominador como aproximación salvo que se implemente y valide un régimen concreto.

### M-R3-4 · MEDIUM · Diagnóstico per tenor y malla publican garantías fuera de lo comprobado

Los diagnósticos transversales y RMSE se calculan antes de aplicar el desplazamiento de calendario, pero la tabla muestra los parámetros desplazados. El campo `is_calendar_arbitrage_free` del CSV compara w a **strike USD fijo** y por lo tanto cambia k entre tenores. La prueba europea emplea k forward fijo en las hipótesis descritas. El campo llamado `is_extrapolated_tau` recibe el indicador global que incluye strikes. La columna de puts comprueba solo puntos discretos y la malla etiqueta su primera observación como aprobada sin pareja de comparación. El informe de Gemini cita 82 tests y 0,0434 USD de MAE de holdout. Se recolectaron 62 y el archivo contiene 0,05633 USD. La tabla documental de IV a 31/59 días tampoco coincide con los diez valores de producción repetidos abajo.

**Aceptación.** Recalcular diagnósticos después del ajuste, separar estados raw y final, y reportar comparación de precios y varianza con sus coordenadas correctas. Generar cifras y conteos de tests desde resultados efectivamente publicados. [Columnas de diagnóstico](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L509) · [Exportación](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L901)

### L-R3-1 · LOW · Identidad IV–varianza rota al aproximarse a nodos

A 31d y k=0, la pendiente de w antes y después del nodo con paso 2×10⁻⁶ años es 0,114647 y 0,459934. La afirmación C¹ es falsa con interpolación lineal. En el nodo +5×10⁻⁷ años la rama de proximidad divide por el plazo del nodo y devuelve w−tσ²=−1,27460×10⁻⁷. En torno a 3 y 794 días hay también diferencias de pendientes. A t=−1/365 y K=12 se obtiene w≈−0,000812208 aun con modo estricto, una regresión de validación de entrada. Se hallaron 258 decrementos al comparar nodos contra una consulta 1,1×10⁻⁶ años anterior en 801 k∈[−1,20;1,08]; ninguno tenía ambos extremos marcados productivos. El máximo local en la interpolación no se usa en el nodo exacto. Eso permite saltos cuando los extremos no están ordenados.

**Aceptación.** Rechazar t<0, usar el mismo t para w e IV y unificar ramas de nodos. Documentar los empalmes C⁰ si se elige interpolación lineal y testar ambos lados del umbral de proximidad. [Evaluador](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/surface.py#L637)

### L-R3-2 · LOW · HAR-RV falla con una muestra sin orígenes elegibles

Con la semilla 3 y 120 sesiones, el test R2 ya no filtra información. El primer origen comparable se desplaza hasta que hay 50 etiquetas maduras. Multiplicar los retornos y sus varianzas por 10 después del primer origen retornado induce cambio 0,0 pp en su pronóstico. Con las primeras 90 filas y ventana de 55, el bucle no produce predicciones y el resumen lanza `KeyError: 'pred_vol_hist'`. La guarda de causalidad es correcta. Falta un contrato de entrada para el caso vacío.

**Aceptación.** Diagnosticar explícitamente el mínimo de historia, ventana y observaciones maduras, o devolver resultado vacío documentado en un canal consumible. Probar ambos casos sin volver a introducir un mínimo que exceda el corte causal. [Guarda causal](https://github.com/JDELGADO2607/ImpVolSurface/blob/3d81ff18cae3a9f8dc74c174015fed17031a8da8/src/forecasts.py#L83)

## Comparación cuantitativa

| Métrica | R2 | R3 |
| --- | ---: | ---: |
| Contratos, vencimientos de cadena | 201, 16 | 201, 16 |
| Máximo residuo de reconstrucción IV | 0,000022118 USD | 0,000022118 USD |
| Tasa continua 31d/59d | 4,09822% / 4,25173% | 4,09822% / 4,25173% |
| Forward 31d/59d | 12,37299 / 12,41503 USD | 12,37299 / 12,41503 USD |
| MAE/RMSE M4 in-sample en 201 contratos | 0,0291 / 0,0484 USD | 0,0578 / 0,0817 USD |
| MAE/RMSE M3 plano in-sample | 0,0482 / 0,0816 USD | 0,0482 / 0,0816 USD |
| MAE/RMSE del estimador propio de holdout, muestra común n=197 | 0,03887 / 0,06491 USD | 0,05633 / 0,07992 USD |
| MAE/RMSE de IV en esas tablas | 2,37791 / 4,12023 pp | 3,68304 / 5,37312 pp |
| Hedge acciones | −357 | −348 |
| Delta agregado desde tabla | 0,11 | 0,11 |
| Gamma agregado desde tabla | 125,01 | 102,36 |
| Vega agregado por pp desde tabla | 7,95 USD | 7,31 USD |
| Theta diario agregado desde tabla | −5,46 USD | −5,66 USD |
| Capital académico de stress | 5.435,31 USD | 5.370,82 USD |
| HAR-RV anualizado y señal | 72,97%, largo | 72,97%, largo |
| P&L straddle Base, 0% / +25% | −107,14 / +130,21 USD | −107,14 / +130,21 USD |

En la crisis severa sticky moneyness, el P&L revalorado cae 496,56→454,19 USD y la aproximación Taylor 757,71→658,44 USD. El residuo pasa de −261,15 a −204,25 USD. El calendar Base sin shock cambia de 51,69 a 96,24 USD; con spot −15%, de −110,59 a −97,92 USD. Estos cambios se atribuyen conjuntamente a superficie y cobertura; la curva es idéntica. En parámetros SVI, a sube de 0,01451 a 0,01924 en 31d y de 0,00423 a 0,01144 en 59d. Los demás parámetros publicados de esos dos cortes coinciden.

El holdout R2 diagnostica un corte y R3 un algoritmo híbrido. Las filas observadas son las mismas. Comparar predicciones identifica deterioro para esos estimadores en esa muestra, sin validar la nueva metodología 2D. El resultado M4 abarca LEAPS y no equivale a desempeño sobre el dominio restringido. El capital baja 9 USD por corregir las dos primas y 55,485 USD por el cambio de nueve acciones, salvo redondeo.

| K USD | R2 31d IV % | R3 31d IV % | R2 59d IV % | R3 59d IV % |
| ---: | ---: | ---: | ---: | ---: |
| 11 | 47,8540 | 53,3567 | 44,3905 | 49,1540 |
| 12 | 45,2680 | 51,0502 | 42,6616 | 47,5984 |
| 13 | 44,2711 | 50,1682 | 42,1258 | 47,1187 |
| 14 | 45,1176 | 50,9168 | 42,6138 | 47,5555 |
| 15 | 46,5213 | 52,1647 | 43,8057 | 48,6265 |

En los 201 contratos coinciden exactamente último precio, madurez, log-forward moneyness, IV invertida y residuo. Los cambios de IV de superficie provienen conjuntamente del ajuste, armonización y soporte, no de una nueva curva de tasas ni de una nueva inversión. El motor EDP no cambió en el diff. La prueba CRR de H5 mostró un error de nivel frente a EDP de 0,00042–0,00046 USD en el refinamiento a 4.000 pasos, pequeño frente al cambio de precio de 0,0296 USD entre plazos. En pares de strike soportados de una búsqueda de 81 puntos entre 9,5 y 19,5 USD y tenores exactos más cuatro intermedios, no se observaron decrementos de put mayores que 0,0003 con CRR de 480 pasos. La búsqueda no demuestra monotonía global ni justifica el exponente 0,22.

## Dictámenes por módulo y límites

- **A. Datos y tasas — Retener para corrección.** Spot y fecha coinciden con el historial del repositorio. Falta trazabilidad intradía completa. El máximo timestamp de transacción en la tabla auditada de 575 filas es 17-nov 15:59:55 NY. Las primas son últimos trades asíncronos y no sustentan evidencia de arbitraje ejecutable. Distinguir q=0 como supuesto del modelo y 100 como multiplicador contractual. El 17-nov de la curva no concilia con la fuente indicada.
- **B. Superficie — Bloqueada para certificación.** El núcleo de 31/59 días se puede mostrar como corte ilustrativo con sus métricas verificadas. La política y convexidad de producción deben corregirse antes de liberar un dominio continuo.
- **C. Valoración y griegas — Uso puntual contrastado.** El EDP y CRR concuerdan en signo e impacto para el put de control. La convexidad de superficie falla en algunos puntos, lo que compromete sensibilidades derivadas de curvatura de precios. Una griega a IV fija tiene otro objeto y no certifica estabilidad de la superficie completa.
- **D. Stress y estrategias — Uso académico condicionado.** El straddle conserva señal y P&L en el escenario observado. El horizonte HAR de 21 sesiones desde el cierre del 17-nov llega al 17-dic, mientras la expiración de 31 días es el 18-dic, 22 sesiones posteriores contando el día terminal y excluyendo Thanksgiving. La comparación es aproximada. El calendar usa IV de origen para tenor remanente. Es una hipótesis de roll-down, sin una prueba histórica de ejecución. [Calendario NYSE](https://www.nyse.com/trade/hours-calendars)
- **E. Pipeline — Reproducibilidad puntual evaluada; control de procedencia insuficiente.** Véanse los resultados de ejecución y hashes.
- **F. PR completo — Mantener en revisión.** Priorizar dominio y convexidad, luego holdout de producción, fuente de tasas y separación de artefactos.

**Clasificación de constantes.** Spot, fecha, curva y primas son datos que requieren origen. Multiplicador, hora New York y ACT/365 son convenciones. Pasos EDP, tolerancias Brent, floors y mallas son parámetros numéricos. El exponente 0,22 y los umbrales de calibración o señal son hiperparámetros. Cantidades contractuales de cartera, regímenes de coste, shocks y la volatilidad plana del comparador (44%) son supuestos hipotéticos o explícitos benchmarks. El vega de selección a 45% es una referencia de condicionamiento. Las tasas y spot se comparten desde `market_data.py`. Se repite q=0 en distintas interfaces y `forecasts.py` mantiene su propia fecha literal de valoración, de modo que la centralización es parcial. Los valores coinciden para la instantánea probada. Un resultado derivado como MAE, tamaño de suite, IV publicada o capital debe conciliar con el cálculo. Las discrepancias demostradas se detallan arriba.

**Pendiente de verificación.** Procedencia de cotizaciones por hora exacta, reproducibilidad del PDF, disciplina de cobertura fuera de la muestra transversal y garantías sobre dinámica común para puts. La auditoría usa una cadena y mallas finitas. En puts, dos mallas de 1.950 precios cada una con CRR 480/1.200 respetan las cotas intrínseca y K y la monotonía en strike (pendientes entre 0 y 1 salvo error de redondeo). Los tripletes dirigidos muestran por qué la malla de strike gruesa incluso con mayor resolución CRR puede omitir defectos de convexidad. Las alternativas señaladas son recomendaciones para revisión humana.

## Ejecución y trazabilidad de artefactos

El pipeline completo ejecutó las siete etapas, verificó las nueve figuras y terminó con código nativo de Python 0. Produjo el banner de éxito en 868,6 s. Su pytest aprobó 62 pruebas en 534,14 s con una advertencia de SciPy por overflow en el interpolador cúbico al recuperar IV de put. La ejecución independiente de pytest dio 62 aprobadas, una advertencia en 640,92 s y código nativo 0. Ambas usaron Python 3.12.6 y las versiones del archivo de requisitos, verificadas en el entorno de ejecución.

En ambos ensayos, los 45 archivos inventariados de `outputs/` y `docs/` conservan hashes idénticos. Las 19 tablas y nueve figuras coinciden byte a byte con el snapshot de publicación. El chequeo temporal de la suite identifica las siete reescrituras descritas en M-R3-2. La coincidencia final es evidencia de reproducibilidad para este entorno. No verifica frescura en el caso de etapas vacías ni ausencia de escrituras intermedias. [Hashes de pytest](repro_3d81ff1/pytest_hashes.csv) · [Hashes del pipeline](repro_3d81ff1/pipeline_hashes.csv)

## Evidencia y reproducción

[Guía para ejecutar los controles](repro_3d81ff1/README.md) · [Resultados diagnósticos](repro_3d81ff1/resultados.txt)

Reproducir desde el SHA auditado con Python 3.12.6 y versiones fijadas en `requirements.txt`. Las sondas de superficie usan la API de producción y valoran aparte con una CDF normal y árboles CRR independientes. Los ensayos de pipeline, hash y cartera usan extracciones o directorios temporales. Los valores de precios se expresan por acción salvo las tablas explícitas de P&L o capital. Los valores de IV se expresan en porcentajes y sus diferencias en puntos porcentuales.
