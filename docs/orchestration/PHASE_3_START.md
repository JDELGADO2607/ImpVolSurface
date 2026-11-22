# PHASE_START — PHASE_3: validación independiente amplia del motor

Base técnicamente aprobada `ea0df6f097904352e5345bb6fbc712008e319bf2`. Rama/worktree Gemini JDELGADO2607/heston-implementation, PR#5. Informe de cierre fase2 publicado junto a esta especificación. **Esta fase valida; no calibra. La calibración definitiva corresponde a fase4 y requiere PHASE_APPROVED de fase3.** No merge ni force-push.

## Alcance y criterios fijados antes de resultados

Mantener datos, particiones y vector global PoC de fase1 congelados. No reajustar parámetros, no nuevos filtros, no optimización de mercado ni uso de holdouts para elegir modelo. Los escenarios paramétricos siguientes son pruebas numéricas hipotéticas; no estimaciones Q adicionales ni shocks económicos recomendados.

Objetivo comparativo predeclarado0.002USD, un quinto del tick0.01, para precios bajo los mismos parámetros/contratos. Separar error propio, error de referencia e interpolación de curva. Las comparaciones son numéricas sobre puntos finitos, no una demostración global de arbitraje ausente. Si un régimen no cumple, conservar todos los resultados y analizar causa; no modificar tolerancia, excluirlo en silencio ni declarar aprobado el dominio completo. Una restricción justificada del dominio o aumento de resolución debe documentarse con evidencia y someterse al auditor.

## Matriz congelada

1. **Mercado97 puts:** todos los contratos de puts_selected_clean.csv, vector PoC aprobado, spot12.33,q0,fecha17-nov-2026 y curva común. Evaluar API propia con sus defaults reales (sin sustituirlos por una malla de prueba distinta), malla fina n_s240/n_v120/m_t=max(100,round(600*T)) y QuantLib americano refinado. Reportar97/97 o cada rechazo, causas y cobertura. Error máximo, MAE/RMSE numérico frente a referencia, por tenor y partición60/22/15. El error frente a mercado es descriptivo, no una nueva calibración ni otro holdout optimizado.
2. **Regímenes hipotéticos:** para cada fila siguiente usar K9,12.33,17 y plazos10,94,430d, puts europeas y americanas:54 puntos de parámetros/contratos,108 precios. Curva común y q0. No seleccionar solo puntos favorables.

| ID | v0 | kappa | theta | xi | rho |
| --- | ---: | ---: | ---: | ---: | ---: |
| A | Vector PoC exacto del manifiesto fase1 | mismo | mismo | mismo | mismo |
| B | PoC | PoC | PoC | PoC | 0 |
| C | PoC | PoC | PoC | PoC | +0.70 |
| D | 0.04 | 2.0 | 0.04 | 0.30 | −0.60 |
| E | 0.04 | 1.0 | 0.04 | 0.60 | −0.70 |
| F | 0.36 | 2.0 | 0.25 | 0.60 | −0.40 |

E viola Feller y es un control obligatorio, no una razón automática para descartarlo. Reportar ratio, sin imponerlo en calibración.

3. **Límites:** xi0 exacto con v0=theta0.20,kappa2,rho0, tasas planas0 y0.05, K11/12.33/15 y31/94d: europeo BS independiente, americano EDP1D/CRR refinados con idénticas hipótesis. Probar v0=0 con deriva de varianza positiva; si QuantLib no admite ese punto, documentar limitación de referencia y controlar límite v0 descendente y refinamiento propio, sin inventar una coincidencia. Payoff a T0 ya probado, mantenerlo.
4. **Continuidad y fronteras:** casos históricos K14.75 a31/37d, K20.42/612d,K5/430d,K10/31d, enero2029, tres días y extremos temporales. La matriz97 cubre muchos; completar faltantes. Añadir vencimiento27.5d y pequeñas perturbaciones temporales al mismo strike para continuidad y refinamiento propio; no compararlo con QuantLib redondeando la fecha sin declarar el cambio contractual. Puntos fuera del dominio deben rechazarse/documentarse claramente.

## Referencias y convergencia

