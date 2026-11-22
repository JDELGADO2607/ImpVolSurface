# PHASE_REJECTED — PHASE_4, reparación1/3 autorizada

## Base, objetivo y fuentes

Base exacta `fefe46ebb7028aa786abf3a8fca7377d667efda4`, misma rama/worktree Gemini, PR5. Leer [informe independiente](../audits/HESTON_PHASE_4_fefe46e.md), scripts/log y [encargo inicial](PHASE_4_START.md). Objetivo: que la entrega publicada se regenere, sus gates verifiquen evidencia real y el informe describa fielmente lo ejecutado. No mejorar el ajuste por iniciativa propia. Última aprobación09d9beb; fase5 sigue prohibida.

## Cambios autorizados y componentes congelados

Editar pipeline_phase4, tests de fase4, documentación e inputs/artefactos de esa fase. Adaptar calibrador solo lo estrictamente necesario para el runner y su trazabilidad, manteniendo API previa. No modificar solver2D, rates_curve, heston_model, datos/split/bounds, objetivo, filtros ni resultados históricos. No rediseñar cachés ni empezar IV/griegas/stress. No merge/force-push.

## Entregable1: reproducción real de optimización y valoración

1. Recuperar **archivos originales** de los tres refinamientos y publicar los inputs/resultados/trazas existentes que faltan. Publicar runner que realmente llame al optimizador y genere esas salidas usando configuración y malla efectivas. Debe existir un comando completo desde fuentes versionadas hasta resultados, sin scripts ocultos ni dependencia de JSON locales no entregados. Distinguir modo regeneración costosa del modo auditoría/replay de resultados originales.
2. No fabricar trazas de convergencia reconstruidas a partir del CSV. Si no se conservan los originales, reconocerlo y comunicar qué ejecución mínima es necesaria para reponer evidencia. No repetir automáticamente las tres optimizaciones de varias horas si se pueden recuperar los originales y reproducir las SSE.
3. Usar `Heston2DSolver().price(...)` y su resultado tipado en todas las ramas de valoración, también ganador distinto del benchmark y refinamiento extra-fino. Mantener dominios/defaults reales aprobados:160/80/min60; fino240/120/min100 y extra320/160/min160, con factoresT ya fijados. No pasar s_min/v_min/m_t a Grid2D ni usar solve/API inexistente. No estrechar dominios a3*S/vmax1 al corregir la llamada: conservar los dominios aprobados del solver.
4. Probar ejecución fresca de las ramas antes ocultas por tablas existentes, mediante casos reales representativos rápidos de K/T y la misma interfaz. El caso de un ganador cambiado debe poder valorarse sin precios previos. La tabla final97 debe provenir del vector exportado y registrar motor/malla/origen.

## Entregable2: integridad sin sobreingeniería

1. Eliminar retornos por mera existencia. **Opción preferida:** evaluar de nuevo las etapas baratas y generar salidas en un directorio aislado, sin reutilizar derivados mutables de fase4. Puede reutilizarse fase3 aprobada si vector canónico completo, inputs, código y mallas coinciden y se comprueba su evidencia con los verificadores ya disponibles. La etiqueta WINNER_POC_CONSERVED no prueba identidad.
2. Si se conservan resultados costosos originales, compararlos con su origen declarado y recalcular SSE con las entradas actuales antes de usarlos. Un hash calculado después de cargar no prueba correspondencia con el experimento anterior. No desarrollar un framework genérico.
3. Antes de PASS: exigir todos los archivos de salida requeridos, esquemas y valores finitos;97 IDs únicos coincidentes con la muestra,60/22/15 según split; parámetros finitos dentro de bounds; por lo menos un refinamiento local realmente convergido y elegible; errores/métricas recalculados desde precios; controles económicos efectivos y controles de malla por valores, no etiquetas. Economía debe cubrir9puntos y sus cotas/prima de ejercicio; no basta con exportar la tabla.
4. Un fallo de etapa debe producir excepción clara o verdictFAIL, nunca mensaje de éxito incondicional ni manifiesto parcial favorable. Los outputs y tiempos deben distinguir optimización original, replay y cálculos nuevos. Registrar hash del pipeline/config además de módulos de pricing y fuentes originales de optimización.

## Entregable3: selección y precisión

