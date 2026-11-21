# INFORME DE LÍNEA BASE Y AUDITORÍA FORENSE — ImpVolSurface
**Fecha de corte:** 21 de noviembre de 2026  
**Rama de trabajo:** `fix/quant-audit-2026-11` (creada a partir de `JDELGADO2607/feat-nu-american-options`)  
**Commit base:** `e871eab1d3bbf73184e2757448fbc7933acd56fa`  
**Estado del árbol de trabajo inicial:** Limpio (`working tree clean`).  
**Auditor / Ingeniero Cuantitativo Sénior:** Antigravity (Google DeepMind)

---

## 1. Entorno de Ejecución y Trazabilidad de Git

### 1.1 Estado de Git y Comparación de Commits
* **Commit auditado:** `e871eab1d3bbf73184e2757448fbc7933acd56fa`
  * Mensaje: `feat(nu-options): complete American options PDE engine, SVI surface, stress testing and full documentation`
  * Rama de origen: `JDELGADO2607/feat-nu-american-options`
* **Commit previo:** `2564fa4` (`Initial commit`)
* **Diferencia con el estado auditado:** Ninguna en el árbol inicial. El repositorio se encontraba exactamente en el commit auditado sin modificaciones locales previas.
* **Rama de reparación creada:** `fix/quant-audit-2026-11` para preservar la rama principal y evitar force-pushes o pérdida de historial.

### 1.2 Versiones del Entorno de Software
* **Sistema Operativo:** Windows 11 (64-bit)
* **Python:** 3.12.6
* **NumPy:** 2.1.1
* **SciPy:** 1.18.0
* **Pandas:** 2.2.2
* **Statsmodels:** 0.15.0
* **Scikit-Learn:** 1.9.1
* **Matplotlib:** 3.9.2
* **OpenPyXL:** 3.1.5
* **Pytest:** 9.2.0
* **MiKTeX / pdflatex:** 25.12.0.0 (disponible en `C:\Users\CAROL\AppData\Local\Programs\MiKTeX\miktex\bin\x64\pdflatex.exe`)

---

## 2. Árbol de Módulos, Dependencias y Archivos de Entrada

### 2.1 Estructura de Módulos
```
rockling/
├── data/
│   ├── raw/
│   │   └── Opciones_Completo.xlsx          # Fuente primaria Excel (Hoja1 y Hoja2)
│   └── processed/
│       └── nu_historical_daily.csv         # Serie histórica diaria NU (2021-2026)
├── src/
│   ├── market_data.py                     # Curva cupón cero / par, spot, forward
│   ├── data_cleaning.py                   # Ingesta, parseo OCC, tau, cotas y tiers
│   ├── pricing_bs.py                      # Black-Scholes analítico y griegas
│   ├── pricing_crr.py                     # Árbol binomial CRR benchmark
│   ├── pricing_american_fd.py             # Crank-Nicolson PDE + Rannacher + Penalización
│   ├── iv_inversion.py                    # Inversor Brent y comparación Bloomberg
│   ├── surface.py                         # SVI Raw, PCHIP temporal, LOO validation
│   ├── model_comparison.py               # Matriz 2x2 de tarificación
│   ├── greeks.py                          # Griegas numéricas y analíticas
│   ├── portfolio.py                       # Portafolio 5 patas y cobertura delta
│   ├── stress_testing.py                  # Stress testing multifactorial
│   ├── forecasts.py                       # Volatilidad histórica, EWMA, HAR-RV
│   └── strategies.py                      # Straddle y Calendar spread
├── tests/
│   ├── test_contracts_and_dates.py        # 4 tests
│   ├── test_iv_recovery.py                # 3 tests
│   ├── test_no_lookahead.py               # 3 tests
│   ├── test_portfolio_and_stress.py       # 2 tests
│   ├── test_pricing_american.py           # 4 tests
│   ├── test_pricing_bs.py                 # 3 tests
│   └── test_surface_and_interpolation.py  # 4 tests
├── outputs/
│   ├── tables/                            # 15 archivos CSV generados
│   ├── figures/                           # 9 gráficos PNG
│   └── data_diagnostics/                  # Volcados y reportes diagnósticos
└── docs/
    ├── DECISIONES_Y_LIMITACIONES.md
    ├── ESTADO_CONTINUACION.md
    ├── GUIA_EXPOSICION_10_MIN.md
    ├── MANUAL_MATEMATICO_COMPLETO.tex
    ├── MANUAL_MATEMATICO_COMPLETO.pdf
    └── PREGUNTAS_DEFENSA.md
```

