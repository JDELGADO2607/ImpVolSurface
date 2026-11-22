# Auditoría Heston fase4 — reparación2/3

Fecha22-nov-2026. **PHASE_REJECTED** para SHA **5984a514ae983586a4e63a5affb0e17889f1dad4**, rama JDELGADO2607/heston-implementation, [PR5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5). Publicación comprobada por ls-remote y revisión de una extracción git archive independiente. Informe/evidencia en rama de coordinación/[PR4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4), sin modificar la implementación auditada.

## Resultado y resolución

Los contraejemplos concretos de la ronda anterior se corrigieron: finitud del pricing97, particiones/resúmenes, diferencias crudas de malla, archivo económico obligatorio y verificación real de snapshot/dependencias en la ruta de valoración. Sin nuevos cambios del motor, parámetros ni precios finales. F4-M2 queda **RESOLVED materialmente** al corregir comparativas y retirar las afirmaciones de óptimo global, convexidad demostrada por shocks aislados y sobreajuste probado de A.

Permanece **F4-H2 HIGH, PARTIALLY_RESOLVED**, con dos comprobaciones necesarias aún ausentes: validez económica/finitud del conjunto de9controles y correspondencia de primas/contratos del pricing con su fuente canónica. Conteo material pendiente de fase4: **0 BLOCKER,1HIGH,0MEDIUM**. No es un nuevo defecto del núcleo ni una recalibración rechazada por error de ajuste. Se autoriza **reparación3/3**, última ordinaria, focalizada en el cierre de integridad. Última aprobación09d9beb; no fase5 ni merge.

| Hallazgo histórico fase4 | Estado actual |
| --- | --- |
| F4-H1, runner y API fresca | RESOLVED; controles favorables conservados |
| F4-H2, integridad | PARTIALLY_RESOLVED; detalle reproducible abajo |
| F4-M1, convergencia/selección | RESOLVED en control material; conservar PoC es decisión académica documentada |
| F4-M2, informe | RESOLVED materialmente; pequeños residuos editoriales no justifican otra ronda |
| F4-L1, precisión canónica | RESOLVED a roundoff |

## Pruebas independientes

**85tests PASS en123.54s**, fases0–4, sin cambios/altas/bajas de archivos oficiales bajo data/docs/outputs/results/figures. Se repitieron los scripts de auditoría anteriores sobre el nuevo SHA y se extendieron tres casos de cierre. [Log consolidado](HESTON_PHASE_4_5984a51_evidence.txt) y scripts de reproducción se publican junto al informe.

Comprobación adicional posterior a tests y diagnósticos contra los bytes del archivo git archive:134archivos oficiales, cero modificados/ausentes/añadidos. Las alteraciones de prueba no contaminaron la entrega.

| Caso sobre función real de cierre | Resultado |
| --- | --- |
| Legítimo | PASS |
| Precio+1USD, resumen anterior | Rechazo |
| NaN en precio propio fino, QL fino o prima observada | Rechazo con contrato/columna |
| Inf en precio propio default | Rechazo |
| Salida económica ausente | Rechazo |
| Varianza inicial negativa / todos los refinamientos fallidos | Rechazo |
| Etiqueta de partición o conteo de resumen contradictorios | Rechazo |
| Error QL1000~1USD con flagsPASS antiguos | Rechazo por diferencia cruda |
| Precio americano económico Inf | **PASS** |
| Precio americano económico1e9USD, strike9USD | **PASS** |
| Reemplazar lastPrice de97contratos por prop_fine_price | **PASS; MAE/RMSEtrain=0,MAEholdouts=0** |

Los casos inválidos se construyen únicamente en temporales. No se encontraron Inf ni primas sustituidas en la entrega legítima; el defecto demostrado es que el verificador acepta evidencia inconsistente como válida.

### F4-H2: evidencia económica no validada

`src/heston/pipeline_phase4.py`, bloque `Validate raw economic controls`, aproximadamente`:1436`: se exige longitud9, Am>=intrínseco, Am>=EU y flags de monotonía/convexidad. No se exige finitud de sus precios ni cota superiorAm<=K. Inf satisface las comparaciones >=;1e9también. Los flags antiguos no se recalculan a partir de esos precios. Así se exporta `gate_economic_properties_pass=True` para un precio imposible de una put de strike9.

