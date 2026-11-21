# Proyecto Cuantitativo: Superficie de Volatilidad Implícita, Métodos Numéricos de EDP, Stress Testing y Estrategias con Opciones Americanas de Nu Holdings Ltd. (NU)

**Entidad:** Mesa de Derivados & Gestión de Riesgos de Renta Variable  
**Subyacente:** Nu Holdings Ltd. (NYSE: NU)  
**Fecha Base de Mercado:** 17 de noviembre de 2026, 16:00 EST (America/New_York)  
**Precio Spot de Referencia ($S_0$):** $12.33 USD (Cierre oficial NYSE)  
**Tasa de Dividendos ($q$):** 0.00 % anual ($q = 0$, verificado en Formulario SEC 6-K del 12-nov-2026)  
**Curva Libre de Riesgo:** Curva Par del Tesoro de EE.UU. (4.10% a 4.84% compuesta continua)  
**Entorno de Ejecución:** Python 3.12.6, NumPy 2.1.1, SciPy 1.18.0, Pandas 2.2.2, OpenPyXL 3.1.5, Pytest 9.2.0, MiKTeX (pdflatex)  
**Rama de Auditoría y Reparación:** `fix/quant-audit-2026-11` (100% verificada, 37/37 tests passing)

---

## 1. Resumen Ejecutivo del Proyecto

Este repositorio contiene la implementación cuantitativa completa, verificada, auditada y reproducible que resuelve los **Puntos 46 a 56** para la valoración y gestión de riesgos de opciones americanas sobre NU:
1. **Auditoría Forense y Depuración (Puntos 46 y 47):** Importación de 575 contratos reales (303 calls, 272 puts, 16 vencimientos), corrección de truncamientos intradiarios de $\tau$, detección del reseteo a cero de bid/ask en Yahoo, y clasificación en Tiers mediante cotas de no arbitraje y condicionamiento $\kappa = 0.01 / \text{Vega} \le 3.0$ pp/centavo (201 contratos limpios). Auditoría de 68 pares Call-Put idénticos (dispersión media de 4.26 pp explicada por asincronía de `lastPrice`).
2. **Motores de Valoración Americanos y Estabilidad de Griegas (Puntos 48 y P0-A):** Implementación de Black-Scholes analítico para Calls sin dividendos (Merton, 1973) y diferencias finitas Crank-Nicolson con suavizado de Rannacher y penalización cuadrática (Forsyth & Vetzal, 2002) para Puts americanas. **Estabilización de Griegas Numéricas:** Dominio espacial común e invariante $S_{\max} = 4.0 \cdot \max(S_0, K)$ y evaluación sobre malla compartida con interpolación PCHIP local, estabilizando el Gamma de la Put $K=12$ de $3.3547$ a **$0.2375$** (consistente con Gamma europeo de $0.2346$).
3. **Inversión Numérica a Volatilidad Implícita (Punto 49):** Algoritmo de Brent sobre intervalo bracket $[0.01, 5.00]$ y contraste estratificado con Bloomberg mediante merge `1:1` estricto, reportando estados de convergencia transparentes (`CONVERGED_PRICE_TOL` vs `CONVERGED_VOL_TOL`).
4. **Construcción y No Arbitraje de la Superficie SVI (Puntos 50, 51 y P0-C):** Proyección en log-forward moneyness $k = \ln(K/F)$ y calibración de la parametrización Raw SVI de Gatheral imponiendo estrictamente la condición de alas de Roger Lee ($b(1+|\rho|) \le 1.95 < 2.0$), densidad mariposa no negativa $g(k) \ge 0$ al **100.0%** en la malla empírica, y proyección monótona acumulativa de calendario ($\partial w / \partial \tau \ge 0$). Validación cruzada Leave-One-Strike-Out agrupada sobre 197 contratos fuera de muestra con pricing americano en puts: **MAE = $\$0.0389$ USD**, **RMSE = $\$0.0649$ USD**.
5. **Comparación de los Cuatro Modelos (Puntos 54 y 55):** Matriz $2 \times 2$ (Europeo/Americano $\times$ Plano/Superficie) distinguiendo formalmente ajuste In-Sample ($N=201$) y validación Out-of-Sample LOO ($N=197$). La superficie SVI reduce el error MAE en un 40.9% general y en un 48.4% en opciones ITM (de $\$0.0854$ a $\$0.0398$ USD).
6. **Stress Testing de Cadena Fija Unificado (Puntos 52 y P0-B):** Cartera hipotética delta-neutral de 5 patas con cobertura dinámica de **-357 acciones de NU** ($\Delta_{\text{neto}} = +0.11$). Marco de contabilidad dual que incorpora el Escenario Nulo ($\text{P\&L} \equiv \$0.00$), aísla la diferencia inicial de marca a modelo ($-\$20.43$ USD) y calcula el capital económico mediante margen regulatorio (Reg T / FINRA 4210, $\$5\,435.31$ USD). **Desmitificación de Taylor:** La discrepancia anterior de $-\$3\,253$ USD se corrige a **$-\$261.15$ USD** (Full EDP $= +\$496.56$ USD vs Taylor $= +\$757.71$ USD), demostrando que la brecha histórica obedecía al Gamma numérico inflado ($3.3547$ vs $0.2375$) y a la mezcla de bases de precio inicial.
7. **Estrategias Cuantitativas de Trading (Puntos 53 y P1-C):** Modelo HAR-RV (Corsi, 2009) con validación **walk-forward purificada** ($s \le t - 21$), eliminando cualquier sesgo de anticipación (QLIKE = **$0.1855$**, superior a EWMA con $0.2099$). Pronóstico a 21 días (72.97%) dinámicamente enlazado a la señal ($z = +0.505 > 0$) para estructurar un Straddle delta-neutral con cobertura de -23 acciones basada en el delta americano de la Put (-0.3839) y Calendar Spread a strike fijo $K=13.00$ ($\sigma_{\text{fwd}} = 38.15\%$).

