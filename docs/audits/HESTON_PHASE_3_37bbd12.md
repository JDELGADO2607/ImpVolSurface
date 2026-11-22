# Auditoría independiente Heston fase 3 — validación amplia

SHA auditado `37bbd12d52819c765c64a950333962af9410073d`, publicado en PR#5; base aprobada `ea0df6f097904352e5345bb6fbc712008e319bf2`. Extracción limpia. El commit solo añade validación, tests y artefactos; no cambia el motor ni calibra. Codex publica este informe/evidencias en la rama separada de coordinación, PR#4.

**PHASE_REJECTED**, reparación focalizada **1/3**. La evidencia de precisión del motor es favorable. El rechazo corresponde al validador que declara controles no realizados y a conclusiones que exceden la evidencia; **no se ha demostrado un defecto material de los precios comparados**. Hallazgos **0 BLOCKER,0 HIGH,2 MEDIUM,1 LOW**. No iniciar calibración de fase4 todavía. No cambiar parámetros, muestra o umbrales para reparar el informe.

## Evidencia favorable reproducible

48 tests de fases0–3 aprobados en77.90s. Hashes antes/después de todos los archivos existentes bajo data/,docs/,results/: cero cambios. Los10 hashes de outputs publicados coinciden. No se ejecutó otra vez todo el pipeline de1840s: se revisó código completo de validación y se reprodujo una muestra determinista adversarial sobre la extracción del SHA.

Mercado97: cobertura97 símbolos únicos, particiones60/22/15 sin exclusiones nuevas, vectorPoC y tasas congelados. Recalculando CSV: máximo error de malla fina frente a QuantLib0.0005457562USD; MAE0.0000556376 yRMSE0.0001023496. El default real también está bajo el objetivo, máximo0.0006833029, MAE0.0000845202USD. Son errores **entre motores al mismo vector**, no nueva calibración ni error frente a observaciones de mercado.

El auditor reprodujo tres peores discrepancias y cinco contratos seleccionados con semilla260721: ocho contratos, mallas default/fina y referencia QuantLib construida directamente. Diferencias de reproducción al nivel de redondeo, ninguna discrepancia material frente a los CSV. También ejecutó18 comparaciones de regímenes (17 casos distintos, una repetición con control de integración): máximo por régimen y selección determinista, más máximo europeo de cada régimenA–F con órdenes144/192. Se reproduce el caso más difícil europeoE,Feller<1, K12.33/430d: error−0.0005093404USD. Diferencia de órdenes de integración en las seis europeas, máximo4.44e−15USD. No se afirma haber recalculado los205 precios desde cero ni que estos controles prueben toda la distribución paramétrica.

Los108 precios publicados tienen las18 combinaciones exigidas por régimen,9americanas/9europeas. No se observa uso de holdouts para optimizar ni llamadas de calibración en el diff. Los97 y108 errores cumplen el objetivo0.002USD en las tablas y en las muestras recalculadas. Los tres controles QuantLib700→1000 publicados difieren aproximadamente0.000102–0.000112USD, por debajo de0.0005.

El límite xi0 y las propiedades de la construcción del motor conservan la evidencia independiente de [fase2](HESTON_PHASE_2_ea0df6f.md), cuyo código no cambia. Las correcciones pedidas aquí no exigen rehacer MCS–IT.

## F3-M1 MEDIUM — Resultados de validación no se derivan de todos los controles anunciados

### a. Resumen de refinamiento favorable fijado literalmente

`src/heston/pipeline_phase3.py`, bloque de manifiesto alrededor de1022–1040: `worst_3_refinement_status` se asigna siempre a `ALL_CONVERGED_WITHIN_002`. No depende del error ni del status del dataframe de refinamiento. Tampoco hay un dictamen agregado de los controles económicos/límites/tasas que distinga fallo o no evaluación.

Prueba negativa independiente: se cargan las tablas legítimas como fixtures; en copia temporal se fija únicamente el primer refinamiento a error1USD y statusFAIL. Los helpers se sustituyen por esas fixtures **solo para probar el agregador**, sin simular precios reales ni tocar los outputs oficiales. La ejecución devuelve todavía `ALL_CONVERGED_WITHIN_002`. Script `repro_phase3_37bbd12_negative.py`. No se afirma que los refinamientos legítimos publicados fallen: el defecto es que el resumen no podría reconocer ese fallo si ocurriera.

Corregir resumen para derivarlo de cantidades verificadas y estados efectivos, con pruebas negativas. No introducir framework nuevo. Mantener distintos estados PASSED,FAILED yNOT_EVALUATED cuando corresponda; el 100% de unas matrices no certifica las demás.

### b. Monotonía temporal descrita pero no calculada

`run_economic_arbitrage_checks`, líneas747–877, anuncia calendar monotonicity pero solo recorre tenores para comparar strikes, no compara los precios entre tenores. CSV no tiene incrementos temporales ni test correspondiente. Informe sección6.1, punto5, afirma monotonía para cada strike.

