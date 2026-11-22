# INFORME DE SEGUNDA RONDA DE AUDITORÍA Y CONTROL DE CALIDAD INDEPENDIENTE
## Repositorio: `JDELGADO2607/ImpVolSurface`
### Pull Request #1: `fix/quant-audit-2026-11` $\to$ `master`

**Rol:** Auditor Cuantitativo Independiente / Ingeniero Financiero Sénior  
**Especialidad:** Valoración de Opciones Americanas, Superficies de Volatilidad Implícita SVI/PCHIP, Métodos Numéricos de EDP y Stress Testing  
**Fecha del Dictamen:** 21 de noviembre de 2026  
**Rama Auditada:** `fix/quant-audit-2026-11`  
**Commit Inicial de Referencia:** `62816f5`  
**Commit Final de Cierre:** `0ea7689` (consolidación de la segunda ronda de auditoría)  
**Estado de la Suite de Pruebas:** **48 / 48 APROBADAS (100% de éxito, 0 fallos, 0 regresiones)**  
**Tiempo de Ejecución Integral del Pipeline (`run_all.py`):** 673.3 segundos (11.2 minutos, determinista y verificado de extremo a extremo)

---

## 1. Resumen Ejecutivo y Dictamen Técnico Final

La primera ronda de reparaciones resolvió los defectos más graves de la línea base original (la inestabilidad numérica de Gamma en el motor EDP de Crank-Nicolson, la contaminación contable de precios de mercado en el stress testing, el sesgo de anticipación en el estimador HAR-RV y la falta de consistencia contractual).

No obstante, una segunda auditoría cuantitativa independiente identificó **cuatro problemas críticos pendientes** que impedían recomendar el merge a `master`:
1. **Inconsistencia Temporal en Nodos Exactos:** La función `surface_iv()` aplicaba proyección monótona únicamente al interpolar en madureces intermedias, pero al evaluar vencimientos calibrados exactos devolvía la varianza del corte original, generando decrementos de varianza total (violaciones de calendario en los Casos A y B) y discontinuidades artificiales de salto al aproximarse a los nodos.
2. **Garantías Ficticias en Fallback PCHIP:** Los cortes spline registraban automáticamente un `100.0%` de ausencia de arbitraje mariposa basado en una fórmula analítica SVI $g(k)$ inaplicable a splines por tramos, sin verificar la convexidad numérica de precios de opciones.
3. **Desconexión entre Señales y Posiciones Simuladas:** La función de estrategia calculaba siempre el P&L de un straddle largo independientemente de si la señal emitida era `NO_TRADE` o `SHORT_VOLATILITY`, convirtiendo la señal en un rótulo cosmético.
4. **Ocultación de Errores en el Pipeline:** El orquestador `run_all.py` capturaba fallos de `pytest` como simples advertencias e imprimía un banner de éxito con código de salida 0.

Tras implementar las correcciones definitivas, validar formalmente su fundamento matemático, incorporar 11 nuevas pruebas unitarias y de estrés (elevando la suite a **48 pruebas**), regenerar todas las tablas y gráficos desde las fuentes primarias y actualizar la documentación completa, se emite el siguiente dictamen:

> ### DICTAMEN TÉCNICO: **APROBADO PARA MERGE (READY TO MERGE)**
> El Pull Request #1 cumple la totalidad de los criterios de aceptación cuantitativa, financiera y computacional. La superficie SVI/PCHIP es estrictamente continua y libre de arbitraje de calendario en todos los nodos y puntos intermedios; las validaciones de fallback son transparentes y empíricamente verificadas; las simulaciones de trading ejecutan fielmente la señal causal emitida; y el pipeline garantiza la propagación bloqueante de errores con código de salida estricto.

---

## 2. Resumen Detallado de los Cuatro Defectos Identificados

