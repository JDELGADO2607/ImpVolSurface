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
