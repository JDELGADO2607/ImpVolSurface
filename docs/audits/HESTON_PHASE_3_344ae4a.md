# Auditoría independiente Heston fase 3 — reparación 2

SHA auditado `344ae4af1460ec2bc2ae6a28eac382f3c12c32ae`, publicado en PR#5, comparado con `28bd72a29640b0c8a93b8c11f9023d39222f1ccc`. Extracción limpia, sin modificar implementación. Codex publica evidencia y coordinación en PR#4, con commit distinto del auditado.

**PHASE_REJECTED**, reparación focalizada **3/3**, último intento ordinario de fase3. La corrección de errores numéricos y los casos negativos anteriores funcionan; la integridad no condiciona todavía el dictamen por defecto y faltan dos dependencias de reutilización. Continúa abierto **1 MEDIUM (F3-M1)**. F3-M2 está cerrado en aspectos materiales; F3-L2 de metadatos queda resuelto; F3-L1 sigue como limitación numérica LOW aceptada. No hay defecto material nuevo demostrado del motor ni autorización para calibración/fase4.

## Evidencia favorable

56 tests de fases0–3 aprobados en123.05s. Hashes antes/después de todos los archivos existentes bajo data/,docs/,results/: cero cambios. Siete tablas de precios siguen idénticas byte a byte a37bbd12. Los inputs/outputs legítimos corresponden a sus hashes; las fuentes corresponden tras normalizaciónLF, sin divergencia numérica por CRLF. SciPy se identifica ahora como1.18.0 y ambos errores sin referencia en v0=0 sonNaN, con estadoN/A_NO_REF.

Se reprodujeron controles de calendario y tasas, sin nueva discrepancia material. La precisión de mercado97 y regímenes108 conserva la evidencia de auditorías anteriores porque el motor y precios no cambian: máximos publicados de malla fina0.0005457562 y0.0005093404USD, respectivamente, bajo presupuesto0.002. No se recalcula todo el pipeline ni se reajustan parámetros.

Los dos contraejemplos previos están corregidos: precio+1USD con referencia intacta y error almacenado1USD con etiquetaPASS ahora generan FAILED. También se controla finitud y coherencia de errores. La opción strict_verification=True rechaza la tabla alterada. El problema restante está en el comportamiento por defecto y la cobertura del origen, no en esos controles ya añadidos.

## F3-M1 MEDIUM — Integridad detectada pero no exigida para aprobar

`src/heston/pipeline_phase3.py`, helpers alrededor de244–269,530–551,896–914,run_economic_arbitrage_checks alrededor de1018–1036, y agregado alrededor de1365–1510.

### 1. Una tabla no verificada puede producir PASSED por defecto

strict_verification=False es el default. Los cargadores calculan all_verified=False ante un hash incompatible, pero devuelven igualmente los datos con un atributo de diagnóstico. El agregador calcula all_snapshot_verified y lo usa para etiquetar procedencia; **no lo incluye en overall_passed**.

Prueba independiente en copia temporal: aumentar en1USD tanto proprietary_fine_usd como ql_refined_700_usd de la primera fila, conservando error/status. La diferencia entre ambos sigue bajo tolerancia, pero los valores ya no son los del origen37bbd12 y el hash falla. Resultado real:

- overall_status=PASSED;
- market_97_status=PASSED;
- prices_source_commit=UNVERIFIED_OR_FRESH_EXECUTION.

No se afirma que esos precios manipulados sean resultados reales del motor. La prueba demuestra que una procedencia rechazada no impide certificar una ejecución que está reutilizando datos. Un cálculo fresco es una ruta distinta: no debe confundirse con leer una tabla no verificada.

Corrección mínima: si se solicita reutilización, **todos los precios reutilizados deben tener origen validado antes de que overall pueda ser PASSED**. Puede abortarse con SnapshotIntegrityError o devolverse FAILED. Un modo no estricto puede conservar datos para diagnóstico, pero no dar aprobación. Alternativamente hacer estricto el uso ordinario. La ruta fresca explícita debe identificar su fuente actual sin fingir origen37bbd12.

### 2. Los precios económicos reutilizados quedan fuera de la guarda

VERIFIED_SNAPSHOT_METADATA contiene siete tablas, pero la tabla económica también aporta precios reutilizados. run_economic_arbitrage_checks lee price_american,price_european yepsilon de un CSV existente sin validar su origen. all_snapshot_verified solo recoge mercado,regímenes ycontinuidad.

Contraejemplo independiente: sustituir en copia temporal los45 precios americanos/europeos por max(K−12.33,0)+1e−12, conservando mallas/epsilons. Esas cantidades satisfacen por construcción muchas restricciones estáticas, pero **no son los precios del modelo ni del snapshot**. El pipeline recalcula los checks y devuelve economic_status=PASSED yoverall=PASSED, atribuyendo además prices_source_commit=37bbd12. Las tablas mercado97/108 permanecen legítimas en este caso.

