# Auditoría independiente Heston fase 2 — reparación 1

SHA auditado `ea0df6f097904352e5345bb6fbc712008e319bf2`, publicado en PR#5. Base comparada `cd5ed3e08794af474cee1d56a5862eb1a8647d79`. Extracción limpia e inmutable; Codex no modifica el motor que audita. Publicación del informe en rama de coordinación, PR#4, con commit distinto del auditado.

**PHASE_APPROVED — PHASE_2**, limitado a construcción del motor propio de puts y controles iniciales. Se autoriza **PHASE_3: validación numérica amplia**, según [criterios predeclarados](../orchestration/PHASE_3_START.md). No habilita calibración definitiva, IV, griegas de cartera, integración ni merge. La calibración será fase4 tras aprobar fase3.

## Reproducción y resolución de hallazgos

38 tests de fases0/1/2 aprobados en59.79s. Hashes de todos los archivos existentes bajo data/,docs/,results/ antes/después: cero cambios. Cinco hashes del manifiesto de salidas fase2 coinciden con los archivos publicados.

| Hallazgo previo | Estado para aprobar fase2 | Evidencia |
| --- | --- | --- |
| F2-M1 MEDIUM: contratos y sensibilidades no soportados | RESOLVED | Calls/tipos distintos de P/PUT rechazados antes de valorar, incluso a T0. Theta=None. Derivada respecto a v0 explícita, unidades y alias vega documentados como preliminares. |
| F2-M2 MEDIUM: identidad IT confundida con EDP y falsas M-matrices | RESOLVED en controles materiales; residuos editoriales LOW | Nombre/unidades algebraicas, diagnóstico diferencial separado y advertencia de que no mide por sí solo el continuo. Se reconoce signo de matrices y se corrige fase3/4. No se aprueba el guion como demostración matemática. |
| F2-L1 LOW: overshoot cúbico y frontera europea no exacta | LIMITACIÓN ACEPTADA, continúa abierta para validación | No se cambia el algoritmo ni se ocultan errores con clipping. La evidencia previa demuestra escala pequeña en los casos concretos, no una cota universal. |

No queda defecto material demostrado que impida el alcance inicial de fase2. Se conserva un pendiente documental LOW descrito abajo; no se abre otra ronda solo por ello.

## Comprobaciones independientes de esta reparación

El auditor ejecutó tipos C,CALL,binary,X y cadena vacía, tanto a T0 como31/365: todos levantan ValueError. La protección ocurre antes del caso de vencimiento y evita el contraejemplo de call con precio43.93USD frente a cota77.72USD. P y PUT son equivalentes en una prueba adicional, diferencia0.

Se reprodujeron los12 precios de puts del pipeline: máximo desacuerdo6.66e−15USD. En todos esos resultados theta es None; d_price_d_v0 coincide con su alias y ambos campos de complementariedad coinciden según su semántica explícita. No se afirma haber validado esas derivadas como griegas operativas.

La reparación no altera etapas de precio MCS–IT para P. La auditoría anterior sigue aportando comparación contra QuantLib refinado, máximo0.000330390USD en12 puntos; límites xi0 exacto contra BS/CRR/EDP1D; ampliación de dominio; y controles sobre contraejemplos históricos. Evidencia [informe anterior](HESTON_PHASE_2_cd5ed3e.md) y [scripts/log](HESTON_PHASE_2_cd5ed3e_evidence.txt). No se recalibró ni se repitió ese conjunto completo innecesariamente.

El diagnóstico temporal incorporado reproduce los valores independientes congelados antes de esta reparación:

| Pasos | Identidad algebraica IT | Defecto interior brutoUSD | Norma por añoUSD/año |
| --- | ---: | ---: | ---: |
| 20 | 0 | 0.0051840138373 | 0.41472110698 |
| 40 | 0 | 0.0009930245098 | 0.15888392156 |
| 80 | 0 | 0.0002022464757 | 0.06471887222 |

Máximo desacuerdo entre diagnóstico nuevo y CSV4.96e−17USD. El código de esta función reutiliza el diagnóstico del auditor: la independencia de su evidencia proviene de su elaboración y ejecución antes de la reparación, no de presentar dos copias del mismo algoritmo como dos pruebas independientes. Es un control trapezoidal local con tasa plana e interior específico; no el residuo exacto del paso MCS ni una demostración del error global del problema continuo.

## Pendiente editorial LOW y límites aceptados

F2-L2 LOW, informe de implementación secciones8/9: subsisten frases de estabilidad incondicional/segundo orden universal en el guion y cifras del cuadro temporal que difieren levemente del CSV. El ratio del defecto bruto no es el ratio de la norma dividida por dt: los segundos son2.6102 y2.4550. Tres niveles decrecientes no prueban orden global para todo payoff, frontera y parámetro. El guion es borrador **no aprobado para defensa**; deberá reconciliarse con evidencia y restricciones antes de fase8. En fase3 se debe marcar ese estado y evitar usarlo como certificado de precisión/estabilidad.

No se requiere rediseñar el algoritmo para sostener una frase ni abrir una reparación documental reiterativa ahora. La aprobación técnica descansa en implementación y precios comprobados, con dominio limitado, y no avala las afirmaciones restantes del guion. El error pequeño de F2-L1 se reportará en el estudio amplio, sin clipping.

La muestra97/60/22/15, vector Q, curva y spot permanecen congelados. El contraste inicial no valida todos los regímenes Heston, signos de rho, Feller incumplido, vencimientos y grillas. Tampoco valida superficie equivalente, identificación de parámetros ni rentabilidad de estrategias. Los benchmarks históricos SVI conservan sus limitaciones. No se interpreta paso inicial de0.01USD como presupuesto final; fase3 mantiene objetivo0.002USD con error de referencia estimado.

## Próxima acción autorizada

Gemini recibe PHASE_START fase3 con matriz fijada antes de resultados:97 puts al vector PoC y defaults reales frente a mallas finas; seis regímenes paramétricos y108 precios europeos/americanos; casos xi0 y v0=0; comparación económica, regularidad, ejercicio, refinamientos de tiempo/espacio/dominio y trazabilidad. No calibrar parámetros ni cambiar muestra. Si falla un régimen, reportarlo y solicitar reparación focalizada o restricción justificada; no relajar umbrales ni omitirlo.

Entregar SHA publicado y PHASE_READY_FOR_AUDIT para revisión independiente antes de fase4. Sin merge/force-push, gastos ni extensiones de modelo. Implementación y auditoría continúan en ramas separadas.

Reproducción: copiar `repro_phase2_ea0df6f.py` y `repro_phase2_ea0df6f_tests.py` desde coordinación a docs/audits de una extracción limpia del SHA auditado; ejecutar desde raíz con requirements-heston.txt. Log `HESTON_PHASE_2_ea0df6f_evidence.txt` y tabla `HESTON_PHASE_2_ea0df6f_replay.csv`. Los scripts no escriben artefactos oficiales. El commit del informe queda identificado en el historial de este archivo y en HANDOFF.