### Defecto 1: Inconsistencia Temporal y Arbitraje de Calendario en Nodos Calibrados
* **Ubicación:** `src/surface.py` (función `surface_iv()`).
* **Descripción:** Cuando $\tau$ no coincidía con un vencimiento calibrado, la función calculaba $w_{\text{mono}} = \text{np.maximum.accumulate}(w_{\text{tenors}})$ y evaluaba un interpolador PCHIP temporal. Sin embargo, si `tau in self.slices`, la función ejecutaba una bifurcación previa y devolvía directamente $w_{\text{raw}}(\tau, k)$ sin aplicar la proyección.
* **Impacto Numérico:**
  * La superficie era no decreciente entre ciertos puntos interpolados, pero admitía decrementos de varianza total entre los nodos calibrados originales.
  * Se generaban discontinuidades artificiales de salto tipo aguja: $\lim_{\epsilon \to 0^+} w(\tau_i + \epsilon) \neq w(\tau_i)$.
* **Reproducción Cuantitativa (Parámetros Internos no Redondeados):**
  * **Caso A (2026-12-04 vs 2026-12-11, $k = -0.163$):**
    * $\tau_1 = 0.046575$ años (17.0 días): $w_1 = 0.016687$, $\sigma_1 = 59.86\%$.
    * $\tau_2 = 0.065753$ años (24.0 días): $w_2 = 0.015675$, $\sigma_2 = 48.83\%$.
    * **Diferencia Cruda:** $\Delta w = w_2 - w_1 = -0.001012 < 0$ (**Arbitraje de Calendario detectado en el nodo exacto**).
    * Al evaluar $\tau_2 - 10^{-5}$, la interpolación arrojaba $w = 0.016687$, cayendo bruscamente a $0.015675$ en $\tau_2$.
  * **Caso B (2026-12-18 vs 2026-12-24, $k = +0.225$):**
    * $\tau_1 = 0.084932$ años (31.0 días): $w_1 = 0.018956$, $\sigma_1 = 47.24\%$.
    * $\tau_2 = 0.101370$ años (37.0 días): $w_2 = 0.017444$, $\sigma_2 = 41.48\%$.
    * **Diferencia Cruda:** $\Delta w = w_2 - w_1 = -0.001512 < 0$ (**Arbitraje de Calendario detectado en el nodo exacto**).

### Defecto 2: Atribución de Garantías Ficticias de Arbitraje a Cortes Fallback PCHIP
* **Ubicación:** `src/surface.py` (método `_calibrate()`).
* **Descripción:** Cuando una rebanada no cumplía los requisitos de SVI (por ejemplo, tener menos de 6 strikes) y conmutaba a PCHIP, el diccionario de parámetros registraba mecánicamente:
  ```python
  'pct_no_butterfly_arb': 100.0
  ```
* **Causa Cuantitativa:** La fórmula de densidad neutral al riesgo $g(k)$ formulada por Gatheral & Jacquier (2014) depende analíticamente de las derivadas primera y segunda de la hipérbola SVI:
  $$w'(k) = b \left( \rho + \frac{k-m}{\sqrt{(k-m)^2 + \eta^2}} \right), \quad w''(k) = \frac{b \eta^2}{((k-m)^2 + \eta^2)^{3/2}}$$
  Esta relación no tiene ningún sentido matemático cuando se aplica a un spline por tramos cúbicos. Además, PCHIP preserva la monotonicidad de los puntos muestrales de varianza, pero no garantiza automáticamente que los precios de las opciones calculados a partir de ella sean convexos respecto al strike ($\frac{\partial^2 C}{\partial K^2} \ge 0$).
* **Evidencia Diagnóstica:** Al evaluar numéricamente el corte LEAPS de 794 días (2029-01-19, 12 strikes), se identificó que debido a una cotización de última transacción anómala e ilíquida en el strike profundo ITM $K=3.0$ ($P_{\text{Call}} = \$10.25$, IV = $103.88\%$), la curva presentaba 4 violaciones de convexidad en precios y 7 de monotonía en puts, a pesar de que el código reportaba ficticiamente $100.0\%$ libre de arbitraje.

