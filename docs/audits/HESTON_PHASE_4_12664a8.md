# Auditoría Heston fase4 — reparación1/3

Fecha22-nov-2026. **PHASE_REJECTED**, SHA exacto **12664a8ca88fd9c3f365fe449391af9deeb5f19d**, rama JDELGADO2607/heston-implementation, [PR5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5). Publicación confirmada con ls-remote. Auditoría en extracción git archive limpia e independiente; el informe se publica en coordinación/[PR4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4), sin cambios de implementación ni merge.

## Dictamen

La reparación avanza materialmente: runner de optimización y tres JSON publicados, replay de SSE, API de valoración corregida, eliminación de retornos por mera existencia de fase4, selección por diferencias efectivas de precios train y vector canónico conservado. Los precios muestreados continúan dentro del presupuesto de precisión. No hay nuevo fallo demostrado del núcleo Heston.

Continúa **F4-H2 HIGH** por finitud, procedencia de fase3 y controles de malla incompletos. **F4-M2 MEDIUM** queda parcialmente resuelto: principales cifras comparativas corregidas, pero subsisten garantías matemáticas no justificadas y discrepancias documentales. Conteo abierto de fase4: **0 BLOCKER,1HIGH,1MEDIUM,0LOW**. No se añaden nuevos defectos materiales; se acota lo que falta de los ya registrados. Se autoriza reparación2/3, sin nueva optimización ni fase5.

## Matriz de hallazgos anteriores

| ID | Estado | Evidencia |
| --- | --- | --- |
| F4-H1 HIGH, reproducción/API | RESOLVED en entregables y controles examinados | JSON A/B/C y runner con optimización/replay publicados; API fresca y extra-fina ejecutadas bajo vector distinto |
| F4-H2 HIGH, integridad | PARTIALLY_RESOLVED | Ya rechaza precio+1, archivo obligatorio ausente, parámetros inválidos y todos los refinamientos fallidos; aún aprueba NaN/Inf y referencias de malla alteradas con flags favorables |
| F4-M1 MEDIUM, selección/convergencia | RESOLVED en control material | Exige refinamiento local convergido, cuantifica cambios en los60train y conserva PoC como decisión académica dentro del presupuesto; la equivalencia no prueba sobreajuste |
| F4-M2 MEDIUM, informe | PARTIALLY_RESOLVED | Flat/SVI/Heston principales reconciliados y sensibilidad ampliada a12contratos; sobreviven afirmaciones globales y algunos conteos/cifras |
| F4-L1 LOW, redondeo | RESOLVED dentro de precisión de máquina | Vector actual difiere del original solo a~1e-15, no a seis decimales; se conservan y documentan arranques históricos aproximados |

## Controles independientes y resultados

Reejecución: **80tests PASS en134.27s**, fases0–4. Hashes antes/después de todos los archivos en data/docs/outputs/results/figures: **sin cambios, altas ni bajas**. No usar ese resultado como sustituto de los controles siguientes. Scripts publicados: `repro_phase4_12664a8_controls.py`, `repro_phase4_12664a8_tests.py` y log consolidado `HESTON_PHASE_4_12664a8_evidence.txt`.

Las pruebas de gate llaman **step10_build_manifest real**, con copias temporales de las salidas requeridas y datos financieros legítimos, alterando un elemento cada vez:

| Caso | Resultado |
| --- | --- |
| Legítimo | PASS |
| Precio fino+1USD conservando resumen | REJECTED |
| Precio fino NaN | **PASS**, se omite implícitamente de MAE/RMSE y discrepancia |
| Referencia QL fina NaN | **PASS** |
| lastPrice NaN | **PASS** |
| Precio propio default Inf | **PASS** |
| Archivo económico ausente | REJECTED |
| Varianza inicial negativa | REJECTED |
| Todos los refinamientos locales fallidos | REJECTED |
| Precio de malla QL1000 desplazado1USD y error declarado1USD, flagsPASS conservados | **PASS** |
| Etiqueta de partición de un contrato incorrecta | **PASS**, la agrupación usa IDs canónicos pero no reconcilia la etiqueta publicada |
| Resumen train59 con97precios correctos | **PASS**, métricas raw correctas pero se exporta resumen contradictorio |

Los dos últimos son inconsistencias de artefactos, no prueba de que el cálculo de MAE utilice mal los IDs. Se distinguen del defecto de finitud, que sí reduce el número de observaciones realmente evaluadas sin reducir la cobertura declarada.

### F4-H2: causa y consecuencias

`pipeline_phase4.py:1283` valida longitud/IDs y`:1301` calcula agregados, pero no exige finitud previa de las columnas numéricas obligatorias. `np.mean`, `np.max` aplicados a Series pandas delegan a reducciones que omiten NaN por defecto. Por tanto60filas no equivalen a60residuos válidos. Un error de valoración puede desaparecer del agregado y reportarse cobertura completa.

Ejemplo: train legítimo MAE0.02573726190963425/RMSE0.037979063096091094; al sustituir el primer precio porNaN obtiene MAE0.025665012111492455/RMSE0.038099903024791416 y conserva PASS. No toda omisión mejora todas las métricas; el defecto es la omisión no declarada. Defaults infinitos ni siquiera participan en los gates de finitud actuales.

`pipeline_phase4.py:1349`/`:1350` sigue comprobando flags de refinamiento, en lugar de reconstruir diferencias de los precios. La prueba desplaza QL1000+1USD y mantiene booleanos antiguos: PASS. El propio productor step6 calcula correctamente cuando se ejecuta fresco, pero el cierre no acredita los valores que recibe/publica. El encargo anterior exigía comprobarlos por valores.

