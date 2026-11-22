# Plan maestro autorizado

Estados permitidos NOT_STARTED, IN_PROGRESS, READY_FOR_AUDIT, APPROVED, REJECTED y BLOCKED. Cada dependencia requiere PHASE_APPROVED del SHA exacto. Tres reparaciones máximas, registradas en historia.

| Fase | Entregable | Dependencia | Estado | Reparaciones |
| --- | --- | --- | --- | --- |
| CONTEXT_SETUP | Contexto publicado y accesible a ambos agentes | Ninguna | APPROVED | 0 |
| 0 | Congelacion, datos, tasas, dependencias y baseline | CONTEXT_SETUP | APPROVED | 1 |
| 1 | PoC QuantLib puts americanas | 0 | APPROVED | 3 |
| 2 | Solver propio 2D, ADI y obstáculo | 1 | APPROVED | 1 |
| 3 | Validación independiente del solver contra QuantLib | 2 | APPROVED | 3 |
| 4 | Calibración definitiva global y refinamiento | 3 | APPROVED | 3 |
| 5 | Precios Heston e IV equivalentes por tipo | 4 | APPROVED | 0 |
| 6 | Integración en comparación, griegas, cartera y stress | 5 | APPROVED | 0 |
| 7 | Comprobar resultados principales y regenerar tablas/figuras necesarias | 6 | APPROVED | 0 |
| 8 | Limitaciones y exposición académica de diez minutos, cierre mínimo | 7 | IN_PROGRESS | 0 |

Los [criterios](docs/context/ACCEPTANCE_CRITERIA.md) gobiernan la revisión. Fase 1 es un gate de viabilidad, admite detener la migración por limitación fundamental. Fase 4 puede calibrar con QuantLib si el coste del solver propio obliga, con validación posterior de precios propios.

Actualización humana22-nov: fase4aprobada sobre7f51a81con F4-H2 aceptado como limitación, no reparado; ver addendum de auditoría. Restan dos fases de implementación(5superficie,6integración).7/8son comprobación y síntesis final mínima, sin nuevas funcionalidades ni hardening. Priorizar resultados reales; los escenarios adicionales de robustez quedan en limitaciones y se retoman solo si hay tiempo.

La salida final es docs/audits/HESTON_FINAL_INDEPENDENT_AUDIT.md y HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW. No ejecutar merge. Ver [protocolo](docs/orchestration/PROTOCOL.md).