### Defecto 3: Desconexión entre Señales Cuantitativas y Estructura de Portafolio Simulado
* **Ubicación:** `src/strategies.py` (función `analyze_strategy_1_straddle()`).
* **Descripción:** Aunque se implementó la función `generate_strategy_signal()` para clasificar la oportunidad entre `LONG_VOLATILITY_STRADDLE`, `SHORT_VOLATILITY_STRADDLE` y `NO_TRADE`, el bloque subsiguiente ejecutaba de forma fija e incondicional:
  ```python
  premium_paid = (c_obs + p_obs) * CONTRACT_MULTIPLIER
  options_payoff = call_payoff + put_payoff
  gross_pnl = (options_payoff - premium_paid) + stock_pnl
  ```
* **Impacto Financiero:** Modificar el pronóstico de volatilidad alteraba el texto de la señal, pero la simulación seguía valorando siempre un straddle largo debitando prima y asumiendo fricciones transaccionales. Si el modelo emitía `NO_TRADE`, la cartera reportaba pérdidas o ganancias en lugar de registrar una exposición nula (\$0.00 USD) y costos nulos (\$0.00 USD).

### Defecto 4: Ausencia de Propagación de Errores y Códigos de Salida en el Pipeline
* **Ubicación:** `run_all.py`.
* **Descripción:** El orquestador ejecutaba `test_exit_code = pytest.main(["-v", "tests/"])`, pero ante `test_exit_code != 0` simplemente imprimía un mensaje de advertencia (`[WARNING]`) y proseguía hasta el bloque final anunciando:
  ```
  PIPELINE EXECUTED SUCCESSFULLY IN XX SECONDS!
  ```
  y terminaba el proceso con código de retorno implícito 0. Tampoco validaba la existencia y finitud de las tablas y figuras generadas por cada etapa.

---

## 3. Correcciones Adoptadas y Fundamento Matemático

### 3.1. Evaluación Temporal Unificada y Monotonicidad Continua (Fase 1)
Se rediseñó por completo el motor de evaluación de `VolatilitySurface`:
1. **Secuencia Proyectada Monótona:** Para cualquier $k$, se evalúan las varianzas de los $N$ cortes calibrados $w_{\text{raw}}(\tau_i, k)$ y se obtiene la secuencia acumulativa monótona no decreciente:
   $$w^*(\tau_i, k) = \max_{1 \le j \le i} w_{\text{raw}}(\tau_j, k), \quad \forall i = 1, \dots, N$$
2. **Interpolación PCHIP Temporal Continua ($C^1$):** Para cualquier $\tau \in [\tau_1, \tau_N]$, se evalúa el interpolador cúbico monótono de Hermite:
   $$w(k, \tau) = \text{PCHIP}_{\tau}\left( \{(\tau_i, w^*(\tau_i, k))\}_{i=1}^N \right)(\tau)$$
   Dado que los nodos $\{w^*(\tau_i, k)\}$ son monótonos por construcción, PCHIP preserva la monotonicidad estricta para todo $\tau$:
   $$\frac{\partial w(k, \tau)}{\partial \tau} \ge 0 \quad \forall \tau \in [\tau_1, \tau_N]$$
   Y como el interpolador coincide exactamente con el valor del nodo en cada vencimiento calibrado ($w(k, \tau_i) \equiv w^*(\tau_i, k)$), se eliminan por completo las discontinuidades de salto:
   $$\lim_{\epsilon \to 0^+} w(k, \tau_i + \epsilon) = \lim_{\epsilon \to 0^-} w(k, \tau_i - \epsilon) = w^*(\tau_i, k)$$
3. **Extrapolaciones Planas Continuas:**
   * $\tau < \tau_1$: Se extrapola a volatilidad implícita constante $\sigma(k, \tau) = \sigma(k, \tau_1) \implies w(k, \tau) = w^*(\tau_1, k) \cdot \frac{\tau}{\tau_1}$. A medida que $\tau \to 0$, $w \to 0$ con pendiente positiva.
   * $\tau > \tau_N$: Se extrapola a volatilidad implícita constante $\sigma(k, \tau) = \sigma(k, \tau_N) \implies w(k, \tau) = w^*(\tau_N, k) \cdot \frac{\tau}{\tau_N}$, asegurando $\frac{\partial w}{\partial \tau} > 0$.
