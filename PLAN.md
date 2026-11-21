# Plan maestro autorizado

Estados permitidos NOT_STARTED, IN_PROGRESS, READY_FOR_AUDIT, APPROVED, REJECTED y BLOCKED. Cada dependencia requiere PHASE_APPROVED del SHA exacto. Tres reparaciones máximas, registradas en historia.

| Fase | Entregable | Dependencia | Estado | Reparaciones |
| --- | --- | --- | --- | --- |
| CONTEXT_SETUP | Contexto publicado y accesible a ambos agentes | Ninguna | APPROVED | 0 |
| 0 | Congelacion, datos, tasas, dependencias y baseline | CONTEXT_SETUP | REJECTED | 1 |
| 1 | PoC QuantLib con puts americanas, multistart y holdout | 0 | NOT_STARTED | 0 |
| 2 | Solver propio 2D, ADI y obstáculo | 1 | NOT_STARTED | 0 |
| 3 | Validación independiente del solver contra QuantLib | 2 | NOT_STARTED | 0 |
| 4 | Calibración definitiva global y refinamiento | 3 | NOT_STARTED | 0 |
| 5 | Precios Heston e IV equivalentes por tipo | 4 | NOT_STARTED | 0 |
| 6 | Integración en comparación, griegas, cartera y stress | 5 | NOT_STARTED | 0 |
| 7 | Regeneración global, integridad y auditoría | 6 | NOT_STARTED | 0 |
| 8 | Síntesis académica, documento y defensa de diez minutos | 7 | NOT_STARTED | 0 |

Los [criterios](docs/context/ACCEPTANCE_CRITERIA.md) gobiernan la revisión. Fase 1 es un gate de viabilidad, admite detener la migración por limitación fundamental. Fase 4 puede calibrar con QuantLib si el coste del solver propio obliga, con validación posterior de precios propios.

La salida final es docs/audits/HESTON_FINAL_INDEPENDENT_AUDIT.md y HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW. No ejecutar merge. Ver [protocolo](docs/orchestration/PROTOCOL.md).
