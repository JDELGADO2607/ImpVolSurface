# PHASE_START — cierre7/8 indispensable, solo documentación

Base **4c63e19583c740711fdf001f1ae7e6bd9d99d4b9**, misma rama/worktreePR5. **Fase6numérica aprobada** tras auditoría focal: [informe](../audits/HESTON_PHASE_6_4c63e19.md). Codex ejecutó `python run_all.py --heston`:30.1s, seis tablas regeneradas coinciden. Comparó los5contratos/griegas conQL y reconciliaciónPnLcorrecta. No volver a ejecutar pipeline, tests, calibración ni experimentos: ya satisfactorios, esta entrega cambia solamente prosa/tablas.

## Tarea única

Actualizar `docs/reports/INFORME_FASE_6_INTEGRACION_FINANCIERA.md` y su guion10min para coincidir con las tablas reales ya publicadas. No generar documentos nuevos extensos ni frameworks de renderizado. No cambiar código, precios, inputs, parámetros o CSV para hacerlos coincidir con la prosa.

1. Regenerar/copiar con redondeo de presentación la tabla de5patas desde `portfolio_greeks_and_valuation.csv`: primas reales0.86,0.15,0.47,0.60,0.30; Greeksperunit reales, incluido deltaCallK14 **+0.17778002**, la cantidad−5ya hace negativa la delta de su posición. No mezclar signo unitario con cantidad. Totales616USDobservado/596.10169modelo,hedge−393ya son correctos.
2. Tabla h/h2desde `portfolio_convergence_checks.csv`; no números de otras ejecuciones. Resumen de métricas desde `models_comparison_summary.csv` y `phase6_summary_metrics.json`.
3. Conclusión central: putsHestonMAE0.02384725vsflatamericano0.03738470(~36.21%reducción),callsHeston0.08729128vsflat0.05679266(empeora),combinadoHeston0.06154203vsflatamericano0.04891579(empeora). No mejora88%ni superioridad global. No recalibrar para cambiar esa conclusión; explicar calibración exclusiva de puts y limitaciones del contraste externo sin atribuir toda diferencia a una causa no demostrada.
4. Tests:100declarados porGemini, no101; Codexreejecutó6de fase6. No repetir suite para corregir un conteo de texto. Semianalítico no implica aritmética exacta; delta-neutralidad es aproximada por redondeo. Margen5613.87981es estimación académica basada en primasHeston/margen simplificado, no cálculoFINRA/OCC ni primas observadas. Thetaacortamiento con curva congelada; TaylorsegundoS/primersigma0sin volga/crosscompletos.
5. Guion10min usa únicamente resultados/tablas correctos, explica volatilidad inicial frente aIVequivalente, ejercicio americano, diferenciasfinitas intuitivas, comparación, hedge/stress y limitaciones. ConservarF4-H2aceptado y precisión3dIVcomo limitaciones; nada de repararrobustez. No beneficioshistóricos: seisstressson instantáneos/hipotéticos, sin tiempo/fricciones ni probabilidades.

## Entrega y finalización

Publicar nuevoSHA de documentación, diff corto y worker_done indicando que no cambió código/CSV/resultados. No phase nueva de desarrollo, no nuevos tests, no merge. Codex verificará diff y cifras y emitirá informe independiente final con SHAdefinitivo y revisiónhumana pendiente. No declarar aprobación definitiva humana. Si una discrepancia exige cambiar código/precios reales, comunicarla; no expandir este cierre por cuenta propia.
