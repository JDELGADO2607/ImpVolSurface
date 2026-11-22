# PHASE_START — PHASE_6: integración financiera mínima

Base **b4cb3d6840e1596ed656cad1768b642e936c9845**, misma rama/worktree Gemini/PR5. Fase5aprobada con [limitaciones](../audits/HESTON_PHASE_5_b4cb3d6.md). Prioridad humana: terminar resultados reales defendibles, reutilizar motores/calibración, no robustez industrial ni repetir0–4. Puedes usar2–3subagentes reales con archivos disjuntos, sin instalación ni escritores simultáneos; centraliza integración/commit. Si no hay capacidad, continúa sin simularla.

## Objetivo y alcance

Entregar comparación de modelos, griegas y cartera/hedge, stress y un comando de pipelineHeston funcional. Cambiar solo adaptadores/módulos necesarios, tests focalizados y outputs aisladosfase6. Conservar implementaciónSVI e interfaces históricas. No calibrar otra vez, cambiar inputs/vector/bounds, implementar modelos nuevos, frameworks, cachés ni campañas de corrupción. No merge ni force-push.

Reutilizar fases4/5publicadas cuando sus resultados ya satisfacen el cálculo; no regenerar todo por cambiar documentación. Modelos/cotizaciones/parámetros de una única fuente existente. Si hay duplicación de adaptadores, usar el ya aprobado `curve.to_quantlib_term_structure(dense_daily=True)` en los nuevos cálculos en vez de reconstruir nudos redondeados. No rediseñar curvas.

## 1. Comparación sobre muestra común

Usar97puts/142calls con contratos/muestra y particiones congelados. Cuatro columnas claramente identificadas: europeo constanteBS, americano constante1D, europeoHeston y americanoHeston. Para callsq0/r>=0 americano=europeo; puts americanasHeston directo solver2D o precios finos ya publicados. EuropeoHeston puede ser QLsemianalítico; no usar BSconIVamericana como si fuera su europeoHeston.

Reutilizar benchmarkflat44% del comparador existente, etiquetado como supuesto exante; no recalibrarlo para mejorar métricas. Curva común para valoración nueva, D(T)paraBS y curva temporal para1Damericano. Si se conserva comparaciónSVIhistórica, reutilizarla y advertir diferencias de curva/muestra, sin reabrirSVI.

Exportar precios/residuos por contrato y MAE/RMSE por tipo/partición, cobertura y EEP. Separar errorfrentemercado de diferenciaentre motores. La menorMAE no prueba rentabilidad ni identificación del modelo. No nuevaLOO ni otroholdout.

## 2. Cartera y sensibilidades coherentes

Conservar las5patas/cantidades de PORTFOLIO_LEGS en src/portfolio.py. Primas y strikes desde los datos versionados, multiplicador100, sin literales de primas/resultados. Valorar cada pata directamente bajoHeston y agregar qty*multiplier; mostrar valor observado y modelo separados. No valorar riesgo pasando por IVequivalentes mal condicionadas.

Reutilizar métodos de diferencias finitas existentes/adaptarlos al evaluadorHeston: delta,gamma,sensibilidad a sigma0=sqrt(v0) y theta con convención explícita. dP/dv0 o dP/dsigma0 NO es vegaIV; indicar unidad y factor0.01cuando se expresa porpp. Mantener otros cuatro parámetros, curva y política de no recalibración al perturbar. Vanna/volga solo si se reutilizan de forma sencilla para la aproximaciónTaylor del proyecto; no crear nuevas familias de riesgo.

Usar dominios/resoluciones comparables y evitar bumps infinitesimales que amplifiquen ruido. Comprobar h yh/2o malla más fina en dospatas relevantes; reportar estabilidad numérica y efecto económico, sin nueva matriz exhaustiva. Para theta definir si se acorta vencimiento con curva congelada o se hace roll: la primera es aproximación explícita aceptable académicamente; no presentarla como roll exacto. No nuevo framework de roll.