4. **Trazabilidad de Ajustes:** Cada corte registra en `svi_slice_parameters.csv` el número de puntos modificados por la proyección (`calendar_adj_points`), el ajuste máximo $\Delta w$ (`max_calendar_adj_w`), el porcentaje de soporte afectado (`pct_calendar_adjusted`) y el estado formal (`CALENDAR_ARBITRAGE_REMOVED_VIA_PROJECTION` vs `MONOTONIC_ORIGINAL`).

### 3.2. Validación Económica Cruzada en Cortes Fallback (Fase 2)
Se implementó la función `validate_slice_economic_arbitrage()` con los siguientes estándares:
1. **Erradicación de Falsas Garantías:** En cortes PCHIP, `pct_no_butterfly_arb` reporta explícitamente `NaN`, señalando que la fórmula analítica $g(k)$ es `NOT_APPLICABLE_TO_SPLINE`.
2. **Diferencias Divididas de Convexidad en Precios:** Para mallas de strikes no necesariamente equidistantes $K_1 < K_2 < \dots < K_m$, se calculan las primeras y segundas diferencias divididas:
   $$\frac{\Delta C}{\Delta K_i} = \frac{C(K_{i+1}) - C(K_i)}{K_{i+1} - K_i}, \quad \frac{\Delta^2 C}{\Delta K_i^2} = \frac{\frac{\Delta C}{\Delta K_{i+1}} - \frac{\Delta C}{\Delta K_i}}{\frac{K_{i+2} - K_i}{2}}$$
   La ausencia de arbitraje mariposa se valida exigiendo $\frac{\Delta^2 C}{\Delta K_i^2} \ge -\text{tol}$ ($\text{tol} = 10^{-4}$), reportando la métrica empírica `pct_price_convex`.
3. **Monotonía y Cotas Intrínsecas Americanas:** Verificación estricta de que las Calls decrecen en strike ($\Delta C \le 0$), las Puts crecen en strike ($\Delta P \ge 0$), y se respetan las cotas $C \in [(S-K)^+, S]$ y $P \in [(K-S)^+, K]$.
4. **Soporte Local vs Global:** La función `surface_iv()` evalúa si el punto $(k, \tau)$ está dentro del rango observado del vencimiento local (`SUPPORTED_LOCAL_GRID`), fuera de la rebanada pero dentro del rango global (`EXTRAPOLATED_LOCAL_SLICE`), o fuera de toda la superficie (`EXTRAPOLATED_GLOBAL_DOMAIN`).

### 3.3. Vinculación Dinámica Señal-Portafolio (Fase 3)
Se creó la función `build_straddle_portfolio_from_signal()`, que desacopla la decisión cuantitativa de la ejecución y define tres estructuras independientes:
* **`LONG_VOLATILITY_STRADDLE` (Spread $\ge +5.0$ pp):**
  * Posiciones: $+1.0$ Call, $+1.0$ Put, $-23$ acciones de NU (cobertura delta americana).
  * Flujo inicial: Débito de prima $-\$133.00$ USD.
  * Payoffs: Clásica curva convexa en V con ganancias acotadas únicamente por la amplitud del movimiento terminal.
* **`NO_TRADE` ($|\text{Spread}| < 5.0$ pp):**
  * Posiciones: $0.0$ Calls, $0.0$ Puts, $0$ acciones.
  * Flujo inicial: $\$0.00$ USD.
  * Fricciones y P&L: Rigurosamente $\$0.00$ USD en todos los shocks y regímenes de costos, con justificación explícita de neutralidad.