La reutilización en `pipeline_phase4.py:567`–`:583` verifica una proximidad de vector y una etiqueta PASSED del manifiesto, pero no hashes del archivo, inputs o código. Además `np.allclose` conserva su rtol por defecto pese a describir identidad canónica. Prueba adicional **sobre step5 real**, usando un contrato real NU261218P00012000 en una copia temporal: alterar su precio fino propio de fase3 aNaN conservando manifiesto original produce `prop_fine_price=null`, `status_discrepancy_gate_002=FAIL` y **valuation_provenance=PHASE3_VERIFIED_AUDITED**. El cierre anterior permite precisamente esos NaN. Esta prueba de etapa usa un contrato para ahorrar cómputo; el control independiente del agregador usa los97IDs completos. No se afirma haber ejecutado un pipeline entero corrupto durante decenas de minutos.

Corrección mínima: `isfinite` explícito sobre columnas obligatorias antes de reducir, igualdad de IDs/particiones/datos de mercado con fuente canónica y ausencia de excepciones no declaradas; comprobar los3precios de malla/referencias y sus diferencias sin confiar en flags; antes de reutilizar fase3 usar su verificador ya existente con inputs/código/parámetros/tablehashes. Alternativa: desactivar esa reutilización y valorar fresco. No crear un framework de caché ni volver a calibrar.

### API y motor: controles favorables

Se ejecutaron step5 y step6 reales en una copia de datos con un contrato31d,K12, usando v0=0.20 y el resto del vector conservado, con etiqueta WINNER_NEW_OPTIMUM. La prueba fuerza valoración fresca y extra-fina sin alterar el motor: precio propio fino **0.4715874002USD**, QL700 **0.4716160337USD**, discrepancia **0.0000286335USD**; sensibilidad QL700/1000 **0.0000159258USD**, propia fina/extra **0.0000411747USD**. Se cierra el TypeError anterior; no se atribuye validación universal del dominio a este caso.

El runner publicado permite recrear optimizaciones mediante `python -m src.heston.run_refinements --optimize all` y verificar originales mediante `--replay-only`. El auditor ejecutó el segundo; resultados detallados en evidencia. No se repiten las optimizaciones históricas por mera rutina. La coincidencia de SSE demuestra reproducción del objetivo bajo esos vectores; no es una certificación forense independiente de cada evento de la traza original.

Replay observado: A SSE inicial0.08664053018236909/final0.08662191655501233; B0.08784052169683074/0.08783275332557498; C0.08825896423071354/0.0881999529309007. Las seis diferencias frente a JSON fueron0.00e+00. A/B conservan status0 y Cstatus2, sin convertir el fallo en éxito. El runner ejecutado no escribe artefactos en modo replay.

## F4-M2: límites que debe respetar el informe

`INFORME_FASE_4_CALIBRACION_HESTON.md`, secciones4,9,10: el texto aún dice que elegir A **constituiría** sobreajuste numérico; que aumentos en coordenadas aisladas evidencian convexidad local; y la tabla denomina Heston **Óptimo Global Libre de Arbitraje**. Tres refinamientos locales no prueban mínimo global. La equivalencia frente a un presupuesto de error no prueba que la pequeña mejora sea ruido. La función `f(x,y)=x²+y²-4xy` crece en ambas coordenadas desde0 y decrece en la direcciónx=y: sensibilidad aislada no prueba convexidad multidimensional. Estas son afirmaciones no justificadas, no precios erróneos demostrados.

La decisión defendible es conservar PoC por continuidad y materialidad académica, reconociendo que A mejora ligeramente el SSE train. Ausencia de arbitraje de la dinámica ideal y propiedades del evaluador numérico deben presentarse por separado; ensayos finitos no prueban propiedades globales del discretizador.

Otros residuos a reconciliar en la misma corrección: la sección1 asigna2/5/8contratos a tenores retenidos37/94/304d; el split efectivo contiene7/5/3. La tabla histórica de sección2 conserva ratiosFeller equivocados y el salto fino de start3 citado1.77 frente a21.46878 de fase1. El JSON ganador mezcla0.00043USD con0.015centavos y0.00184USD con0.084centavos: corresponden aproximadamente0.043/0.184centavos. El manifiesto runtime0.0 no es el tiempo de una regeneración end-to-end; distinguir ensamblado/replay/calibración. Nada de esto exige modificar primas, parámetros ni tolerancias para coincidir con la prosa.

## Procedimiento, límites y siguiente acción

Ejecutar los scripts adjuntos desde cwd del SHA12664a8 con dependencias versionadas. Los diagnósticos cambian únicamente archivos temporales. El replay no escribe resultados oficiales. No se reejecutó el pipeline global histórico ni toda la valoración/calibración: el núcleo no cambió, la reparación afecta interfaces y validación. El siguiente gate sigue siendo este mismo ámbito, no una cuarta ronda de fase3.

No hay evidencia actual de precios finales no finitos en los artefactos legítimos: los NaN/Inf son pruebas negativas deliberadas. Su aceptación contradice explícitamente la cobertura y las reglas de rechazo requeridas. Por eso se mantiene HIGH, aunque el snapshot legítimo pueda tener precios económicamente razonables.

**PHASE_REJECTED** para12664a8. Autorizar únicamente [reparación2/3](../orchestration/PHASE_4_REPAIR_2.md), finitud/procedencia/mallas y reconciliación de informe. F4-H1/F4-M1/F4-L1 no requieren nuevas optimizaciones. Última aprobación global por fase sigue siendo09d9beb, no el SHA de esta reparación. Fase5 y merge siguen pendientes.
