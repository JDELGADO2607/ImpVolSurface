# Estado para reanudar

Regla humana 22-nov-2026: todos los próximos encargos de fase o reparación a Gemini deben precisar objetivo/SHA, alcance, método, entregables, aceptación previa, prohibiciones y condiciones de parada; separar obligaciones, decisiones delegadas y consultas. Leer [instrucciones específicas](docs/orchestration/PROTOCOL.md#instrucciones-específicas-para-fases-y-reparaciones) antes del próximo envío. Priorizar sencillez y evitar ambigüedad sin reducir rigor.

PHASE_CONTEXT_SETUP_APPROVED. PHASE_0 APPROVED en0fb87583c6f4023049a4e6f4ae5c36c7aad247d3.
PHASE_1 APPROVED en654d1c2d05a0301dc3068cdc34219df3d42d2af7 tras3 reparaciones.
PHASE_2 APPROVED enea0df6f097904352e5345bb6fbc712008e319bf2 tras1 reparacion. Es aprobacion de construccion/controles iniciales del solver de puts, no validacion universal.
PHASE_3 APPROVED en09d9beb060a4a80d9dc4ae7035407cbc8e81e061 tras reparacion3/3: cerrados los controles materiales de integridad sin cambiar motor ni precios.60tests y controles independientes aprobados. F3-L1 temporal y F3-L3 editorial LOW aceptados, no garantia global.
Ultimo SHA aprobado09d9beb060a4a80d9dc4ae7035407cbc8e81e061. Fase4 REJECTED en fefe46ebb7028aa786abf3a8fca7377d667efda4, entrega inicial. Reparacion1/3 autorizada por defectos reproducibles:2HIGH/2MEDIUM/1LOW. Worker inicial ctx_fcd8d2585265/task_3c950a7c54fb terminado. [Auditoria4](docs/audits/HESTON_PHASE_4_fefe46e.md), [reparacion detallada](docs/orchestration/PHASE_4_REPAIR_1.md).
[Auditoria fase2](docs/audits/HESTON_PHASE_2_ea0df6f.md). [PHASE_START3](docs/orchestration/PHASE_3_START.md). [Criterios](docs/context/ACCEPTANCE_CRITERIA.md).
F2-M1 cerrado API puts/None y sensibilidad varianza; F2-M2 controles materiales cerrados. F2-L1 interpolacion/fronteras y F2-L2 borrador de guion/cifras quedan LOW aceptados para etapa inicial, sin aprobarlos para defensa final.
Coordinacion JDELGADO2607/heston-coordination, PR4 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-coordination.
Implementacion Gemini JDELGADO2607/heston-implementation, PR5 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-implementation.
Run run_0891738e9cf5; reparacion3 fase3 terminada por ctx_d42b25ff3875, task task_3ef280157c05, mensaje msg_1e0b2e42235a. No cuarta reparacion de fase3. PR4/PR5 OPEN.
Terminado datos/baseline, PoC QuantLib, construccion y validacion amplia del motor propio. Falta calibracion definitiva e integracion/fases4-8. Sin bloqueo metodologico vigente.
Reparacion1 fase4 entregada: ctx_974945bb04cf, task task_d2e7c612f2fe, run run_0891738e9cf5. Informe y encargo commit8231d4cc13e116c955f98eed513cc4d48c7c6fb3 verificados accesibles, PR4 OPEN. Siguiente accion atender evento/SHA nuevo; no polling. Recuperar evidencia original de optimizaciones y runner real; corregir API fresca, reutilizacion por existencia y gates; justificar seleccion y reconciliar informe.76tests PASS/139.66s, sin escrituras oficiales, no bastan para aprobar. Conservar optimizaciones verificables: no repetirlas por rutina. Cambio de redondeo~1.9e-6USD en12controles, no defecto material del motor. No modificar solver/tasas ni avanzar fase5 antes de aprobacion. No auditar archivos en modificacion.
Reproduccion ultimo estado: extraccion SHA aprobado, requirements-heston.txt, python -m pytest tests/test_heston_phase0.py tests/test_heston_phase1.py tests/test_heston_phase2.py -q; scripts del informe.
SVI congelado3d81ff1, auditoriaR3 PR3, sin aprobacion global. Enunciado original ausente; mapeo secundario46-56 disponible.
Tres reparaciones maximas por fase, sin merge/force-push ni ampliacion metodologica; revision humana final pendiente. Cuota restante no expuesta.
Reanudar con git fetch y AGENTS,CONTEXT,HANDOFF,PLAN y ultimo informe.