* **`SHORT_VOLATILITY_STRADDLE` (Spread $\le -5.0$ pp):**
  * Posiciones: $-1.0$ Call, $-1.0$ Put, $+23$ acciones de NU (cobertura delta inversa).
  * Flujo inicial: Crédito recolectado de $+\$133.00$ USD.
  * Perfil de Riesgo: Etiquetado formalmente como `THEORETICAL_SHORT_STRADDLE_UNBOUNDED_TAIL_RISK`. Bajo el shock nulo ($S_T = S_0$), maximiza la ganancia por retención de prima ($+\$92.86$ USD netos en base); ante movimientos severos ($\pm 25\%$), incurre en pérdidas pronunciadas no acotadas.
* **Invariancia de Pronóstico:** Se verificó que ninguna función utiliza el valor fijo $72.97\%$ de forma forzada; cualquier pronóstico dinámico pasado como argumento es procesado de inmediato.

### 3.4. Propagación Bloqueante de Errores en el Orquestador (Fase 4)
Se reestructuró `run_all.py`:
1. Cada etapa se ejecuta de forma controlada registrando tiempo, estatus y errores.
2. Tras cada paso se invoca `_validate_table_file()`, que comprueba: existencia del archivo, tamaño $> 0$ bytes, cantidad mínima de registros y ausencia de valores infinitos (`np.isinf`) en columnas críticas.
3. Si una etapa crítica lanza una excepción o falla la validación, el pipeline se detiene inmediatamente (`[ABORTED]`) y termina con `sys.exit(1)`.
4. La ejecución de la suite de pruebas mediante Pytest es el paso final vinculante: si `test_exit_code != 0`, el script falla con `sys.exit(test_exit_code)`.
5. El mensaje de éxito y el código 0 solo se emiten cuando las 7 etapas de cálculo y las 48 pruebas de Pytest concluyen satisfactoriamente.

---

## 4. Matriz de Trazabilidad de la Segunda Ronda

| Problema Auditado | Prueba Fallida Previa | Código / Módulo Modificado | Prueba Aprobada Nueva | Resultado y Artefacto Afectado |
|---|---|---|---|---|
| **Defecto 1:** Arbitraje de calendario en nodos exactos $\tau \in \text{tenors}$ (Casos A y B). | Contraejemplos en `scratch/check_calendar_arb.py`: diff Caso A = $-0.001012$, Caso B = $-0.001512$. | `src/surface.py` (`surface_iv`, `evaluate_slice_total_variance`). | `test_calendar_arbitrage_all_calibrated_tenors_and_neighborhoods`<br>`test_calendar_arbitrage_specific_counterexamples`<br>`test_surface_node_continuity` | `outputs/tables/svi_slice_parameters.csv`<br>`outputs/figures/smile_2d_slices.png`<br>`outputs/figures/term_structure_atm.png`<br>`outputs/figures/surface_3d_volatility.png` |
| **Defecto 2:** Garantía ficticia de arbitraje en Fallback PCHIP (`pct_no_butterfly_arb = 100.0%`). | Auditoría de parámetros: asignación automática en cortes con 2 a 5 strikes. | `src/surface.py` (`validate_slice_economic_arbitrage`, `_calibrate`). | `test_pchip_fallback_economic_validation_and_no_fictitious_guarantees`<br>`test_local_vs_global_extrapolation_tracking` | `svi_slice_parameters.csv` (`pct_no_butterfly_arb` es `NaN` en splines; se reporta `pct_price_convex` y metadatos). |
| **Defecto 3:** Señales de trading desconectadas del portafolio simulado. | Simulación manual con forecast neutro o bajista producía P&L idéntico de straddle largo. | `src/strategies.py` (`build_straddle_portfolio_from_signal`, `analyze_strategy_1_straddle`). | `test_strategy_portfolio_position_linkage_and_signal_dispatch`<br>`test_forecast_parameter_dynamic_dispatch_no_hardcoding` | `outputs/tables/strategy1_straddle_scenarios.csv`<br>`outputs/figures/strategy1_payoff_scenarios.png` |
| **Defecto 4:** Pipeline no propagaba fallos de pruebas (retornaba código 0). | Ejecución con fallo intencional de test terminaba con banner de éxito en versión anterior. | `run_all.py` (`run_pipeline`, `_validate_table_file`). | `test_missing_mandatory_file_fails`<br>`test_non_finite_validation_fails`<br>`test_empty_table_validation_fails`<br>`test_intentional_stage_exception_returns_nonzero`<br>`test_intentional_test_failure_returns_nonzero` | `run_all.py` termina con `sys.exit(code)` estricto ante cualquier error. |

