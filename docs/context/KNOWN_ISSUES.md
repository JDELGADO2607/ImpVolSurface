# Hallazgos y aplicabilidad

Referencia vigente [auditoría R3](https://github.com/JDELGADO2607/ImpVolSurface/blob/e1b4f5bf9b306e2213a4858598499ef45d284d66/docs/audits/CODEX_AUDIT_R3_3d81ff1.md), evidencia y scripts enlazados dentro de ella. No se declara ningún problema eliminado hasta probar la ruta Heston implementada. Módulos y líneas exactas constan en el informe fijado.

| R3 ID | Severidad | Estado | Evidencia / módulo | Aplicabilidad Heston |
| --- | --- | --- | --- | --- |
| B-R3-1 | BLOCKER | Abierto, SVI congelado | Mariposas negativas 290,476d K≈9,68, surface.py | Repetir propiedades de precios, no portar armonización SVI |
| H-R3-1 | HIGH | Abierto | Extrapolación desplaza 31d/K10 y 430d/K5 | Política de dominio y selección sí, fórmula SVI histórica |
| H-R3-2 | HIGH | Parcialmente resuelto | strict y flags difieren, LEAPS, 3d | Comprobar cuarentena en todos los consumidores |
| H-R3-3 | HIGH | Abierto | Holdout difiere de refit productivo | Reconstrucción de calibración completa y cobertura |
| H-R3-4 | HIGH | Abierto | Curva manual y conversión par/zero | Vigente en fase 0 |
| M-R3-1 | MEDIUM | Parcialmente resuelto | Nulos y etapas vacías pasan run_all | Vigente |
| M-R3-2 | MEDIUM | Parcialmente resuelto | Pytest reescribe siete salidas | Vigente |
| M-R3-3 | MEDIUM | Abierto | Capital y P&L usan distintas carteras | Vigente en integración |
| M-R3-4 | MEDIUM | Abierto | Métricas y documentación distintas | Vigente |
| L-R3-1 | LOW | Parcialmente resuelto | w != tau IV² junto a nodos, plazo negativo | Propiedades de nueva API, no copiar interpolación |
| L-R3-2 | LOW | Abierto | HAR muestra corta sin orígenes elegibles | Vigente si se reutiliza forecast |

SHA de detección de todas estas filas `3d81ff18cae3a9f8dc74c174015fed17031a8da8`.
R2 en 855eb1cfbd300ddf488bd02d348883f5eac756b8 tenía B1/H1–H5/M1–M3/L1–L2. La matriz completa de resolución y reproducción está en el informe R3. H5 (put K14,75 a 31/37d), M3 (fuga HAR corta) y L1 (cifras straddle Base) se resolvieron en sus contraejemplos concretos. H5 no es demostración global. M3 dejó el nuevo error de muestra vacía L-R3-2. Las restantes resoluciones son parciales o abiertas según esa matriz.

Estados admitidos Abierto, Resuelto, Parcialmente resuelto, No verificable y Obsoleto por cambio metodológico. Congelar SVI no convierte automáticamente sus hallazgos en obsoletos para el benchmark histórico.

## Estado especifico Heston al aprobar fase1

F0-01/F0-02/F0-03 cerrados para la linea base en0fb8758. F1-01,F1-02,F1-03,F1-04 cerrados para PoC en654d1c2; evidencia y reproduccion en HESTON_PHASE_1_654d1c2.md y sus referencias historicas. Los cierres no se trasladan al benchmark SVI ni a modulos financieros aun no integrados. Limitaciones abiertas de datos/identificacion se aceptan para viabilidad, sin prometer parametros unicos ni exactitud global.

## Fase2, SHAcd5ed3e, antes de reparacion1

F2-M1 MEDIUM Abierto: interfaz C con frontera de put (43.9339USD frente a cota77.7222 en prueba de interfaz), theta0 no calculada y dP/dv0 ambiguamente vega. F2-M2 MEDIUM Abierto: identidad IT presentada como resolucion exacta del LCP, garantia M-matriz contradicha por signo de coeficientes y orden de fases confundido. F2-L1 LOW aceptado como limitacion inicial: overshoot cubico~2e-6USD y frontera europea no exacta~1.28e-5USD en caso probado. No defectos materiales de los12 precios puts smoke. Evidencia y scripts HESTON_PHASE_2_cd5ed3e.md. F2-M1/M2 aplican a Heston, no provienen automaticamente de SVI.

Actualizacion posterior fase2, SHAea0df6f: F2-M1 RESUELTO (API puts,thetaNone,sensibilidad varianza explicita). F2-M2 RESUELTO en controles materiales de identidad IT/diagnostico diferencial y M-matrices; residuo editorial se conserva como F2-L2 LOW Abierto, borrador de guion no aprobado para defensa y cifras menores a reconciliar antes de fase8. F2-L1 LOW sigue abierto como limitacion inicial aceptada. Ninguno equivale a un fallo material demostrado de los12precios puts; validacion amplia de fase3 pendiente. Evidencia HESTON_PHASE_2_ea0df6f.md.

## Fase3 SHA37bbd12, antes de reparacion1

F3-M1 MEDIUM Abierto: summaryworst3 fijado favorable aun ante FAIL inyectado; calendario no ejecutado; test de tasas solo nodal, no pasos cruzados; error0/PASS para v0 sin referencia y metadata incompleta. F3-M2 MEDIUM Abierto: epsilon de dos mallas llamado cota rigurosa y conclusiones globales/no monotonia de refinamiento no reconocidas. F3-L1 LOW Abierto/aceptado como aproximacion inicial: default60->61pasos salta~6.17e-5USD cerca de73.6083d, por debajo de0.002 pero no C1global; con malla temporal fija se elimina ese salto en el ensayo. Scripts/evidencia HESTON_PHASE_3_37bbd12.md. Sin prueba de defecto material de precios muestreados; no autoriza calibracion fase4.

Actualizacion fase3 SHA28bd72a: F3-M1 parcialmente resuelto (calendario,tasas,p0/ref y worst3 dinamico); sigue MEDIUM abierto por reutilizacion basada solo en existencia y gate mercado/regimenes basado en etiquetas: prueba de cacheprecio+1USD y maxerror1USD/statusPASS mantienen PASSED. F3-M2 resuelto en delimitacion material. F3-L1 LOW documentado/aceptado, sin cambio de motor. F3-L2 LOW residual metadata: max_abs_err0 sin referencia frente a campo principalN/A, scipy_version contiene modulo.49tests PASS,7tablas de precio bitwise37bbd12,hashesfuente LFcanon validos; no falla financiera demostrada de outputs actuales. Evidencia HESTON_PHASE_3_28bd72a.md. Reparacion2/3 sin calibracion.

Actualizacion fase3 SHA344ae4a: F3-M1 MEDIUM parcialmente resuelto: errores recalculados y origenhash disponible, pero all_snapshot_verified no condiciona overall; precios/ref alterados juntos danPASSED, economia sustituida por intrinseco daPASSED/origen37, y theta_ADI cambiado en copia de fuente no invalida verificacion. F3-L2 RESUELTO (NaN de errores sin ref y SciPyversion real); F3-M2 material cerrado, F3-L1 LOW aceptado.56tests sin escritura oficial y precios legitimos sin cambios. Informe HESTON_PHASE_3_344ae4a.md; reparacion3/3 ultima, sin cuarta ronda automatica ni calibracion.

Actualizacion fase3 SHA09d9beb: F3-M1 RESUELTO por controles independientes positivos/negativos y corrida aislada; fuente de pricing y economia vinculadas al snapshot, gate no aprueba origen invalido.60tests PASS/171.55s,116archivos oficiales identicos al archive. PHASE_APPROVED; no cuarta reparacion. F3-L1 LOW temporal sigue aceptado para integracion. F3-L3 LOW editorial abierto: informe aun dice estabilidad incondicional, infiere regimen asintotico de medias y dice12 vencimientos donde hay16; corregir en fase8, no es fallo demostrado del motor. F3-M2 material cerrado/F3-L2 resuelto. Ver HESTON_PHASE_3_09d9beb.md. No elimina hallazgos del benchmark SVI ni aprueba griegas o parametros nuevos por anticipado.

Fase4 entrega inicial SHA fefe46e REJECTED: F4-H1 HIGH archivos de optimizacion requeridos no publicados/runner no ejecuta refinamientos y API solver fresca invalida; F4-H2 HIGH reuse por existencia y agregador aprueba precios+1/salida economica ausente/particionincorrecta, origen no vinculado. F4-M1 MEDIUM equivalencia SSE/precio sin fundamento y benchmark permite seleccionar aun sin refinamientos convergidos; F4-M2 MEDIUM reporte falsea comparaciones84/split/sensibilidad. F4-L1 LOW redondeo temprano del PoC, impacto max~1.89e-6USD en12casos, distinto de la vulnerabilidad general de origen.76tests PASS sin escrituras oficiales; precios PoC heredados siguen viables. Reparacion1/3 focalizada, sin fase5. Ver HESTON_PHASE_4_fefe46e.md y PHASE_4_REPAIR_1.md.

Fase4 reparacion1 SHA12664a8: F4-H1 RESUELTO en entregables/API/replay (JSON originales y runner,6SSE reproducidas0diferencia, caso fresco/extra real funciona). F4-M1 RESUELTO materialmente (convergencia local obligatoria y diferencias de precios train); F4-L1 RESUELTO a roundoff. F4-H2 HIGH PARCIAL: NaNprecio/ref/cotizacion e Infdefault pasan gate; snapshotfase3NaN sale comoPHASE3_VERIFIED_AUDITED; mallas rawmal/flagsTrue danPASS. F4-M2 MEDIUM PARCIAL: principales comparativas corregidas pero conserva optimo global/convexidad inferida/sobreajuste demostrado y residuos de conteos/unidades.80tests PASS sin cambios oficiales. Reparacion2/3 exclusivamente guardas y reporte, no recalibrar ni fase5. Evidencia HESTON_PHASE_4_12664a8.md.

Fase4 reparacion2 SHA5984a51: F4-M2 RESUELTO materialmente; guardas de pricing97, mallas y snapshot/dependencias cierran contraejemplos anteriores. F4-H2 HIGH PARCIAL porque economia admiteInf/1e9USD conK9 y al sustituir lastPrice por prop_fine se aprueba MAE0 sin comparar fuente canónica.85tests PASS/123.54s y134archivos oficiales intactos; sin fallo nuevo del nucleo. Reparacion3/3 ultima, solo controles economicos y correspondencia de inputs; no recalibrar, no fase5, no cuarta automatica si queda material. Ver HESTON_PHASE_4_5984a51.md/PHASE_4_REPAIR_3.md.
