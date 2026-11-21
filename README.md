# Proyecto Cuantitativo: Superficie de Volatilidad Implícita, Métodos Numéricos de EDP, Stress Testing y Estrategias con Opciones Americanas de Nu Holdings Ltd. (NU)

**Entidad:** Mesa de Derivados & Gestión de Riesgos de Renta Variable  
**Subyacente:** Nu Holdings Ltd. (NYSE: NU)  
**Fecha Base de Mercado:** 17 de noviembre de 2026, 16:00 EST (America/New_York)  
**Precio Spot de Referencia ($S_0$):** $12.33 USD (Cierre oficial NYSE)  
**Tasa de Dividendos ($q$):** 0.00 % anual ($q = 0$, verificado en Formulario SEC 6-K del 12-nov-2026)  
**Curva Libre de Riesgo:** Curva Par del Tesoro de EE.UU. (4.10% a 4.84% compuesta continua, DEC-014)  
**Entorno de Ejecución:** Python 3.12.6, NumPy 2.1.1, SciPy 1.18.0, Pandas 2.2.2, OpenPyXL 3.1.5, Pytest 9.2.0, MiKTeX (pdflatex)  
**Rama de Auditoría y Reparación:** `fix/quant-audit-2026-11` (100% verificada, **82/82 tests passing**, exit code 0)  
**Certificación de Superficie:** [docs/SURFACE_RELEASE_STATUS.md](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/docs/SURFACE_RELEASE_STATUS.md) | [docs/audits/GEMINI_REMEDIATION_R3.md](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/docs/audits/GEMINI_REMEDIATION_R3.md)

---

## 1. Resumen Ejecutivo del Proyecto

Este repositorio contiene la implementación cuantitativa completa, verificada, auditada independientemente y reproducible que resuelve los **Puntos 46 a 56** para la valoración y gestión de riesgos de opciones americanas sobre NU, remediando todos los hallazgos de las Rondas 1, 2 y 3 (auditoría CODEX `855eb1c`):

1. **Auditoría Forense y Depuración (Puntos 46 y 47):** Importación de 575 contratos reales (303 calls, 272 puts, 16 vencimientos), corrección de truncamientos intradiarios de $\tau$, detección del reseteo a cero de bid/ask en Yahoo, y clasificación en Tiers mediante cotas de no arbitraje y condicionamiento $\kappa = 0.01 / \text{Vega} \le 3.0$ pp/centavo (201 contratos limpios). Auditoría de 68 pares Call-Put idénticos.
2. **Motores de Valoración Americanos y Estabilidad de Griegas (Puntos 48 y P0-A):** Implementación de Black-Scholes analítico para Calls sin dividendos (Merton, 1973) y diferencias finitas Crank-Nicolson con suavizado de Rannacher y penalización cuadrática (Forsyth & Vetzal, 2002) para Puts americanas. Dominio espacial común e invariante $S_{\max} = 4.0 \cdot \max(S_0, K)$ con malla compartida e interpolación PCHIP local, estabilizando el Gamma de la Put $K=12$ en **$0.2375$**.
3. **Inversión Numérica a Volatilidad Implícita (Punto 49):** Algoritmo de Brent sobre intervalo bracket $[0.01, 5.00]$ y contraste estratificado con Bloomberg mediante merge `1:1` estricto, reportando estados de convergencia transparentes (`CONVERGED_PRICE_TOL` vs `CONVERGED_VOL_TOL`).
4. **Construcción y No Arbitraje de la Superficie SVI/PCHIP 2D (Puntos 50, 51, P0-C y R3):** 
   - **Armonización Global de Cortes SVI (DEC-016):** Desplazamiento vertical $a_i \leftarrow a_i + \Delta a_i$ combinado con interpolación lineal por tramos en varianza total, preservando $C^\infty$ convexidad en strikes ($d^2 C/dK^2 \ge 0$) y eliminando definitivamente las violaciones de convexidad en vencimientos interpolados (hallazgo bloqueante B1).
   - **Horizonte Productivo Certificado ($\tau \le 430$ días):** Cuarentena formal del vencimiento LEAPS de enero de 2029 (794d) como exploratorio (DEC-017).
   - **Validación Cruzada Holdout Genuinamente 2D (DEC-018):** Exclusión simultánea de calls y puts por strike/tenor con re-calibración y re-pricing FD americano sobre 197 contratos: **MAE IV = 2.67 pp**, **MAE Precio = \$0.0434 USD**.
   - **Cotas de Monotonía Temporal en Puts Americanas:** Garantía de no-pérdida de valor de continuación en puts ITM ($\Delta P \ge 0$).
