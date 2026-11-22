# Auditoría Heston fase4 — reparación3/3, bloqueo para revisión

Fecha22-nov-2026. SHA exacto auditado **7f51a811ae5815dadf8c26b46f707e9f7cb0d05c**, rama JDELGADO2607/heston-implementation, [PR5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5). Publicado, comprobado por ls-remote y auditado en extracción git archive independiente. Informe/evidencias en coordinación/[PR4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4), sin cambios del auditor a implementación ni merge.

**Dictamen: no aprobar fase4; estado de orquestación PHASE_4_BLOCKED, HUMAN_REVIEW_REQUIRED.** Tres reparaciones ordinarias agotadas. No se despacha reparación4 ni se autoriza fase5. El bloqueo es del cierre de validación económica, no una conclusión de inviabilidad de Heston ni un fallo demostrado de los precios legítimos publicados.

## Resumen y matriz de resolución

La tercera reparación corrige los contraejemplos de la ronda anterior: economíaInf/1e9, datos no finitos y primas sustituidas por precios del modelo ahora rechazan; también reconstruye intrínseco/EEP y propiedades americanas desde precios crudos. **87tests PASS en120.52s**, sin escrituras oficiales. La tabla económica legítima cumple además las cotas europeas independientes que se comprobaron en esta ronda.

Sin embargo, el verificador aún permite sustituir las9puts europeas por cero y ajustar coherentemente sus EEP. El gate devuelvePASS pese a3violaciones de cota europea descontada, con déficit máximo **4.611031239654112USD**. Es una omisión de la misma validación económica F4-H2, cuyo encargo final incluía cotas europeas aplicables. No es una diferencia numérica inmaterial.

| Hallazgo fase4 | Estado al detener |
| --- | --- |
| F4-H1, runner/reproducción/API | RESOLVED para controles auditados |
| F4-M1, selección/convergencia | RESOLVED materialmente |
| F4-M2, documentación/comparación | RESOLVED materialmente, con limitaciones de interpretación ya registradas |
| F4-L1, redondeo canónico | RESOLVED a roundoff |
| F4-H2, integridad económica | PARTIALLY_RESOLVED; cotas europeas descontadas ausentes |

Conteo pendiente de fase4: **0 BLOCKER,1HIGH,0MEDIUM,0LOW**; limitaciones históricas aceptadas de otras fases no se recuentan aquí. PHASE_BLOCKED describe el estado del proceso por el límite de reparaciones, no una reclasificación del hallazgo como severidadBLOCKER.

## Defecto demostrado: validación europea incompleta

Archivo `src/heston/pipeline_phase4.py:1531` admite `P_Eu>=-1e-4`;`:1545` solo limita `P_Eu<=K+1e-4`. Esas condiciones no son las cotas europeas de la curva común. El bloque verifica Am>=EU y Am<=K, y recalcula forma de los precios americanos; nada de ello impone la cota inferior correcta al precio europeo.

Con dividendos nulos y descuento deterministaD(T), la ausencia de arbitraje exige para una put europea:

`max(K*D(T)-S0,0) <= P_Eu(K,T) <= K*D(T)`.

La cota inferior se deduce de paridadC-P=S0-KD y C>=0, o de convexidad del payoff bajo la medida de valoración; la superior se obtiene del payoff<=K. No confundir esas cotas con la cota americana intrínseco<=P_Am<=K de este proyecto con tasas no negativas. UsarK como límite europeo superior es más débil queKD; usar0 como único límite inferior deja sin verificar las puts ITM. Mantener Am>=EU no repara esa omisión.

### Reproducción

El script independiente [repro_phase4_7f51a81_european_bounds.py](repro_phase4_7f51a81_european_bounds.py) usa el gate de producción real, sus97precios legítimos y copias temporales de todos los outputs requeridos. Solo transforma en memoria los9controles económicos:

```python
econ['price_european'] = 0.0
econ['early_exercise_premium'] = econ['price_american']
# step10_build_manifest real con los demás datos legítimos
```

No toca precios americanos, fuente de mercado, parámetros, flags, motor ni tabla de pricing97. Por eso no se crea artificialmente una contradicción aritmética de EEP: la prima se reconstruye correctamente. El resultado es **PASS**, con3violaciones europeas obvias:

| Control | P_Eu legítimo USD | Cota inferior KD-S0 USD | P_Eu inyectado |
| --- | ---: | ---: | ---: |
| K17,31d | 4.6112373952 | 4.6110312397 | 0 |
| K17,94d | 4.5291670643 | 4.4825784120 | 0 |
| K17,430d | 4.7923300515 | 3.7713147482 | 0 |

