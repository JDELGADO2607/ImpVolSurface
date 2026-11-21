# Decisiones vigentes

Registro por Codex, 21-nov-2026. Cada entrada distingue autorización y detalle pendiente. Supuestos comunes cadena transversal, Q, q=0 y alcance académico.

## H-001 — Congelar SVI

Fecha 2026-11-21. Estado ACCEPTED.
Problema congelar svi. Alternativas reparaciones sucesivas o dinámica común.
Decisión Conservar R3 como benchmark y explorar Heston clásico. Justificación y evidencia Autorización humana tras revisión R3.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Sin borrar historia, nueva rama.


## H-002 — Motor de referencia

Fecha 2026-11-21. Estado ACCEPTED.
Problema motor de referencia. Alternativas solver inmediato o quantlib primero.
Decisión PoC QuantLib con ejercicio americano antes del solver. Justificación y evidencia Autorización humana.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Verificar versión y soporte real de AmericanExercise.


## H-003 — Objetivo e insumos

Fecha 2026-11-21. Estado ACCEPTED.
Problema objetivo e insumos. Alternativas iv europea, llamadas o precio americano.
Decisión Mínimos cuadrados no ponderados de puts americanas observadas. Justificación y evidencia Autorización humana.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Calls solo contraste externo, misma muestra en benchmarks.


## H-004 — Solver académico

Fecha 2026-11-21. Estado ACCEPTED.
Problema solver académico. Alternativas árbol o edp 2d publicada.
Decisión Desarrollar diferencias finitas propias después del gate PoC. Justificación y evidencia Autorización humana.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Conservar EDP 1D como control.


## H-005 — ADI y ejercicio

Fecha 2026-11-21. Estado PROPOSED.
Problema adi y ejercicio. Alternativas mcs, hv, penalización, splitting it.
Decisión MCS con obstáculo IT es candidato sujeto a comparación y documentación. Justificación y evidencia Literatura en marco matemático.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Decisión concreta antes de fase 2.


## H-006 — Tasas

Fecha 2026-11-21. Estado ACCEPTED.
Problema tasas. Alternativas aproximación explícita o bootstrap con repricing.
Decisión Curva determinista común, fuente y disponibilidad verificadas en fase 0. Justificación y evidencia Hallazgo H-R3-4.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Método concreto pendiente, no llamar bootstrap a conversión de frecuencia.


## H-007 — Selección y holdout

Fecha 2026-11-21. Estado ACCEPTED.
Problema selección y holdout. Alternativas todas las filas o filtros económicos fijados.
Decisión Reglas predeclaradas y trazables, conservar aceptadas y rechazadas. Justificación y evidencia Autorización humana.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Tamaño definitivo pendiente de fase 0.


## H-008 — Identificación

Fecha 2026-11-21. Estado ACCEPTED.
Problema identificación. Alternativas parámetro único de un inicio o multistart.
Decisión Reportar estabilidad de parámetros y predicciones por separado. Justificación y evidencia Autorización humana.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Feller evaluada, sin imposición automática.


## H-009 — Gobierno entre fases

Fecha 2026-11-21. Estado ACCEPTED.
Problema gobierno entre fases. Alternativas pausa humana cada ronda o autonomía acotada.
Decisión Codex aprueba fases técnicas con tres reparaciones máximas. Justificación y evidencia Autorización humana vigente.
Supuestos los comunes y los que se congelen en fase 0. Consecuencias Revisión humana final y bloqueos fundamentales.


## Relación con historia

[DEC-001 a DEC-018](../DECISIONES_Y_LIMITACIONES.md) se conservan como historia.
D08 del [alcance inicial](../00_Alcance_y_auditoria.md) queda SUPERSEDED por H-001. Su motivación de que Heston requiere calibración física no aplica a la calibración neutral al riesgo autorizada.
Las garantías de DEC-009/010/014/016 específicas de SVI quedan SUPERSEDED para diseño Heston y cuestionadas para R3 por auditoría. DEC-015 de cuarentena sigue describiendo comportamiento histórico, sin definir la muestra nueva.
DEC-001/003/004/005/007/012 conservan utilidad, su aplicabilidad se confirma por fase. DEC-008/013/017 y documentación de tasas tienen defectos abiertos, no equivalen a implementación certificada.
La pausa humana obligatoria entre rondas SVI queda SUPERSEDED para las fases ordinarias Heston por H-009. Las puertas antiguas son historia y no aprueban ni bloquean por sí mismas una fase nueva.