No es un fallo de las desigualdades matemáticas: son condiciones necesarias, no una identidad con el precio Heston. Es un fallo de procedencia. Verificar los campos de precios/epsilon de esa tabla mediante un snapshot versionado o recalcularlos. Puede usarse una representación canónica de los campos numéricos pertinentes para tolerar serialización documentada, sin confundir cambios diagnósticos con cambios de precio. No se exige un nuevo gestor de caché ni volver a calcular205 contratos.

### 3. Se registran hashes de fuentes, pero no se comparan con la valoración de origen

verify_snapshot_inputs_and_params verifica siete inputs financieros y parámetrosA, no las dependencias de código de valoración. compute_normalized_source_sha256 existe, pero solo se usa para registrar el manifiesto posterior.

Prueba aislada: copiar los siete inputs y los tres módulos de valoración a una raíz temporal; verificar que esa raíz legítima pasa. Cambiar únicamente el default theta_ADI de1/3 a1/2 en la copia de solver_2d.py. La verificación sigue devolviendo True, “All inputs and parameter dependencies verified against snapshot”. No se ejecuta ese solver modificado ni se atribuye un error de precio al cambio; demuestra ausencia de comparación de dependencia. Las hipótesis numéricas del cálculo de origen ya no son las mismas.

Añadir comparación previa de huellas normalizadas de solver_2d.py,heston_model.py y rates_curve.py y configuración de valoración pertinente contra una referencia inmutable del origen conocido. No fijar el hash de todo el pipeline de diagnóstico si eso obliga a revalorar por un cambio editorial: separar dependencias de precio de procesamiento posterior.

## Pruebas reproducibles de esta revisión

`repro_phase3_344ae4a_integrity.py` ejecuta cargadores, controles económicos y agregador reales; solo usa fixtures legítimas para límites/tasas costosos. Se trata de pruebas de integridad del controlador, no de precios artificiales presentados como financieros. Todo ocurre en copias temporales.

| Caso | Resultado actual |
| --- | --- |
| Snapshot legítimo | PASSED,origen37bbd12 |
| Precio+1 con referencia original | FAILED,caso anterior resuelto |
| Error1 con etiquetaPASS | FAILED,caso anterior resuelto |
| Precio y referencia+1 | PASSED,origen no verificado |
| Precios económicos sustituidos | PASSED,origen37bbd12 |
| Mismos inputs con default ADI alterado en copia | Verificador devuelveTrue |

El último caso es prueba del verificador, no una ejecución completa del pipeline con un motor distinto. No se demuestra manipulación de los datos públicos actuales. Los tres pendientes pueden corregirse con guardas de procedencia; no hace falta alterar precios, ecuaciones ni mallas.

## Encargo final de reparación3/3

- Un origen inválido con reuse=True nunca puede terminar en aprobación, aun cuando el error aritmético de dos columnas alteradas conjuntamente sea pequeño.
- Cubrir todos los precios reutilizados, incluida la base económica, y dependencias de precio normalizadas contra el snapshot versionado; no generar la referencia desde el mismo archivo sospechoso.
- Conservar pruebas positivas del origen legítimo y negativas previas. Añadir los tres casos independientes anteriores; ambos defaults y modo estricto deben tener semántica clara. Una ejecución fresca explícita sigue su propia procedencia.
- Mantener motor, muestras, parámetros,grids,umbral0.002 y siete tablas originales. Si se elige recalcular solo economía en vez de reutilizarla, documentar coste/origen y preservar el resto. No introducir plataforma de caché ni cambiar criterios por los resultados.

Tras nuevo SHA, Codex reauditará. Si queda defecto material al terminar esta tercera reparación, no se abrirá una cuarta ronda automática: se registrará el bloqueo y su causa/alternativa conforme al protocolo. No calibración/fase4,merge o force-push mientras fase3 no esté aprobada.

La regularidad temporal aproximada F3-L1 permanece documentada, por debajo del presupuesto de precio y pendiente de control específico para IV/griegas; no requiere reparación ahora. No se usa esta revisión para ampliar el alcance académico.

## Evidencia y límites

Scripts `repro_phase3_344ae4a_integrity.py`, `repro_phase3_344ae4a_diagnostics.py`, `repro_phase3_344ae4a_tests.py`; log `HESTON_PHASE_3_344ae4a_evidence.txt`. Copiar a docs/audits de extracción limpia del SHA auditado y ejecutar desde raíz con requirements-heston.txt. El diagnóstico compara además con extracción37bbd12 en TEMP; el negativo y pytest no requieren esa extracción anterior. No se modifican artefactos oficiales.

No se vuelve a reproducir todo el pipeline de30min porque el motor/precios no cambian. La evidencia numérica amplia y sus límites se conservan en los informes37bbd12 y28bd72a. El pendiente afecta al reconocimiento automático de evidencia válida, no a una nueva invalidez matemática demostrada de Heston.
