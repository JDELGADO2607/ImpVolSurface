# Auditoría independiente Heston fase 3 — reparación 1

SHA auditado `28bd72a29640b0c8a93b8c11f9023d39222f1ccc`, publicado en PR#5; base `37bbd12d52819c765c64a950333962af9410073d`. Extracción limpia, sin modificaciones de implementación por Codex. Informe/evidencias en rama de coordinación, PR#4; su commit es distinto del auditado.

**PHASE_REJECTED**, reparación focalizada **2/3**. La mayor parte de la reparación es correcta y los precios legítimos siguen siendo favorables. Falta proteger la reutilización de tablas y la decisión numérica del agregador. No se autoriza fase4/calibración. Hallazgos actuales: **0 BLOCKER,0 HIGH,1 MEDIUM abierto y2 LOW aceptados**. No se exige rehacer el motor ni repetir toda la valoración.

## Lo que se resolvió y se reprodujo

49 tests de fases0–3 aprobados en107.89s. Hashes antes/después de todos los archivos existentes en data/,docs/,results/: cero cambios.

Las siete tablas de precios heredadas son **idénticas byte a byte** a37bbd12: mercado97, resúmenes por tenor/partición, tres peores refinamientos, regímenes108, refinamientosB–F y continuidad. Se comprobaron los10 hashes de outputs y los7 de inputs del manifiesto: todos corresponden a los archivos publicados.

Los cuatro hashes de fuente coinciden tras normalizar CRLF→LF. La diferencia de hash de bytes originales de la extracción es de serialización de saltos de línea, **no una divergencia del código ni un hallazgo financiero**. Cualquier comprobación de fuente reutilizada debe adoptar una normalización documentada para evitar falsos rechazos por formato.

Se recalculan las36 transiciones temporales desde los precios:4 caídas brutas,0 más allá de estimación empírica; máximo desacuerdo con la tabla1.11e−16USD. Se recalculan tasas nodales, pasos reales y5 fechas QuantLib: discrepancia con el CSV8.47e−22. El adaptador original/daily en10000 tiempos continuos entre0.001 y3años da máximo2.63424e−6 enD, corroborando que igualdad en fechas enteras no equivale a igualdad en todo tiempo.

La secuencia v0 exporta el parámetro, precios en tres mallas, referencia y excepción real. A v0=0 el campo comparativo principal abs_err_usd es NaN y el estadoN/A_NO_REF; la excepciónRuntimeError('0: invalid value') coincide con la comprobación real del auditor anterior. Las conclusiones ya distinguen estimación empírica de cota analítica y retiran C1 global; no se demuestra un defecto material del núcleo de puts.

| Hallazgo previo | Estado de esta revisión |
| --- | --- |
| F3-M1 a: resumen worst3 literal | RESOLVED para ese contraejemplo; el nuevo test negativo efectivamente obtiene FAILED. Persisten otras vías de PASS incoherente descritas abajo. |
| F3-M1 b/c: calendario y pasos reales de tasas | RESOLVED en controles ejecutados. |
| F3-M1 d/e: v0 y procedencia | Sustancialmente corregidos; procedencia registrada pero aún no usada para autorizar reutilización. Un alias de error sin referencia continúa en0, residualLOW. |
| F3-M2: extrapolación de conclusiones empíricas | RESOLVED en delimitación material; no se aprueba una garantía global ni cada adjetivo del borrador. |
| F3-L1: salto de malla temporal | LIMITACIÓN ACEPTADA, documentada; no corregida numéricamente ni requerida ahora. |

Los precios97/108 no cambiaron y conservan la evidencia de [auditoría anterior](HESTON_PHASE_3_37bbd12.md). Para mercado97, máximo fino0.0005457562 ydefault0.0006833029USD; regímenes108 máximo0.0005093404USD. No se repiten todos los precios porque el núcleo y las tablas permanecen congelados.

## F3-M1 MEDIUM, parcialmente resuelto — Reutilización no verificada y gate dependiente de etiquetas

Archivos `src/heston/pipeline_phase3.py`: run_market_97_validation alrededor de133–141, run_hypothetical_regimes_108 alrededor de399–404, run_continuity_and_edge_cases alrededor de751–755, run_economic_arbitrage_checks alrededor de864–880 y agregación alrededor de1202–1242.

Las nuevas rutas con reuse_verified_tables=True comprueban existencia de CSV y los devuelven. No cotejan hashes contra el snapshot publicado, no verifican entradas/dependencias contra ese origen ni rechazan cambios antes de reutilizar. El manifiesto calcula hashes **después**, y prices_source_commit está fijado literalmente a37bbd12 incluso si los CSV cargados difieren. Registrar un hash nuevo del resultado modificado no verifica identidad con su fuente histórica.

El agregador de mercado97 y regímenes108 comprueba número de filas y etiquetasPASS, pero no valida efectivamente cantidades finitas bajo0.002USD ni la coherencia precio−referencia−error. El peor3 sí tiene una comprobación numérica además del status; las otras matrices no la heredan.

### Pruebas negativas independientes

