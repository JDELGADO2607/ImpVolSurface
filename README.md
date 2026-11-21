# Proyecto Cuantitativo: Superficie de Volatilidad Implícita, Métodos Numéricos de EDP, Stress Testing y Estrategias con Opciones Americanas de Nu Holdings Ltd. (NU)

**Entidad:** Mesa de Derivados \& Gestión de Riesgos de Renta Variable  
**Subyacente:** Nu Holdings Ltd. (NYSE: NU)  
**Fecha Base de Mercado:** 17 de noviembre de 2026, 16:00 EST (America/New_York)  
**Precio Spot de Referencia ($S_0$):** $12.33 USD (Cierre oficial NYSE)  
**Tasa de Dividendos ($q$):** 0.00 % anual ($q = 0$, verificado en Formulario SEC 6-K del 12-nov-2026)  
**Curva Libre de Riesgo:** Curva Par del Tesoro de EE.UU. (4.10% a 4.84% compuesta continua)  
**Entorno de Ejecución:** Python 3.12.6, NumPy 2.1.1, SciPy 1.18.0, Pandas 2.2.2, OpenPyXL 3.1.5, Pytest 9.2.0, MiKTeX (pdflatex / xelatex)

---

## 1. Resumen Ejecutivo del Proyecto

Este repositorio contiene la implementación cuantitativa completa, verificada y reproducible que resuelve los **Puntos 46 a 56** para la valoración y gestión de riesgos de opciones americanas sobre NU:
1. **Auditoría Forense y Depuración (Puntos 46 y 47):** Importación de 575 contratos reales (303 calls, 272 puts, 16 vencimientos), corrección de truncamientos intradiarios de $\tau$, detección del reseteo a cero de bid/ask en Yahoo, y clasificación en Tiers mediante cotas de no arbitraje y condicionamiento $\kappa = 0.01 / \text{Vega} \le 3.0$ pp/centavo (201 contratos limpios).
2. **Motores de Valoración Americanos y Validación Independiente (Punto 48):** Implementación de Black-Scholes cerrado para Calls sin dividendos (coincidencia analítica garantizada por Teorema de Merton) y diferencias finitas Crank-Nicolson con suavizado de Rannacher y penalización cuadrática (Forsyth \& Vetzal, 2002) para Puts americanas. Validación numérica contra árbol binomial Cox-Ross-Rubinstein (CRR, 1000 pasos) con discrepancia $< \$0.0005$ USD.
3. **Inversión Numérica a Volatilidad Implícita (Punto 49):** Algoritmo de Brent sobre intervalo bracket $[0.01, 5.00]$ y contraste estratificado no circular con Bloomberg (`IV Mid` y `IV Last Trade`), explicando la asincronía de ~21 horas.
4. **Construcción de la Superficie de Volatilidad (Puntos 50 y 51):** Proyección en log-forward moneyness $k = \ln(K/F)$ y calibración de la parametrización Raw SVI de Gatheral. Validación cruzada Leave-One-Strike-Out sobre 196 contratos fuera de muestra: MAE de precio = $\$0.039$ USD y MAE de IV = 2.48 pp. Verificación analítica de ausencia de arbitraje mariposa ($g(k) \ge 0$) y de calendario ($\partial w / \partial \tau \ge 0$).
5. **Comparación de los Cuatro Modelos (Punto 54 y 55):** Matriz $2 \times 2$ (Europeo/Americano $\times$ Plano/Superficie) aislando la prima americana (hasta $\$0.025$ en ITM) frente al efecto dominante de la superficie SVI, que reduce el error en más del 54% en ITM (MAE de $\$0.0854$ a $\$0.0396$).
6. **Stress Testing de Cadena Fija (Punto 52):** Cartera hipotética delta-neutral de 5 patas con cobertura de -354 acciones de NU. Evaluación de 5 escenarios multifactoriales y demostración de la ruptura de la aproximación local de Taylor en caídas severas (discrepancia de $\$3,253$ USD en crisis de -20%), probando que la revaloración completa por EDP es mandatoria.
7. **Estrategias Cuantitativas de Trading (Punto 53):** Modelo econométrico HAR-RV (Corsi, 2009) con pronóstico a 21 días (72.97%) frente a IV ATM (44.02%), fundamentando un Straddle delta-neutral y un Calendar Spread sobre la volatilidad forward (38.15%), con análisis explícito de 3 regímenes de costos y advertencias sobre sesgos de backtest.