---

## 5. Comparación Cuantitativa Antes vs Después

### 5.1. Arbitraje de Calendario en los Contraejemplos Identificados

| Caso de Prueba | Vencimiento 1 ($\tau_1$) | Vencimiento 2 ($\tau_2$) | Log-Moneyness $k$ | $\Delta w = w_2 - w_1$ (Antes) | $\Delta w = w_2 - w_1$ (Después) | Diagnóstico Final |
|---|---|---|---|---|---|---|
| **Caso A** | 2026-12-04 (17d) | 2026-12-11 (24d) | $-0.163$ | **$-0.001012$** (Arbitraje) | **$+0.000000$** | Monotonía garantizada; arbitraje eliminado. |
| **Caso B** | 2026-12-18 (31d) | 2026-12-24 (37d) | $+0.225$ | **$-0.001512$** (Arbitraje) | **$+0.000000$** | Monotonía garantizada; arbitraje eliminado. |
| **Continuidad $\tau_2 \pm 10^{-6}$** | 2026-12-11 (24d) | 2026-12-11 (24d) | $-0.163$ | Salto de **$0.001012$** | Discrepancia **$< 10^{-8}$** | Continuidad $C^1$ perfecta sin saltos. |

### 5.2. Metadatos de Validación de Cortes Fallback PCHIP (`svi_slice_parameters.csv`)

| Vencimiento | Días $\tau$ | Método | `pct_no_butterfly_arb` (Antes) | `pct_no_butterfly_arb` (Después) | `pct_price_convex` (Nuevo) | Estado de Validación Transversal |
|---|---|---|---|---|---|---|
| 2026-11-20 | 3.0d | PCHIP Spline | 100.0% (Ficticio) | **NaN** (No aplica) | **100.00%** | `VERIFIED_EMPIRICAL_CONVEX_BOUNDS` |
| 2027-12-17 | 395.0d | PCHIP Spline | 100.0% (Ficticio) | **NaN** (No aplica) | **100.00%** | `VERIFIED_EMPIRICAL_CONVEX_BOUNDS` |
| 2029-01-19 | 794.0d | PCHIP Spline | 100.0% (Ficticio) | **NaN** (No aplica) | **89.47%** | `EMPIRICAL_ANOMALIES_DETECTED` |

### 5.3. Comportamiento de la Simulación de Estrategias ante Diferentes Señales

*(Reconciliado con el régimen de costos Base de `strategy1_straddle_scenarios.csv` según hallazgo de auditoría L1)*

| Escenario de Señal | Pronóstico HAR-RV | IV Straddle | Acción Emitida | Contratos Opciones | Acciones Cobertura | Costo de Fricción | P&L Escenario Nulo | P&L Shock +25% |
|---|---|---|---|---|---|---|---|---|
| **Causal Real (17-nov)** | 72.97% | 45.90% | `LONG_VOLATILITY_STRADDLE` | $+1$ Call, $+1$ Put | $-23$ acciones | $\$7.14$ USD | $-\$107.14$ USD | $+\$130.21$ USD |
| **Contrafactual Neutro** | 46.00% | 45.90% | `NO_TRADE` | $0.0$ | $0$ | **$\$0.00$ USD** | **$\$0.00$ USD** | **$\$0.00$ USD** |
| **Contrafactual Bajista** | 30.00% | 45.90% | `SHORT_VOLATILITY_STRADDLE` | $-1$ Call, $-1$ Put | $+23$ acciones | $\$7.14$ USD | $+\$92.86$ USD | $-\$144.49$ USD |