Hedgeacciones=-deltaopciones, con redondeo y residual explícitos; reusar esa misma cartera en stress. Si se reporta capital/margen, calcularlo dinámicamente de posiciones/primas y conservar fórmula académica existente identificada como aproximación, no cálculo regulatorio exacto.

## 3. Stress simple y explicable

RevaloraciónHeston de los mismos contratos/cantidades. Mantener kappa,theta,xi,rho; escenarios instantáneos(dt0) para no introducir complejidad temporal: nulo; spot-5%; spot+5%; sigma0+5pp; spot-20%/sigma0+12pp; spot+15%/sigma0-8pp. Convertir sigma0shock a v0shock=(sqrt(v0)+dSigma0)^2. Son escenarioshipotéticos, no predicciones ni probabilidades históricas. No trasladar shocksSVIde skew/curvatura como parámetrosHeston arbitrarios.

Precio base y shocked con el mismo motor/configuración por pata. PnLestrés=Vshock-Vbase, incluido hedgeacciones cuando se presente; separar mark-to-model inicial frente a precio observado. Escenario nulo debe devolverPnLnuméricamente0por construcción coherente, no por un parche de salida. Comparar delta/gamma/Taylor simple con revaloración para shocks pequeños; declarar sus límites en los grandes.

## 4. Pipeline y cierre indispensable

Adaptación mínima de run_all.py o entradaHeston dedicada documentada que consuma artefactos aprobados y genere comparación/cartera/stress/tablas/figuras sin ejecutar multistart ni pipelinesSVI. Un solo comando reproducible desde inputs versionados y outputs previos identificados. No nueva infraestructura de etapas.

Conservar estrategias/HARexistentes como académicos con sus limitaciones; no desarrollar backtest ni nuevos pronósticos para esta integración. Si una dependencia impide el comandoHeston, aislar solo lo necesario sin borrar historia.

Preparar cierre7/8dentro de la entrega cuando sea práctico: tablas/figuras necesarias, lista breve de limitaciones y guion de10min usando documentación existente. Esos cierres no son nuevas fases de implementación ni otra batería industrial. No bancos/documentos gigantes; breve esquema defendible y referencias existentes bastan.

## Aceptación y pruebas focalizadas

- Muestra/curva/vector coherentes, precios finitos, comparaciónEEPy unidades económicas correctas; no inventar datos ni garantías globales.
- Pruebas reales de agregación de5patas, deltahedge, escenario nulo y separaciónmark-to-model/PnL. Chequear sensibilidad de2patas y Taylor en pequeño shock; no campañas sintéticas de manipulación de archivos.
- Reutilizar evidencia de precisión anterior. En cartera31/59d, auditoría5midió error1D/QL<0.001USD. IV3dson aproximadas y endpoints0.01no son volatilidadidentificada: no usarlos como señal económica, ocultarlos como ceros válidos ni justificar un hedge con ellos.
- Las griegas y valores de stress deben usar mismo modelo, no mezclar sensitividadesBS con revaloraciónHeston. Error material de valoración/consistencia requiere corrección mínima; limitaciones menores se documentan y no bloquean.
- Ejecutar tests nuevos y regresiones afectadas; una corrida del comandoHeston de integración. No repetir toda la auditoría ni cálculoscostososya aprobados. Logs extensos a archivo y resumen breve.

Entregar SHApublicado, comando de ejecución, tablas porcontrato/pata/escenario y resúmenes, pocas figuras útiles, informeBREVE y limitaciones. Corregir en síntesis las afirmaciones5de35/35IVexitosas: hay29/35putsy33/35calls interiores; distinguir valoración de identificación. No reabrir5por esos textos.

Retornar PHASE_READY_FOR_AUDIT porworker_done, con contribuciones de subagentes si se usaron. Codex hará auditoría focalizada de resultados reales y cierre mínimo7/8, luego revisiónhumanafinal. No ampliar metodología ni hacermerge. Antes de trabajoextra aplicar: ¿necesario para funcionar, defender resultados y explicar en10min? Si no, documentar/dejar fuera.
