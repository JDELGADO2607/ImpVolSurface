# Auditoría independiente — Heston fase 3, reparación 3/3

Fecha: 22-nov-2026. **Dictamen técnico: PHASE_APPROVED**, limitado a precios y dominios numéricos ensayados. Se autoriza fase4 según [especificación previa](../orchestration/PHASE_4_START.md); no constituye aprobación global del PR ni merge.

SHA de implementación auditado y publicado: **09d9beb060a4a80d9dc4ae7035407cbc8e81e061**, rama JDELGADO2607/heston-implementation, [PR #5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5). Base de esta reparación: 344ae4af1460ec2bc2ae6a28eac382f3c12c32ae. El commit que contiene este informe pertenece a la rama independiente de coordinación, [PR #4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4), y no es el SHA auditado.

## Resumen y alcance

La tercera reparación cierra F3-M1: el agregador deja de aprobar tablas reutilizadas de procedencia inválida, incluyendo cambios pareados de precio/referencia y sustitución de precios económicos. Compara las dependencias fuente de valoración con las del snapshot previamente auditado. El caso legítimo sigue aprobando. No se modificó el motor ni se recalibraron parámetros para cerrar el hallazgo.

Cambios de implementación: `src/heston/pipeline_phase3.py`, `tests/test_heston_phase3.py`, `data/heston/phase3/phase3_execution_manifest.json`, `docs/reports/INFORME_FASE_3_VALIDACION_HESTON.md`. Inspección del diff y extracción limpia mediante git archive del SHA completo, sin utilizar el árbol activo de Gemini. Publicación comprobada mediante ls-remote. Independencia: Codex solo escribió scripts diagnósticos e informes, sin corregir la implementación.

## Matriz de resolución

| Hallazgo | Estado al cerrar | Evidencia |
| --- | --- | --- |
| F3-M1 MEDIUM, comprobaciones/integridad de validación | RESOLVED para la ruta auditada | Caso legítimo PASS; todas las alteraciones reproducidas rechazan; vínculo previo de tres fuentes y siete inputs |
| F3-M2 MEDIUM, garantías excesivas/convergencia | RESOLVED en delimitación material; residuos editoriales abajo | Error de mallas declarado empírico, referencia fija y no monotonía reconocidas; informe independiente limita el dictamen |
| F3-L1 LOW, salto de número de pasos con T | Abierto, aceptado y trasladado a integración de IV/griegas | ~6.17e-5 USD cerca de 73.6083d; con malla temporal fija se elimina en el ensayo previo |
| F3-L2 LOW, metadata v0=0 y versión SciPy | RESOLVED desde 344ae4a, confirmado | Ambos errores sin referencia NaN, N/A_NO_REF y excepción QL efectiva; SciPy1.18.0 |
| F3-L3 LOW, residuos documentales | Abierto, no bloquea esta validación; reconciliar en fase8 | Afirmaciones y conteo de vencimientos descritos abajo |

Defectos materiales abiertos de esta fase: **0 BLOCKER, 0 HIGH, 0 MEDIUM**. Nuevo hallazgo de esta ronda: **1 LOW editorial**. Abiertos propios de fase3: F3-L1 y F3-L3, ambos LOW aceptados para avanzar. No se certifican automáticamente los módulos históricos ni se borran sus hallazgos.

## Reproducción independiente de F3-M1

Los scripts de [evidencia](HESTON_PHASE_3_09d9beb_evidence.txt) ejecutan loaders, constructor económico y agregador reales. Para aislar las pruebas negativas de integridad, solamente las etapas costosas y no modificadas de límites/tasas se sustituyen por sus fixtures legítimos. Además se ejecutó una corrida completa de esas etapas reales en un directorio de salida temporal. Ningún caso requiere modificar archivos oficiales.

| Prueba | Resultado actual | Resultado previo donde aplicaba |
| --- | --- | --- |
| Snapshot legítimo, defaults de reutilización/strict=False | PASSED, origen37bbd12 | PASSED |
| Precio fino de mercado +1 USD | FAILED | Ya corregido en344ae4a |
| Columna de error=1 USD conservando etiqueta favorable | FAILED | Ya corregido en344ae4a |
| Precio fino y referencia QL incrementados ambos +1 USD, residual conservado | FAILED | PASSED en344ae4a |
| 45 precios Am/EU económicos sustituidos por intrínseco+1e-12 | FAILED económico y global | PASSED/origen37bbd12 en344ae4a |
| eps económico sustituido por10 USD | FAILED | Nuevo control independiente |
| Payload de régimen alterado | FAILED | Nuevo control independiente |
| Tabla de continuidad reserializada/alterada | FAILED | Nuevo control independiente |
| Tabla mercado inexistente, carga strict | SnapshotIntegrityError | Control negativo |
| Solver copiado: theta_ADI 1/3 cambiado a1/2 | Verificación de origen FALSE | TRUE en344ae4a |
| Copia legítima de dependencias fuente/inputs | Verificación TRUE | Control positivo |
| strict=True ante snapshot alterado | SnapshotIntegrityError | Control positivo de rechazo |

Archivos/líneas del SHA auditado: `pipeline_phase3.py:83` registra hashes fuente, `:115` canoniza payload económico, `:144` compara fuentes, `:196` vincula dependencias al cargador, `:1058` controla economía, `:1433` incluye economía en procedencia, `:1483`/`:1523` condicionan gates, `:1569` condiciona economía y `:1604` condiciona overall a integridad cuando se reutiliza. El modo no estricto puede leer para diagnóstico pero ya no transforma origen inválido en aprobación.

Fundamento: si se modifica P y Pref por la misma cantidad c, `(P+c)-(Pref+c)=P-Pref`; comprobar el residual no verifica procedencia. Tampoco cumplir cotas/convexidad acredita que una tabla se obtuvo del modelo. La comparación con fingerprints de evidencia inmutable e inputs/código conocidos cierra los contraejemplos concretos. El hash canónico económico redondea a diez decimales científicos, suficiente para tolerar serialización; no debe describirse como autenticación exacta de todo float. No es una defensa contra un autor que modifique también deliberadamente el código y sus fingerprints.

## Resultados numéricos y artefactos

Las siete tablas de precios verificadas siguen **bitwise idénticas a37bbd12**. No hay mejora de precio atribuible a esta reparación: cambió la fiabilidad de su validación. Las revaloraciones independientes de las rondas previas continúan siendo aplicables al núcleo inalterado; véanse [37bbd12](HESTON_PHASE_3_37bbd12.md), [28bd72a](HESTON_PHASE_3_28bd72a.md) y [344ae4a](HESTON_PHASE_3_344ae4a.md), con sus scripts.

| Matriz | Cobertura | Error comparativo |
| --- | ---: | ---: |
| Mercado, propio fino vs QL700 | 97/97;60/22/15 por split | max0.000545756160718, MAE0.0000556376362235, RMSE0.000102349594864 USD |
| Mercado, defaults vs QL700 | 97/97 | máximo previo verificado ~0.000683303 USD |
| Regímenes A–F, EU y AM | 108/108 | max0.000509340381657, MAE0.0000685166356550 USD |
| Peores3, extra-fino vs QL1000 | 3/3 | ~0.0003481,0.0002238,0.0002081 USD |
| Economía del vector PoC | 45 puntos,35 mariposas,36 transiciones | 4 diferencias temporales brutas negativas; ninguna excede sensibilidad empírica propagada |

Tolerancia comparativa predeclarada0.002 USD; referencia refinada controlada en rondas anteriores. No equivale a tolerancia universal sobre derivadas. Calendario recalculado coincide con CSV hasta1.11e-16 USD. Tasas recalculadas coinciden hasta8.47e-22 en factores de descuento; discrepancia adaptador QL diario frente a curva continua hasta2.63424e-6 en D(t), no cero. Esos errores de descuento son adimensionales, aunque el informe implementador use USD en algunos párrafos.

Hashes de outputs e inputs verificados y fuente normalizada LF coincide. Diferencias CRLF/LF no son discrepancias del motor. **60 tests aprobados en171.55s**, fases0–3, sin cambios en archivos observados antes/después. Una segunda comparación contra los bytes del archivo git archive verificó **116 archivos oficiales** bajo data/docs/results/outputs/figures: cero modificados, ausentes o añadidos. La duración incluye concurrencia con la corrida diagnóstica; no comparar como benchmark aislado de rendimiento.

## F3-L3: documentación no certificada como prueba matemática

`INFORME_FASE_3_VALIDACION_HESTON.md:28` conserva “estabilidad incondicional” inferida de la matriz; `:109` deduce régimen asintótico/ausencia de oscilaciones de una diferencia media. Estos ensayos finitos no demuestran tales afirmaciones generales. `:37` debe distinguir la propagación algebraicamente correcta de una incertidumbre cuya magnitud es solo empírica. `:68` dice12 fechas, mientras la propia tabla y datos contienen16 vencimientos. Se registra como residuo LOW de comunicación, no como fallo probado de precios ni motivo para una cuarta reparación de fase3.

Reproducción del conteo: `len(pd.read_csv('data/heston/phase3/market_97_summary_by_tenor.csv'))` devuelve16. Corrección recomendada en síntesis fase8: presentar estabilidad observada, incertidumbre empírica y conteos derivados de tablas. La alternativa de añadir pruebas para justificar una garantía universal es innecesaria para el alcance académico.

## Reproducción y limitaciones

Desde una extracción del SHA auditado y dependencias `requirements-heston.txt`, ejecutar los scripts de esta rama documental con cwd de la extracción:

```text
python <ruta>/repro_phase3_09d9beb_integrity.py
python <ruta>/repro_phase3_09d9beb_acceptance.py
python <ruta>/repro_phase3_09d9beb_diagnostics.py
python <ruta>/repro_phase3_09d9beb_tests.py
```

El diagnóstico publicado compara los siete SHA256 de precios con el snapshot auditado; el log conserva además la comparación bitwise entre extracciones37bbd12/09d9beb realizada en el espacio independiente. `repro_phase3_09d9beb_archive_integrity.py` requiere `source.zip` original del SHA en cwd para comparar archivos oficiales después de pruebas. Logs y scripts se publican como evidencia independiente.

No se reejecutaron las ~30min de toda la valoración de mercado/regímenes: se conservaron precios byte-idénticos y motores congelados ya contrastados independientemente, y se reejecutaron controles modificados, límites/tasas reales y agregación. La corrida actual usa reutilización verificada de origen37bbd12, no se presenta como una generación fresca de todos los precios bajo09d9beb. Sin pruebas nuevas de precisión de griegas ni calibración definitiva en esta fase.

Dominio publicable provisional: puts, curvas/configuraciones y regímenes ensayados; malla finita, no todos los cinco parámetros dentro de sus bounds ni ausencia global de arbitraje. El límite v0=0 conserva N/A de referencia QL, evidencia de refinamiento propio y límite positivo, sin coincidencia industrial ficticia. Las pequeñas irregularidades de interpolación y cambio de pasos exigen mallas comparables para IV y sensibilidades futuras.

## Decisión y siguiente acción

**PHASE_APPROVED para09d9beb060a4a80d9dc4ae7035407cbc8e81e061.** Se cierra la tercera y última reparación ordinaria de fase3. Sin cuarto intento. Puede comenzar únicamente fase4 bajo la especificación publicada, con tres refinamientos locales, objetivo train en precios americanos, selección por train, holdout intacto y contraste final con solver propio. Los parámetros finales requerirán controles nuevos si cambian respecto a PoC. La aprobación técnica por fase usa la autorización humana vigente; revisión humana definitiva y merge siguen pendientes.