---

## 2. Estructura del Repositorio

```
rockling/
├── data/
│   ├── raw/
│   │   └── Opciones_Completo.xlsx              # Archivo original primario intacto (solo lectura)
│   └── processed/
│       └── nu_historical_daily.csv             # Serie diaria histórica (2021-2026)
├── src/
│   ├── market_data.py                         # Curva del Tesoro r(tau), spot y forward
│   ├── data_cleaning.py                       # Parseo OCC, tau exacto, cotas, tiers y paridad
│   ├── pricing_bs.py                          # Black-Scholes analítico y Griegas
│   ├── pricing_crr.py                         # Árbol binomial CRR (benchmark)
│   ├── pricing_american_fd.py                 # Crank-Nicolson + Rannacher + Penalización + Malla Fija
│   ├── iv_inversion.py                        # Inversor Brent, tolerancia dual y contraste Bloomberg
│   ├── surface.py                             # Calibración Raw SVI, Lee wings, PCHIP y Leave-One-Out
│   ├── model_comparison.py                   # Matriz 2x2 in-sample y LOO out-of-sample
│   ├── greeks.py                              # Griegas unificadas analíticas y numéricas estables
│   ├── portfolio.py                           # Portafolio 5 patas y cobertura delta dinámica (-357 sh)
│   ├── stress_testing.py                      # Stress testing con contabilidad dual y escenario nulo
│   ├── forecasts.py                           # Estimador HAR-RV walk-forward causal purificado
│   └── strategies.py                          # Escenarios, enlace dinámico y costos de Estrategias 1 y 2
├── tests/
│   ├── test_contracts_and_dates.py            # Tests de parseo, tau, tiers y paridad
│   ├── test_pricing_bs.py                     # Tests de paridad, monotonicidad y griegas
│   ├── test_pricing_american.py               # Tests de prima americana, FD vs CRR y penalización
│   ├── test_pde_greeks_stability.py           # Tests de estabilidad de Gamma/Vanna y dominio fijo
│   ├── test_iv_recovery.py                    # Tests de recuperación sintética Brent y estatus
│   ├── test_surface_and_interpolation.py      # Tests de SVI, Lee wings, mariposa 100% y calendario
│   ├── test_portfolio_and_stress.py           # Tests de delta-neutralidad, P&L nulo y reconciliación
│   └── test_no_lookahead.py                   # Tests de walk-forward purificado e invariancia contrafactual
├── outputs/
│   ├── tables/                                # 15 tablas CSV auditables generadas
│   ├── figures/                               # 9 gráficos de alta resolución
│   └── data_diagnostics/                      # Volcados y reportes diagnósticos brutos
├── docs/
│   ├── AUDITORIA_REPARACION_BASELINE.md       # Auditoría de línea base pre-reparación
│   ├── INFORME_FINAL_REPARACION.md            # Informe final de auditoría, cambios y defensa
│   ├── DECISIONES_Y_LIMITACIONES.md           # Registro vivo de decisiones cuantitativas (DEC-001 a DEC-009)
│   ├── MANUAL_MATEMATICO_COMPLETO.tex         # Manual exhaustivo en LaTeX (24 págs)
│   ├── MANUAL_MATEMATICO_COMPLETO.pdf         # PDF compilado con pdflatex
│   ├── GUIA_EXPOSICION_10_MIN.md              # Guion oral de 8 diapositivas (10 min)
│   ├── PREGUNTAS_DEFENSA.md                   # Catálogo exhaustivo de preguntas técnicas
│   └── REFERENCIAS_VERIFICADAS.md             # Catálogo bibliográfico con DOIs verificados
├── requirements.txt                           # Dependencias de Python fijadas
├── run_all.py                                 # Script maestro ejecutable integral con verificación pytest
└── README.md                                  # Este documento
```

---

## 3. Instrucciones de Reproducción y Verificación

### 3.1 Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3.2 Ejecución del Pipeline Completo
Para ejecutar todo el flujo desde los datos brutos hasta la generación de tablas, figuras y verificación pytest:
```bash
python run_all.py
```

