# Auditoría independiente Heston fase 1 — reparación 2

SHA auditado `3a294af73f0215e0435223d20015545245164bdf`, publicado en PR#5. Comparación contra `af105d1b221d4b096695b979fb72bc55834cf47e`. Evidencia y estado publicados por Codex en rama de coordinación independiente, PR#4; ningún cambio de implementación del auditor.

Dictamen **PHASE_REJECTED**, reparación focalizada **3/3**. PoC favorable en ajuste y convergencia para el vector ya examinado; queda una vía demostrada de aceptación de caché inválida. No se autoriza fase2 todavía. Hallazgos: **0 BLOCKER,1 HIGH,0 MEDIUM,1 LOW**. La reparación3 es el último intento ordinario autorizado para esta fase.

## Evidencia favorable y alcance

- Extracción limpia del SHA y comprobación de publicación en GitHub.
- 22 tests de fases0+1 aprobados en20.98s. Hashes antes y después de todos los archivos existentes bajo data/, docs/, results/: cero cambios.
- Las cuatro tablas de precios train/strike/tenor/full no cambian ninguna columna numérica financiera respecto a af105d1; cambian tiempos de evaluación. No cambian heston_model.py, calibration.py ni rates_curve.py. Por ello se conserva la evidencia independiente del informe previo:97 precios reproducidos, máximo refinamiento adicional0.000606435USD y métricas favorables. No se repite esa evaluación completa innecesariamente.
- Los cinco objetivos finos nuevos coinciden con los reproducidos independientemente en la auditoría anterior: diferencia máxima9.71e−17USD². Orden de candidatos cercanos2,5,1,4; candidato3 con SSE fina21.4687839101USD², frente a0.0867617087 del candidato2.
- Los siete hashes de inputs publicados coinciden con sus archivos. Los tests negativos de precio de train modificado, SSE negativa y parámetros fuera de límites pasan.
- El término cruzado está corregido a rho*xi*v*S*V_Sv; la tabla común84 concilia; se eliminó la afirmación de óptimo global y la exigencia infundada de regularizar Feller. No se modificó la muestra ni los cinco parámetros globales.

Referencias de evidencia heredada: [informe af105d1](HESTON_PHASE_1_af105d1.md), [revaloración97](HESTON_PHASE_1_af105d1_reprice.csv) y [log independiente](HESTON_PHASE_1_af105d1_evidence.txt). Esta reutilización de evidencia se justifica por diff exacto de código y datos, no por declaración de Gemini.

## Matriz de resolución

| Hallazgo | Estado vigente | Comentario |
| --- | --- | --- |
| F1-01 HIGH, presupuesto numérico | RESOLVED en dominio probado | Código de valoración y precios intactos; validación previa aplicable. |
| F1-02 MEDIUM, matemática/documentación | PARTIALLY_RESOLVED; residual LOW | Corregidos defectos materiales de fórmula, interpretación y métricas. Restan especificaciones de malla y tolerancia erróneas. |
| F1-03 MEDIUM, precios crudos y diagnósticos | RESOLVED para PoC | No hay cambios que invaliden la auditoría anterior. No es prueba de arbitraje global ausente. |
| F1-04 HIGH, caché | PARTIALLY_RESOLVED | Hashes y casos negativos originales corregidos; queda aceptación selectiva sin replay. |

## F1-04 HIGH — Replay selectivo permite seleccionar el candidato que no se verificó

Archivo `src/heston/pipeline_phase1.py`, líneas137–150 y185–210. El replay solo se ejecuta cuando `row.status == 0 and row.final_sse < 1.0`. Después, `best_row = df_ms.sort_values('final_sse').iloc[0]` permite seleccionar cualquier fila, incluidas aquellas excluidas del replay. La SSE fina sí se calcula, pero no se usa para rechazar la contradicción ni proteger la selección.

Procedimiento reproducible, con datos originales y precios/QuantLib reales, sin monkeypatch del motor:

1. Copiar a un directorio temporal el manifiesto y la tabla multistart del SHA auditado.
2. En la fila del inicio3, conservar los cinco parámetros publicados; fijar status2, successFalse y tipoABNORMAL_TERMINATION. Cambiar únicamente final_sse=0 y final_rmse=0, mutuamente consistentes. Ningún input financiero cambia; los hashes originales siguen siendo correctos.
3. Llamar `validate_and_load_multistart_cache` con el train original, su curva y fecha comunes.
4. La función acepta la caché y devuelve inicio3 como mejor candidato con objetivo0. Al mismo tiempo ha calculado una SSE fina de21.4687839101 para ese mismo vector, con inicio2 mejor en malla fina. Se reprodujo adicionalmente el objetivo original en la misma malla de calibracion:0.5861874690884654USD2, frente al0 ficticio aceptado; no se confunde la diferencia entre mallas con inconsistencia de la cache.

