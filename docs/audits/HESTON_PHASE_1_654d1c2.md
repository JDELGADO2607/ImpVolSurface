# Auditoría independiente Heston fase 1 — cierre de PoC

SHA auditado y técnicamente aprobado `654d1c2d05a0301dc3068cdc34219df3d42d2af7`, publicado en PR#5. Base del diff `3a294af73f0215e0435223d20015545245164bdf`. Publicación del auditor separada en rama JDELGADO2607/heston-coordination, PR#4. El commit del informe es distinto del de implementación y queda identificado por el historial y HANDOFF.

**PHASE_APPROVED — PHASE_1**. Se autoriza iniciar PHASE_2 conforme a [especificación publicada](../orchestration/PHASE_2_START.md). La aprobación corresponde a la viabilidad de esta PoC QuantLib y a este SHA exacto; no aprueba el PR global, no habilita calibración con solver propio ni sustituye revisión humana final. No se ejecuta merge.

## Evidencia de cierre

Extracción limpia del SHA;25 tests de fases0+1 aprobados en27.74s. Hashes de todos los archivos existentes bajo data/, docs/, results/ antes/después de pytest: cero cambios. Dependencias de requirements-heston.txt, QuantLib1.44.

Prueba independiente del camino positivo: se copian caché y manifiesto a directorio temporal y se ejecuta validate_and_load_multistart_cache con train y curva comunes reales. Se devuelve inicio2, parámetros v0=0.18613777847584, kappa=2.7254603668370714, theta=0.2136796992000426, xi=0.4817847258429695, rho=−0.9498066630129804. Ratio Feller5.0179586.

Las cinco SSE de calibración se reproducen mediante evaluación adicional directa del calibrador. Diferencia máxima con valores serializados1.84297e−13USD². La tabla fina recalculada coincide con la publicada hasta9.71445e−17USD².

| Inicio | SSE reproducida en malla de calibración |
| --- | ---: |
| 1 | 0.08806700976234906 |
| 2 | 0.08664898485384938 |
| 3 | 0.5861874690884654 |
| 4 | 0.08904358807667545 |
| 5 | 0.08779177256160134 |

El replay ahora se aplica a todas las filas. La selección de caché admite únicamente status0; los fallidos permanecen en evidencia. El contraejemplo anterior status2/SSE0 del inicio3 queda cubierto por pytest. El auditor prueba además otro inicio: conserva el vector del inicio4, fija SSE0 y RMSE0 en copia temporal. Se rechaza por objetivo real0.08904359USD², sin alterar precios ni invocar una valoración ficticia. Se prueban independientemente RMSE NaN,+inf y−1 en el inicio5; todos se rechazan antes de selección. Inputs: siete hashes válidos.

## Matriz de hallazgos de la fase

| Hallazgo | Estado para el SHA aprobado | Alcance de conclusión |
| --- | --- | --- |
| F1-01 HIGH, malla productiva fuera de presupuesto | RESOLVED | Evidencia previa reproducida sobre97 contratos y refinamientos adicionales; no cota global del error. |
| F1-02 MEDIUM, matemática y cifras documentales | RESOLVED en aspectos materiales | Fórmula cruzada, tabla84, mallas dinámicas, unidades/tolerancia de replay, timestamp oficial e identificación de motores reconciliados. |
| F1-03 MEDIUM, diagnósticos vacíos/clipping | RESOLVED para PoC | Precios crudos, pendientes divididas, fronteras no evaluables, temporal a K fijo y gate económico. |
| F1-04 HIGH, selección de caché sin verificar | RESOLVED en caminos examinados | Hashes comparados, finitud, coherencia de pérdidas, replay incondicional y elegibilidad explícita. No se afirma autenticación criptográfica ni cobertura de todo input imaginable. |

Ningún hallazgo material abierto impide el gate de esta fase. No se abre una cuarta ronda de reparaciones.

## Ajuste y evaluación fuera de muestra

El último commit solo modifica validador, tests e informe. No cambia datos, parámetros, motores ni precios exportados. Se conserva, con diff verificable, la evidencia numérica independiente de af105d1/3a294af. No se repite una calibración ni una regeneración completa por un cambio de validación.

| Partición | N | MAE USD | RMSE USD |
| --- | ---: | ---: | ---: |
| Train | 60 | 0.0257837070 | 0.0380001077 |
| Strike holdout | 22 | 0.0210862642 | 0.0265887561 |
| Tenor holdout | 15 | 0.0204274251 | 0.0263866142 |
| Calls externas | 142 | 0.0873293012 | 0.1281179680 |

