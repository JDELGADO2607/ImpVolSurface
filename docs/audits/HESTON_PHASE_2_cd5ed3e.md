# Auditoría independiente Heston fase 2 — construcción del solver propio

SHA auditado `cd5ed3e08794af474cee1d56a5862eb1a8647d79`, publicado en PR#5; base aprobada `654d1c2d05a0301dc3068cdc34219df3d42d2af7`. Extracción limpia, sin modificar implementación. Publicación del auditor en rama de coordinación, PR#4. El commit del informe y evidencias es distinto del auditado y queda identificado en HANDOFF e historial.

**PHASE_REJECTED**, reparación focalizada **1/3**. El núcleo MCS–IT para puts tiene evidencia numérica favorable y pasa el gate inicial de precios. Los pendientes son el contrato de la interfaz y garantías matemáticas/documentales que exceden lo que se ha verificado. No se pide sustituir el método ni mejorar artificialmente el ajuste. Hallazgos: **0 BLOCKER,0 HIGH,2 MEDIUM,1 LOW**; el LOW se acepta como limitación inicial, sin exigir reparación inmediata.

## Evidencia favorable reproducida

- 34 tests de fases0/1/2 aprobados en66.49s. Hashes de todos los archivos existentes bajo data/, docs/, results/ antes/después: cero cambios. Los cuatro hashes de outputs del manifiesto fase2 coinciden.
- Los12 precios smoke exportados se reproducen con discrepancia máxima6.66e−15USD. Comparación independiente contra referencias más finas, no solo la malla del pipeline: europeo AnalyticHestonEngine de orden192; americano FDM con tFactor700,mínimo120,x280,v140. Máximo error0.000330390USD, menor que0.01 del gate inicial y que0.002 en estos12 puntos. **Esto no aprueba todavía la matriz amplia de fase3**.
- El núcleo de valoración implementa operadores propios, sistemas tridiagonales y etapas MCS–IT; no llama a un motor QuantLib. Hay imports transitivos opcionales por los tipos y curva existentes, distintos de usar QuantLib para calcular NPV. El algoritmo tridiagonal se contrasta independientemente con resolución matricial densa: error máximo1.11e−16.
- Crecimiento del dominio Smax100→160 y vmax10→20, aumentando la resolución para conservar aproximadamente el paso transformado local: diferencias1.12895e−5USD a94d y2.55575e−6 a794d, put ATM, malla inicial120/60/150. No es prueba global de independencia del truncamiento.
- Se ejecutó xi=0 exactamente, v0=theta=0.20, kappa2 y rho0 con tasa plana0.05. Se contrastan europea con BS independiente y americana con CRR independiente de2500/5000 pasos y EDP1D existente800/800, sin cambiar hipótesis. Véase tabla y scripts.

| Caso xi=0 | Europeo2D | BS independiente | Americano2D | CRR5000 | EDP1D800/800 |
| --- | ---: | ---: | ---: | ---: | ---: |
| K12.33,94d | 1.0295658253 | 1.0297435342 | 1.0420397474 | 1.0422111708 | 1.0421646427 |
| K15,31d | 2.6615858927 | 2.6616629115 | 2.6913326240 | 2.6914635441 | 2.6914279056 |

La prueba entregada por Gemini usa xi=1e−5 en su límite; eso es una aproximación, no xi0 exacto. La auditoría adicional sí prueba el caso exacto indicado arriba. El error observado sigue debajo de0.002USD. No se necesita reimplementar otro motor.

## Contraejemplos históricos y puntos adicionales

Vector PoC aprobado, mismo spot12.33,q0 y curva, precios americanos brutos:

| K | Días | Precio2D | QuantLib más fino | DiferenciaUSD |
| --- | ---: | ---: | ---: | ---: |
| 14.75 | 31 | 2.4318701802 | 2.4317582346 | 0.0001119456 |
| 14.75 | 37 | 2.4427365667 | 2.4426516764 | 0.0000848903 |
| 20.42 | 612 | 8.2121410230 | 8.2117287509 | 0.0004122721 |
| 5 | 430 | 0.0838561651 | 0.0838722598 | −0.0000160946 |
| 10 | 31 | 0.0427166600 | 0.0427383174 | −0.0000216574 |
| 17 | 794 | 5.6082424751 | 5.6078160467 | 0.0004264284 |

Estos puntos no muestran los defectos materiales de interpolación SVI que motivaron el cambio. No demuestran ausencia de arbitraje global ni validan todos los parámetros, strikes, vencimientos y resoluciones del nuevo motor. No se recalibra la muestra ni se optimiza con holdouts.

## F2-M1 MEDIUM — Interfaz devuelve resultados que aún no soporta

