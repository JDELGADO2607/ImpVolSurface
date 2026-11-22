# Decisión humana posterior a la auditoría de fase4

Fecha22-nov-2026. Implementación examinada:7f51a811ae5815dadf8c26b46f707e9f7cb0d05c. No nuevo commit de implementación ni cuarta reparación.

El usuario instruyó aceptar el contraejemplo como limitación mientras no afecte los datos reales, y después confirmó: “vamos con el rigor necesario nada mas”, dejando los escenarios de robustez para después del deadline y ordenando iniciar fase5. Autoriza también a Gemini a utilizar subagentes si dispone de esa capacidad real.

**PHASE_APPROVED para continuar sobre los datos reales auditados, con F4-H2 abierto y aceptado expresamente como limitación.** Se levanta el bloqueo operativo de fase4; no se certifica como corregido el gate de cotas europeas ni se elimina el [informe histórico](HESTON_PHASE_4_7f51a81.md). Sus precios legítimos satisfacen las cotas,87tests pasan y los contraejemplos anteriores fueron corregidos. Esta decisión modifica el alcance de aceptación por instrucción humana, no los resultados matemáticos ni tolerancias para simular una reparación.

Se conservan97puts,60/22/15y142calls de contraste; no se depuran contratos por un escenario sintético. No se declara que el gate sea robusto frente a toda manipulación de artefactos. F4-H2 debe figurar en limitaciones finales y solo se retomará si hay tiempo o nueva instrucción; no bloquea las fases ordinarias sobre fuentes versionadas y resultados reales comprobados. No se autoriza ignorar errores reales de precio, unidades, ejercicio, convergencia o causalidad.

El trabajo de implementación restante se concentra en fase5(superficie) y6(integración). Las comprobaciones y documentación mínimas de7/8son actividades de cierre, sin añadir modelos, frameworks ni nuevas funcionalidades. Revisión humana final y prohibición de merge se mantienen. Instrucción vigente de fase5: [PHASE_5_START](../orchestration/PHASE_5_START.md).