97/97 puts evaluadas, sin reducción de cobertura ni nuevos rechazos. Ningún holdout se usa para elegir parámetros en la implementación inspeccionada. Los errores cumplen los criterios fijados antes del ajuste. Son particiones de una instantánea, no validación temporal histórica.

En la muestra común84: Heston MAE0.02315795USD, RMSE0.03392139, máximo0.18228136; baseline plano con curva común MAE0.03967434, RMSE0.06028916, máximo0.33331439; SVI histórico MAE0.06844167, RMSE0.08857929, máximo0.2463. La curva histórica de SVI difiere: la mejora conjunta no aísla causalmente el efecto del modelo.

La auditoría previa reprodujo los97 precios crudos con discrepancia8.88e−16USD; frente a refinamientos temporal/espacial/conjunto, máximos0.000396961/0.000281665/0.000417803USD. Refinamiento adicional tFactor900,x320,v160 en los tres casos más sensibles: máximo0.000606435USD, bajo presupuesto0.002USD. Las65 pruebas interiores de convexidad,32 fronteras no evaluables y75 transiciones temporales son controles finitos, no un teorema sobre el aproximador numérico entero. Véanse [informe](HESTON_PHASE_1_af105d1.md), [97 revaloraciones](HESTON_PHASE_1_af105d1_reprice.csv) y [evidencia](HESTON_PHASE_1_af105d1_evidence.txt).

## Límites aceptados y observaciones no bloqueantes

- Identificación: rho está cerca del límite de búsqueda; los candidatos cercanos producen dispersión de unos0.04517USD en K17/794d. No es evidencia de cinco parámetros identificados de forma única, ni justifica imponer Feller o ampliar el modelo.
- El candidato3 converge formalmente según el optimizador pero su SSE empeora notablemente al refinar; no se usa como precio operativo. El candidato4 no converge y es inelegible. No confundir estado del optimizador con convergencia numérica de una EDP.
- Tolerancia de replay1e−4USD² es conservadora frente al redondeo observado~1e−13. No se interpreta como error de precio. En la caché publicada no altera el ganador: la brecha2–5 supera dos veces esa tolerancia. Afinarla o seleccionar directamente por SSE recién calculada es mejora opcional; no se requiere otra reparación por ello.
- La elegibilidad reforzada está en la ruta de caché examinada. Una futura calibración definitiva debe mantener política coherente al crear nuevos candidatos y demostrar sus propios objetivos; esta aprobación no certifica toda optimización futura.
- Los artefactos conservan la ejecución oficial23:41:08Z de la entrega previa; este SHA añade validación, no una regeneración financiera. Los valores no se presentan como recalibrados nuevamente. La regeneración completa se reserva al gate de integración.
- Curva CMT basada en instrumentos sintéticos y disponibilidad histórica según fase0: no es reconstrucción de bonos individuales. Datos asíncronos y falta de spreads ejecutables limitan interpretación económica. Calls son contraste externo, no evidencia de calibración sobre calls.

No se validó aún solver propio, IV equivalente, nuevas griegas ni integración financiera. Las aprobaciones de fases0 y1 no resuelven por sí solas todos los hallazgos históricos de SVI/pipeline: su aplicabilidad se revisará en fase7.

## Próxima fase autorizada

PHASE_2 implementa el motor2D propio con método publicado MCS–IT y mallas/fronteras justificadas; QuantLib queda como referencia independiente. Debe entregar pruebas iniciales y diagnósticos. La validación extensa será fase3 y solo después se permitirá calibración definitiva. Los criterios se fijan antes de evaluar nuevos resultados, distinguiendo el gate inicial de implementación del presupuesto final de validación. No modificar SVI, muestra ni límites para favorecer el resultado.

Evidencia de esta auditoría: [script positivo y negativo](repro_phase1_654d1c2.py), [tests/hashes](repro_phase1_654d1c2_tests.py), [log](HESTON_PHASE_1_654d1c2_evidence.txt). Para reproducir, copiar los scripts desde la rama de coordinación a docs/audits de una extracción del SHA auditado y ejecutar desde raíz `python docs/audits/repro_phase1_654d1c2.py` y `python docs/audits/repro_phase1_654d1c2_tests.py`. Solo se modifican copias temporales y logs del auditor. No se aprueba ni ejecuta merge.
