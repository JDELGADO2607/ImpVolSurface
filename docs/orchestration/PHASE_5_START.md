# PHASE_START — PHASE_5: precios e IV equivalentes Heston

## Base, autorización y objetivo

Base exacta **7f51a811ae5815dadf8c26b46f707e9f7cb0d05c**, rama/worktree Gemini JDELGADO2607/heston-implementation, PR5. La instrucción humana de22-nov levanta el HOLD para continuar y acepta F4-H2 como limitación sobre escenarios artificiales. Leer [decisión de alcance](../audits/HESTON_PHASE_4_7f51a81_ACCEPTED_SCOPE.md) y este encargo; no reparar otra vez fase4.

Objetivo: construir superficie de IV desde precios Heston con los parámetros finales ya disponibles y preparar su uso en integración. **Rigor necesario sobre datos/resultados reales; no infraestructura de robustez.** No nueva calibración, filtros, cambios de muestra o motor2D, proyecciones, clipping de precios, parámetros por tenor ni extensiones Heston. No merge/force-push. No empezar fase6 hasta PHASE_APPROVED de nuevo SHA.

## División de trabajo autorizada

Puedes utilizar2–3subagentes si tu entorno ofrece realmente esa capacidad; no inventar mecanismos ni retrasarte instalándolos. Reparto recomendado: A)inversión americana/curva1D, B)calls/pipeline/tablas/figuras, C)pruebas numéricas y documentación breve. Asignar archivos distintos, acordar interfaces primero y concentrar integración/commit en Gemini. No dos escritores sobre un archivo, ni agentes modificando la rama de coordinación de Codex. Si no hay subagentes, ejecutar el mismo alcance sin ellos.

## Inputs y archivos

Leer vector completo de data/heston/phase4/heston_calibrated_parameters.json y curva determinista aprobada, spot12.33,q0,fecha17-nov-2026,ACT/365. Misma muestra97puts y142calls de contraste congeladas en manifests: no inventar conteos ni seleccionar una nueva muestra favorable. Reutilizar precios Heston propios finos legítimos ya publicados de fase4 donde coincidan contrato/vector/curva, identificando su origen; no volver a calcularlos sin necesidad.

Cambios autorizados: nuevo módulo pequeño de IV Heston(p.ej.src/heston/equivalent_iv.py), pipeline_phase5.py, tests de fase5, artefactos aislados data/heston/phase5/, figuras en subcarpeta de fase5 e informe breve de implementación. Extensión mínima compatible del motor1D existente si necesita consumir la curva; conservar ruta histórica escalar y SVI. No reescribir motores ni refactorizar todo iv_inversion.

## Método obligatorio

**Puts:** precio americano Heston -> Brent sobre la EDP americana1D de volatilidad constante. Resolver P_Am_1D(sigma;misma curva)-P_Am_Heston=0, no usar BS europeo para estas puts. La EDP1D histórica solo acepta r constante: incorporar opcionalmente la curva determinista al cálculo de deriva/descuento con tiempo calendario t=T-tau, preservando el caso escalar. Reutilizar Crank–Nicolson/Rannacher/obstáculo existente. Usar tasas coherentes en cada paso y fronteras; no sustituir silenciosamente toda la curva por r_zero(T). Es una adaptación concreta necesaria, no un nuevo framework de curvas.

**Calls:** bajo q0y tasas no negativas, generar precio europeo Heston con el motor semianalítico disponible y contrastarlo/invertirlo por BS usando D(T)de la curva común (r_zero=-lnD/T es exacto para ese descuento europeo). Las calls observadas no participan en calibración; sus errores son contraste externo. Si el motor QL solo admite fechas enteras, usar tenores de días enteros o rechazar madurez fraccionaria explícitamente; no redondearla sin avisar ni implementar otro motor semianalítico para esta fase.

No mezclar IV americana equivalente, IV europea, sqrt(v0),sqrt(theta) o varianza instantánea. Si se exporta w=T*sigma_IV², identificar cuál IV y verificar esa identidad. No afirmar monotonía global de w o ausencia de arbitraje de una superficie de IV americana por analogía automática con IV europea.

## Inversión y límites económicos relevantes

- Mantener malla/dominio constantes durante cada inversión para evitar que Brent persiga cambios de discretización. Documentar bracket inicial y cualquier ampliación numérica razonable, residual de precio y estado del solver. No aceptar un endpoint solo porque devuelve una prima cercana si la IV no es identificable.
- En puts ITM dominadas por ejercicio o primas prácticamente en la frontera, puede haber IV equivalente no única o mal condicionada a precisión numérica. Reportar estado explícito, NaN o intervalo si realmente puede sustentarse; no forzar sigma_min ni interpretar esas filas como observaciones malas que deban borrarse. No exigir un método sofisticado de intervalos: estado de no identificación es suficiente.
- Para precio fuera de límites, falta de bracket, no convergencia o precisión insuficiente: conservar fila y motivo. No rellenar superficies, extrapolar ni suavizar para esconder huecos. Diferenciar rechazo por datos de observación y por falta de identificación de la IV del modelo.
- Un residual pequeño de Brent no demuestra precisión EDP ni estabilidad IV: en casos representativos contrastar malla más fina y sensibilidad de precio a sigma. No prometer precisión de IV superior a la que permite la sensibilidad numérica local.

