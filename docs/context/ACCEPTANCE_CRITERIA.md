# Criterios antes de evaluar resultados

Propietario Codex. Versionar cualquier cambio de criterio y su motivo antes de seleccionar resultados. Una tolerancia debe relacionarse con escala de precio, granularidad observada y error numérico medido, sin presuponer bid/ask fiable. Fase 0 propondrá presupuesto de error y criterios cuantitativos para PoC; Codex los fijará antes de la calibración.

| Fase | Evidencia exigida para aprobar |
| --- | --- |
| Contexto | Archivos enlazados, fuentes e historia distinguidas, SHA publicado y lectura confirmada por Gemini |
| 0 | Manifiesto de inputs, puts válidas y descartes, soporte, fuente de tasas y convenciones, dependencias/versiones, benchmarks reproducibles y split congelado |
| 1 | AmericanExercise y FdHestonVanillaEngine efectivos, objetivo USD, parámetros globales válidos, multistart, logs de convergencia, Feller reportada, coste y refinamiento, errores por tenor y holdout en muestras comunes |
| 2 | Stencils, frontera v=0 y truncamiento justificados, ADI publicado con obstáculo, tests iniciales europeos y americanos |
| 3 | Comparación independiente QuantLib en grilla de K,T,rho,v, refinamiento espacial/temporal y de dominio, límites económicos y residual complementario, límite xi=0,v0=theta, europeo semianalítico |
| 4 | Parámetros Q definitivos, control de error durante ajuste, comprobación fina y multistart, sensibilidad e identificación separada de estabilidad predictiva |
| 5 | Precios válidos antes de IV, inversión americana/europea separada, residual y excepciones explícitos, calls observadas externas |
| 6 | Modelos y unidades en griegas coherentes, mallas comparables, cartera única, capital declarado aproximado si corresponde, P&L nulo y reconciliación, forecast causal |
| 7 | Pipeline aislado desde insumos, hashes y esquemas, pruebas sin escrituras oficiales, métricas sobre muestras comunes, actualización del registro de hallazgos |
| 8 | Documento técnico, resumen, guía cronometrada de diez minutos, defensa comprensible, cifras derivadas verificadas |

Precisar en fase 0 la matriz de benchmark y partición sin fuga. Para fase 1, valorar error de calibración frente a dispersión e iliquidez, sin exigir ganar a SVI in-sample. Registrar todos los starts incluidos los fallidos y cobertura de predicción. Una solución pegada a límites o parámetros muy distintos con precios equivalentes exige diagnóstico de identificación.

La convergencia requiere al menos tres resoluciones y variación separada de espacio, tiempo y dominio cuando el caso lo requiera. Una coincidencia entre dos motores a una resolución no basta. Error comparativo se confronta con estimaciones independientes de ambos motores. Los fallos económicos deben exceder error numérico justificado para clasificarse materiales.

No hay tolerancias numéricas definitivas aprobadas todavía. No ejecutar selección oportunista de resultados para fijarlas después. No aceptar un mínimo artificial de tamaño de muestra. Reducciones justificadas de dominio conservan cobertura y comparación común.

Una limitación de modelo/datos puede documentarse y aceptarse si el objetivo académico continúa siendo viable. Bloqueos fundamentales detienen la siguiente fase. Máximo tres reparaciones razonables por fase.

Gate PoC fijado antes de calibracion en [auditoria 0fb8758](../audits/HESTON_PHASE_0_0fb8758.md). MAE train 0,080/RMSE0,120 USD, holdout por split MAE0,100, presupuesto numerico0,002. Diagnosticos relativos no constituyen rechazo aislado. Ver informe para dominios y limitaciones.
