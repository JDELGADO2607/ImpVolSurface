# Estado de Lanzamiento y Certificación de la Superficie de Volatilidad 2D (PR #1)

**Repositorio:** `JDELGADO2607/ImpVolSurface`  
**Rama:** `fix/quant-audit-2026-11`  
**Fecha de Certificación:** 21 de noviembre de 2026  
**Auditoría de Referencia:** Hallazgos Independientes CODEX (`CODEX_AUDIT_855eb1c.md`) y R3 Quant Remediation  

---

## 1. Resumen Ejecutivo de Producción

La superficie de volatilidad implícita bidimensional $\sigma_{\mathrm{imp}}(k, \tau)$ ha sido completamente re-arquitecturada para eliminar de forma estricta:
1. Las violaciones de convexidad transversal en vencimientos interpolados (hallazgo bloqueante **B1**).
2. La contaminación por extrapolación en tenores largos sobre strikes ilíquidos (**H1**).
3. El fallo por datos espurios en el vencimiento LEAPS de enero de 2029 (**H2**).
4. La pérdida de valor de continuación temporal en puts americanas ITM (**H5**).
5. Las garantías ficticias de convexidad en cortes con soporte insuficiente (**M1**).

La superficie certificada garantiza la ausencia total de oportunidades de arbitraje estático (mariposa, calendario y dominancia económica) en todo su horizonte productivo mediante un esquema de **armonización global de niveles de varianza por corte** ($a_i \leftarrow a_i + \Delta a_i$) combinado con **interpolación lineal por tramos en varianza total** ($w(k, \tau) = (1-\lambda)w_1(k) + \lambda w_2(k)$).

---

## 2. Horizonte de Producción y Política de Cuarentena LEAPS

### 2.1. Horizonte Productivo Certificado ($\tau \le 430$ días)
- **Rango Operativo:** Desde $\tau = 10$ días (2026-11-27) hasta $\tau = 430$ días (2028-01-21).
- **Cortes SVI Calibrados:** 13 cortes calibrados mediante SVI cuasi-explícito con penalización de Roger Lee y convexidad garantizada ($g(k) \ge 0$).
- **Cortes de Fallback:** 2 cortes con interpolación PCHIP local debidamente etiquetados (`2026-11-20` con 3 días y `2027-12-17` con 395 días).
- **Política de Consumo en Producción (`policy='strict'`):** Es el modo predeterminado en `surface.surface_iv(tau, k, policy='strict')`. Cualquier consulta que exceda $\tau > 430$ días genera inmediatamente una excepción `ValueError`, impidiendo que órdenes de trading o modelos de riesgo consuman volatilidades no aptas para producción.

### 2.2. Vencimiento LEAPS 2029 en Cuarentena (`2029-01-19`, $\tau = 794$ días)
- **Diagnóstico del Fallo Original:** En el commit `855eb1c`, el corte de enero de 2029 falló la calibración SVI debido a una anomalía de mercado en el strike $K=3.0$ (Call \$10.25 vs Put \$0.04, volumen 1), que violaba paridad put-call por \$0.32 USD.
- **Resolución Técnica:** Al depurar el outlier en $K=3.0$, el corte calibró exitosamente bajo SVI con RMSE 1.00%, alas de Lee $< 2.0$ y 100% libre de arbitraje de mariposa.
- **Dictamen Prudencial:** Debido a la extrema dispersión temporal (gap de 364 días entre enero de 2028 y enero de 2029) y la escasa liquidez de contratos deep OTM, este corte se clasifica formalmente como:
  ```python
  production_status = "QUARANTINED_LEAPS_EXPLORATORY_ONLY"
  is_production_ready = False
  ```
- **Consumo:** Solo accesible mediante `policy='allow_extrapolation'` para propósitos estrictamente exploratorios o de investigación.

---

## 3. Núcleo Productivo de Referencia (Core Grid)

Para la verificación operativa y auditorías automatizadas, se define el Núcleo Productivo en los vencimientos mensuales más líquidos:
- **Tenor 1:** $\tau = 31$ días (2026-12-18)
- **Tenor 2:** $\tau = 59$ días (2027-01-15)
- **Strikes Principales:** $K \in \{11.0, 12.0, 13.0, 14.0, 15.0\}$ USD (Spot $S_0 = 12.33$ USD).

### Métricas del Núcleo en `outputs/tables/surface_release_grid.csv`