La auditoría sí calcula las36 transiciones de9strikes por5tenores. Hay cuatro incrementos negativos brutos; el peor K17,31→94d es−0.00002097946USD. La incertidumbre empírica sumada de ambos precios es0.0001938299USD. Ninguna de las cuatro excede esa estimación. Por tanto **no es un defecto material del motor demostrado**, pero no debe reportarse monotonía exacta sin ejecutar la prueba ni borrar esos signos. Exportar transiciones, diferencias, estimaciones y decisión, distinguiendo raw y tolerancia.

Finitud y cota superior tampoco aparecen como controles efectivos en el status. El auditor verificó los45 pares de precios finitos y cota P<=K en esta tabla; incorporar la verificación al alcance anunciado para no depender de texto declarativo.

### c. Tabla de tasas no evalúa los pasos del solver que cruzan nudos

`run_rates_curve_integration_check`, líneas882–923, integra cada intervalo **exactamente entre nudos adyacentes**, donde el forward es constante. La igualdad resultante es correcta, pero no comprueba el paso real del solver que cruza un salto de tasa. Tampoco llama al adaptador QuantLib pese a anunciar esa comparación. Las garantías del informe sección7 no se derivan de este ensayo.

El auditor reproduce la integración real D_N=exp(−sum_i r(T−(i+0.5)dt)*dt) con N usado por el motor. Diferencias frente a D(T):

| Plazo | Ndefault | ErrorD default | Nfine | ErrorD fina |
| --- | ---: | ---: | ---: | ---: |
| 31d | 60 | +7.95903e−7 | 100 | −4.37746e−7 |
| 94d | 77 | +3.16688e−6 | 155 | +5.36580e−7 |
| 212d | 174 | +6.28783e−6 | 348 | +2.59605e−6 |
| 430d | 353 | +8.12464e−6 | 707 | −8.03983e−7 |
| 794d | 653 | −4.69459e−6 | 1305 | +3.32930e−7 |

D es adimensional, no USD. Son discrepancias pequeñas, no una prueba de error material de precios; contradicen exactitud a máquina de la integración por pasos del solver. Mantener separado el ensayo nodal exacto del ensayo de pasos reales; medir también la diferencia original/dailyQuantLib como se pidió, sin exigir igualdad falsa ni cambiar la curva.

### d. Referencia ausente convertida en error0 y PASS002

`run_analytical_limits_validation`, líneas603–628, etiqueta la secuencia v0 descendente como `max_abs_err_usd=0` y `status_002=PASS` solo por finitud y precio positivo. No existe referencia para ese0 y la tabla ni siquiera exporta el valor v0 de cada fila. `ql_status` se fija por condicional y no se ejecuta ni se exporta.

La auditoría confirma realmente que QuantLib1.44 rechaza v0=0 con RuntimeError('0: invalid value'); a v0=0.0001 sí admite el caso. El valor0 necesita una validación de límite/refinamiento, no un error comparativo inventado. Valores independientes a31d ATM:

| v0 | 160/80 | 240/120 | 320/160 | QuantLib700,280/140 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 0.1951226005 | 0.1953673578 | 0.1954237625 | NO_ADMITIDO |
| 0.0001 | 0.1955714346 | 0.1958041655 | 0.1958545288 | 0.1955741275 |

Los resultados son finitos y muestran refinamiento favorable; no se demuestra que el error sea0. Exportar v0/parámetros, soporte real de referencia, N/A para error sin referencia y estado de prueba cualitativa separado. Ejecutar referencia/límite descendente y conservar excepciones reales. No imponer Feller o excluir v0 simplemente para obtener PASS.

### e. Vínculo de procedencia incompleto

El manifiesto contiene hashes de outputs y vectorA, pero no hashes de inputs ni identificación del código/entorno que produjo la evaluación. Los inputs no cambiaron en Git y la auditoría pudo reconstruir la fuente; no se demuestra mezcla real de ejecuciones. Completar vínculo requerido por PHASE_3_START con hashes de puts/splits/manifiestoPoC/curva pertinentes y fuente/versiones. Usar hashes de archivos fuente o un SHA previo más estado de cambios cuando sea necesario para evitar una falsa referencia autorreferente. No construir un gestor genérico de caché.

## F3-M2 MEDIUM — Incertidumbre empírica tratada como cota rigurosa y conclusiones globales

Informe secciones5–7 y conclusiones: define epsilon=abs(Pfine−Pdefault) y asume abs(error)<=epsilon, llamando rigurosa a la banda de butterfly y concluyendo ausencia de arbitraje estructural. La propagación ponderada de **cotas verdaderas** es matemáticamente correcta; la diferencia de dos mallas no constituye por sí sola una cota del error de ninguna de ellas. Se había fijado explícitamente esa distinción antes de ejecutar fase3.