5. **Comparación de Modelos (Puntos 54 y 55):** Matriz $2 \times 2$ (Europeo/Americano $\times$ Plano/Superficie) distinguiendo formalmente ajuste In-Sample ($N=201$) y validación Out-of-Sample LOO ($N=197$). La superficie SVI reduce el error MAE en un 40.9% general y en un 48.4% en opciones ITM.
6. **Stress Testing de Cadena Fija Unificado (Puntos 52, P0-B y 13.B):** Cartera hipotética delta-neutral de 5 patas con cobertura dinámica de **-357 acciones de NU** ($\Delta_{\text{neto}} = +0.11$). Marco de contabilidad dual que incorpora el Escenario Nulo ($\text{P\&L} \equiv \$0.00$), aísla la diferencia inicial de marca a modelo ($-\$20.43$ USD) y calcula el margen dinámico prudencial adaptado al valor de mercado observable (DEC-015).
7. **Estrategias Cuantitativas de Trading y Causalidad Estricta (Puntos 53, P1-C, M3 y H4):** Modelo HAR-RV (Corsi, 2009) con validación walk-forward purificada y corte causal estricto para muestras cortas ($N \ge 50$). El pronóstico activa `LONG_VOLATILITY_STRADDLE` con vinculación exacta de órdenes; ante señales neutrales (`NO_TRADE`), la simulación arroja estrictamente 0 contratos, 0 fricción y $\$0.00$ de P&L. Parámetro `export_artifacts` que blinda la inmutabilidad de artefactos en suites de prueba (H4).

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
│   ├── market_data.py                         # Curva del Tesoro r(tau), spot y forward (DEC-014)
│   ├── data_cleaning.py                       # Parseo OCC, tau exacto, cotas, tiers y paridad
│   ├── pricing_bs.py                          # Black-Scholes analítico y Griegas
│   ├── pricing_crr.py                         # Árbol binomial CRR (benchmark)
│   ├── pricing_american_fd.py                 # Crank-Nicolson + Rannacher + Penalización + Malla Fija
│   ├── iv_inversion.py                        # Inversor Brent, tolerancia dual y contraste Bloomberg
│   ├── surface.py                             # Calibración SVI, armonización global, interpolación lineal y holdout 2D
│   ├── model_comparison.py                   # Matriz 2x2 in-sample y LOO out-of-sample
│   ├── greeks.py                              # Griegas unificadas analíticas y numéricas estables
│   ├── portfolio.py                           # Portafolio 5 patas y cobertura delta dinámica (-357 sh)
│   ├── stress_testing.py                      # Stress testing con contabilidad dual y margen dinámico (DEC-015)
│   ├── forecasts.py                           # Estimador HAR-RV causal con guarda M3 para muestras cortas
│   └── strategies.py                          # Estrategias 1 y 2 con exportación controlada de artefactos (H4)
├── tests/
│   ├── test_contracts_and_dates.py            # Tests de parseo, tau, tiers y paridad (5 tests)
│   ├── test_pricing_bs.py                     # Tests de paridad, monotonicidad y griegas (6 tests)
│   ├── test_pricing_american.py               # Tests de prima americana, FD vs CRR y penalización (6 tests)
│   ├── test_pde_greeks_stability.py           # Tests de estabilidad de Gamma/Vanna y dominio fijo (5 tests)
│   ├── test_iv_recovery.py                    # Tests de recuperación sintética Brent y estatus (2 tests)
│   ├── test_surface_and_interpolation.py      # Tests de SVI, mariposa, calendario y PCHIP (10 tests)
│   ├── test_surface_convexity_and_extrapolation.py # Suite de regresión R3 (Convexidad 2D B1, H1, H2, H5, M1, L2, Core) (12 tests)
│   ├── test_portfolio_and_stress.py           # Tests de delta-neutralidad, P&L nulo y margen dinámico (5 tests)
│   ├── test_no_lookahead.py                   # Tests de causalidad estricta e invariancia de hashes H4 (8 tests)
│   └── test_pipeline_error_propagation.py     # Tests de propagación estricta de errores del pipeline (4 tests)
├── outputs/
│   ├── tables/                                # 16 tablas CSV auditables validadas por contratos de datos
│   ├── figures/                               # 9 gráficos de alta resolución verificados
│   └── data_diagnostics/                      # Volcados y reportes diagnósticos brutos
├── docs/
│   ├── SURFACE_RELEASE_STATUS.md              # Estado de certificación, horizonte <=430d y reglas de consumo
│   ├── audits/
│   │   ├── CODEX_AUDIT_855eb1c.md             # Auditoría externa independiente CODEX
│   │   └── GEMINI_REMEDIATION_R3.md           # Informe de remediación integral R3 con matriz de trazabilidad
│   ├── SEGUNDA_AUDITORIA_PR1.md               # Informe de la Segunda Ronda de Auditoría Independiente
│   ├── DECISIONES_Y_LIMITACIONES.md           # Registro vivo de decisiones cuantitativas (DEC-001 a DEC-018)
│   ├── MANUAL_MATEMATICO_COMPLETO.tex         # Manual exhaustivo en LaTeX (24 págs)
│   ├── MANUAL_MATEMATICO_COMPLETO.pdf         # PDF compilado con pdflatex
│   ├── GUIA_EXPOSICION_10_MIN.md              # Guion oral de 8 diapositivas (10 min)
│   ├── PREGUNTAS_DEFENSA.md                   # Catálogo exhaustivo de preguntas técnicas (29 preguntas)
│   └── REFERENCIAS_VERIFICADAS.md             # Catálogo bibliográfico con DOIs verificados
├── requirements.txt                           # Dependencias de Python fijadas
├── run_all.py                                 # Script maestro ejecutable con contratos de datos y pytest estricto
└── README.md                                  # Este documento
```

---

## 3. Instrucciones de Reproducción y Verificación

### 3.1 Instalación de Dependencias
```bash
pip install -r requirements.txt
```

### 3.2 Ejecución del Pipeline Completo (con Contratos de Datos y Verificación Pytest)
```bash
python run_all.py
```
El script maestro valida automáticamente los contratos de datos de las 16 tablas, comprueba la integridad de las figuras y ejecuta la suite completa de 82 pruebas unitarias. Si cualquier prueba o contrato falla, el script termina con código de error no nulo.

### 3.3 Ejecución de la Suite de Pruebas Automatizadas
```bash
pytest -v
```
Ejecuta los **82 tests automatizados** distribuidos en los 10 módulos de pruebas.

---

## 4. Tablas y Resultados Numéricos Principales

| Archivo Generado | Filas / Registros | Descripción Cuantitativa |
|---|---|---|
| `outputs/tables/options_audit.csv` | 575 filas | Auditoría completa con banderas de rechazo y asignación de Tiers 1-4. |
| `outputs/tables/options_clean.csv` | 201 filas | Contratos de alta calidad elegibles para la superficie. |
| `outputs/tables/iv_call_put_parity_audit.csv` | 68 pares | Auditoría de paridad Call-Put en pares simultáneos. |
| `outputs/tables/options_with_iv.csv` | 201 filas | Volatilidades implícitas propias calculadas por Brent + EDP con estatus de tolerancia. |
| `outputs/tables/iv_comparison_bloomberg.csv` | 4 tramos | Sesgo medio (+0.19 pp en 90-365d) y MAE frente a Bloomberg Mid. |
| `outputs/tables/svi_slice_parameters.csv` | 15 cortes | Parámetros $(a, b, \rho, m, \eta)$, Lee wing bound y estado de mariposa/PCHIP. |
| `outputs/tables/surface_release_grid.csv` | 450 puntos | Malla de lanzamiento 2D con 24 campos obligatorios, derivadas de precio y flags. |
| `outputs/tables/surface_quality_diagnostics.csv` | 15 cortes | Diagnóstico completo por corte, soporte observable, flags y restricciones. |
| `outputs/tables/surface_final_holdout_validation.csv` | 197 contratos | Validación OOS bidimensional genuina: MAE IV = 2.67 pp, MAE Precio = \$0.0434 USD. |
| `outputs/tables/surface_leave_one_out_validation.csv` | 197 tests | Validación LOO 1D agrupada con motor FD americano. |
| `outputs/tables/model_comparison_summary.csv` | 7 segmentos | In-sample vs LOO out-of-sample demostrando reducción de MAE de \$0.085 a \$0.039 en ITM. |
| `outputs/tables/hypothetical_portfolio.csv` | 6 posiciones | 5 opciones + cobertura con -357 acciones ($\Delta_{\text{neto}} = +0.11$, Gamma estable). |
| `outputs/tables/stress_test_matrix.csv` | 12 escenarios | P&L con contabilidad dual, Escenario Nulo (\$0.00) y margen dinámico. |
| `outputs/tables/stress_test_leg_breakdown.csv` | 60 registros | Desglose por pata reconciliado al céntimo en todos los escenarios de estrés. |
| `outputs/tables/volatility_forecast_evaluation.csv` | 3 modelos | Evaluación OOS walk-forward purificada ($s \le t-21$) de HAR-RV (QLIKE = 0.1855). |
| `outputs/tables/strategy1_straddle_scenarios.csv` | 21 escenarios | Payoff del Straddle ATM enlazado causalmente al pronóstico y cubierto con -23 acciones. |
| `outputs/tables/strategy2_calendar_scenarios.csv` | 21 escenarios | Payoff del Calendar Spread a strike fijo $K=13.00$ ($\sigma_{\text{fwd}} = 38.15\%$). |

---

## 5. Figuras y Visualizaciones Generadas

* `outputs/figures/smile_2d_slices.png`: Cortes 2D de la sonrisa de volatilidad por vencimiento con soporte empírico acotado.
* `outputs/figures/surface_3d_volatility.png`: Superficie 3D de volatilidad implícita en coordenadas $(k, \tau)$ suave y monótona.
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
2. **Adopción de la superficie SVI armonizada en varianza total libre de arbitraje:** Instituir la superficie SVI con restricciones de Roger Lee ($b(1+|\rho|) < 2.0$), armonización global de niveles e interpolación lineal de varianza total como la referencia oficial de *mark-to-model* para vencimientos $\tau \le 430$ días.
3. **Mandato de Revaloración Completa por EDP en Stress Testing:** Prohibir el uso exclusivo de aproximaciones de Taylor por Griegas para shocks severos ($|\Delta S| \ge 10\%$). En caídas del 20%, la no-linealidad financiera genera una discrepancia de $-\$261.15$ USD frente a Taylor.
4. **Disciplina de Fricciones y Cobertura Americana:** Exigir que las estrategias de volatilidad utilicen el delta americano real para la cobertura y descuenten un hurdle rate mínimo para cubrir el spread bid-ask y los costos de margen dinámico.