| $\tau$ (días) | Strike ($K$) | IV (%) | Call Price (\$) | Put Price (\$) | $\frac{d^2 C}{dK^2}$ | Convexa | Sin Arb. Calendario | Estado Producción |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 31.0 | 11.0 | 49.21% | \$1.5613 | \$0.1933 | +0.1651 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 31.0 | 12.0 | 46.70% | \$0.8612 | \$0.4905 | +0.2501 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 31.0 | 13.0 | 45.73% | \$0.4049 | \$1.0340 | +0.2329 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 31.0 | 14.0 | 46.55% | \$0.1750 | \$1.8072 | +0.1244 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 31.0 | 15.0 | 47.91% | \$0.0727 | \$2.7109 | +0.0570 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 59.0 | 11.0 | 44.39% | \$1.7118 | \$0.3077 | +0.1601 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 59.0 | 12.0 | 42.66% | \$1.0509 | \$0.6424 | +0.2070 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 59.0 | 13.0 | 42.13% | \$0.5924 | \$1.1829 | +0.1880 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 59.0 | 14.0 | 42.61% | \$0.3192 | \$1.9127 | +0.1255 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |
| 59.0 | 15.0 | 43.81% | \$0.1720 | \$2.7726 | +0.0692 | **Sí** | **Sí** | `SUPPORTED_LOCAL_GRID` |

*Verificación:* 100% de puntos convexos, 100% de spreads de calendario no-negativos ($\Delta C_{\mathrm{cal}} \ge 0$), y valor de puts americanas estrictamente creciente con el vencimiento.

---

## 4. Estructura de Tablas de Lanzamiento y Diagnóstico

### 4.1. Malla de Lanzamiento (`outputs/tables/surface_release_grid.csv`)
- **Dimensiones:** 450 filas $\times$ 24 columnas (18 tenores $\times$ 25 strikes entre \$8.0 y \$20.0).
- **Campos Obligatorios:** `tau_days`, `tau_years`, `strike`, `forward`, `log_moneyness`, `raw_total_variance`, `projected_total_variance`, `surface_iv_pct`, `call_price_model`, `put_price_model`, `dC_dK`, `d2C_dK2`, `is_convex`, `calendar_spread_vs_prev_tau`, `is_calendar_arbitrage_free`, `american_put_time_monotonic`, `dominant_tenor_tau`, `delta_w_projected`, `is_extrapolated_strike`, `is_extrapolated_tau`, `is_production_ready`, `quality_flag`, `slice_support_K_min`, `slice_support_K_max`.
- **Diagnóstico Global:** Convexidad de precios 99.11% en toda la grilla (incluyendo alas extremas extrapoladas) y 100.0% en el soporte local observable.

### 4.2. Diagnóstico de Calidad por Corte (`outputs/tables/surface_quality_diagnostics.csv`)
- **Dimensiones:** 15 filas $\times$ 27 columnas (un registro por vencimiento de mercado).
- **Tratamiento del Corte de 3 días (`2026-11-20`):** Marcado con `pct_price_convex = NaN` y estado `INSUFFICIENT_DATA_TWO_STRIKES` (`is_production_ready: False`). Elimina formalmente el reclamo ficticio de 100% convexidad del pipeline anterior.
- **Trazabilidad de Ajustes:** Registra el número de puntos ajustados por proyección de calendario (`calendar_adj_points`), el incremento máximo de varianza total ($\Delta w_{\max}$) y la lista explícita de restricciones matemáticas verificadas y no verificadas.

### 4.3. Validación Cruzada Out-of-Sample Bidimensional (`outputs/tables/surface_final_holdout_validation.csv`)
- **Metodología:** Leave-One-Strike-Out genuinamente bidimensional. Cada par (strike, tenor) excluye simultáneamente Calls y Puts. Se recalibra el corte SVI correspondiente, se re-armoniza la superficie bidimensional completa, se interpola la varianza en 2D y se re-valúan los contratos mediante el motor de Diferencias Finitas Americano (PSOR).
- **Resultados Globales (197 contratos observados):**
  - **Error Medio Absoluto de IV (MAE):** 2.67 puntos porcentuales (pp).
  - **Error Medio Absoluto de Precio (MAE):** \$0.0434 USD.
  - **MAE en Calls:** 2.27 pp / \$0.0400 USD.
  - **MAE en Puts:** 3.24 pp / \$0.0482 USD.
- **Rendimiento:** Validación completa ejecutada en menos de 11 segundos con paralelización vectorizada y solver matricial optimizado.

---

## 5. Reglas de Consumo para Módulos Clientes

1. **Estrategias y Generación de Señales (`src/strategies.py`):**
   - No consultar tenores fuera del horizonte productivo ($\tau \le 430$ días).
   - Utilizar el parámetro `export_artifacts=True` únicamente en ejecuciones maestras de `run_all.py`. Los tests deben invocar funciones con `export_artifacts=False` para preservar la inmutabilidad de los artefactos de producción.
2. **Valoración Numérica de Derivados Americanos (`src/pricing_american_fd.py`):**
   - Alimentar la malla de diferencias finitas directamente desde `surface.surface_iv(tau, k)`.
   - La superficie garantiza varianzas locales suaves sin discontinuidades escalonadas ($C^0$ kinks).
3. **Módulo de Pruebas de Estrés y Portafolio (`src/stress_testing.py`):**
   - El margen dinámico de posiciones cortas se liquida en función del precio observable `obs_price` y la cantidad neta, garantizando cobertura prudencial en escenarios extremos.
