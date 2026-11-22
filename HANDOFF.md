# Estado para reanudar

Regla humana 22-nov-2026: todos los próximos encargos de fase o reparación a Gemini deben precisar objetivo/SHA, alcance, método, entregables, aceptación previa, prohibiciones y condiciones de parada; separar obligaciones, decisiones delegadas y consultas. Leer [instrucciones específicas](docs/orchestration/PROTOCOL.md#instrucciones-específicas-para-fases-y-reparaciones) antes del próximo envío. Priorizar sencillez y evitar ambigüedad sin reducir rigor.

PHASE_CONTEXT_SETUP_APPROVED. PHASE_0 APPROVED en0fb87583c6f4023049a4e6f4ae5c36c7aad247d3.
PHASE_1 APPROVED en654d1c2d05a0301dc3068cdc34219df3d42d2af7 tras3 reparaciones.
PHASE_2 APPROVED enea0df6f097904352e5345bb6fbc712008e319bf2 tras1 reparacion. Es aprobacion de construccion/controles iniciales del solver de puts, no validacion universal.
PHASE_3 APPROVED en09d9beb060a4a80d9dc4ae7035407cbc8e81e061 tras reparacion3/3: cerrados los controles materiales de integridad sin cambiar motor ni precios.60tests y controles independientes aprobados. F3-L1 temporal y F3-L3 editorial LOW aceptados, no garantia global.
Ultimo SHA aprobado09d9beb060a4a80d9dc4ae7035407cbc8e81e061. Fase4 IN_PROGRESS: especificacion de calibracion definitiva autorizada, pendiente despacho/resultado. [Auditoria](docs/audits/HESTON_PHASE_3_09d9beb.md), [encargo detallado](docs/orchestration/PHASE_4_START.md).
[Auditoria fase2](docs/audits/HESTON_PHASE_2_ea0df6f.md). [PHASE_START3](docs/orchestration/PHASE_3_START.md). [Criterios](docs/context/ACCEPTANCE_CRITERIA.md).
F2-M1 cerrado API puts/None y sensibilidad varianza; F2-M2 controles materiales cerrados. F2-L1 interpolacion/fronteras y F2-L2 borrador de guion/cifras quedan LOW aceptados para etapa inicial, sin aprobarlos para defensa final.
Coordinacion JDELGADO2607/heston-coordination, PR4 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-coordination.
Implementacion Gemini JDELGADO2607/heston-implementation, PR5 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-implementation.
Run run_0891738e9cf5; reparacion3 fase3 terminada por ctx_d42b25ff3875, task task_3ef280157c05, mensaje msg_1e0b2e42235a. No cuarta reparacion de fase3. PR4/PR5 OPEN.
Terminado datos/baseline, PoC QuantLib, construccion y validacion amplia del motor propio. Falta calibracion definitiva e integracion/fases4-8. Sin bloqueo metodologico vigente.
Siguiente accion entregar PHASE_START4 con especificacion publicada y recibir nuevo SHA para auditoria. Tres refinamientos locales con starts historicos2/5/1, malla americana consistente, seleccion solo train, holdouts intactos y validacion final propia. No modificar solver/tasas para calibrar, no avanzar fase5 antes de aprobacion. No auditar archivos en modificacion.
Reproduccion ultimo estado: extraccion SHA aprobado, requirements-heston.txt, python -m pytest tests/test_heston_phase0.py tests/test_heston_phase1.py tests/test_heston_phase2.py -q; scripts del informe.
SVI congelado3d81ff1, auditoriaR3 PR3, sin aprobacion global. Enunciado original ausente; mapeo secundario46-56 disponible.
Tres reparaciones maximas por fase, sin merge/force-push ni ampliacion metodologica; revision humana final pendiente. Cuota restante no expuesta.
Reanudar con git fetch y AGENTS,CONTEXT,HANDOFF,PLAN y ultimo informe.