### 3.3 Ejecución de la Suite de Pruebas Unitarias y de Regresión
Para correr los 37 tests automatizados:
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
| `outputs/tables/iv_call_put_parity_audit.csv` | 68 pares | Auditoría de paridad Call-Put en pares simultáneos. |
| `outputs/tables/options_with_iv.csv` | 201 filas | Volatilidades implícitas propias calculadas por Brent + EDP con estatus de tolerancia. |
| `outputs/tables/iv_comparison_bloomberg.csv` | 4 tramos | Sesgo medio (+0.19 pp en 90-365d) y MAE frente a Bloomberg Mid. |
| `outputs/tables/svi_slice_parameters.csv` | 16 cortes | Parámetros $(a, b, \rho, m, \eta)$, Lee wing bound y 100% de no arbitraje mariposa. |
| `outputs/tables/surface_leave_one_out_validation.csv` | 197 tests | Validación OOS: MAE de precio = $\$0.0389$ USD, RMSE = $\$0.0649$ USD con pricing americano. |
| `outputs/tables/model_comparison_summary.csv` | 7 segmentos | In-sample vs LOO out-of-sample demostrando reducción de MAE de $\$0.085$ a $\$0.039$ en ITM. |
| `outputs/tables/hypothetical_portfolio.csv` | 6 posiciones | 5 opciones + cobertura con -357 acciones ($\Delta_{\text{neto}} = +0.11$, Gamma estable). |
| `outputs/tables/stress_test_matrix.csv` | 12 escenarios | P&L con contabilidad dual, Escenario Nulo (\$0.00) y margen regulatorio (\$5,435.31). |
| `outputs/tables/stress_test_leg_breakdown.csv` | 60 registros | Desglose por pata reconciliado al céntimo en todos los escenarios de estrés. |
| `outputs/tables/volatility_forecast_evaluation.csv` | 3 modelos | Evaluación OOS walk-forward purificada ($s \le t-21$) de HAR-RV (QLIKE = 0.1855). |
| `outputs/tables/strategy1_straddle_scenarios.csv` | 21 escenarios | Payoff del Straddle ATM enlazado causalmente al pronóstico y cubierto con -23 acciones. |
| `outputs/tables/strategy2_calendar_scenarios.csv` | 21 escenarios | Payoff del Calendar Spread a strike fijo $K=13.00$ ($\sigma_{\text{fwd}} = 38.15\%$). |

---

## 5. Figuras y Visualizaciones Generadas

* `outputs/figures/smile_2d_slices.png`: Cortes 2D de la sonrisa de volatilidad por vencimiento con soporte empírico acotado.
* `outputs/figures/surface_3d_volatility.png`: Superficie 3D de volatilidad implícita en coordenadas $(k, \tau)$ monótona en tiempo.
* `outputs/figures/term_structure_atm.png`: Estructura temporal ATM ($k=0$) desde 3 días hasta 2.2 años.
* `outputs/figures/model_comparison_errors.png`: Errores absolutos medios (MAE) de los cuatro modelos por segmento.
* `outputs/figures/stress_test_pnl_waterfall.png`: P&L por escenario comparando Revaloración Full EDP vs Taylor con base modelo unificada.
* `outputs/figures/stress_crisis_leg_breakdown.png`: Desglose reconciliado de P&L por pata en el Escenario 3 de Crisis Severa (-20% spot).
* `outputs/figures/nu_historical_vol_and_forecasts.png`: Volatilidad histórica realizada (2021-2026) y pronóstico causal HAR-RV purificado.
* `outputs/figures/strategy1_payoff_scenarios.png`: Curvas de retorno del Straddle delta-neutral con tres regímenes de fricción.
* `outputs/figures/strategy2_calendar_payoff.png`: Perfil de beneficio a 31 días del Calendar Spread en strike 13.00.

---

## 6. Recomendaciones Institucionales para la Mesa de Derivados

1. **Abandono inmediato de Black-Scholes con volatilidad plana:** La tarificación con volatilidad constante subestima el valor de las opciones dentro del dinero en un 48.4% y distorsiona el cálculo del margen de garantía.
2. **Adopción de la superficie SVI en varianza total libre de arbitraje:** Instituir la superficie SVI con restricciones de Roger Lee ($b(1+|\rho|) < 2.0$) y acumulación monótona temporal como la referencia oficial de *mark-to-model*.
3. **Mandato de Revaloración Completa por EDP en Stress Testing:** Prohibir el uso exclusivo de aproximaciones de Taylor por Griegas para shocks severos ($|\Delta S| \ge 10\%$). En caídas del 20%, la no-linealidad financiera genera una discrepancia de $-\$261.15$ USD frente a Taylor.
4. **Disciplina de Fricciones y Cobertura Americana:** Exigir que las estrategias de volatilidad utilicen el delta americano real para la cobertura y descuenten un hurdle rate mínimo para cubrir el spread bid-ask y los costos de margen regulatorio.

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
