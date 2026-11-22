# Mapa del código al iniciar Heston

| Componente | Responsabilidad / entrada | Reutilización |
| --- | --- | --- |
| data/raw/Opciones_Completo.xlsx | Cadena original de dos hojas | Conservar intacto |
| src/data_cleaning.py | clean_and_audit_options, OCC, tau, filtros y merge | Revisar selección y mantener trazabilidad |
| src/market_data.py | Spot, fecha, get_zero_rate, D y forward | Corregir/etiquetar curva determinista en fase 0 |
| src/pricing_bs.py | BS y griegas analíticas europeas | Benchmark e inversión calls |
| src/pricing_american_fd.py | fd_american_price y price_american_option | Benchmark americano 1D e IV equivalente |
| src/pricing_crr.py | Árbol CRR | Contraste independiente |
| src/iv_inversion.py | implied_vol e invert_clean_dataset, Brent | IV equivalente y control residual |
| src/surface.py | VolatilitySurface, SVI/PCHIP, holdout y release grid | Histórico congelado |
| src/model_comparison.py | Cuatro modelos, constante 44% | Extender con Heston y muestras comunes |
| src/greeks.py | Diferencias finitas de precio | Revisar unidades y estabilidad |
| src/portfolio.py | build_hypothetical_portfolio y PORTFOLIO_LEGS | Integración mediante cartera única |
| src/stress_testing.py | run_stress_testing, shocks y capital | Conciliar datos de cartera y modelos |
| src/forecasts.py | HAR purgado, histórico subyacente | Mantener causalidad y diagnosticar muestras cortas |
| src/strategies.py | Straddle y calendar académicos | Conservar hipótesis e interpretar sensibilidad |
| run_all.py | Pipeline, tablas/figuras, pytest | Aislar ejecuciones y validar procedencia |
| tests/ | Tests unitarios, griegas, superficie, causalidad y pipeline | SVI histórico, nuevos tests por fase |
| outputs/tables y outputs/figures | Artefactos R3 publicados | Mantener separados de nuevos Heston |

Flujo actual Excel → limpieza → IV por contrato → superficie SVI → precios/cartera/stress/estrategias → tablas/figuras. El historial diario alimenta HAR-RV por otra ruta. Bibliotecas fijadas en requirements.txt. Heston todavía no tiene módulos comprometidos. Gemini definirá rutas mínimas en fase 0 y actualizará este mapa por transferencia acordada, sin anticipar componentes ficticios.

## Actualizacion al aprobar fase1

La descripcion anterior corresponde al estado inicial historico. En la rama de implementacion, SHA654d1c2, existen src/heston/rates_curve.py (curva y adaptador diario QuantLib), option_selection.py (seleccion trazable), data_split.py (particiones), baseline_pricing.py, pipeline_phase0.py, heston_model.py (motores QuantLib), calibration.py (multistart) y pipeline_phase1.py (validacion de cache y evaluaciones). Entradas/salidas aisladas data/heston/ y data/heston/phase1/. Tests test_heston_phase0.py y test_heston_phase1.py. Dependencias requirements-heston.txt.
Estos archivos estan en la rama de implementacion, no se copian como codigo a coordinacion. El solver propio aun no existe en el SHA aprobado; Gemini lo incorporara en fase2 y proporcionara mapa actualizado con commit verificable.

Entrega fase2 cd5ed3e bajo auditoria, aun no aprobada: src/heston/solver_2d.py implementa malla/operadores/MCS-IT propios; pipeline_phase2.py genera smoke/convergencia/limites/stencils en data/heston/phase2; test_heston_phase2.py. rates_curve.py incorpora forward instantaneo. Los precios de puts tienen evidencia favorable; no utilizar calls/griegas de esa API hasta corregir su alcance. La validacion amplia del solver sigue siendo fase3.

Actualizacion fase2 ea0df6f aprobada para construccion inicial: solver_2d.py restringe contratos a P/PUT, theta=None, d_price_d_v0 explicita y diagnostico trapezoidal separado de identidad IT. Pipeline exporta temporal_consistency.csv y metadatos ampliados. Algoritmo de precio de puts preservado. Fase3 validara amplitud numerica antes de autorizar uso para calibracion.

Entrega fase3 37bbd12 bajo auditoria: pipeline_phase3.py agrega matriz97/108,limites,continuidad,economia y tasas; test_heston_phase3.py y data/heston/phase3 con10CSV/manifiesto. No cambia el nucleo solver2D ni calibra. Validador pendiente de reparacion1 segun informe37bbd12; codigo de fase3 no constituye aun un gate aprobado.