Script `repro_phase3_28bd72a_gate.py`. Copias temporales de las10 tablas y manifiesto legítimos. Se ejecutan el cargador de caché real y el agregador real. Para ahorrar el recálculo de límites/tasas se suministran sus tablas legítimas como fixtures; no se usa esta sustitución como evidencia de precios financieros. No se modifica ningún archivo oficial.

| Caso | Modificación | Hash del precio coincide con manifiesto origen | Resultado real |
| --- | --- | --- | --- |
| Control legítimo | Ninguna | Sí | PASSED, error máximo0.0005457562 |
| Precio alterado | Primera proprietary_fine_usd +=1USD; columnas de error/status conservadas | No | **PASSED**; el error precio−referencia de esa fila es1USD, pero resumen sigue en0.0005457562 |
| Error numérico fallido, etiqueta obsoleta | Primera abs_err_fine_usd=1USD; statusPASS conservado | No | **PASSED**, aun con máximo reportado de1USD |

Los tres resultados atribuyen precios a37bbd12. Por tanto, la política de reutilización explícitamente autorizada “tras verificar hashes/inputs/fuente” no está implementada en las rutas que la anuncian. Los datos públicos actuales sí son legítimos y coinciden con el origen; **no se afirma que estén alterados**. El defecto es reproducible y permitiría certificar datos antiguos/inconsistentes en la siguiente ejecución.

### Reparación mínima autorizada

1. Verificar **antes de leer como válido** el snapshot reutilizado contra una referencia versionada inmutable de precios, inputs, parámetros/configuración y dependencias de valoración relevantes. La referencia debe proceder de los commits publicados y examinados, no regenerarse de los mismos CSV que se intenta validar. Normalizar saltos de línea de fuente de forma explícita. Si no se puede demostrar compatibilidad, fallar claramente o recalcular explícitamente.
2. Recalcular errores comparativos desde precios/referencias y exigir finitud y umbral numérico en mercado97 y regímenes108. Una etiquetaPASS no sustituye esa comprobación. Comprobar que los errores almacenados sean consistentes o regenerarlos de manera explícita; no alterar precios para hacerlos coincidir con el status.
3. Agregar tests que ejecuten los cargadores/agregador con hash de precio cambiado, inputs o fuente incompatible, error1USD con statusPASS y valores numéricos no finitos. Mantener control positivo del snapshot legítimo y el negativo worst3 ya corregido.

Una alternativa sencilla es desactivar la reutilización automática y exigir un origen explícito y verificado para el ahorro de tiempo. No hace falta recalcular205 precios por corregir estos controles ni construir una plataforma genérica de caché. La solución concreta puede ser un manifiesto de snapshot pequeño y una función de comprobación. Evitar atribución fija a37bbd12 si se calcula realmente una ejecución nueva.

## Residuos LOW, sin nueva exigencia de precisión

**F3-L1:** sigue existiendo el salto de unos6.17e−5USD al cambiar60→61pasos en el default. Es menor que0.002USD y se reconoce como límite de aproximación. La documentación corrige la afirmación C1 global. No se pide modificar el motor; la evaluación de griegas/IV posterior debe controlar discretización.

**F3-L2:** en la fila v0=0, abs_err_usd=NaN y statusN/A_NO_REF son correctos, pero el alias max_abs_err_usd conserva0.0. Conviene que todos los campos comparativos sin referencia sean N/A para evitar uso accidental del alias. La propiedad scipy_version contiene `scipy.stats._continuous_distns`, que es un módulo, no la versión de SciPy; usar la versión real. Son correcciones pequeñas de metadatos, no fallos demostrados de valoración ni motivo para reabrir una calibración.

Persisten expresiones demasiado categóricas en el borrador, pero el marco ahora declara límites finitos/empíricos. No se convierte ese refinamiento editorial en otra ronda matemática. La aprobación final de material de defensa seguirá reservada a fase8.

## Dictamen y siguiente acción

Motor y tablas numéricas publicadas: favorables en el dominio comprobado. Calendario/tasas/límites: mejoras verificadas. Integridad de reutilización y decisión del validador: pendiente deF3-M1. Emitir reparación2/3 acotada a esa vía, conservando muestras, parámetros, motor y presupuesto0.002USD. No calibrar ni iniciar fase4 sin PHASE_APPROVED. No merge/force-push.

Para conservar recursos, reutilizar las siete tablas legítimas mediante una comprobación real de su origen; generar únicamente diagnósticos/metadatos afectados e identificar su procedencia. Tras un nuevo SHA publicado, Codex reauditará; máximo tres rondas ordinarias en esta fase.

Evidencia: `repro_phase3_28bd72a_gate.py`, `repro_phase3_28bd72a_diagnostics.py`, `repro_phase3_28bd72a_tests.py` y `HESTON_PHASE_3_28bd72a_evidence.txt`. Copiar scripts desde coordinación a docs/audits de una extracción limpia del SHA auditado, instalar requirements-heston.txt y ejecutar desde la raíz. El script de diagnóstico compara además con una extracción anterior37bbd12 en TEMP, según su ruta explícita; el test negativo y pytest no requieren esa extracción anterior. Ninguna prueba escribe resultados oficiales.