1. Recuperar PoC original a plena precisión desde el manifiesto aprobado de fase1; no constantes de seis decimales presentadas como exactas. Redondeo solo en documentos. Los starts ya ejecutados con redondeo pequeño pueden mantenerse si se identifican como tales y se documenta su impacto: no exigir tres nuevas optimizaciones por esa desviación inmaterial.
2. Separar benchmark de convergencia de refinamientos. Si todos los refinamientos fallan, detener la fase con evidencia; benchmark no cuenta como optimización exitosa. Recalcular SSE/RMSE de candidatos admitidos, excluir statusfallidos/NaN/fuera de bounds.
3. Mantener decisión basada solo en train. La regla de conservación por equivalencia numérica está permitida; el literal0.0001USD² no tiene conversión universal a0.001USD en prima ni fue fijado en el encargo. O bien seleccionar el mínimo SSE fino válido, o justificar conservar PoC con cambios de precios reales sobre train y su sensibilidad numérica. No atribuir retrospectivamente un umbral al protocolo. No perseguir un mínimo global ni forzar mejorar el MAE.
4. No usar métricas holdout o calls para escoger candidato/regla. Reportarlas después del vector congelado. Para las métricas de IV se mantiene la reserva a fase5.

## Entregable4: reconciliar informe y sensibilidad

Generar números desde tablas: split37/94/304d, tres tenores retenidos y13train; defaults160/80/min60; vectores efectivamente utilizados; ratioFeller y proximidad de rho. Comparación84: flat comúnMAE~0.0396743, SVIhistórico~0.0684417, Hestonpropio~0.0231092 para la entrega auditada; no usar0.142/0.018 ni mejora80%. Actualizar números si cambian datos derivados al corregir vector, conservando misma muestra y curvas identificadas.

El descenso minúsculo al rho truncado no es un fallo a corregir. Reportar signo y desplazamiento efectivo, no afirmar que toda perturbación aumenta SSE ni que ello demuestra convexidad de objetivo/identificación. Completar doce precios representativos de sensibilidad fijados en encargo o justificar explícitamente cobertura menor como limitación: no declarar realizados doce si hay seis. Diferenciar CIR positivo/Feller de frontera absorbente, y residuos de mercado/modelo/datos de error de motor. No prometer garantías globales desde controles finitos.

## Pruebas de aceptación obligatorias

- Positivo: evidencia original legítima, pasos y métricas coherentes; gate finalPASS con todas las salidas y cobertura.
- Negativos **sobre funciones de producción**, en directorios temporales: precio crudo+1 conservando resumen viejo; salida económica ausente; v0negativo; partición alterada; todos los refinamientosstatusfallidos; cambio de vector con resultados previos presentes. Cada uno debe rechazar o regenerar inequívocamente datos correspondientes al cambio, nunca devolver los precios anteriores como válidos para el nuevo vector.
- Ruta fresca real del solver y caso de ganador nuevo, sin TypeError y comparada con QL bajo idéntico vector. Incluir caso que obligue a comprobar la llamada extra-fina. Evitar tests que solo afirmen un diccionario local o repitan una comparación ajena al pipeline.
- Replay independiente de las SSE publicadas y cumplimiento de configuración. No volver a ejecutar toda fase3: núcleo sin cambios. Mantener tolerancias y muestras del encargo; si hay diferencia numérica pequeña justificarla en vez de modificar umbrales.
- Tests fases0–4 aislados con hashes de artefactos oficiales antes/después, logs completos en archivos. No modificar salidas oficiales desde tests.

## Parada y retorno

Si falta evidencia original irrecuperable, si el coste exige repetir optimizaciones o si aparece defecto real del núcleo fuera de este alcance, informar técnicamente antes de expandir trabajo. No simular resultados ni solicitar permisos ordinarios ya cubiertos. No avanzar a fase5 para aprovechar tiempo mientras esta dependencia está rechazada.

Publicar nuevo SHA y `PHASE_READY_FOR_AUDIT` por worker_done, con diff, comandos de regeneración y replay, informe, artefactos, resultados de todos los contraejemplos, tests y limitaciones. Esta es reparación1/3; resolver la causa en una ronda focalizada. La aprobación solo podrá corresponder al nuevo SHA efectivamente auditado.