QuantLib debe valorar americano con AmericanExercise, mismos cinco parámetros y spot/dividendos/curva, sin calibrador europeo. Europeo semianalítico con integración controlada (p.ej. órdenes144/192 o constructor adaptativo cuando proceda); no prometer precisión solo por el orden. La referencia americana debe estimar su propio error: malla fina y un refinamiento adicional en puntos sensibles, como punto de partida tFactor700/min120/x280/v140 y refinamiento tFactor1000/min160/x360/v180 en los controles sensibles, buscando discrepancia<=0.0005USD en esos controles. Publicar si la referencia no alcanza precisión suficiente.

Control propio: producción/defaults reales, malla fina anterior y refinamiento adicional n_s320/n_v160/m_t=max(160,round(900*T)) para las3 mayores discrepancias observadas en mercado97 (regla fijada ahora), más un caso ATM por régimenB–F. Separar refinamiento temporal y espacial, mantener dominio; estudiar ampliar Smax/vmax con resolución local comparable. Registrar al menos3 niveles en los casos representativos; no inferir orden global de una sola diferencia. Comparar la malla fina, pero reportar también cualquier fallo del default para no esconder un problema cambiando la interfaz auditada.

La curva bootstrap original y el adaptador diario QuantLib coinciden en fechas enteras, con aproximación entre nodos diarios. Medir/declarar esa discrepancia y la integración de r(t=T−tau), especialmente pasos que cruzan nudos. No confundir tasa cero con forward instantáneo ni llamar exacta la integración por punto medio a través de un salto.

## Propiedades económicas y diagnóstico del obstáculo

Sobre precios crudos: finitud, cotas aplicables, americana>=intrínseco y>=europea, monotonía en strike, convexidad de puts y monotonía americana temporal a K fijo bajo una única dinámica. Usar mallas de strikes regulares e irregulares; propuesta congelada K7,9,10.5,11,12.33,13.4,15,17,20.42, plazos3,31,94,430,794d al vectorA. Reutilizar precios coincidentes. Reportar todo signo adverso y cómo varía al refinar, no corregirlo con clipping/proyección posterior.

Propagar incertidumbre de precio a los controles: para butterfly ponderado alpha*Plo+(1−alpha)*Phi−Pmid, error<=alpha*epsilon_lo+(1−alpha)*epsilon_hi+epsilon_mid; no usar0.002USD como tolerancia de una segunda derivada con otras unidades. Los epsilon estimados por malla no son cotas teóricas universales. Clasificar violaciones materiales solo con reproducción y error numérico contrastado; no borrar efectos pequeños de interpolación como F2-L1.

Conservar distinción entre identidad algebraica IT y consistencia EDP. Evaluar cerca de ejercicio/continuación y con refinamiento. El diagnóstico trapezoidal de fase2 es un control interior local; no demuestra por sí solo error global de segundo orden. Comprobar que los resultados de no arbitraje no se apoyen únicamente en lambda*(U−g)=0.

## Entregables y límites de autonomía

Código nuevo principalmente de validación/tests y pipeline aislado data/heston/phase3/, informe docs/reports/INFORME_FASE_3_VALIDACION_HESTON.md con mallas, parámetros completos, fuentes, tiempos, cobertura/rechazos, todas las discrepancias y limitaciones. Incluir manifiesto que vincule inputs, parámetros, versión de código y salidas; tests sin escribir artefactos oficiales. Reservar pipeline histórico global para integración.

No ampliar contratos ni calcular nuevas griegas. El guion de defensa de fase2 sigue siendo borrador, no aprobado: marcar ese estado y no reutilizar afirmaciones de estabilidad universal, exactitud o independencia demostrada que sus ensayos no prueban. Reconciliar cifras de nuevos informes desde CSV; las tablas de defecto bruto y norma por año tienen ratios distintos. La síntesis final se hará en fase8.

Si encuentras un defecto material del núcleo que impide validar, comunicar evidencia reproducible antes de rediseñarlo. Se autorizarán reparaciones focalizadas con nuevos SHAs; no fabricar un PASS ni ajustar criterios tras ver resultados. Máximo3 rondas de reparación de fase3. Las limitaciones no materiales se documentan sin perseguir perfección numérica.

Publicar SHA completo nuevo y PHASE_READY_FOR_AUDIT con archivos/diff, comandos, evidencias y fallos pendientes mediante worker_done. Esperar auditoría técnica independiente antes de fase4. Ningún resultado de esta fase autoriza calibración por iniciativa propia ni merge.