`src/heston/solver_2d.py`, interfaz price y líneas482–510,525–550 aproximadamente: acepta option_type=C y construye payoff de call, pero ambas resoluciones implícitas imponen valor0 en Smax. Esa frontera es de put, no de call. No se encuentra un rechazo de contratos distintos de P.

Reproducción concreta: vector PoC, K12.33,T31/365,r0.05,q0,spot90,option_type=C,is_american=False,m_t100, dominio por defectoSmax100. Devuelve **43.9339152440USD**. La cota europea C>=max(0,S−K*exp(−rT)) exige **77.7222492553USD**. No es una diferencia numérica irrelevante. El spot90 es un diagnóstico de la interfaz genérica anunciada, no un contrato observado de NU ni evidencia de que los12 smoke puts fallen. La severidad es MEDIUM por estar fuera del alcance autorizado de puts de esta fase.

Corrección mínima autorizada: **rechazar explícitamente calls y tipos no soportados**, con test de fallo claro. No implementar calls como ampliación de esta fase. La posterior superficie call europea podrá usar su motor validado y la metodología de fase5.

La misma interfaz entrega theta=0.0 para madurez positiva aunque el comentario dice expansión futura. Para un put ATM94d,spot12.33,tasa plana0.05 y vector PoC, devuelve0; perturbación independiente de madurez±0.0001años, misma malla, da theta calendario≈−1.84094075USD/año bajo esa convención. El0 es un placeholder, no una sensibilidad calculada. Retirar ese resultado o representarlo como no disponible, sin exigir calcular nuevas griegas en fase2.

El campo vega realmente estima dP/dv0 mediante la solución en varianza, no una sensibilidad por punto de IV. La derivada puede ser útil, pero debe llamarse sensibilidad a varianza inicial y declarar sus unidades, sin presentarse como vega de volatilidad implícita. Delta/gamma y demás sensibilidades siguen preliminares y no validadas para uso en cartera. No autorizar cobertura con ellas todavía.

## F2-M2 MEDIUM — Certificación del LCP y de matrices no se deriva de los controles

`src/heston/solver_2d.py`, líneas499–518; informe secciones2/8/9 y10, especialmente líneas61,240–243,270–275,305–317.

Los controles implementados son U>=g,lambda>=0 y lambda*(U−g)=0. Son propiedades algebraicas de la actualización IT: si x=Yhat−dt*lambda_old, U=max(x,g) y lambda_new=max(0,(g−x)/dt), el producto es0 para cualquier x. No examinan por sí solos si (U_n−U_prev)/dt−L_hU es el multiplicador. Por tanto, la frase “desacopla de forma exacta las restricciones del LCP continuo” y la inferencia de resolución exacta del problema americano no están demostradas. El algoritmo IT publicado aproxima el LCP; no hace desaparecer el error de splitting y discretización.

Como contraste, la auditoría calcula una **consistencia temporal trapezoidal interior**:

E=U_n−U_prev−dt*[0.5*(L_hU_n+L_hU_prev)+0.5*(lambda_n+lambda_prev)].

Se usa tasa plana0.05,T0.25,misma malla80/40 y dominio, snapshots con el mismo dt obtenidos de madurezT y T−dt. Restricción interior8<S<18 y0.04<v<0.4. No se llama a esto residuo exacto del paso MCS ni se deduce que MCS esté incorrecto por discrepar del trapecio. Es un diagnóstico independiente de consistencia con la EDP, separado de la identidad IT:

| Pasos | Campo comp del solver | maxabs(E) USD | maxabs(E)/dt USD/año |
| --- | ---: | ---: | ---: |
| 20 | 0 | 0.0051840138 | 0.4147211070 |
| 40 | 0 | 0.0009930245 | 0.1588839216 |
| 80 | 0 | 0.0002022465 | 0.0647188722 |

Los defectos disminuyen al refinar, evidencia favorable; no son0 a máquina aunque el campo comp sea0 en todos los casos. No se impone una tolerancia nueva a este diagnóstico ni se exige resolver un LCP2D exacto.

El informe también afirma que dividir −rV entre A1 yA2 garantiza matrices M y estabilidad incondicional. La división no controla el signo de los coeficientes de deriva central. Con la propia malla por defecto y parámetros PoC, la subdiagonal de A1 tiene mínimo−4.14966824 y171 coeficientes negativos; al formar I−theta_ADI*dt*A1 existe una entrada fuera de diagonal **positiva0.00117479192**. En A2 también hay dos coeficientes inferiores negativos, mínimo−26.79182143. No se cumple la condición de matriz Z necesaria para ser una M-matriz. Esto refuta esa afirmación, **no demuestra por sí solo inestabilidad del esquema MCS**.