### 2.2 Hashes Criptográficos SHA-256 de Archivos de Entrada
| Archivo | SHA-256 Hash |
|---|---|
| `data/raw/Opciones_Completo.xlsx` | `306F8D3C1A52C7A67952D08881516BDC8632856E3ABD6B33DE373C4BC77FFB53` |
| `data/processed/nu_historical_daily.csv` | `A510F9A48EAA0FC4F95CFBFCDA491DE09F4A6B14956EFB0F3959C7C57AC5989A` |

---

## 3. Estado de la Suite de Pruebas Existente

Al ejecutar `pytest -v` en la línea base:
```
============================= 23 passed in 30.09s =============================
```
**Diagnóstico crítico:** Aunque el 100% de los 23 tests pasan, varios tests contienen **criterios tautológicos o consolidan defectos matemáticos severos**:
1. `tests/test_portfolio_and_stress.py::test_stress_test_matrix_integrity` (línea 52):
   Exige explícitamente `assert abs(s3_row['taylor_discrepancy']) > 5.0`. Valida y aprueba que Taylor falle por una discrepancia enorme, la cual fue provocada por un error numérico en Gamma y por el error de marca inicial.
2. `tests/test_surface_and_interpolation.py::test_svi_parameters_bounds` (línea 59):
   Exige `assert row['pct_no_butterfly_arb'] >= 80.0`. Tolera hasta un **20% de violaciones de arbitraje mariposa** en los cortes de superficie.
3. `tests/test_surface_and_interpolation.py::test_no_calendar_arbitrage_monotonic_total_variance` (línea 36):
   Únicamente evalúa monotonía en $k=0.0$ (ATM). Ignora completamente los strikes OTM/ITM donde se presentan decrementos de varianza total entre vencimientos adyacentes.
4. `tests/test_no_lookahead.py::test_historical_dataset_no_lookahead` (línea 26):
   Comprueba únicamente que la fecha máxima del CSV histórico sea `<= 2026-11-17`. No verifica si durante el bucle de validación walk-forward se utilizan etiquetas futuras de retornos a 21 días que no estaban maduras a la fecha de cada predicción $t$.
5. `tests/test_pricing_american.py`:
   No contiene ninguna prueba de estabilidad de Gamma o Vanna ante perturbaciones de malla o bumps de diferencias finitas en opciones americanas.

---

## 4. Estado de las Tablas de Referencia y Métricas Impugnadas

| Tabla de Referencia | Métrica Reportada en Línea Base | Diagnóstico Forense y Causa del Defecto | Estado de Aceptación |
|---|---|---|---|
| `hypothetical_portfolio.csv` (Leg 3: Put K=12, tau=31d) | $\text{Gamma}_{\text{unit}} = 3.3547$, $\text{Pos Gamma} = 1006.41$ | Reconstrucción de dominio $S_{\max} = 4.0 \cdot \max(S_0, K)$ varía el mallado en cada bump de $S_0 \pm 0.01$. El error de interpolación cúbica dividido por $\Delta S^2 = 10^{-4}$ multiplica el ruido por 10,000. El valor real de Gamma con malla fija es $\sim 0.237$. | **IMPUGNADO** (Defecto P0) |
| `hypothetical_portfolio.csv` (Leg 5: Put K=11, tau=59d) | $\text{Gamma}_{\text{unit}} = 0.0059$ | Distorsión análoga por salto de malla e interpolación. | **IMPUGNADO** (Defecto P0) |
| `stress_test_matrix.csv` (Escenario S3 Crisis -20%) | Discrepancia Taylor = $\$3,253.29$ USD | P&L de estrés mezcla precio modelo final con `lastPrice` inicial (error de marca inicial de $-\$20.47$ USD). Además, el término $\frac{1}{2} \Gamma (\Delta S)^2$ estalla debido al Gamma artificialmente inflado ($1006.41 \times 0.5 \times (-2.466)^2 \approx \$3,060$ USD). | **IMPUGNADO** (Defecto P0) |
| `stress_test_matrix.csv` (Escenario S1 Roll-Down 10d) | $\text{Full PnL} = -\$13.43$, $\text{Taylor} = -\$10.79$ | Contaminado por la diferencia inicial mark-to-model. No existe un escenario NULO ($\Delta S=0, \Delta t=0, \Delta \sigma=0$) que verifique que el P&L sea exactamente cero. | **IMPUGNADO** (Defecto P0) |
| `svi_slice_parameters.csv` (Corte 2029-01-19) | $b(1 + |\rho|) \approx 2.465$, $88.0\%$ sin arbitraje | Viola la cota de alas de Roger Lee ($b(1+|\rho|) < 2$). Se calibra SVI de 5 parámetros con solo 4 observaciones. Penalización en código usaba umbral erróneo de 3.9 en vez de 2.0. | **IMPUGNADO** (Defecto P0) |
| `surface_leave_one_out_validation.csv` | $\text{MAE Precio} = \$0.039$, $\text{MAE IV} = 2.48\text{ pp}$ | Puts americanas se valoran con `bs_price('P', ...)` europeo en vez del motor americano Crank-Nicolson FD. No es leave-one-strike-out agrupado (filtra información si coexisten C y P del mismo strike). | **IMPUGNADO** (Defecto P1) |
| `volatility_forecast_evaluation.csv` | $\text{QLIKE} = 0.1813$, $\text{RMSE} = 15.65\text{ pp}$ | La ventana de entrenamiento causal `clean_data.iloc[:t]` incluye filas $t-1 \dots t-20$ cuyo `target_rv_forward` abarca días posteriores a $t$. Hay fuga de información futura (look-ahead leak). | **IMPUGNADO** (Defecto P0) |
| `strategy1_straddle_scenarios.csv` | Pronóstico $= 72.97\%$, IV ATM $= 44.02\%$ | El valor $72.97\%$ está hardcodeado como parámetro por defecto en `src/strategies.py`. La delta de la put americana se calculó con Black-Scholes europeo usando la IV de la call. | **IMPUGNADO** (Defecto P0) |
| `strategy2_calendar_scenarios.csv` | Varianza forward $38.15\%$ en $K=13.0$ | No distingue si la varianza forward se extrae a strike fijo o moneyness constante; no modela riesgo de asignación temprana ni margen de acciones. | **IMPUGNADO** (Defecto P0) |