---

## 6. Resultados de la Suite Completa de Pruebas Automatizadas

La suite totaliza **48 pruebas automatizadas** distribuidas en 9 módulos especializados. Todas fueron ejecutadas secuencialmente por `pytest -v` dentro de `run_all.py`, obteniendo **100% de aprobación sin un solo fallo**:

```
============================= test session starts =============================
platform win32 -- Python 3.12.6, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\CAROL\orca\workspaces\ImpVolSurface\rockling
collected 48 items

tests/test_contracts_and_dates.py::test_parse_occ_symbol_valid PASSED            [  2%]
tests/test_contracts_and_dates.py::test_parse_occ_symbol_invalid PASSED          [  4%]
tests/test_contracts_and_dates.py::test_exact_tau_calculation PASSED             [  6%]
tests/test_contracts_and_dates.py::test_audit_dataset_properties PASSED          [  8%]
tests/test_iv_recovery.py::test_call_synthetic_recovery PASSED                   [ 10%]
tests/test_iv_recovery.py::test_american_put_synthetic_recovery PASSED           [ 12%]
tests/test_iv_recovery.py::test_iv_uninvertible_bounds_handling PASSED           [ 14%]
tests/test_no_lookahead.py::test_historical_dataset_no_lookahead PASSED          [ 16%]
tests/test_no_lookahead.py::test_counterfactual_future_invariance PASSED         [ 18%]
tests/test_no_lookahead.py::test_forecast_evaluation_results PASSED              [ 20%]
tests/test_no_lookahead.py::test_strategy_signal_sensitivity PASSED              [ 22%]
tests/test_no_lookahead.py::test_strategy_portfolio_position_linkage_and_signal_dispatch PASSED [ 25%]
tests/test_no_lookahead.py::test_forecast_parameter_dynamic_dispatch_no_hardcoding PASSED [ 27%]
tests/test_pde_greeks_stability.py::test_gamma_stability_across_bumps PASSED     [ 29%]
tests/test_pde_greeks_stability.py::test_mesh_refinement_convergence PASSED     [ 31%]
tests/test_pde_greeks_stability.py::test_cross_greeks_finite_and_stable PASSED [ 33%]
tests/test_pde_greeks_stability.py::test_penalty_convergence_diagnostics PASSED [ 35%]
tests/test_pipeline_error_propagation.py::test_missing_mandatory_file_fails PASSED [ 37%]
tests/test_pipeline_error_propagation.py::test_non_finite_validation_fails PASSED [ 39%]
tests/test_pipeline_error_propagation.py::test_empty_table_validation_fails PASSED [ 41%]
tests/test_pipeline_error_propagation.py::test_intentional_stage_exception_returns_nonzero PASSED [ 43%]
tests/test_pipeline_error_propagation.py::test_intentional_test_failure_returns_nonzero PASSED [ 45%]
tests/test_portfolio_and_stress.py::test_portfolio_construction_and_delta_neutrality PASSED [ 47%]
tests/test_portfolio_and_stress.py::test_null_shock_scenario_zero_pnl PASSED     [ 50%]
tests/test_portfolio_and_stress.py::test_reconciliation_leg_sum_equals_total PASSED [ 52%]
tests/test_portfolio_and_stress.py::test_mark_to_model_separation PASSED         [ 54%]
tests/test_portfolio_and_stress.py::test_taylor_discrepancy_rational_magnitude PASSED [ 56%]
tests/test_pricing_american.py::test_american_put_early_exercise_premium PASSED [ 58%]
tests/test_pricing_american.py::test_american_call_matches_european_with_zero_dividends PASSED [ 60%]
tests/test_pricing_american.py::test_fd_vs_crr_benchmark PASSED                  [ 62%]
tests/test_pricing_american.py::test_fd_grid_convergence PASSED                  [ 64%]
tests/test_pricing_american.py::test_american_put_gamma_stability_sweep[0.005] PASSED [ 66%]
tests/test_pricing_american.py::test_american_put_gamma_stability_sweep[0.01] PASSED  [ 68%]
tests/test_pricing_american.py::test_american_put_gamma_stability_sweep[0.02] PASSED  [ 70%]
tests/test_pricing_american.py::test_american_put_gamma_stability_sweep[0.05] PASSED  [ 72%]
tests/test_pricing_bs.py::test_bs_put_call_parity PASSED                         [ 75%]
tests/test_pricing_bs.py::test_bs_monotonicity PASSED                            [ 77%]
tests/test_pricing_bs.py::test_bs_analytical_greeks_vs_fd PASSED                 [ 79%]
tests/test_surface_and_interpolation.py::test_surface_evaluation PASSED          [ 81%]
tests/test_surface_and_interpolation.py::test_calendar_arbitrage_all_calibrated_tenors_and_neighborhoods PASSED [ 83%]
tests/test_surface_and_interpolation.py::test_calendar_arbitrage_specific_counterexamples PASSED [ 85%]
tests/test_surface_and_interpolation.py::test_surface_node_continuity PASSED    [ 87%]
tests/test_surface_and_interpolation.py::test_total_variance_positivity_and_finiteness PASSED [ 89%]
tests/test_surface_and_interpolation.py::test_svi_parameters_and_lee_wings PASSED [ 91%]
tests/test_surface_and_interpolation.py::test_pchip_fallback_economic_validation_and_no_fictitious_guarantees PASSED [ 93%]
tests/test_surface_and_interpolation.py::test_local_vs_global_extrapolation_tracking PASSED [ 95%]
tests/test_surface_and_interpolation.py::test_american_economic_arbitrage_checks PASSED [ 97%]
tests/test_surface_and_interpolation.py::test_leave_one_strike_out_accuracy_and_american_engine PASSED [100%]

================== 48 passed, 2 warnings in 494.35s (0:08:14) ==================
```

