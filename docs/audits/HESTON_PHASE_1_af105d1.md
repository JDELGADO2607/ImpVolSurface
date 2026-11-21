# Auditoría independiente Heston fase 1 — reparación 1

SHA auditado `af105d1b221d4b096695b979fb72bc55834cf47e`, publicado en PR de implementación #5. Base comparada `d6a369c3b636ee0ddb539ddf1938664b54107c4a`. Auditor Codex, extracción limpia en directorio temporal, sin modificar implementación. Rama de publicación independiente `JDELGADO2607/heston-coordination`, PR #4. El commit del informe es distinto del auditado y se obtiene del historial de este archivo.

Dictamen **PHASE_REJECTED**, reparación focalizada **2/3**. La PoC conserva evidencia favorable de ajuste; no se autoriza todavía el solver propio. Hallazgos abiertos: 0 BLOCKER,1 HIGH,1 MEDIUM,0 LOW clasificados; observaciones opcionales separadas. El rechazo corresponde a integridad de reutilización de calibraciones y documentación matemática y numérica, no a una conclusión de inviabilidad de Heston.

## Resultado de la revisión anterior

| Hallazgo | Estado | Evidencia |
| --- | --- | --- |
| F1-01 HIGH, malla productiva fuera de presupuesto | RESOLVED en el dominio numérico probado | Se unificó producción y se separaron refinamientos; véase evidencia independiente adjunta. Una malla finita no establece una cota global del error. |
| F1-02 MEDIUM, documentación inconsistente | PARTIALLY_RESOLVED | Conteos y muchas tablas por tenor corregidos. Persisten errores en comparativa, interpretación y algoritmo documentado. |
| F1-03 MEDIUM, diagnósticos vacíos y clipping | RESOLVED para el gate PoC inspeccionado | Precios crudos por defecto, pendientes divididas y frontera NOT_TESTABLE, transiciones temporales y gate integral. No equivale a demostrar ausencia global de arbitraje. |

## Pruebas independientes

17 tests de fases 0 y 1 aprobados en 20,63 segundos. Hashes de archivos bajo data/, docs/ y results/ presentes antes y después de pytest: cero cambios. La evidencia cubre archivos existentes; no se afirma una certificación universal de aislamiento para todo test futuro.

Se revaloran mediante construcción directa de contratos y motores QuantLib los 97 precios, sin usar el wrapper de valoración para NPV. Producción tFactor300, mínimo60, x160/v80; refinamientos temporal500/min100, espacial240/120 y conjunto. Se refinan adicionalmente los casos de mayor desviación hasta tFactor900/min180, x320/v160. Scripts y logs adjuntos contienen los valores exactos. La evaluación no repite los veinte minutos de optimización: conserva candidatos publicados y reproduce sus objetivos a mayor resolución.

Métricas de producción recalculadas sobre los mismos contratos:

| Partición | N | MAE USD | RMSE USD |
| --- | ---: | ---: | ---: |
| Train | 60 | 0.0257837070 | 0.0380001077 |
| Strike holdout | 22 | 0.0210862642 | 0.0265887561 |
| Tenor holdout | 15 | 0.0204274251 | 0.0263866142 |

No cambios de selección respecto a la entrega previa, sin rechazos adicionales: 97/97 evaluadas. Holdouts no entran al objetivo inspeccionado; no se los utiliza para elegir parámetros en esta auditoría. El ajuste pasa los criterios predeclarados. La correlación seleccionada continúa cerca del límite de búsqueda y la dispersión predictiva de candidatos a K17/794d ronda0.04517 USD: limitaciones de identificación que deben declararse, no ocultarse.


Objetivos finos reproducidos con factor200,minimo25,x200,v100 (SSE en USD2):

| Inicio | SSE fina |
| --- | ---: |
| 1 | 0.08833666095450823 |
| 2 | 0.08676170871978404 |
| 3 | 21.46878391010828 |
| 4 | 0.08948211442410489 |
| 5 | 0.08791652157519067 |

