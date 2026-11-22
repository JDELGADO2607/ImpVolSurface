# PHASE_START — PHASE_4: calibración definitiva global de Heston

## Objetivo, base y alcance

Base de implementación `09d9beb060a4a80d9dc4ae7035407cbc8e81e061`, rama `JDELGADO2607/heston-implementation`, PR #5. Iniciar únicamente después del mensaje PHASE_APPROVED de Codex para esa base. Obtener una parametrización Q global defendible, con calibración americana en precios y precios finales contrastados con el solver propio. No exigir superar el ajuste in-sample de SVI ni atribuir identificación física a parámetros Q.

Leer AGENTS, CONTEXT, HANDOFF y PLAN de la rama de coordinación publicada; después esta especificación, criterios y auditoría `HESTON_PHASE_3_09d9beb.md`. Los estados históricos de esos archivos en la rama de implementación no sustituyen el estado vigente de coordinación. No hacer cherry-pick indiscriminado de todos los documentos de coordinación.

Autorizado: nuevo `src/heston/pipeline_phase4.py`, tests de fase4, configuración/adaptación mínima del calibrador para explicitar la malla, artefactos aislados `data/heston/phase4/`, informe `docs/reports/INFORME_FASE_4_CALIBRACION_HESTON.md`. Conservar API de fases anteriores y sus resultados. No modificar el núcleo MCS-IT, tasas, datos, split, filtros o bounds. Si aparece un defecto de esos componentes, reportarlo antes de rediseñar.

## Datos y objetivo invariables

- Spot 12.33 USD, q=0, valoración 17-nov-2026, ACT/365, curva determinista aprobada y adaptador QuantLib común. Registrar hashes efectivos, fecha y convenciones.
- Misma selección de 97 puts: **60 train / 22 strike holdout / 15 tenor holdout**. Conservar identidades de contratos y los vencimientos retenidos completos; calls observadas son contraste externo, nunca objetivo.
- Ajustar únicamente `SSE(Theta)=sum_train (P_Am_QL(Theta)-lastPrice)^2`, sin pesos, normalizaciones por prima ni volatilidades como objetivo. AmericanExercise efectivo para cada contrato. Una sola Theta=(v0,kappa,theta,xi,rho) en todos los vencimientos.
- Bounds heredados: v0,theta=[0.01,1.5], kappa=[0.10,15], xi=[0.05,3], rho=[-0.95,0.95]. No imponer Feller, fijar parámetros por conveniencia ni ampliar bounds para mejorar cifras. Reportar proximidad a fronteras y ratio de Feller.

## Método autorizado y control de coste

Usar **QuantLib para optimizar** y validar después el vector elegido con el solver propio. La fase3 muestra la viabilidad numérica del solver, pero no obliga a asumir el coste de usarlo en cada iteración. Explicar esta decisión en el informe.

1. Recuperar los cinco resultados multistart de fase1 junto con sus estados y procedencia aprobada. Recalcular sus SSE al menos en la malla de calibración original antes de usarlos; conservar el fallo del start4 y la inestabilidad de malla del start3 como evidencia, sin promoverlos a convergidos. No relanzar por defecto los cinco experimentos gruesos ya auditados.
2. Realizar **tres refinamientos locales** con puntos iniciales iguales a los vectores finales de los starts históricos **2, 5 y 1**, en ese orden. Esta selección se basa en train y su ranking fino previo, no en holdouts. Incluir el vector PoC exacto como benchmark invariable, incluso si coincide con el primer punto inicial.
3. Objetivo durante estos refinamientos: QL americano, `m_t=max(60,round(300*T)), x=160, v=80`, sin clipping. El mínimo de 60 debe ser efectivo también en el calibrador: no heredar silenciosamente su mínimo antiguo de 25. Registrar método, eps/tolerancias, máximos de iteraciones/evaluaciones y mallas en un archivo de configuración **antes** de ejecutar los refinamientos. Se permite reutilizar L-BFGS-B existente; presupuesto inicial máximo 35 iteraciones por start. Elegir configuración por escala/numericalidad documentada, no para fabricar un estado de éxito.
4. Registrar cada start, vector inicial/final completo, SSE inicial/final recalculada, RMSE=sqrt(SSE/60), status/success/message, n_iter/n_eval, tiempo, fallos del motor y hits de bounds. No ocultar excepciones mediante una penalización presentada como precio o SSE válida. Guardar diagnóstico de fallos y excluir candidatos no finitos o con terminación fallida de la selección de optimizados.
5. Revaluar **todos los candidatos finales**, incluidos fallidos para diagnóstico, y el benchmark PoC en `QL700/min120/x280/v140` sobre los 60 train. Elegir el menor SSE fino entre candidatos convergidos válidos y benchmark PoC, sin consultar errores holdout. Si gana el benchmark, declarar que se conserva, no inventar una mejora. Exigir al menos un refinamiento local convergido válido para cerrar la investigación; si ninguno converge, reportar bloqueo con evidencia, sin aumentar presupuestos indefinidamente.
6. No es necesario demostrar unicidad ni mínimo global. Si ranking o ganancias son menores que la sensibilidad de discretización observada, declarar equivalencia numérica y limitar la interpretación. No buscar una mejora inmaterial con rondas adicionales.

