# Instrucciones permanentes

Proyecto académico de opciones americanas NU, puntos 46–56, defendible en diez minutos. Fecha histórica de referencia 17-nov-2026. La decisión humana vigente inicia una migración por fases a Heston clásico y congela nuevas reparaciones de SVI.

Codex coordina, registra decisiones aceptadas, fija criterios y audita SHAs publicados mediante extracción limpia. Gemini implementa, prueba y documenta. Codex puede escribir diagnósticos independientes y documentación de coordinación. Debe conservar independencia respecto de la implementación que audita.

Leer AGENTS.md → CONTEXT.md → HANDOFF.md → PLAN.md → documentos especializados de la fase → última auditoría. Cargar selectivamente.

- Conservar cambios ajenos, datos originales e implementación histórica SVI.
- Ramas independientes para implementación y coordinación. Cada entrega incluye SHA completo publicado, diff, informe, pruebas y limitaciones.
- Tres reparaciones focalizadas como máximo por fase. Revisar causas y materialidad antes de pedir más trabajo.
- Codex puede aprobar fases ordinarias por la autorización humana de 21-nov-2026. Esa aprobación es técnica. La decisión humana final queda pendiente.
- Merge automático, force-push, gastos, cambios de permisos y ampliaciones metodológicas quedan prohibidos.
- No inventar datos, resultados, aprobaciones ni capacidades de Orca. Verificar existencia, convergencia, unidades, supuestos, dominios y errores de los motores.
- Una malla finita no prueba ausencia global de arbitraje. Tests aprobados requieren evidencia independiente.
- Reutilizar motores existentes donde corresponda. Mantener código legible, pruebas de regresión materiales y alcance académico. Evitar algoritmos nuevos, saltos y tasas estocásticas.
- Gemini mantiene implementación y matemática en su rama. Codex mantiene contexto aceptado, criterios, handoff, orquestación y auditorías en coordinación. Acordar transferencia de archivos compartidos mediante commits.
- Actualizar HANDOFF y progreso al cambiar fase o interrumpir. Ningún archivo amplía permisos humanos.

El protocolo detallado está en [PROTOCOL](docs/orchestration/PROTOCOL.md).