Start2 sigue siendo el menor de los cinco evaluados, sin demostrar optimo global. El candidato3 muestra fuerte sensibilidad numerica y no se usa como referencia de valoracion.

## F1-04 HIGH — Caché no vinculada a datos ni objetivos, defecto demostrado

Archivo `src/heston/pipeline_phase1.py`, líneas57–62,94–95,113–150. La interfaz promete reutilizar resultados con hashes válidos. En realidad calcula hashes de los inputs actuales, pero no los compara con los inputs de la calibración guardada. Basta que exista `heston_multistart_results.csv`. Selecciona por la columna guardada final_sse sin validar su consistencia matemática, sin recalcular objetivo y sin comprobar metadatos de la calibración ni resultados finos.

Reproducción aislada, dos casos independientes:

1. Copiar data/heston a un directorio temporal, conservando manifiesto y candidatos. Aumentar únicamente la primera lastPrice de train en0.01 USD. El pipeline anuncia resultados verificados y acepta el candidato guardado sin invalidar la caché.
2. Con datos sin modificar, cambiar únicamente final_sse del candidato3 a−1. El pipeline selecciona ese candidato como mejor. Por definición SSE=sum(error_i^2)>=0. No hay error de redondeo que justifique−1.

El script intercepta la primera valoración después de la selección para evitar una regeneración innecesaria y no usa ese precio como prueba de fallo financiero. Demuestra aceptación de caché inválida; no afirma que estas entradas manipuladas completarían el gate con PASS. No hay evidencia de manipulación de los candidatos actualmente publicados: el defecto afecta la capacidad del pipeline de distinguirlos de resultados antiguos/inválidos.

Consecuencia: una ejecución con datos nuevos puede presentarse como calibración verificada de esos datos cuando realmente reutiliza parámetros de otra muestra. Objetivos y clasificación guardados pueden contradecir los parámetros. Es una regresión introducida por el nuevo camino de reutilización.

Reparación mínima: caché explícitamente ligada a hashes de train/curva/spot/dividendos y especificación del objetivo, malla de calibración, bounds y versión pertinente; validar esquema, finitud, SSE no negativa, coherencia RMSE y límites paramétricos. Comparar huellas antes de usar; ante incompatibilidad fallar claramente o recalibrar explícitamente. Reproducir SSE de los candidatos al reutilizarlos con tolerancia de serialización justificada. Conservar por separado SSE original y SSE de malla fina, con tablas exportadas. Añadir tests negativos que ejecuten esta ruta y no solo lean CSV. No crear infraestructura genérica de caché.

## F1-02 MEDIUM — Persiste documentación matemática y comparativa incorrecta

`docs/reports/INFORME_FASE_1_POC_HESTON.md`:

- Línea153 escribe término cruzado rho*sigma*sqrt(v)*S*V_Sv. Bajo la dinámica de esta fase, d<S,v>/dt=(sqrt(v)S)(xi sqrt(v))rho=rho*xi*v*S. El coeficiente correcto es rho*xi*v*S*V_Sv. El motor externo usa su propia implementación; el defecto demostrado está en la explicación que serviría de base al solver propio.
- Línea155 declara Gauss-Lobatto adaptativo con precisión~1e−7. El código llama AnalyticHestonEngine(model) sin tolerancia: la firma instalada indica integrationOrder=144. No corresponde al overload relTolerance/maxEvaluations. Documentar la cuadratura realmente invocada y separar orden de integración de precisión demostrada. `FdHestonVanillaEngine.__init__.__doc__` especifica default `FdmSchemeDesc::Hundsdorfer()`, no una selección indeterminada entre esquemas.
- Línea86 dice “Mínimo Global Óptimo”. Cinco búsquedas locales solo establecen mejor candidato encontrado. La sección2.4 copia SSE original de Start2 como si fuera fina; publicar valores calculados en una tabla y distinguir mallas.
- Líneas163–165 no concilian con la tabla común84. CSV recalculado: Heston MAE0.0231579537, RMSE0.0339213925, máximo0.1822813648; flat MAE0.0396743356, RMSE0.0602891639, máximo0.3333143939; SVI MAE0.0684416667, RMSE0.0885792872, máximo0.2463. Informe publica máximos0.1889/0.2450/0.3120. El error del baseline de0.245 a0.333 es material para interpretar colas.
- Línea128 exige información temporal explícita o regularización de Feller como conclusión de dispersión. La dispersión no implica esa necesidad; Feller no asegura identificación. No está autorizada una nueva obligación metodológica. Conservar Heston clásico global Q y reportar incertidumbre, sin agregar datos ni regularización para favorecer el resultado.
- Línea196 certifica ausencia total de arbitraje. Los diagnósticos son finitos; la dinámica común aporta estructura teórica, pero no demuestra propiedades globales del aproximador numérico. Cambiar la afirmación por resultado numérico con dominio y tolerancias.
- K30 para put con spot12.33 es ITM profundo, no OTM. Su cercanía al intrínseco corresponde al ejercicio inmediato en estos parámetros, no a una identidad terminal general. Enlaces file:/// de una máquina local no son evidencias accesibles en GitHub; usar relativos.

