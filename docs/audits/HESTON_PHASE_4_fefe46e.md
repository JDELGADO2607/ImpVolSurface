# Auditoría independiente — Heston fase4, entrega inicial

Fecha22-nov-2026. **PHASE_REJECTED**. SHA auditado **fefe46ebb7028aa786abf3a8fca7377d667efda4**, implementación JDELGADO2607/heston-implementation, [PR5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5). Último SHA técnicamente aprobado09d9beb060a4a80d9dc4ae7035407cbc8e81e061. El commit documental de este informe pertenece a coordinación/[PR4](https://github.com/JDELGADO2607/ImpVolSurface/pull/4) y es distinto del auditado.

## Dictamen ejecutivo

Los precios publicados mantienen el ajuste viable y las pequeñas discrepancias de motores conocidas. No se demuestra aquí un fallo nuevo del núcleo Heston. La fase no puede aprobarse: el pipeline no reproduce su propia entrega desde las fuentes publicadas, la ruta de valoración fresca usa una API inexistente y vuelve a introducir reutilización por existencia y gates insuficientes. La documentación contiene cifras y conclusiones materialmente incompatibles con sus tablas.

Conteo: **0 BLOCKER, 2 HIGH, 2 MEDIUM, 1 LOW**. Se autoriza reparación1/3 de alcance acotado, sin fase5 ni recalibración automática completa. Eliminar ramas de reutilización no verificadas es una alternativa preferible a construir infraestructura genérica de caché. La evidencia de fases anteriores no elimina la necesidad de validar las nuevas interfaces.

## Alcance y reproducción

Commit publicado confirmado mediante git ls-remote y auditado en extracción git archive independiente, sin cambios en la implementación. Diff: extensión mínima de `calibration.py`, nuevo `pipeline_phase4.py` de1295líneas,16tests y13artefactos incluyendo manifiesto, más informe. El solver2D, modelo y curva no cambiaron respecto a fase3.

Scripts adjuntos: `repro_phase4_fefe46e_controls.py`, `repro_phase4_fefe46e_prices.py`, `repro_phase4_fefe46e_tests.py`; [log consolidado](HESTON_PHASE_4_fefe46e_evidence.txt). Ejecutarlos desde cwd de una extracción del SHA auditado con requirements-heston.txt. Los controles usan copias temporales para alterar archivos, nunca producción. Las pruebas de manifest llaman al agregador real con los resúmenes que consume la ruta de producción; no sustituyen su lógica por un test que la replique.

## F4-H1 HIGH — pipeline publicado incompleto y valoración fresca inejecutable

**Defecto computacional demostrado.** `pipeline_phase4.py:193`/`:221` exige `refinement_A_res.json`, `refinement_B_res.json`, `refinement_C_res.json` para ensamblar los resultados. Ninguno está en el commit. El pipeline no llama a `run_single_start` ni ejecuta el optimizador: el import de minimize no genera los archivos. La configuración y CSV no sustituyen estos inputs requeridos.

Reproducción real de step3 sobre directorio temporal limpio: `FileNotFoundError: Refinement JSON missing ... refinement_A_res.json`. El mismo archivo falta en la extracción publicada aun cuando los CSV finales sí existen. No se puede verificar ni reproducir la cadena end-to-end de los tres refinamientos a partir de las fuentes entregadas.

Segundo bloqueo, en `:585`–`:596`: la rama que debe valorar un ganador distinto del PoC crea `Grid2D(s_min=...,v_min=...,m_t=...)` y llama a constructor/solve de un solver con otra interfaz. La clase real admite `Grid2D(strike,v0,n_s,n_v,...)`; `Heston2DSolver` expone `.price(...)`, no `.solve(...)`. Forzando únicamente `selection_status='WINNER_NEW_OPTIMUM'` en una copia del ganador, primera valoración fresca: **TypeError: Grid2D.__init__() got an unexpected keyword argument 's_min'**. La ruta extra-fina alternativa tiene el mismo patrón. Config además llama defaults a120/60/min50, aunque los defaults reales aprobados son160/80/min60. Reutilizar los precios viejos oculta estos problemas, no los corrige.

Impacto: no hay nueva calibración ni validación reproducible de un vector cambiado; el fallo no es una diferencia de tolerancia. Corrección: publicar entradas/logs originales verificables y runner real/configurable que pueda generarlas; usar la API pública aprobada del solver sin rediseñarlo. Conservar las optimizaciones originales si puede recuperarse evidencia íntegra y reproducir sus SSE; no repetir horas de optimización por rutina. Si no pueden recuperarse, declararlo y regenerar lo indispensable, sin reconstruir supuestas trazas desde una tabla resumen.

## F4-H2 HIGH — resultados reutilizados sin vínculo y cierre con evidencia inválida

**Defecto de integridad demostrado.** Retornos por mera existencia en `pipeline_phase4.py:116`,`:321`,`:502`,`:975`. `step1_validate_inputs` calcula hashes pero no los compara con un origen previo de cada resultado. La integración fase3 en`:514` lee tablas según una etiqueta de ganador, sin comprobar parámetros, código, configuración e inputs. `step10_build_manifest:1194` omite archivos que faltan y su gate`:1203` depende de resúmenes/booleans, sin validar precios, particiones, controles económicos o parámetros finales. `run_pipeline` usa esas etapas sin una validación posterior que cierre el hueco.

Resultados de controles reales:

| Alteración en copia temporal | Resultado del agregador |
| --- | --- |
| Legítimo | PASS,12 outputs |
| Primer `prop_fine_price` incrementado1USD, resumen viejo | **PASS** |
| Eliminar archivo económico requerido | **PASS**,11outputs |
| Varianza inicial del ganador=-1 | **PASS** |
| Resumen train declara59 contratos, total permanece97 | **PASS** |
| Cambiar v0 a0.5 en step5 con tablas existentes | Devuelve exactamente los precios anteriores |

Los últimos cambios no son correcciones realizadas por el auditor: son contraejemplos en copias descartables. Las pruebas negativas de `test_heston_phase4.py:337` en adelante comprueban un diccionario o una comparación local; no ejercen estos caminos de producción. Por eso76tests pueden pasar sin detectar el problema.

Fundamento: un hash recién calculado acredita identidad del archivo leído, no correspondencia con el experimento que se afirma representar. La comparación financiera requiere mismos datos, parámetros, curva y configuración. Contar filas del resumen no acredita IDs únicos ni60/22/15 contratos efectivos. Corrección sencilla: ejecución fresca aislada por defecto para etapas baratas y pricing; reutilizar solo evidencia de origen verificado cuando corresponda, con igualdad de vector y configuración. Derivar gates de las observaciones crudas, exigir todos los artefactos y controles antes de PASS. No se exige resistencia criptográfica frente a un autor que altere también el código verificador.

## F4-M1 MEDIUM — conservación del benchmark y convergencia sin criterio cuantitativo suficiente

**Decisión metodológica discutible y defecto de control.** `pipeline_phase4.py:407` introduce `discretization_noise_sse=0.0001`, no presente en la configuración, y declara que equivale a0.001USD en prima. No existe esa conversión universal. SSE tiene unidadesUSD² y depende del vector completo de residuos y del tamaño de muestra. Para perturbación de precios e:

`|SSE(P+e)-SSE(P)| <= 2*||P-Pobs||_2*||e||_2 + ||e||_2^2`.

Puede ser razonable conservar PoC si el cambio predictivo es inmaterial, tal como permite la especificación, pero debe medirse esa equivalencia y no atribuir un umbral no justificado al protocolo predeclarado. El candidato A tiene SSE fino0.08657919092024632 frente a0.08661183034789599 del benchmark redondeado: mejora3.26394276497e-5USD². El informe no permite concluir por ese número solo que el cambio de primas es menor que0.001USD.

Además, el benchmark cuenta como candidato convergido en`:370`/`:396`: la rutina no exige al menos un refinamiento local convergido como establece el encargo. En control unitario de la rutina con contrato real y todos los refinamientos marcados fallidos, el benchmark permite conservar un ganador. No se afirma que los tres refinamientos reales hayan fallado: las tablas publicadas declaran A/B convergidos y C anormal, correctamente excluido.

Corrección: separar benchmark de optimizaciones, exigir la convergencia mínima y justificar con cambios reales de precios y sensibilidad de malla cualquier decisión de conservarlo. No es necesario forzar un ganador nuevo, modificar parámetros, endurecer el ajuste ni perseguir un mínimo global. Publicar el criterio y su aplicación con honestidad temporal; no llamar predeclarado a un número ausente del encargo/configuración.

Contraste adicional independiente: QL700 sobre12contratos (K9/12.33/17,T31/94/430/794d) arroja diferencia máxima A/PoC exacto **0.00187797997182USD**. Es evidencia favorable a que una conservación explícitamente justificada puede ser razonable para alcance académico; no acredita la conversión0.0001SSE->0.001precio ni resuelve el control de convergencia. Esta grilla es diagnóstico numérico del auditor, no selección por error holdout.

## F4-M2 MEDIUM — informe incompatible con datos y comparación económica

**Discrepancias demostradas**, `docs/reports/INFORME_FASE_4_CALIBRACION_HESTON.md`, secciones1,2,5,8–10. El split real retiene tres vencimientos37/94/304d; el informe dice dos37/612d. Train tiene13tenores, no10. El documento llama defaults a120/60 y presenta como vector no redondeado las coordenadas históricas aunque su JSON usa seis decimales.

Sobre los mismos84 contratos, recalculando de columnas de precios y lastPrice:

| Modelo/motor | MAE USD | RMSE USD |
| --- | ---: | ---: |
| Heston propio fino | 0.0231092457746622 | 0.0338752213871970 |
| Heston QL fino | 0.0231298287416917 | 0.0338947181665238 |
| Flat curva común | 0.0396743356162873 | 0.0602891638640565 |
| Flat tasa por contrato | 0.0390224617573579 | 0.0594047946980200 |
| SVI históricoR3 | 0.0684416666666667 | 0.0885792871897692 |

El informe cita flatMAE0.142/RMSE0.185, SVI0.018 y mejoraHeston>80%. La reducción de MAE Heston propio frente a flat común es **41.75265845%**. La curva histórica SVI difiere: tampoco atribuir todo el cambio a modelo. Las métricas de mercado no equivalen al error entre motores, ni todo el residuo restante queda demostrado como error estructural: incluyen iliquidez/asincronía y otras limitaciones.

La tabla de sensibilidad incluye rho=-0.95 con deltaSSE=-9.5940e-7, contradiciendo “todas las perturbaciones incrementan SSE”. Ese descenso minúsculo no es un nuevo fallo del modelo. Un aumento de SSE en coordenadas aisladas tampoco demuestra convexidad local en todas las direcciones. `shock_val=-0.02` etiqueta un desplazamiento efectivamente truncado a~-0.000193, y solo se publican seis contratos de sensibilidad frente a los doce solicitados. Registrar desplazamiento efectivo y alcance, sin inferencia estadística ficticia. La condición Feller no se impuso y se satisface, pero el cero CIR de este caso no debe llamarse absorbente cuando kappa*theta>0.

Corrección: generar cifras/tablas desde artefactos, reconciliar split, motores, precisión y límites, eliminar garantías no sustentadas. No editar resultados para coincidir con la prosa ni aplazar al guion final discrepancias que invierten la comparación actual.

## F4-L1 LOW — redondeo temprano y nombre de benchmark exacto

JSON final contiene `[0.186138,2.72546,0.21368,0.481785,-0.949807]`, distinto del PoC original a plena precisión. Diferencias absolutas por parámetro del orden2.2e-7 a3.7e-7. No se declara un efecto material en precios por ese redondeo; el problema de identidad/procedencia sí forma parte de F4-H2: las columnas finas se copiaron de fase3 al vector original, no del vector exportado. En train, SSE QL fino del candidato publicado y suma del pricing final difieren ligeramente por ello (~5.29e-8USD²).

Conservar precisión completa del vector canónico; usar redondeo solo para presentación. Los tres refinamientos existentes partieron de aproximaciones a seis decimales: declarar esa desviación y su impacto en lugar de repetir automáticamente las tres optimizaciones. Si se conserva PoC, exportar el vector original exacto y vincular sus precios de fase3 de forma explícita y verificada.

Los12controles QL independientes midieron efecto máximo del redondeo de **1.89353536806e-6USD**, muy inferior al presupuesto0.002. Por eso se clasifica LOW en precisión; la ausencia general de vínculo que permite reutilizar precios para v0=0.5 sigue siendo HIGH. No confundir ambas materialidades.

## Pruebas, límites y conclusión

Se reejecutaron fases0–4: **76tests PASS en139.66s**, sin cambios/creaciones/borrados en data/docs/outputs/results/figures observados antes y después. Los hashes de11artefactos de salida coinciden en bytes; el de configuración coincide normalizandoCRLF aLF. Esa diferencia de serialización **no** se clasifica como defecto financiero. Las métricas finales por partición se recalcularon desde precios y coinciden con sus CSV: trainMAE0.02573726/RMSE0.03797906, strikeMAE0.02110820, tenorMAE0.02030449. Cobertura97,60/22/15; las tablas efectivas no presentan el split erróneo del texto.

No se repitieron horas de optimización: faltan sus entradas/trazas en el commit y el defecto de reproducción ya se obtiene sin ellas. La tabla de convergencia es evidencia declarada pendiente de recuperar, no demostración independiente de que toda optimización sea falsa. Los precios finos/defaults actuales coinciden con la evidencia PoC previamente auditada, sujeto a la diferencia de vector exportado descrita. Se añadieron12contratos QL independientes para cuantificar cambios de vector; log/CSV adjuntos. Una malla finita no establece ausencia global de arbitraje ni unicidad paramétrica.

Dictámenes: datos/curva y núcleo heredados mantienen sus aprobaciones previas; calibración definitiva, integración de valoración y reproducibilidad de fase4 **no aprobadas**. Stress/IV/griegas futuras no evaluadas aquí. PR global pendiente. Correcciones autorizadas únicamente en el [encargo de reparación1](../orchestration/PHASE_4_REPAIR_1.md); cada corrección debe producir nuevo SHA y auditoría. No fase5, merge ni force-push.
