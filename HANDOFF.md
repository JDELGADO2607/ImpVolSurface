# Estado para reanudar

PHASE_CONTEXT_SETUP_APPROVED. PHASE_0 APPROVED en0fb87583c6f4023049a4e6f4ae5c36c7aad247d3.
PHASE_1 APPROVED en654d1c2d05a0301dc3068cdc34219df3d42d2af7 tras3 reparaciones.
PHASE_2 APPROVED enea0df6f097904352e5345bb6fbc712008e319bf2 tras1 reparacion. Es aprobacion de construccion/controles iniciales del solver de puts, no validacion universal.
PHASE_3 REJECTED en28bd72a29640b0c8a93b8c11f9023d39222f1ccc, reparacion2/3 autorizada: reutilizacion sin verificar y gate que confia en etiquetas, no motor. NO calibracion; fase4 espera aprobacion de fase3.
Ultimo SHA aprobadoea0df6f097904352e5345bb6fbc712008e319bf2. SHA fase3 auditado28bd72a29640b0c8a93b8c11f9023d39222f1ccc; pendiente nuevo SHA de reparacion2.
[Auditoria fase2](docs/audits/HESTON_PHASE_2_ea0df6f.md). [PHASE_START3](docs/orchestration/PHASE_3_START.md). [Criterios](docs/context/ACCEPTANCE_CRITERIA.md).
F2-M1 cerrado API puts/None y sensibilidad varianza; F2-M2 controles materiales cerrados. F2-L1 interpolacion/fronteras y F2-L2 borrador de guion/cifras quedan LOW aceptados para etapa inicial, sin aprobarlos para defensa final.
Coordinacion JDELGADO2607/heston-coordination, PR4 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-coordination.
Implementacion Gemini JDELGADO2607/heston-implementation, PR5 OPEN, worktree C:/Users/CAROL/orca/workspaces/ImpVolSurface/heston-implementation.
Run run_0891738e9cf5; reparacion2 fase3 asignada ctx_5771a878bb22, task task_f597110b247e. Informe77ed6828b66fbf8b796ab488752e81c756c621fd verificado accesible, PR4 OPEN.
Terminado datos/baseline, PoC QuantLib y motor MCS-IT propio inicial. Falta validacion amplia, calibracion definitiva e integracion/fases4-8. Sin bloqueo metodologico vigente.
Siguiente accion reparar controles y documentacion de fase3, nuevo SHA y reauditoria. [Informe actual](docs/audits/HESTON_PHASE_3_28bd72a.md). Precios legitimos intactos,49tests sin escrituras oficiales; cache alterada puede declarar PASS, pendiente guarda de origen y comparacion numerica. No cambiar parametros con holdouts ni auditar archivos en modificacion.
Reproduccion ultimo estado: extraccion SHA aprobado, requirements-heston.txt, python -m pytest tests/test_heston_phase0.py tests/test_heston_phase1.py tests/test_heston_phase2.py -q; scripts del informe.
SVI congelado3d81ff1, auditoriaR3 PR3, sin aprobacion global. Enunciado original ausente; mapeo secundario46-56 disponible.
Tres reparaciones maximas por fase, sin merge/force-push ni ampliacion metodologica; revision humana final pendiente. Cuota restante no expuesta.
Reanudar con git fetch y AGENTS,CONTEXT,HANDOFF,PLAN y ultimo informe.