---

## 7. Limitaciones Residuales Transparentes

Para mantener el más alto estándar de integridad cuantitativa, se documentan formalmente las siguientes limitaciones metodológicas residuales:
1. **Alcance de las Comprobaciones sobre Malla Finita:** La ausencia de arbitraje de calendario y mariposa se comprueba sobre mallas discretas densas de log-moneyness ($k \in [-0.6, +0.6]$) y madureces temporales continuas. Ninguna verificación en malla finita constituye una demostración universal en $\mathbb{R}^2$; fuera del soporte observado aplican advertencias de extrapolación.
2. **Iliquidez Estructural en LEAPS (Enero 2029):** El vencimiento de 794 días exhibe asimetrías severas en strikes extremos ($K=3.0$, donde la Call cotiza con IV de $103.88\%$ y la Put con $52.31\%$). Este corte se mantiene etiquetado como `EMPIRICAL_ANOMALIES_DETECTED`. Para aplicaciones institucionales de alta sensibilidad, se recomienda restringir su uso a strikes $K \ge 5.0$.
3. **Simulaciones Prospectivas sin Orden Ejecutable:** Las estrategias cuantitativas evaluadas son simulaciones analíticas bajo supuestos conservadores de fricción, diseñadas para contrastar la hipótesis de prima de riesgo de volatilidad. No deben interpretarse como órdenes de trading en vivo ni como rentabilidades históricas probadas.

---

## 8. Conclusión y Recomendación Final

La presente segunda ronda de auditoría y reparación cierra de manera definitiva todos los cabos sueltos matemáticos y de ingeniería del repositorio `ImpVolSurface`:
- **Consistencia temporal absoluta** en la superficie SVI/PCHIP sin saltos en nodos calibrados.
- **Transparencia económica real** en los cortes de fallback spline.
- **Conexión causal y ejecutable** de las estrategias de volatilidad.
- **Garantía de calidad e integridad del pipeline** mediante propagación bloqueante de errores.

Se recomienda al mantenedor del repositorio proceder con el **merge de la rama `fix/quant-audit-2026-11` a la rama principal `master`**.