---

## 2. Estructura del Repositorio

```
rockling/
├── data/
│   ├── raw/
│   │   └── Opciones_Completo.xlsx              # Archivo original (solo lectura)
│   └── processed/
│       └── nu_historical_daily.csv             # Serie diaria histórica (2021-2026)
├── src/
│   ├── market_data.py                         # Curva del Tesoro r(tau), spot y forward
│   ├── data_cleaning.py                       # Parseo OCC, tau exacto, cotas y tiers
│   ├── pricing_bs.py                          # Black-Scholes analítico y Griegas
│   ├── pricing_crr.py                         # Árbol binomial CRR (benchmark)
│   ├── pricing_american_fd.py                 # Crank-Nicolson + Rannacher + Penalización
│   ├── iv_inversion.py                        # Inversor Brent y contraste Bloomberg
│   ├── surface.py                             # Calibración Raw SVI, PCHIP y Leave-One-Out
│   ├── model_comparison.py                   # Matriz 2x2 de los 4 modelos de tarificación
│   ├── greeks.py                              # Griegas analíticas y numéricas de EDP
│   ├── portfolio.py                           # Portafolio 5 patas y cobertura delta
│   ├── stress_testing.py                      # Stress testing multifactorial cadena fija
│   ├── forecasts.py                           # Estimador HAR-RV walk-forward causal
│   └── strategies.py                          # Escenarios y costos de Estrategias 1 y 2
├── tests/
│   ├── test_contracts_and_dates.py            # Tests de parseo, tau y tiers
│   ├── test_pricing_bs.py                     # Tests de paridad, monotonicidad y griegas
│   ├── test_pricing_american.py               # Tests de prima americana, FD vs CRR y malla
│   ├── test_iv_recovery.py                    # Tests de recuperación sintética Brent
│   ├── test_surface_and_interpolation.py      # Tests de evaluación SVI y no arbitraje
│   ├── test_portfolio_and_stress.py           # Tests de delta-hedge y matrices de estrés
│   └── test_no_lookahead.py                   # Tests de causalidad estricta y costos
├── outputs/
│   ├── tables/                                # 11 tablas CSV auditables generadas
│   ├── figures/                               # 7 gráficos de alta resolución
│   └── data_diagnostics/                      # Volcados y reportes diagnósticos brutos
├── docs/
│   ├── 00_Alcance_y_auditoria.md              # Auditoría inicial y alcance formal
│   ├── DECISIONES_Y_LIMITACIONES.md           # Registro vivo de decisiones cuantitativas
│   ├── MANUAL_MATEMATICO_COMPLETO.tex         # Manual autocontenido en LaTeX (19 págs)
│   ├── MANUAL_MATEMATICO_COMPLETO.pdf         # PDF compilado con pdflatex
│   ├── GUIA_EXPOSICION_10_MIN.md              # Guion oral de 8 diapositivas (10 min)
│   ├── PREGUNTAS_DEFENSA.md                   # 25+ preguntas difíciles con respuestas
│   └── REFERENCIAS_VERIFICADAS.md             # Catálogo bibliográfico con DOIs
├── run_all.py                                 # Script maestro ejecutable integral
└── README.md                                  # Este documento
```

---

## 3. Instrucciones de Reproducción y Verificación

### 3.1 Requisitos del Sistema
* Python 3.11 o 3.12
* Paquetes de Python: `pip install numpy scipy pandas matplotlib openpyxl pytest statsmodels yfinance`
* Compilador LaTeX (opcional para recompilar PDF): MiKTeX / TeXLive (`pdflatex`)

### 3.2 Ejecución del Pipeline Completo
Para ejecutar todo el flujo desde los datos brutos hasta la generación de tablas y figuras:
```bash
python run_all.py
```

### 3.3 Ejecución de la Suite de Pruebas Unitarias
Para correr los 23 tests de verificación automatizada:
```bash
pytest -v
```

### 3.4 Compilación de la Documentación LaTeX
```bash
pdflatex -interaction=nonstopmode -output-directory=docs docs/MANUAL_MATEMATICO_COMPLETO.tex
```

---

## 4. Tablas y Resultados Numéricos Principales