La referencia primaria [Haentjens e In ’t Hout](https://arxiv.org/pdf/1309.0110), secciones3–5, estudia la adaptación ADI–IT y su error/convergencia. Las condiciones de resultados de estabilidad no son una certificación universal de esta malla, fronteras, tasas, interpolador y obstáculo. Conservar fuentes y explicar hipótesis; no inventar demostraciones a partir de smoke tests.

Corrección focalizada: identificar las tres métricas actuales como factibilidad/complementariedad algebraica IT con unidades correctas; lambda tiene USD/año, por lo que lambda*(U−g) tiene USD²/año. Documentar y conservar un diagnóstico independiente de consistencia/defecto temporal con refinamiento (puede reutilizar la evidencia adjunta citándola y reservar validación extensa a fase3). Eliminar garantías no demostradas de exactitud continua, M-matrices o estabilidad incondicional del código. No rediseñar el solver solo para hacer cierta una frase documental.

Corregir además el orden de fases: **fase3 es validación independiente amplia del motor; fase4 es calibración definitiva**. El mensaje de entrega y el informe proponen calibrar en fase3 e incluso citan un libro completo de114 opciones sin fuente. Muestra vigente97 puts,60train/22strike/15tenor; no hay autorización para nuevas observaciones ni para saltarse el gate de validación. La precisión0.002 en12 casos no debe figurar como aprobación ya obtenida de fase3. Esto no es evidencia de que se haya ejecutado esa calibración; debe corregirse antes de asignar la siguiente tarea.

## F2-L1 LOW — Fronteras e interpolación no conservan exactitud económica a máquina

La interpolación cúbica no preserva automáticamente el obstáculo entre nodos. Ejemplos con spot12.33: K20/3d devuelve7.6699984509 frente a intrínseco7.67; K30/31d devuelve17.6699978819 frente a17.67. En una evaluación continua independiente del interpolador para una malla K20/31d el menor gap fue−1.79384e−6USD. Son errores inferiores a0.002 y no constituyen un defecto material del precio en los casos examinados. No añadir clipping artificial para ocultarlos; reportar tolerancias.

La fila S=0 europea, K12.33,T1,r0.05,m_t20, da11.7286716229 frente a descuento exacto11.7286588041 (diferencia1.28188e−5). La frontera se impone antes de cada solve S y el solve v la modifica ligeramente. No se exige corregirla ahora por su escala observada, pero no llamarla exacta a máquina ni omitir sus efectos en la validación amplia. No se ha probado su comportamiento con todo parámetro/grilla.

## Trazabilidad, límites y siguiente acción

Código y precios se auditan sin modificaciones. Se reprodujo la tabla smoke y se comprobaron hashes; no se regeneró todo el pipeline histórico ni se repitieron las20 valoraciones de la tabla de convergencia. Se realizaron controles independientes de espacio/dominio, límites, nuevos contratos y consistencia temporal. No se ha validado uso en calibración, Greeks de producción, superficie equivalente, stress ni estrategias.

Reparación1/3 acotada a F2-M1/F2-M2: restringir API a puts y resultados realmente disponibles, corregir semántica de sensibilidad v0, ajustar diagnóstico/documentación y secuencia de fases, añadir tests negativos pertinentes y preservar precios de puts. No cambiar calibración, muestras, tasas, parámetros ni tolerancias para pasar. No implementar calls/griegas adicionales, no reemplazar MCS–IT y no ejecutar integración global. F2-L1 es limitación aceptada en la fase inicial, no obligación inmediata de reparación.

Tras nuevo SHA publicado, Codex reauditará. Solo después de PHASE_APPROVED se asignará fase3 de validación; **no calibración**. La viabilidad del núcleo de puts es favorable. No merge/force-push ni modificación de rama de coordinación por Gemini.

Scripts independientes: `repro_phase2_cd5ed3e.py` (precios y contraejemplos), `repro_phase2_cd5ed3e_aux.py` (dominio, tridiagonal y consistencia), `repro_phase2_cd5ed3e_limits.py` (xi0, CRR/EDP1D y API), `repro_phase2_cd5ed3e_tests.py` (pytest/hashes), log `HESTON_PHASE_2_cd5ed3e_evidence.txt`, tabla `HESTON_PHASE_2_cd5ed3e_smoke.csv`. Copiar scripts desde coordinación a docs/audits de una extracción limpia del SHA, instalar requirements-heston.txt y ejecutar desde raíz `python docs/audits/<script>.py`. Solo se generan logs/tablas del auditor, sin escribir artefactos oficiales.