---

## 5. Matriz de Hallazgos Forenses y Plan de Reparación

| ID | Módulo / Archivo y Líneas | Defecto / Hallazgo | Impacto Cuantitativo | Prueba Roja Inicial | Corrección Prevista | Criterio de Aceptación |
|---|---|---|---|---|---|---|
| **H-01** | `src/pricing_american_fd.py`: 76-78; `src/greeks.py`: 53-59 | Dominio espacial $S_{\max}$ depende de $S_0$. En bumps de $S \pm 0.01$, la malla cambia y la interpolación cúbica genera oscilaciones catastróficas en $\Gamma$ y Vanna. | Gamma de Put NU K=12 salta a 3.3547 (valor real $\sim 0.237$, error $>1300\%$). | Test de perturbación de bump $\Delta S \in [0.005, 0.05]$ y convergencia de malla $M \in [150, 900]$ falla con dispersión $>50\%$. | Dominio $S_{\max}$ común y fijo para evaluaciones perturbadas, o cálculo de derivadas sobre la misma malla PDE; revisar interpolación cuadrática / monotone spline / tridiagonal directa. | Gamma y Vanna estables ante cambios de $\Delta S$ y refinamiento de malla (variación $<5\%$). |
| **H-02** | `src/stress_testing.py`: 188, 228-240; `src/portfolio.py` | P&L de estrés toma $P_{\text{stressed}} - P_{\text{market}}$ en vez de $P_{\text{stressed}} - P_{\text{model}}$. Mezcla error de marca inicial ($-\$20.47$) con P&L de shock. No existe escenario nulo. Taylor contaminado por Gamma inflado. | Escenario de shock cero daría P&L no nulo. Discrepancia Taylor de $\$3,253$ USD atribuida falsamente solo a no linealidad. Gráficos con $-354$ acciones hardcodeadas. | Test de escenario nulo ($\Delta S=0, \Delta t=0, \Delta \sigma=0$) reporta P&L $\ne 0$. | Separar `mark_to_model_diff = P0_model - P0_market` y `stress_pnl = P1_model - P0_model`. Añadir escenario nulo estricto. Reconciliar Taylor con griegas corregidas. Dinamizar hedge en gráficos. | P&L del escenario nulo es $0.00 \pm 10^{-6}$ USD. Taylor consistente y explicado analíticamente. |
| **H-03** | `src/surface.py`: 63, 104, 169-172, 274 | SVI calibrado con $<5$ puntos. Lee's wing condition penalizaba con $3.9$ en vez de $2.0$. PCHIP no garantiza monotonía si los nodos de varianza total decrecen entre tenors. Tests aceptaban $20\%$ de arbitraje. | Enero 2029 tiene alas inadmisibles ($b(1+\|\rho\|) = 2.465 > 2$) y $12\%$ de densidad butterfly negativa. Fallbacks silenciosos y extrapolación arbitraria. | Test de verificación de densidad mariposa estricta ($g(k) \ge 0$) y pendientes de alas ($b(1+\|\rho\|) < 2$) en todos los cortes falla. | Política explícita calificar/descartar/fallback. Restringir $b(1+\|\rho\|) \le 2.0$. Chequeo mariposa en soporte real. Verificación de no arbitraje de calendario bidimensional. | Cero violaciones de mariposa en el dominio publicado de cada corte SVI; alas conformes a Roger Lee; soporte explícito. |
| **H-04** | `src/surface.py`: 324-326 | En leave-one-strike-out validation, las puts se valoran con Black-Scholes europeo (`bs_price('P')`). | Error de valoración OOS espurio que ignora la prima de ejercicio anticipado americano. Filtración entre C y P si no se excluyen en bloque por strike. | Test de comparación de precio modelo vs motor americano falla al detectar uso de fórmula europea para puts. | Reemplazar por motor americano Crank-Nicolson FD. Reportar MAE/RMSE desagregado por calls/puts, vencimiento y moneyness. Exclusión agrupada por strike. | Validación OOS coherente con el motor de inversión, sin sesgo metodológico de modelo. |
| **H-05** | `src/forecasts.py`: 83, 97-115 | `target_rv_forward[t]` contiene la varianza promedio de $t+1 \dots t+21$. El loop walk-forward entrena en `clean_data.iloc[:t]`, que incluye $t-20 \dots t-1$ cuyas etiquetas dependen de retornos posteriores a $t$. | Fuga futura (look-ahead bias) en el modelo econométrico HAR-RV. Métricas OOS artificialmente sobreajustadas. | Test contrafactual: modificar retornos futuros posteriores a $t$ cambia la predicción en $t$. | Guardar fechas de inicio y fin de cada etiqueta forward. Purgar (`purging`) las últimas 21 observaciones en el entrenamiento en $t$, garantizando que solo se usen etiquetas cuyo evento terminó `<= t`. | Predicción en $t$ invariante ante perturbaciones de retornos futuros posteriores a $t$. Protocolo causal estricto. |
| **H-06** | `src/strategies.py`: 44, 67-68, 178-185 | Estrategia 1 tiene `forecast_vol_pct = 72.97` hardcodeado. Delta de put americana calculada con BS europeo y volatilidad de la call. Calendar spread no explicita definición de varianza forward ni ejercicio anticipado. | Estrategia desconectada del pipeline; desbalanceo delta del straddle en mercado real; supuestos de backtest no documentados. | Test de sensibilidad de señal ante cambios de pronóstico/IV falla o usa constantes fijas. | Conectar directamente la predicción purgada del pipeline. Delta del straddle con motor americano y la IV propia de la put. Documentar explícitamente forward variance a strike fijo y fricciones. | Señal dinámica y verificable; straddle delta-neutral riguroso; escenarios de estrés prospectivos con fricciones completas. |
| **H-07** | `src/data_cleaning.py`: 88-94; `src/iv_inversion.py`: 147-156 | Merge con Bloomberg sin `validate='one_to_one'`. Inversión Brent reporta `CONVERGED` cuando la tolerancia es de volatilidad (`xtol=1e-5`), pero 64 contratos tienen error de precio $> 10^{-6}$ USD. Tasas par del Tesoro aplicadas sin bootstrapping. | Discrepancias menores de tolerancia no advertidas en documentación. Riesgo de multiplicidad en merges. | Test de verificación de error de reconstrucción de precio vs tolerancia estricta reporta inconsistencia. | Añadir `validate='1:1'`. Registrar explícitamente convergencia en volatilidad vs convergencia en precio. Documentar convención de tasa efectiva par. | Trazabilidad 1:1 verificada; estatus de convergencia transparente y coherente. |

---

## 6. Próximo Paso Inmediato
Habiendo fijado la línea base en este documento sin alterar resultados preexistentes, se procede de inmediato al **BLOQUE P0-A: Reparar Gamma, Vanna y estabilidad de griegas americanas en `src/pricing_american_fd.py`, `src/greeks.py` y `tests/test_pricing_american.py`**.