## Entregables concretos

1. Tabla97puts: ID,K,T,partición,primaobservada,precioHeston/modelo de origen,IVamericana equivalente, residual1D, estado/motivo y configuración. Calcular también IVobservada con el mismo motor/curva cuando sea identificable para errores comparables; no confundir errorIV con errorprecio.
2. Tabla142calls externas: mismos campos relevantes, precioeuropeoHeston y IVBS modelo/observada, residuales y estados. Documentar asincronía/lastPrice y contratos fuera de límites, sin recalibrar para corregirlos.
3. Grilla descriptiva pequeña predefinida: K={9,11,12.33,15,17}, días={3,31,59,94,212,430,794},35puntos por tipo. Generar precios directos del modelo, luego sus IV; usar rechazos explícitos donde corresponda. No construir un interpolador2D nuevo para valorar. Figuras separadas put/call con ejes/unidades y huecos visibles; la interpolación de dibujo no es un nuevo motor financiero.
4. Métricas de precio e IV sobre muestras comunes válidas: conteos, cobertura, rechazos/causas, MAE/RMSE por tipo/partición cuando corresponda. Mantener denominadores completos y separar ajuste, holdout y contrastecalls. No exigir mejorar MAE al excluir contratos difíciles.
5. Manifiesto sencillo con fuentes, SHA/vector/configuración, versiones, tablas/figuras generadas y comandos; informe breve explicando método, resultados y limitaciones. No crear un sistema nuevo de firmas/cachés, fuzzing de archivos ni tolerancia a corrupción artificial.

## Validación proporcional y criterios antes de resultados

- Primero verificar precios del modelo, luego IV. Preservar presupuesto de discrepancia numérica0.002USD de fases3/4, no convertirlo automáticamente en una tolerancia de volatilidad uniforme.
- Controlar extensión1D en seis casos(K,días,sigma): (9,31,0.25),(12.33,31,0.45),(17,31,0.70),(9,430,0.70),(12.33,94,0.25),(17,430,0.45), mismos parámetros y curva frente a referencia QL americana de volatilidad constante; apuntar<=0.002USD. Usar tres mallas en dos casos sensibles de ese conjunto, no repetir toda la matriz Heston ya auditada. Verificar que curva plana reproduzca ruta escalar antigua.
- Para inversiones identificables: reconstrucción en la misma malla <=1e-5USD cuando permita el motor; comprobar una malla más fina en casos representativos dentro del presupuesto0.002USD y reportar cambio en IV. Brent xtol en sigma se registra por separado. Si una fila está mal condicionada, declarar su limitación; no ajustar el criterio para etiquetarla CONVERGED.
- CallsBS: residual analítico de raíz objetivo<=1e-8USD en casos identificables. Contrastar límites descontados y paridad europea en controles reales representativos. No aplicar paridad europea al precio americano de la put.
- Tests: roundtrip con volatilidades conocidas, comparación independiente de precios1D, caso cercano a intrínseco sin IV identificable y resultados/modelos/unidades coherentes. Ejecutar tests de fase5 y regresiones afectadas; fases0–4una vez antes de entregar. No nuevos escenarios de manipulación/corrupción de tablas: quedan en limitaciones por instrucción humana.
- Una ejecución limpia aislada desde datos versionados debe generar tablas/figuras sin contaminar salidas históricas ni desde tests. No exige reejecutar multistart ni pipeline global completo ahora. Reproducibilidad básica sigue siendo necesaria.

## Qué no debe pasar y retorno

No corregirF4-H2 ni relanzar fase4, no depurar las97puts por contraejemplos sintéticos, no datosinventados/resultadoshardcodeados, no recortar dominios para fabricar métricas, no σHeston=sqrt(v0) como sustituto de IV, no cambios de límites tras evaluar ni griegas/stress nuevos. La implementación debe ser comprensible en la exposición académica; evitar sobreingeniería.

Si detectas un error que afecta precios reales, convergencia o consistencia financiera, reportar evidencia y proponer la solución mínima antes de ampliar alcance. Si solo aparece un caso adicional de robustez artificial, registrarlo como limitación y continuar. Registrar costes reales observados; no dar plazos garantizados ni detenerse por ausencia de subagentes.

Publicar nuevo SHA y PHASE_READY_FOR_AUDIT por worker_done con diff, informe, comandos, resultados, cobertura/limitaciones y contribuciones reales de subagentes si se usaron. Esperar auditoría técnica del SHA para fase6. No merge. La aceptación de limitaciones de robustez no autoriza ignorar fallos materiales en nuestros datos/resultados.
