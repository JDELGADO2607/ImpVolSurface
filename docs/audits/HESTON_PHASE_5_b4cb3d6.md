# Fase5 — auditoría focalizada

**PHASE_APPROVED**, SHA **b4cb3d6840e1596ed656cad1768b642e936c9845**, PR5. Fecha22-nov-2026. Extracción limpia del commit publicado; alcance según prioridad humana de mínima complejidad suficiente. No recalibración ni reapertura0–4.

Se implementan EDP1D con curva para inversión americana de puts y precio europeoHeston/BS para calls; vectorHeston conservado. Tablas completas97puts/142calls y grillas35por tipo. Inversiones interiores88puts/140calls; las restantes conservan estado y se excluyen de las métricas de IV común, sin borrar contratos. MAEprecio puts0.02384725/RMSE0.03403627USD y calls0.08729128/0.12809207USD, reproducidos desde tablas. IVmodelo/observación comunes:88puts y137calls; MAE2.5198/12.7531puntos porcentuales respectivamente. No interpretarlos como nueva calibración ni prueba de rentabilidad.

**Verificación independiente:**15puts reales (K11–15a31/59d y opciones3d) repriciadas a susIVpublicadas con QLamericano700/700y EDP1D900/600. En núcleos31/59d máximo errorQL0.00092923USD. ReconstrucciónBS independiente de140calls: residualmáximo1.53e-8USD. ReferenciaHestonAnalytic192con adaptador de curva común sobre142calls: discrepancia máxima frente a tabla0.00040388USD. Pruebas focalizadas fase5:7PASS; regresión fase2+5:20PASS/39.43s. Una advertencia PCHIP de overflow en cálculo auxiliar no produjo precios no finitos en los controles examinados.

**Limitaciones documentables, sin nueva reparación:**

- Putreal NU261120P00012500,3d:IVpublicada0.43422256, refinada0.42854222. ReprecioQL aIVpublicada difiere0.00270591USD y EDPfina0.00240558USD del objetivo: este punto supera el presupuesto comparativo0.002USD; no se declara que toda la superficie lo cumpla. Es sensibilidad del inversor1Dultracorto, no cambio del precioHeston. Equivale a~0.57ppdeIVy0.27centavos; se acepta como limitación académica explícita. Cartera31/59d no usa ese vencimiento.
- Nueveputs devuelven0.01con estadoCONVERGED_AT_LOWER_BRACKET. No tratarlas como IVidentificadas ni como volatilidad económica1%; están excluidas de gráficos/métricas interiores. Incluyen primasOTMmuy pequeñas, no soloITM. Integración debe usar Heston directo y mantener máscara de IVidentificable.
- El adaptador de calls redondea fechas de nudos y la integración analítica tiene precisión finita; la diferencia de precio máxima0.000404USDmedida está debajo del presupuesto0.002USD. Preferir el adaptador común existente al integrar, sin nueva campaña numérica.
- La prosa dice35/35inversiones exitosas, pero los estados interiores son29/35puts y33/35calls. Separar valoración completa de IVidentificada en el cierre. Correcciones editoriales se incorporan a la síntesis de fase6, sin otra ronda5.
- F4-H2permanece como limitación aceptada por usuario; no se declara corregido. No garantías globales por malla finita ni precisión uniforme de IV cerca de vega nula.

Evidencia reproducible: [script](repro_phase5_b4cb3d6_real.py), [precios de control](HESTON_PHASE_5_b4cb3d6_real_prices.csv), [log](HESTON_PHASE_5_b4cb3d6_evidence.txt). Ejecutar script desde cwd de extracciónb4cb3d6con requirements-heston.txt. Verifica datos reales y referencias; no campañas de corrupción de archivos. Se conserva referencia fina del caso3d y comparación de142calls en log adicional.

No hay un defecto material demostrado que impida construir e integrar la versión académica. Aprobar con límites anteriores y continuar **fase6**: comparación, cartera/griegas/stress y pipeline mínimo; [encargo](../orchestration/PHASE_6_START.md). Revisión humana final y no merge siguen vigentes. El SHA del informe documental es distinto del SHA de implementación auditado.