La prueba termina tras la función de validación. **No se afirma que el pipeline completo terminaría con gatePASSED para ese candidato**, ni que las filas publicadas hayan sido alteradas. Se demuestra que el validador y selector admiten una pérdida no verificada y contradicha por su propia evaluación independiente. El candidato fallido entra por una ruta expresamente excluida del replay. Es el mismo defecto de integridad F1-04, no un hallazgo nuevo de inviabilidad del modelo.

Matemática: para parámetros fijos, contratos y motor determinados, SSE=sum_i(P_i(theta)−Pobs_i)² es un número definido, no una etiqueta libre del CSV. Verificar solo SSE>=0 y RMSE=sqrt(SSE/N) no verifica correspondencia con el objetivo. Cero puede cumplir esas dos condiciones y ser falso. El estado del optimizador no demuestra validez de la pérdida ni autoriza omitir esa correspondencia.

Corrección mínima, alternativas:

- Reproducir el objetivo para **todas las filas que puedan ser seleccionadas**, sin usar un estado o SSE declarada como exención de validación. No borrar de las evidencias los inicios fallidos.
- O excluir explícitamente de la selección las filas sin replay verificado, registrando esa decisión. Evitar hacer depender la selección de datos de caché no contrastados.
- Otra alternativa ya autorizada es desactivar la reutilización automática y reconstruir explícitamente; no desarrollar un gestor genérico de caché.

Comprobar finitud explícita de final_rmse antes de comparar y consistencia de SSE/RMSE con tolerancia de serialización justificada. La comparación `abs(NaN−esperado)>tol` no rechaza NaN por semántica IEEE; es una observación por inspección, no una segunda ejecución financiera de este contraejemplo. No se requiere estudiar nuevos modelos ni cambiar límites.

Pruebas exigidas para cerrar: el contraejemplo status2/SSE0 debe rechazarse o ser inelegible antes de seleccionarlo; la caché legítima debe seguir funcionando y el candidato2 conservarse si sus objetivos continúan siendo mínimos; casos de RMSE no finita; datos cambiados y SSE negativa siguen rechazados. Si se conservan todos los candidatos como elegibles, ejecutar replay de todos y validar sus objetivos. Documentar cuándo una malla fina sirve de diagnóstico y cuándo afecta selección. No imponer Feller para resolver este problema computacional.

## F1-02 residual LOW — Especificación documental aún distinta del código

`docs/reports/INFORME_FASE_1_POC_HESTON.md`:

- Línea86 llama malla de calibración a factor100,x100,v50. El calibrador y replay usan factor50,mínimo25,x70,v35. La malla fina usa factor200,mínimo25,x200,v100; nt no es200 fijo. El CSV de objetivos ya es correcto; corregir únicamente su explicación.
- Línea183 promete tolerancia1e−6USD para SSE; código línea144 usa1e−3 y SSE tiene unidadUSD². Documentar y justificar la tolerancia real. Para replay determinista de candidatos serializados, los errores observados fueron de redondeo, no de1e−3USD².
- Fecha de ejecución en cabecera sigue23:17:30Z, mientras manifiesto de esta entrega dice23:41:08Z. Identificar ejecución actual y, si se retiene la anterior, marcarla como histórica.
- Configuración europea menciona Gauss-Legendre/Gauss-Laguerre indistintamente. Precisar el motor efectivamente invocado; no añadir una promesa de precisión derivada solo del orden144. Esta precisión de nomenclatura no altera los precios aprobados en los experimentos.

No se exige una nueva reconciliación general ni reescribir el informe completo. La ecuación y métricas importantes ya están corregidas. Estos residuos no constituyen por sí solos un bloqueo metodológico de Heston; se incluyen en la reparación acotada de integridad.

## Límites y dictamen

La nueva prueba se dirige a la implementación del validador, no a cambiar parámetros sobre holdouts ni a optimizar el ajuste. Las simulaciones, griegas, superficie equivalente y solver propio siguen sin implementar/auditar dentro de esta fase. No se prueba aquí identificabilidad global ni ausencia global de arbitraje numérico. Las limitaciones de datos y comparación con SVI de distinta curva continúan vigentes.

El gate de viabilidad matemática de la PoC tiene evidencia favorable. La integridad de selección automática aún falla. Autorizar reparación3/3 exclusivamente de F1-04 y las líneas documentales especificadas, nuevos tests y nuevo SHA. **No iniciar fase2 sin PHASE_APPROVED**. Si persiste un defecto material después del tercer intento, investigar causa y registrar PHASE_BLOCKED o una alternativa sencilla dentro del alcance; no abrir un cuarto ciclo automático.

Script independiente `repro_phase1_3a294af_cache.py` y evidencia `HESTON_PHASE_1_3a294af_evidence.txt`. Copiar el script a docs/audits de una extracción limpia del SHA auditado, instalar requirements-heston.txt y ejecutar desde su raíz `python docs/audits/repro_phase1_3a294af_cache.py`. El script solo modifica copias temporales. Wrapper de tests/hashes `repro_phase1_3a294af_tests.py`, ejecutable del mismo modo. Los resultados actuales permanecen intactos.