| Archivo Generado | Filas / Registros | Descripción Cuantitativa |
|---|---|---|
| `outputs/tables/options_audit.csv` | 575 filas | Auditoría completa con banderas de rechazo y asignación de Tiers 1-4. |
| `outputs/tables/options_clean.csv` | 201 filas | Contratos de alta calidad elegibles para la superficie. |
| `outputs/tables/options_with_iv.csv` | 201 filas | Volatilidades implícitas propias calculadas por Brent + EDP. |
| `outputs/tables/iv_comparison_bloomberg.csv` | 4 tramos | Sesgo medio (+0.19 pp en 90-365d) y MAE frente a Bloomberg Mid. |
| `outputs/tables/svi_slice_parameters.csv` | 16 cortes | Parámetros $(a, b, \rho, m, \eta)$ y verificación de $g(k) \ge 0$. |
| `outputs/tables/surface_leave_one_out_validation.csv` | 196 tests | Validación OOS: MAE de precio = $\$0.039$, MAE de IV = 2.48 pp. |
| `outputs/tables/model_comparison_summary.csv` | 6 segmentos | Matriz 2x2 demostrando reducción de MAE de $\$0.085$ a $\$0.039$ en ITM. |
| `outputs/tables/hypothetical_portfolio.csv` | 6 posiciones | 5 opciones + cobertura con -354 acciones (Delta neta = -0.30). |
| `outputs/tables/stress_test_matrix.csv` | 10 escenarios | P&L de la cartera fija bajo Sticky-Moneyness y Sticky-Strike. |
| `outputs/tables/volatility_forecast_evaluation.csv` | 3 modelos | Evaluación OOS walk-forward de HAR-RV (QLIKE = 0.1813). |
| `outputs/tables/strategy1_straddle_scenarios.csv` | 21 escenarios | Payoff del Straddle ATM bajo regímenes optimista, base y conservador. |

---

## 5. Figuras y Visualizaciones Generadas

* `outputs/figures/smile_2d_slices.png`: Cortes 2D de la sonrisa de volatilidad por vencimiento.
* `outputs/figures/surface_3d_volatility.png`: Superficie 3D de volatilidad implícita en coordenadas $(k, \tau)$.
* `outputs/figures/term_structure_atm.png`: Estructura temporal ATM ($k=0$) desde 3 días hasta 2.2 años.
* `outputs/figures/model_comparison_errors.png`: Errores absolutos medios (MAE) de los cuatro modelos por segmento.
* `outputs/figures/stress_test_pnl_waterfall.png`: P&L por escenario comparando Revaloración Full EDP vs Taylor.
* `outputs/figures/stress_crisis_leg_breakdown.png`: Desglose de P&L por pata en el Escenario 3 de Crisis Severa (-20% spot).
* `outputs/figures/nu_historical_vol_and_forecasts.png`: Volatilidad histórica realizada (2021-2026) y pronóstico HAR-RV.
* `outputs/figures/strategy1_payoff_scenarios.png`: Curvas de retorno del Straddle delta-neutral con tres regímenes de fricción.
* `outputs/figures/strategy2_calendar_payoff.png`: Perfil de beneficio a 31 días del Calendar Spread en strike 13.00.

---

## 6. Recomendaciones Institucionales para la Mesa de Derivados

1. **Abandono inmediato de Black-Scholes con volatilidad plana:** La tarificación con volatilidad constante subestima el valor de las opciones dentro del dinero en más del 54% y distorsiona el cálculo del margen de garantía.
2. **Adopción de la superficie SVI en varianza total:** Instituir la superficie SVI calibrada diariamente como la referencia oficial de *mark-to-model*, garantizando ausencia de oportunidades de arbitraje estático mariposa y de calendario.
3. **Mandato de Revaloración Completa por EDP en Stress Testing:** Prohibir el uso exclusivo de expansiones de Taylor por Griegas para shocks severos ($|\Delta S| \ge 10\%$). En caídas del 20%, Taylor sobreestimó el P&L en más de $\$3,250$ USD debido a la asimetría de la opcionalidad y la activación del ejercicio anticipado.
4. **Disciplina de Fricciones en Estrategias de Trading:** Incorporar un hurdle rate mínimo de 3 a 5 puntos porcentuales de volatilidad antes de tomar posiciones en primas de riesgo, asegurando que el spread bid-ask y el deslizamiento de rebalanceo delta no destruyan el valor económico de la estrategia.