Decisiones delegadas: organización interna, nombres secundarios de tablas y reutilización de helpers sin cambiar contratos. Cambios de función objetivo, observaciones, bounds, motor, metodología o presupuesto repetidamente agotado requieren consulta técnica a Codex antes de ejecutarse. No son una autorización para consultar al usuario por decisiones rutinarias ya cubiertas.

## Evaluación final independiente de selección

Congelar el vector elegido y su criterio antes de calcular sus métricas holdout. Evaluar después los 97 contratos, sin rechazos silenciosos, con precios observados, QL producción, QL700 y solver propio fino `n_s=240,n_v=120,m_t=max(100,round(600*T))`. Añadir propios defaults reales para comparar precisión productiva. Exportar IDs, partición, K, T, precios crudos, residual frente a mercado, diferencias entre motores y tiempos.

Para los tres mayores errores propios finos frente a QL700 del vector final, controlar QL1000/min160/x360/v180 y propio320/160/max160-round900T; mantener visible la comparación con referencia fija. Si se conserva exactamente PoC y todos los inputs/motores/configuraciones coinciden con fase3 aprobada, puede referenciarse su evidencia validada por hashes en lugar de recomputarla. No construir nueva infraestructura genérica de caché ni reutilizar resultados bajo parámetros diferentes.

Comprobar cotas, finitud, Am>=intrínseco y Am>=EU en controles representativos K=9,12.33,17 y T=31,94,430d del vector final; investigar desviaciones materiales con refinamiento, sin proyección posterior. Si los parámetros finales se alejan de los ensayos fase3, hacer explícito que esa validación no se traslada automáticamente: los controles al vector definitivo son obligatorios.

## Sensibilidad e identificación

Reportar dispersión de parámetros y predicciones de los tres refinamientos y benchmark, con SSE finos comparables. Hacer perturbaciones individuales +/-5% en v0,kappa,theta,xi y +/-0.02 en rho, respetando bounds y registrando el desplazamiento efectivo, sin recalibrar ni tratarlas como escenarios de trading. Comparar SSE train y precios en K=9,12.33,17 a T=31,94,430,794d. No llamar intervalos de confianza a estos escenarios ni afirmar identificación porque el optimizador termina con éxito. No hace falta inferencia estadística sofisticada para esta fase.

## Criterios predeclarados y reporte

- Cobertura 97/97 puts, train60 y holdouts22/15; IDs y particiones idénticos a base. Datos obligatorios ausentes/no finitos deben fallar explícitamente, no producir una selección más favorable.
- Mantener gate de viabilidad: train MAE<=0.080 y RMSE<=0.120 USD; cada holdout MAE<=0.100 USD. Reportar RMSE, máximos, conteos y cobertura por partición/vencimiento incluso si falla. Estos gates no justifican declarar óptimos todos los parámetros.
- Discrepancia propio fino/QL refinado <=0.002 USD en los 97 finales; sensibilidad de referencia QL700/1000 <=0.0005 USD en los tres controles. Reportar también defaults y todo signo económico adverso. Las diferencias entre mallas son estimaciones empíricas, no cotas demostradas.
- Comparar PoC y definitivo sobre exactamente los mismos contratos/curva/motores, y flat/SVI sobre muestra común declarada. Separar errores de ajuste, holdout y motor. No atribuir a Heston diferencias causadas por la curva histórica de SVI. Las métricas de IV equivalente consistentes se completarán en fase5; no aproximarlas con sqrt(v0) ni con una inversión que ignore la curva común.
- Artefactos con inputs/params/config/source/output hashes, versiones, tiempos y ejecución origen. Una tabla incompleta, nula o de otro vector no puede producir PASS. Testear positivo y negativos materiales de selección (status fallido/SSE incoherente), split y artefactos; pruebas siempre en directorios temporales, sin modificar salidas oficiales.
- Ejecutar tests Heston fases0-4. No ejecutar el pipeline histórico completo, rehacer fase3 completa si no cambió el motor ni desarrollar nuevos Greeks, IV, stress o presentación: pertenecen a fases posteriores.

Entregar tablas de calibración por start, precios y métricas por contrato/partición/tenor, controles de malla y sensibilidad, vector final en JSON no redondeado, manifiesto e informe con comandos para regenerar. Si se usan resultados históricos, identificar su SHA y distinguirlos de cálculos nuevos. El informe no necesita copiar los informes anteriores.

## Parada y retorno

Si una ejecución falla, conservar evidencia y explicar si es error de implementación, modelo, datos o diferencia numérica. No filtrar observaciones, cambiar tolerancias después de ver resultados, sustituir AmericanExercise por europeo, usar holdouts para seleccionar, modificar fase3 para fabricar aprobación ni avanzar a fase5. Máximo tres reparaciones de auditoría; no consumirlas en mejoras opcionales.

Publicar nuevo SHA en rama de implementación y responder `PHASE_READY_FOR_AUDIT` por worker_done con SHA completo, diff, informe, configuración, comandos/tests, conteos, tiempos y limitaciones. Esperar PHASE_APPROVED para fase5. No merge, force-push, eliminación de SVI, gastos ni cambios de permisos.