Fundamento: el payoff de una put americana está acotado porK; con la curva determinista no negativa del proyecto y q0, su precio no puede superarK. La desigualdad de cota inferior no garantiza cota superior ni finitud. El escenario inyectado de1e9no es una diferencia numérica ni una limitación de datos. Corrección mínima: validar esquema, valores finitos e identidad de los9contratos, cotas aplicables y coherencia de propiedades declaradas desde precios crudos; rechazar o regenerar campos incoherentes. No tocar el solver.

### F4-H2: primas/contratos no reconciliados con la fuente

El mismo gate valida IDs, finitud y particiones del pricing97, pero no compara lastPrice/strike/madurez/fecha con puts_selected_clean. Prueba real: `df_puts['lastPrice']=df_puts['prop_fine_price']`; todos los campos son finitos, los97IDs y60/22/15permanecen. Recalcular errores contra esas primas modificadas produce ceros y PASS. La fuente de mercado original no se alteró. Que el productor normalmente copie correctamente la prima no satisface la comprobación de correspondencia solicitada en el encargo.

Corregir mediante unión uno-a-uno por ID con fuente canónica y comprobación de sus campos financieros/contractuales a tolerancia de serialización, antes de métricas. No comparar floats con tolerancia0.002depricing para aceptar cambios de cotización; se trata de correspondencia de input, no precisión del motor. Si se regeneran columnas desde la fuente, hacerlo explícitamente y no conservar salidas contradictorias. No fillna, dropna, clipping ni selección de una muestra más favorable.

## Verificación favorable de la reutilización y motores

El script adicional ejerce **step5 real**, usando un contrato de mercado, salidas temporales y copias de inputs/código para los verificadores ya invocados por producción:

- Snapshot/dependencias legítimos: `PHASE3_VERIFIED_AUDITED`, precio finito.
- Solver copiado con theta_ADI alterado: `FRESH_SOLVER_2D_VALUATION`, finito; no se ejecuta el solver alterado, solo se prueba su detección de origen.
- Input financiero copiado alterado: misma regeneración fresca, finita.
- Precio de snapshot alterado aNaN con manifiesto original: regeneración fresca finita, no etiqueta falsa de origen verificado.

También se repitió el vector modificado v0=.20 y el control extra-fino real: propio fino0.4715874002 frente QL7000.4716160337USD, diferencia2.86335e-5; QL700/1000~1.59258e-5 y propio fino/extra~4.11747e-5USD. No se necesita repetir las tres optimizaciones ni todo el pricing congelado para cerrar los dos controles restantes.

## Límites y observaciones no materiales

Se inspeccionó el diff: únicamente pipeline/tests, reporte y metadatos/notas; se preserva la evidencia numérica del núcleo. No se reejecutaron horas de optimización ni el pipeline histórico global. La aceptación del PoC no prueba mínimo global ni unicidad; diferencias de precio dentro de0.002USD permiten una decisión de continuidad, no una demostración de ruido u overfitting. El nuevo texto lo distingue.

El check de identidad del snapshot usa atol1e-7: es tolerancia pequeña de parámetros, no roundoff estricto en double. Para el vector efectivo conservado la diferencia es~1e-15y el efecto de redondeo anterior ya era~1.9e-6USD. Se registra como precisión de comunicación, no como motivo de una cuarta reparación. Igualmente0.00184USD es18.4%del tick0.01, no un tercio; la cota presupuestaria es empírica/comparativa, no demostrada. Corregir esos residuos al reconciliar documentación, sin modificar criterios ni parámetros.

Reproducir desde extracción5984a51 con requirements-heston.txt:

```text
python <ruta>/repro_phase4_5984a51_controls.py
python <ruta>/repro_phase4_5984a51_dependencies.py
python <ruta>/repro_phase4_5984a51_tests.py
```

El primer script usa copias temporales y las rutinas reales de cierre/valoración; el segundo cambia la raíz de lectura del verificador a una copia controlada para comprobar dependencias en la ruta que realmente lo invoca. No se infiere fallo del modelo por esos escenarios artificiales. La suite positiva y el snapshot legítimo siguen pasando.

## Recomendación técnica

**PHASE_REJECTED.** Ejecutar solamente [reparación3/3](../orchestration/PHASE_4_REPAIR_3.md): controles económicos y conciliación de inputs, pruebas negativas reales y metadatos coherentes. Sin nueva calibración, cambio de modelo o inicio de fase5. Cada reparación requiere nuevo SHA publicado y auditoría. Si persiste un defecto material tras esa tercera reparación, no se despachará una cuarta automáticamente: se registrará el bloqueo y sus alternativas para revisión.