La curva procede de get_official_yield_curve y D(T) de get_discount_factor; spot12.33. Los9precios europeos legítimos respetan las cotas. No se afirma que los precios publicados sean cero ni que el solver calcule esos valores. La falla está en certificar como económicamente válida una evidencia que viola sus límites contractuales. El déficit supera de lejos1e-4/0.002USD y no depende de resolución de malla.

## Otros controles y no regresión

Se repitió el [script completo de controles](repro_phase4_7f51a81_controls.py) de las rondas anteriores sobre este SHA:

- Caso legítimoPASS.
- Rechazo de precio+1, NaNpropio/ref/mercado, Infdefault, salida económica ausente, parámetros inválidos, resumen/etiqueta de partición alterados, mallas con precios incompatibles/flagsfavorables y todos los refinamientos fallidos.
- Rechazo de Am económicoInf y1e9USD, y de lastPrice sustituido por prop_fine_price contra fuente canónica.
- Snapshot de fase3 alterado aNaN provoca valoración fresca finita, no una etiqueta falsa de verificación.
- Vector v0=.20, ruta fresca real y extra-fina: propio fino0.4715874002,QL7000.4716160337USD, diferencia2.86335e-5; QL700/1000~1.59258e-5 y propio fino/extra~4.11747e-5USD.

Se ejecutaron87tests fases0–4 y hashes antes/después sobre data/docs/outputs/results/figures: sin cambios/altas/bajas. Adicionalmente se compararon134archivos oficiales con los bytes del git archive: intactos. [Log consolidado](HESTON_PHASE_4_7f51a81_evidence.txt). No se reejecutaron las optimizaciones ni todo el pipeline histórico; se mantuvieron los precios y el vector previamente contrastados y se probaron los caminos de validación modificados.

Reproducción desde cwd de una extracción del SHA auditado, dependencias requirements-heston.txt:

```text
python <ruta>/repro_phase4_7f51a81_european_bounds.py
python <ruta>/repro_phase4_7f51a81_controls.py
python <ruta>/repro_phase4_7f51a81_tests.py
```

El primer script conserva una aserción de que el gate defectuoso devuelvePASS: sirve para reproducir el hallazgo, no es un criterio deseado para una reparación futura. Todo output de prueba se escribe en temporales.

## Interpretación, alternativas y límite de autonomía

La causa recurrente fue reconstruir por separado subconjuntos de invariantes del dictamen, sin una validación económica completa de los campos que se afirman verificar. La tercera reparación cerró las cotas americanas y el vínculo de inputs; dejó incompletas las europeas. La complejidad del pipeline facilita esas omisiones. No hay justificación para cambiar modelo, curva, datos, parámetros, calibración o tolerancias a raíz de este hallazgo.

Posible corrección técnica mínima, **pendiente de autorización**, sería comprobar las dos cotas europeas conD(T)de la misma curva y una tolerancia de precio existente y justificada, añadir positivo/negativo real y volver a auditar un nuevoSHA. No requiere recalibración ni repetir multistart. Una opción más amplia es simplificar el cierre en validadores económicos pequeños y explícitos; aumenta el diff y requiere justificar su coste. Otra posibilidad humana es reducir expresamente el alcance certificado y aceptar la limitación del gate, conservando el hallazgo abierto; no equivaldría a declarar corregida su validación.

No se elige unilateralmente una de esas alternativas ni se encarga una cuarta reparación. La instrucción humana vigente y [AGENTS](../../AGENTS.md) limitan a tres reparaciones por fase. El último SHA aprobado sigue siendo09d9beb, correspondiente a fase3. Fases5–8 no se iniciaron. La viabilidad previa del modelo y los buenos precios observados no sustituyen el cierre de este gate.

## Estado de entrega y siguiente acción

Informe y evidencia publicados en rama documental independiente, PR4 abierto sin fusionar. Notificación de control a Gemini: **PHASE_BLOCKED — HUMAN_REVIEW_REQUIRED**, congelar7f51a81, sin correcciones nuevas ni inicio de fase5. No se presupone una capacidad de bloqueo formal de Orca: la guía de mensajería verificada solo documenta comunicación, por lo que el bloqueo se aplica mediante mensaje y estado persistente.

**Esperar decisión humana sobre cómo reabrir la fase.** No espera activa, no cuarta reparación automática, no aprobación definitiva ni merge. Esta auditoría no certifica los módulos de IV/griegas/stress aún pendientes ni completa la revisión humana final de la migración.