Ejemplo K17/794d: epsilon empírico0.0000630822USD; discrepancia fina frente a referencia QuantLib700 es0.0004895105USD, unas7.76veces mayor. QuantLib también es numérico, de modo que este dato **no identifica un error verdadero exacto ni prueba un defecto material de arbitraje**; ilustra por qué esa diferencia de mallas no debe venderse como certificado. Reportar estimación empírica y limitaciones, manteniendo precios crudos y señales.

Tampoco son monótonas todas las tres secuencias de refinamiento. NU280121P15:3.6286098144→3.6285967661→3.6286275557. Frente a una misma referencia QuantLib1000, los errores son0.0001903344→0.0001772860→0.0002080757USD. Todos están bajo presupuesto; no forzar convergencia monótona ni reparar el motor por esta oscilación pequeña, pero corregir esa afirmación. Comparar errores con referencia fija; cambiar a la vez referencia y malla propia no demuestra reducción monótona del error.

La banda económica es una comprobación finita bajo incertidumbre **estimada**, no una prueba global de ausencia de arbitraje. Corregir esa interpretación y la exactitud de integración de tasas. No añadir clipping, proyección, filtros o una nueva optimización para hacer cierto el texto.

## F3-L1 LOW — Evaluador default no es C1 global por cambio discreto de malla

El ensayo de27.5d y una derivada finita en un punto no demuestra regularidad C1 global. Contraejemplo nuevo con vectorA,K12.33,curva común: T*=60.5/300años, alrededor de73.6083d, donde default pasa de60 a61pasos.

| h años | Nizq/Nder | P(T*+h)−P(T*−h) USD |
| --- | --- | ---: |
| 1e−6 | 60/61 | −0.00005742304 |
| 1e−8 | 60/61 | −0.00006166927 |
| 1e−10 | 60/61 | −0.00006171173 |

Con m_t fijo120 y h1e−10, la diferencia es+4.28894e−10USD, cociente centrado2.14447USD/año, mientras el cociente adaptativo diverge en el experimento. El salto medido es menor que0.002USD: se acepta como limitación de la aproximación inicial y **no se exige rediseñar ahora el motor para obtener continuidad exacta**. Documentar; la futura construcción de IV y griegas debe controlar/fijar discretización apropiadamente. No usar este evaluador para afirmar derivadas temporales globales validadas. La dinámica continua de Heston no es la causa de este salto numérico.

## Reparación y dictamen provisional

Precisión de precios sobre las matrices publicadas y muestra independiente: favorable. Integridad/completitud del validador y alcance de las garantías: pendientes. La calibración de fase4 continúa sin autorizar.

Reparación1/3: corregir agregación de estados y pruebas negativas, implementar/exportar calendario y pasos reales de tasas, separar v0 sin referencia de error0, completar trazabilidad y reconciliar conclusiones. Los signos pequeños, salto default y refinamiento no monótono **no requieren reparación de precios** a esta escala. Mantener motor, parámetros, muestra, bounds, presupuestos y outputs de precios verificados.

No repetir las30min de todos los precios si solo cambian diagnósticos: se pueden reutilizar explícitamente las tablas de37bbd12 tras verificar hashes, entradas y fuente, identificando el SHA de origen de los precios y el origen nuevo de los diagnósticos. No llamar a esa reutilización regeneración financiera completa ni aceptar artefactos viejos sin verificación. Recalcular únicamente límites/controles afectados. No añadir infraestructura de caché general; la regeneración integral llegará en fase7.

Entregar nuevo SHA y PHASE_READY_FOR_AUDIT, sin calibración ni merge. Máximo3reparaciones ordinarias de esta fase; no abrir ciclo indefinido por límites numéricos irrelevantes.

## Reproducción y límites

Scripts `repro_phase3_37bbd12_samples.py` (ocho mercado y12comparaciones de regímenes, v0), `repro_phase3_37bbd12_europeans.py` (seis europeas e integración), `repro_phase3_37bbd12_diagnostics.py` (tablas/calendario/tasas), `repro_phase3_37bbd12_negative.py` (agregador), `repro_phase3_37bbd12_continuity.py` y `repro_phase3_37bbd12_tests.py`; log `HESTON_PHASE_3_37bbd12_evidence.txt`, tabla `HESTON_PHASE_3_37bbd12_market_sample.csv`. Copiar desde coordinación a docs/audits de extracción limpia del SHA auditado y ejecutar desde raíz con requirements-heston.txt. Prueba negativa solo altera fixtures/copias temporales. No se modifica producción.

No se demuestra ausencia de todos los defectos en todo régimen. No se recalibraron parámetros, no se corrió pipeline global histórico ni se validaron griegas operativas, IV equivalente, cartera o rentabilidad. Fuentes de evidencia: código/CSV del SHA, motores numéricos independientes y ecuaciones indicadas; no declaraciones de aprobación humana.
