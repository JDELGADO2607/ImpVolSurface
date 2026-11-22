# PHASE_REJECTED — PHASE_4, reparación2/3

Base exacta12664a8ca88fd9c3f365fe449391af9deeb5f19d, misma rama/worktree/PR5. Leer [informe](../audits/HESTON_PHASE_4_12664a8.md), su script de controles y [reparación1](PHASE_4_REPAIR_1.md). Último aprobado09d9beb. Objetivo único: cerrar F4-H2 y reconciliar F4-M2. F4-H1/API, F4-M1/control de selección y F4-L1/precisión ya tienen controles favorables. **No repetir optimizaciones ni cambiar el vector para cerrar esta ronda.**

## Alcance exacto

Modificar pipeline_phase4, tests de esta fase, informe y metadatos/artefactos afectados. Puede reutilizar verificadores existentes de fase3, sin modificar sus garantías ni la evidencia congelada. No modificar motores, tasas, datos, split, bounds, función objetivo, esquema numérico o criterios. No empezar fase5, ni merge/force-push. No desarrollar un framework genérico de integridad.

## 1. Finitud antes de cualquier agregado

En la interfaz de cierre y la ruta real que la alimenta, exigir columnas de pricing obligatorias existentes y finitas antes de MAE/RMSE/max: K,T,lastPrice y precios QL producción/fino, propios default/fino, además de parámetros y controles numéricos requeridos. Especificar el esquema; no rechazar indiscriminadamente campos opcionales legítimamente N/A de otros módulos. Un NaN/Inf debe lanzar error claro con columna/contrato o generar FAIL explícito, nunca omitir la observación ni conservar cobertura97/97.

No arreglarlo con fillna, dropna, clipping, imputación o cero. No basta convertir una reducción a otra si sigue faltando verificación de cobertura efectiva. Comparar IDs, cotizaciones/contratos y etiquetas de partición con la fuente/split canónicos; derivar resúmenes de los precios validados o rechazar contradicciones antes de publicar.

## 2. Reutilización fase3 con origen real

La condición actual de etiquetaPASSED y np.allclose no verifica archivos ni dependencias. Antes de copiar precios, usar el verificador existente de fase3 para comprobar tabla, inputs financieros, código de pricing, configuración y vector canónico; no recalcular hashes después y tratarlos como aprobación. Identidad de vector con rtol=0 y tolerancia de roundoff explícita, no rtol implícito que acepte cambios de parámetros. Los defaults y mallas deben coincidir.

Si cualquier comprobación falla, detener la reutilización con error o calcular fresco usando el motor aprobado y registrar nuevo origen. No etiquetar PHASE3_VERIFIED_AUDITED para archivo alterado. Alternativa sencilla autorizada: desactivar la reutilización de fase3 y calcular fresco; no cambiar calibración ni montar otra infraestructura de caché. Elegir una sola solución clara.

## 3. Mallas: gate desde precios, no flags

Antes de PASS comprobar tres IDs esperados, referencias finitas y calcular de precios crudos las diferencias QL700/1000 y propio fino/extra. Contrastar0.0005USD/0.002USD vigentes. Verificar coherencia con las columnas derivadas/flags o regenerarlas. No aceptar abs_diff1USD con flagsTrue. No relajar tolerancias ni repetir matriz global3: esta reparación no cambia el núcleo.

## 4. Informe defendible

Conservar decisión académica de mantener PoC. Explicar que A mejora ligeramente SSE y produce cambios pequeños de precio; eso permite mantener benchmark por materialidad/continuidad, **no demuestra** sobreajuste o que la mejora provenga necesariamente de ruido. Eliminar “Óptimo Global” y la prueba de convexidad del objetivo por perturbaciones aisladas. Separar dinámica ideal y garantías efectivamente verificadas del evaluador numérico. No declarar ausencia global de arbitraje demostrada por una muestra.

Reconciliar automáticamente desde tablas: tenores retenidos7/5/3contratos en37/94/304d; ratiosFeller históricos; start3SSE fino21.46878; conversiones USD-centavos en JSON/racional de selección; etiquetas benchmarkREFERENCE, no una nueva optimización convergida. Distinguir tiempos de optimización original, replay y ensamblado; si no hay medición global válida, indicarlo, no0segundos como duración completa. No editar datos para coincidir con texto ni afirmar pruebas no ejecutadas.

## Pruebas obligatorias y criterio de cierre

1. Caso legítimo debe pasar con parámetros/métricas sin cambios materiales.
2. Repetir sobre **funciones reales de producción**, en temporales, los casos del script independiente: NaNprecio, NaNreferencia, NaNcotización, Infdefault; precio+1; archivo económicoausente; parámetrosinválidos; todoslocalesfallidos; partición/resumencontradictorios; errorreal1USDmalla/flagsTrue. Los inválidos deben rechazar; una regeneración canónica de etiquetas/resumen es válida si se registra y nunca conserva salida contradictoria.
3. Alterar precio de fase3 aNaN manteniendo manifiesto original: step5 debe rechazar su origen o calcular fresco finito; nunca provenanceverified. Añadir control positivo con snapshot legítimo. Probar fallo de dependencia/inputs mediante el verificador realmente invocado; no solo testear un helper que producción ignora.
4. Validar ruteo fresco con caso pequeño real ya aprobado; no repetir las tres optimizaciones. Ejecutar tests fases0–4 aislados, registrar hashes antes/después sin cambios oficiales. No tests que solo comparen diccionarios locales o repitan fórmulas desconectadas del pipeline.

Entregables: nuevo SHA, diff focalizado, informe corregido, comandos exactos, resultados de positivos/negativos, manifest con origen real y artefactos coherentes. Mantener configuración y criterios. Si el cambio solo afecta validación, no es necesario regenerar cada sensibilidad y cada precio inalterado; preservar evidencia previa correctamente vinculada y actualizar únicamente lo afectado.

Retornar PHASE_READY_FOR_AUDIT por worker_done con SHA completo publicado y limitaciones. Esta es reparación2/3, no fase3 otra vez. Si surge un defecto de motor o una necesidad de recalibrar, detener esa expansión y consultar a Codex con evidencia. Esperar aprobación técnica del nuevo SHA para fase5.
