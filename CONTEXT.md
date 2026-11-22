# Contexto vigente

La tarea estudia valoración, IV, riesgo y escenarios de opciones americanas NU. El mapeo académico disponible está en [requisitos](docs/context/PROJECT_REQUIREMENTS.md). La defensa dura diez minutos.

Referencia de implementación SVI congelada `3d81ff18cae3a9f8dc74c174015fed17031a8da8`. Auditoría independiente R3 publicada en [CODEX_AUDIT_R3_3d81ff1.md](https://github.com/JDELGADO2607/ImpVolSurface/blob/e1b4f5bf9b306e2213a4858598499ef45d284d66/docs/audits/CODEX_AUDIT_R3_3d81ff1.md) y PR #3. No existe aprobación técnica global de SVI. Las afirmaciones históricas de certificación deben contrastarse con esa auditoría.

El usuario decidió explorar Heston clásico después de la revisión humana. Motivos aceptados son concavidad recurrente, complejidad de reparaciones, dinámica común entre strikes y plazos y aprendizaje de diferencias finitas 2D. La prueba inicial usará QuantLib y precios de puts americanas para incorporar ejercicio anticipado en la calibración neutral al riesgo. Heston fue sugerencia del profesor según declaración del usuario. La selección de SVI del documento inicial queda reemplazada para esta migración.

Existen BS europeo, EDP americana 1D, CRR, Brent, limpieza de cadena, HAR-RV, cartera, stress, estrategias hipotéticas y superficie SVI. Se conservan como referencias con sus limitaciones. La PoC QuantLib esta implementada y aprobada tecnicamente en654d1c2d05a0301dc3068cdc34219df3d42d2af7; el solver propio de puts tiene aprobacion inicial de fase2 enea0df6f097904352e5345bb6fbc712008e319bf2, pendiente de validacion amplia de fase3. Los estados detallados estan en HANDOFF.

La cadena es transversal y asíncrona. Últimos trades carecen de bid/ask ejecutables fiables. Bloomberg aporta contraste. El histórico del subyacente permite estudiar volatilidad realizada, sin panel histórico de opciones para backtesting.

El estudiante debe explicar medida Q, parámetros de Heston, payoff y ejercicio, discretización de derivadas, separación ADI, convergencia, comparación común, riesgo y limitaciones. Derivaciones largas van a anexos.

Continuar en [HANDOFF](HANDOFF.md) y [PLAN](PLAN.md). Detalles en [matemática](docs/context/MATHEMATICAL_FRAMEWORK.md), [decisiones](docs/context/METHODOLOGICAL_DECISIONS.md), [datos](docs/context/DATA_PROVENANCE.md), [hallazgos](docs/context/KNOWN_ISSUES.md), [aceptación](docs/context/ACCEPTANCE_CRITERIA.md), [mapa](docs/context/CODEBASE_MAP.md).