Fuentes de comprobación: firmas del QuantLib1.44 instalado, guardadas en evidencia; [constructor de referencia de FDM](https://github.com/lballabio/QuantLib/blob/v1.40/ql/pricingengines/vanilla/fdhestonvanillaengine.hpp) y [fuente del motor europeo](https://github.com/lballabio/QuantLib/blob/v1.40/ql/pricingengines/vanilla/analytichestonengine.cpp), consultadas como referencias auxiliares de otra versión, no prueba de identidad binaria1.44.

## Observaciones no bloqueantes y límites

La tolerancia de0.002USD no se traslada dimensionalmente sin cálculo a una segunda diferencia dividida en USD inversos. Para futuras mallas estrechas propagar el error de precios a pendientes/butterfly: con error absoluto epsilon y pesos convexos, la incertidumbre del defecto en precios es como máximo2epsilon. No se demuestra aquí una violación material por esa elección de tolerancia en los nodos publicados.

Las pruebas nuevas de shape/malla leen mayormente CSV. La auditoría aporta cálculo independiente, pero las regresiones futuras requieren al menos casos ejecutados contra los motores. No se autoriza ampliar a una batería innecesariamente costosa.

La afirmación de “97 puts con máxima0.000605” debe distinguir puntos observados y puntos diagnósticos sintéticos: K17/794d no pertenece a las cinco puts observadas de ese vencimiento. No confundir cobertura de calibración con cobertura de diagnóstico.

La curva sigue siendo aproximación basada en instrumentos sintéticos CMT, no reconstrucción de bonos individuales observados. Las llamadas externas son contraste de una instantánea; la comparación común con SVI usa una curva histórica distinta y mezcla train/holdout. Las reducciones de MAE no identifican causalmente una mejora pura del modelo ni un backtest.

No se ejecutó pipeline global histórico ni se amplió a módulos posteriores que no cambiaron. La siguiente reparación no requiere multistart completo si los candidatos y sus metadatos son verificables; un refinamiento fallido del tercer candidato de Feller bajo es evidencia diagnóstica, no razón para imponer Feller a priori.

## Recomendación y siguiente acción

Viabilidad de ajuste de PoC favorable, integridad del pipeline pendiente. Una reparación adicional2/3 limitada a F1-04 y F1-02, sin tocar muestra, límites, función objetivo, tolerancias, parámetros por vencimiento ni módulos históricos. Publicar nuevo SHA y PHASE_READY_FOR_AUDIT; no iniciar fase2 hasta PHASE_APPROVED.

Evidencia adjunta: `repro_phase1_af105d1.py`, `repro_phase1_af105d1_cache.py`, `HESTON_PHASE_1_af105d1_evidence.txt`, `HESTON_PHASE_1_af105d1_reprice.csv`. Con dependencias de requirements-heston.txt, ejecutar desde extracción limpia: `python repro_phase1_af105d1.py` y `python repro_phase1_af105d1_cache.py` con PYTHONPATH apuntando a la raíz. Los scripts son diagnósticos del auditor y no modifican artefactos oficiales.
