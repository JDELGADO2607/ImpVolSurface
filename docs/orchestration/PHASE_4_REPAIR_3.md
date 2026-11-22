# PHASE_REJECTED — PHASE_4, reparación3/3 FINAL ordinaria

Base5984a514ae983586a4e63a5affb0e17889f1dad4, mismo worktree/PR5. [Informe y evidencia](../audits/HESTON_PHASE_4_5984a51.md). Último aprobado09d9beb. F4-H1/M1/M2/L1 cerrados en control material; solo F4-H2 permanece parcialmente abierto. No repetir optimizaciones, reabrir diseño del motor ni iniciar fase5. Si persiste defecto material después de esta ronda, no habrá cuarta reparación automática.

## Objetivo y archivos autorizados

Cerrar dos validaciones que faltan en el gate: el conjunto económico9 y correspondencia del pricing97 con inputs canónicos. Autoriza pipeline_phase4/tests/informe y artefactos derivados afectados; no cambia fuente de datos, split, curva, bounds, objetivo ni vector. Mantener los controles de finitud, malla y snapshot ya corregidos. No caché genérico, nuevas funcionalidades, merge ni force-push.

## A. Controles económicos desde evidencia real

En la función de cierre, antes de desigualdades y flags:

1. Exigir esquema y finitud de campos financieros obligatorios de los9controles: K,T,spot,preciosAm/EU,intrínseco y prima de ejercicio si se exportan. No aplicar esto a campos opcionales N/A legítimos de otras tablas. Comprobar los9IDs únicos/tuplas de strikes9/12.33/17 y días31/94/430 establecidos, sin duplicados que conserven longitud9.
2. Derivar intrínseco=max(K-S,0), primaAm-EU y cotas pertinentes usando los parámetros de mercado del proyecto. Para puts americanas con curva no negativa: intrínseco<=Am<=K, a tolerancia numérica ya vigente. Comprobar finitud y límites europeos aplicables. No confiar en una columna de intrínseco o flags antiguos para validar un precio cambiado.
3. Recalcular monotonías en K/T y convexidad no uniforme desde esos9precios, conservando unidades y tolerancias previamente justificadas; rechazar o reconstruir campos derivados incoherentes. No exigir tolerancia cero al error numérico ya aceptado. No inventar una tolerancia mayor para aprobar la tabla.
4. No imputar, eliminar filas, aplicar clipping o sustituir1e9porK. Una observación imposible/infinita debe fallar con un diagnóstico claro.

## B. Contratos y primas canónicos

Unir pricing97 a puts_selected_clean por contractSymbol con validación1a1. Comparar los campos financieros/contractuales usados: strike, lastPrice, tau_years y fecha/días cuando se exporten, además de las particiones ya verificadas. Exigir coincidencia a tolerancia de serialización/roundoff, no al presupuesto0.002USDdel motor. No aceptar una prima cambiada como nueva fuente por calcular después un hash de esa salida.

Las métricas deben usar la prima canónica. Si se decide regenerar columnas/resúmenes desde la fuente, registrar inequívocamente la regeneración y no conservar artefactos contradictorios. El caso df_puts.lastPrice=df_puts.prop_fine_price debe rechazarse o restaurarse explícitamente desde fuente sin producir un ajuste perfecto falso. No es una autorización para cambiar precios observados o selección.

## Pruebas obligatorias sobre producción

- Positivo: artefactos legítimos y gates anteriores conservados.
- Económico: Am=Inf y Am=1e9conK9 y flagsTrue deben rechazar; NaN en campos obligatorios, conjunto de9conduplicado, intrínseco/EEP derivados incoherentes y precio alterado que contradiga las propiedades declaradas deben rechazar o regenerarse desde evidencia válida, nunca PASStarjetasTrue.
- Canónico: sustituir97primas por preciosmodelodebe rechazar/restaurar fuente; alterar strike, fecha o madurez de un contrato manteniendoID debe detectar inconsistencia. Permitir solo diferencias de serialización justificadas, no cambiar criterios al ver datos.
- Repetir los negativos resueltos en las dos rondas anteriores: NaN/Infpricing, precio+1, archivoausente, parámetrosinválidos, fallostodosrefinamientos, partición/resumencontradictorios, mallasrawmal/flagsTrue y snapshot/input/código alterados. No pruebas que solo reimplementen la condición en un diccionario local.
- Suite fases0–4 aislada y hashes antes/después sin escritura oficial. No otra optimización ni pipeline histórico completo; conservar resultados costosos inalterados con origen correcto y actualizar únicamente evidencia afectada.

## Entregables y parada

Nuevo SHA publicado, diff focalizado, comandos/evidencias de positivos y negativos, informe/manifest reconciliados. Corregir de paso residuos editoriales del informe (0.00184USD=18.4%del tick0.01; presupuesto numérico empírico, no cota probada), sin modificar precios/parámetros/tolerancias. No declarar aprobada la fase propia ni empezar5.

Responder PHASE_READY_FOR_AUDIT por worker_done con SHA completo, evidencia y limitaciones. Si detectas necesidad real de cambiar motor, metodología o datos, detener esa expansión y consultar a Codex. Este encargo es la tercera y última reparación ordinaria: debe resolver la causa de integridad con controles coherentes sobre todas las entradas que sustentan el dictamen, sin ampliar el alcance académico.
