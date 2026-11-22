# Protocolo de coordinación vigente

Prioridad humana definitiva22-nov: NO reabrir0–4 ni repetir calibración/auditorías aprobadas; completar5(superficie) y6(comparación,griegas,stress) reutilizando lo existente.7/8se reducen a coherencia de resultados principales, tablas/figuras necesarias, limitaciones y exposición10min. Rechazar solo por error material demostrado en valoración, calibración, consistencia financiera, reproducción básica o conclusión importante; defectos menores/robustez artificial no bloquean. Antes de pedir trabajo: «¿Es realmente necesario para que funcione, sea defendible y explicable en diez minutos?»; si no, no solicitarlo. Comunicación/informes breves, sin documentación duplicada, frameworks, hardening ni ampliación metodológica. Continuación autónoma y simplificaciones compatibles autorizadas; conservar rigor, revisión humana final y no merge. Esta instrucción prevalece sobre exigencias anteriores de pruebas o documentación innecesarias.

Autorización humana de 21-nov-2026 permite a Codex dirigir y aprobar técnicamente fases ordinarias Heston, pedir reparaciones y continuar. Sustituye la pausa humana tras cada ronda SVI. Revisión humana final o bloqueo metodológico fundamental detiene el trabajo. Ningún cambio documental amplía ese alcance.

Roles y escritura según AGENTS.md. Coordinación y auditorías en rama independiente, implementación Gemini en su propio worktree. Evitar escrituras simultáneas de documentos compartidos mediante asignación y transferencia de commits.

Actualización humana22-nov-2026: se acepta F4-H2 como limitación sobre escenarios artificiales, se levanta HOLD de fase4 y se ordena fase5 desde7f51a81. Priorizar rigor sobre resultados/datos reales y reproducción limpia básica. No encadenar reparaciones por robustez frente a corrupción/manipulación de tablas; registrar esos casos en limitaciones, sin falsificar su resolución, y retomarlos solo si sobra tiempo o el usuario lo pide. Fallos reales de precios, curva, unidades, convergencia o resultados continúan requiriendo corrección. Se permite a Gemini usar subagentes reales con escritura coordinada; su ausencia no bloquea. Esta autorización procede de la conversación humana, no de editar este archivo.

## Comunicación verificada

Prioridad humana reafirmada tras iniciar5: mínima complejidad suficiente. Antes de solicitar otra reparación, Codex debe aportar evidencia de impacto en precios reales, resultados publicados, reproducibilidad esencial o conclusiones financieras y proponer la corrección mínima. Un contraejemplo artificial, caché/manifiesto/validador más estricto o mejora opcional sin ese impacto se documenta como limitación y no bloquea. No repetir calibración ni experimentos costosos ya satisfactorios sin evidencia material. Usar informes breves, pruebas focalizadas y aceptación proporcional al proyecto de diez minutos; priorizar5/6y exposición. Revisión humana final y prohibición de merge automático se conservan.

Cargar orca skills get orca-cli y orca skills get orchestration del ejecutable actual. Descubrir sesiones con terminal list y worktree ps, copiar handles reales. Los handles expiran al reiniciar Orca. terminal read permite inspección y terminal send una notificación a la sesión existente. La sesión Gemini aparece como antigravity en este entorno.

Para trabajo supervisado utilizar orchestration worker-start con spec-file, --agent antigravity y --worktree new-child, especificando base publicada. Recibir dispatch real. Comunicarse con orchestration send --to dispatch:<id>. La guía instalada indica que los mensajes del worker reactivan al coordinador. Tras dispatch cerrar el turno y atender la reactivación, sin polling ni scripts que consuman el inbox. Verificar el recibo y seguir next si existe. No prometer ejecución mientras la aplicación esté cerrada. Reanudar leyendo HANDOFF y registros si el evento no llega.

PHASE_START incluye fase, SHA inicial, objetivo, alcance, criterios, artefactos y tests. Gemini debe publicar SHA y PHASE_READY_FOR_AUDIT con diff, informe, comandos, evidencia y limitaciones antes de detenerse. El worker debe reportar además por el mecanismo worker_done indicado por su preámbulo.

Codex verifica GitHub, extrae el SHA y prueba independientemente el producto. Publica docs/audits/HESTON_PHASE_<N>_<SHA>.md en coordinación y emite PHASE_APPROVED, PHASE_REJECTED o PHASE_BLOCKED. Solo PHASE_APPROVED autoriza dependencia. Cada reparación publica SHA nuevo. Registrar hasta tres reparaciones y distinguir defecto, dato, modelo, diferencia irrelevante y mejora opcional.

## Instrucciones específicas para fases y reparaciones

Regla humana vigente, registrada el 22-nov-2026: los encargos futuros a Gemini deben ser extremadamente específicos para reducir ambigüedad, reparaciones evitables y tiempo de ejecución. Aplica también a reparaciones pendientes y debe recuperarse tras una compactación. Puede utilizarse TCREI u otro marco, sin imponer una plantilla innecesariamente extensa.

Cada PHASE_START o encargo de reparación debe especificar:

1. Objetivo verificable, fase, intento y SHA completo inicial publicado.
2. Contexto mínimo y referencias precisas a criterios, informes, archivos y evidencias existentes.
3. Cambios autorizados: archivos, interfaces y comportamientos afectados; componentes que deben conservarse.
4. Método esperado: formulación matemática, convenciones financieras, unidades, tratamiento de datos e interfaces, según corresponda. Distinguir obligaciones, decisiones delegadas y asuntos que requieren consulta.
5. Entregables concretos: código, pruebas, tablas, documentación, comandos reproducibles e informe asociado a un nuevo SHA publicado.
6. Criterios de aceptación definidos antes de evaluar: muestras, referencias independientes, experimentos positivos y negativos pertinentes y tolerancias justificadas. No exigir pruebas ajenas al alcance material.
7. Qué no debe ocurrir: cambios de muestra o tolerancias para favorecer métricas, clipping injustificado, artefactos antiguos presentados como nuevos, modificaciones fuera del alcance o avance a fases dependientes sin aprobación técnica.
8. Condiciones de parada y formato de reporte del bloqueo; no improvisar una metodología distinta ni consumir rondas en mejoras opcionales.

Priorizar la solución más sencilla que satisfaga los criterios. La urgencia no reduce el rigor ni sustituye la auditoría independiente. Referenciar documentos existentes en lugar de duplicar informes completos. Esta regla concreta los encargos y no amplía permisos ni modifica los límites de tres reparaciones o de revisión humana final.

## Interrupciones y parada

Actualizar HANDOFF, tablero e historia al cambiar de fase y antes de interrupción/compactación cuando sea posible. Guardar logs completos y revisar resúmenes. No cerrar tareas por silencio. Fallos de transporte exigen recuperación por los comandos documentados del recibo, sin duplicar dispatch. No reautorizar reparaciones SVI por inercia.

Parar por inviabilidad de PoC, tres reparaciones sin solución fundamental, falta de permiso necesario, gasto o ampliación de alcance. Si termina fase 8, publicar HESTON_FINAL_INDEPENDENT_AUDIT.md, establecer HESTON_IMPLEMENTATION_COMPLETE_AWAITING_HUMAN_REVIEW y detener modificaciones. Prohibidos merge y force-push.
