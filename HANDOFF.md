# Estado para reanudar

Regla humana 22-nov-2026: todos los próximos encargos de fase o reparación a Gemini deben precisar objetivo/SHA, alcance, método, entregables, aceptación previa, prohibiciones y condiciones de parada; separar obligaciones, decisiones delegadas y consultas. Leer [instrucciones específicas](docs/orchestration/PROTOCOL.md#instrucciones-específicas-para-fases-y-reparaciones) antes del próximo envío. Priorizar sencillez y evitar ambigüedad sin reducir rigor.

PHASE_CONTEXT_SETUP_APPROVED. PHASE_0 APPROVED en0fb87583c6f4023049a4e6f4ae5c36c7aad247d3.
PHASE_1 APPROVED en654d1c2d05a0301dc3068cdc34219df3d42d2af7 tras3 reparaciones.
PHASE_2 APPROVED enea0df6f097904352e5345bb6fbc712008e319bf2 tras1 reparacion. Es aprobacion de construccion/controles iniciales del solver de puts, no validacion universal.
PHASE_3 REJECTED en344ae4af1460ec2bc2ae6a28eac382f3c12c32ae, reparacion3/3 autorizada: origen invalido no condiciona gate, economia reutilizada sin pin y fuente de precio sin comparar. Ultimo intento ordinario, no motor. NO calibracion; fase4 espera aprobacion de fase3.
Ultimo SHA aprobadoea0df6f097904352e5345bb6fbc712008e319bf2. SHA fase3 auditado344ae4af1460ec2bc2ae6a28eac382f3c12c32ae; pendiente SHA de reparacion3.
[Auditoria fase2](docs/audits/HESTON_PHASE_2_ea0df6f.md). [PHASE_START3](docs/orchestration/PHASE_3_START.md). [Criterios](docs/context/ACCEPTANCE_CRITERIA.md).
F2-M1 cerrado API puts/None y sensibilidad varianza; F2-M2 controles materiales cerrados. F2-L1 interpolacion/fronteras y F2-L2 borrador de guion/cifras quedan LOW aceptados para etapa inicial, sin aprobarlos para defensa final.
Coordinacion JDELGADO2607/heston-coordination, PR4 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-coordination.
Implementacion Gemini JDELGADO2607/heston-implementation, PR5 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-implementation.
Run run_0891738e9cf5; reparacion3 fase3 asignada ctx_d42b25ff3875, task task_3ef280157c05. Informe5678fc786361a51a399d262bba073ceffc24f10e verificado accesible, PR4 OPEN. Ultimo intento ordinario; alternativa autorizada eliminar reuse y evaluar fresco.
Terminado datos/baseline, PoC QuantLib y motor MCS-IT propio inicial. Falta validacion amplia, calibracion definitiva e integracion/fases4-8. Sin bloqueo metodologico vigente.
Siguiente accion reparar controles y documentacion de fase3, nuevo SHA y reauditoria. [Informe actual](docs/audits/HESTON_PHASE_3_344ae4a.md). Precios legitimos intactos,56tests sin escrituras oficiales. Errores numericos ahora se recalculan; falta veto por integridad/economia/fuente. Sin cuarta ronda automatica. No cambiar parametros con holdouts ni auditar archivos en modificacion.
Reproduccion ultimo estado: extraccion SHA aprobado, requirements-heston.txt, python -m pytest tests/test_heston_phase0.py tests/test_heston_phase1.py tests/test_heston_phase2.py -q; scripts del informe.
SVI congelado3d81ff1, auditoriaR3 PR3, sin aprobacion global. Enunciado original ausente; mapeo secundario46-56 disponible.
Tres reparaciones maximas por fase, sin merge/force-push ni ampliacion metodologica; revision humana final pendiente. Cuota restante no expuesta.
Reanudar con git fetch y AGENTS,CONTEXT,HANDOFF,PLAN y ultimo informe.
