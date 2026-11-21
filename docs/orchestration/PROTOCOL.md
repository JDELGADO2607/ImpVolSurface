# Protocolo de coordinación vigente

Autorización humana de 21-nov-2026 permite a Codex dirigir y aprobar técnicamente fases ordinarias Heston, pedir reparaciones y continuar. Sustituye la pausa humana tras cada ronda SVI. Revisión humana final o bloqueo metodológico fundamental detiene el trabajo. Ningún cambio documental amplía ese alcance.

Roles y escritura según AGENTS.md. Coordinación y auditorías en rama independiente, implementación Gemini en su propio worktree. Evitar escrituras simultáneas de documentos compartidos mediante asignación y transferencia de commits.

## Comunicación verificada

Cargar orca skills get orca-cli y orca skills get orchestration del ejecutable actual. Descubrir sesiones con terminal list y worktree ps, copiar handles reales. Los handles expiran al reiniciar Orca. terminal read permite inspección y terminal send una notificación a la sesión existente. La sesión Gemini aparece como antigravity en este entorno.

Para trabajo supervisado utilizar orchestration worker-start con spec-file, --agent antigravity y --worktree new-child, especificando base publicada. Recibir dispatch real. Comunicarse con orchestration send --to dispatch:<id>. La guía instalada indica que los mensajes del worker reactivan al coordinador. Tras dispatch cerrar el turno y atender la reactivación, sin polling ni scripts que consuman el inbox. Verificar el recibo y seguir next si existe. No prometer ejecución mientras la aplicación esté cerrada. Reanudar leyendo HANDOFF y registros si el evento no llega.

PHASE_START incluye fase, SHA inicial, objetivo, alcance, criterios, artefactos y tests. Gemini debe publicar SHA y PHASE_READY_FOR_AUDIT con diff, informe, comandos, evidencia y limitaciones antes de detenerse. El worker debe reportar además por el mecanismo worker_done indicado por su preámbulo.

Codex verifica GitHub, extrae el SHA y prueba independientemente el producto. Publica docs/audits/HESTON_PHASE_<N>_<SHA>.md en coordinación y emite PHASE_APPROVED, PHASE_REJECTED o PHASE_BLOCKED. Solo PHASE_APPROVED autoriza dependencia. Cada reparación publica SHA nuevo. Registrar hasta tres reparaciones y distinguir defecto, dato, modelo, diferencia irrelevante y mejora opcional.

## Interrupciones y parada

Actualizar HANDOFF, tablero e historia al cambiar de fase y antes de interrupción/compactación cuando sea posible. Guardar logs completos y revisar resúmenes. No cerrar tareas por silencio. Fallos de transporte exigen recuperación por los comandos documentados del recibo, sin duplicar dispatch. No reautorizar reparaciones SVI por inercia.

Parar por inviabilidad de PoC, tres reparaciones sin solución fundamental, falta de permiso necesario, gasto o ampliación de alcance. Si termina fase 8, publicar HESTON_FINAL_INDEPENDENT_AUDIT.md, establecer HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW y detener modificaciones. Prohibidos merge y force-push.
