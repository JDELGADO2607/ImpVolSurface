# Criterios antes de evaluar resultados

Actualización humana22-nov vigente: evaluar rigor matemático, precisión y resultados reales, reproducción limpia básica e integración académica. La robustez ante artefactos artificialmente alterados se documenta como limitación, sin bloquear salvo impacto real demostrado. F4-H2 aceptado expresamente, no reparado; no omitir esta distinción en el informe final. El historial de criterios/pruebas permanece abajo. Fase5 se rige por [PHASE_5_START](../orchestration/PHASE_5_START.md), fijado antes de sus resultados; no exige framework de validación/caché ni nueva campaña de corrupción de archivos.

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

Estado inicial SUPERSEDED: las tolerancias vigentes se fijan por fase en los informes aprobados y especificaciones enlazadas abajo. No ejecutar selección oportunista de resultados para fijarlas después. No aceptar un mínimo artificial de tamaño de muestra. Reducciones justificadas de dominio conservan cobertura y comparación común.

Una limitación de modelo/datos puede documentarse y aceptarse si el objetivo académico continúa siendo viable. Bloqueos fundamentales detienen la siguiente fase. Máximo tres reparaciones razonables por fase.

Gate PoC fijado antes de calibracion en [auditoria 0fb8758](../audits/HESTON_PHASE_0_0fb8758.md). MAE train 0,080/RMSE0,120 USD, holdout por split MAE0,100, presupuesto numerico0,002. Diagnosticos relativos no constituyen rechazo aislado. Ver informe para dominios y limitaciones.

## Gate predeclarado para fases2/3

Fase2 implementa, no autoriza calibracion. Especificacion PHASE_2_START.md: doce smoke valuations (K11/12.33/15,31/94d, europeas y americanas) a vector PoC y curva comunes, max error inicial0.01USD frente a referencia refinada; equivale a un tick para detectar errores de implementacion. Ademas stencils, payoff, obstaculo, frontera v0, xi0/v0=theta y refinamiento separado.
Fase3 realizara matriz mas amplia independiente, objetivo0.002USD (un quinto de tick) con error de referencia y dominio medidos. Estos umbrales corresponden a gates distintos, no a relajar un criterio tras ver resultados. No presentar precision inicial como validacion definitiva. No sustituir convergencia por coincidencia puntual. Fase3 se especificara por completo antes de ejecutar su seleccion de casos.

Especificacion completa de fase3 fijada antes de sus resultados: [PHASE_3_START](../orchestration/PHASE_3_START.md), baseea0df6f. Mercado97 con defaults y malla fina, matriz108 precios/seis regimenes, limites y propiedades economicas con propagacion de incertidumbre. No calibracion en fase3 ni aprobacion de dominio global basada en una malla finita.

Fase3 aprobada en09d9beb tras tres reparaciones; ver auditoria correspondiente. Criterios de fase4 fijados antes de ejecutar: [PHASE_4_START](../orchestration/PHASE_4_START.md), base09d9beb. Tres refinamientos locales QL desde2/5/1 historicos, seleccion por SSE fino train60 y convergencia valida, benchmark PoC conservado, holdouts22/15 solo evaluados despues. Mantener gates de ajuste0.080/0.120 train y0.100 MAE holdout; propio/QL0.002USD y control de referencia0.0005USD. No cambiar datos, bounds ni nucleo para mejorar ajuste. Metricas IV consistentes se completan en fase5, sin sustituciones por volatilidad instantanea.
