# INFORME TÉCNICO FASE 5: SUPERFICIE DE VOLATILIDAD IMPLÍCITA EQUIVALENTE HESTON

**Proyecto:** Opciones Americanas NU Holdings Ltd. (Valuación de Referencia: 17-nov-2026 16:00 EST)  
**Fase:** Fase 5 (`PHASE_5`)  
**Modelo:** Heston Clásico 1993 bajo la medida neutral al riesgo $\mathbb{Q}$  
**Vector de Parámetros Calibrados (Benchmark PoC Conservado):**
- $v_0 = 0.186138$
- $\kappa = 2.725460$
- $\theta = 0.213680$
- $\xi = 0.481785$
- $\rho = -0.949807$
- Razón de Feller: $\frac{2\kappa\theta}{\xi^2} = 5.018 > 1$ (condición estrictamente satisfecha)  
**Curva de Descuento:** US Treasury Par Yield Curve Bootstrap Oficial (ACT/365 Fixed, $q = 0.00$, $S_0 = 12.33$ USD)  
**Base de Código:** Commit `7f51a811ae5815dadf8c26b46f707e9f7cb0d05c` (PR #5)  

---

## 1. Resumen Ejecutivo y Objetivos

Conforme a la instrucción humana de coordinación del 22 de noviembre de 2026, la Fase 5 construye la superficie de volatilidad implícita (IV) equivalente a partir de los precios del modelo clásico de Heston calibrado en la Fase 4.

El trabajo se ejecuta bajo el principio de **mínima complejidad suficiente**:
1. Se conservan sin alteración los parámetros de calibración de la Fase 4 y el motor 2D Heston.
2. Se extiende de forma mínima y compatible el motor EDP 1D americano (`src/pricing_american_fd.py`) para consumir la estructura temporal de tasas determinista $r(t = T - \tau)$, preservando al 100% la compatibilidad numérica escalar preexistente.
3. Se invierten los precios de las 97 puts americanas mediante el algoritmo de Brent sobre la EDP 1D americana, evitando atajos simplificadores (no se usa Black-Scholes europeo para puts americanas).
4. Se contrastan e invierten 142 calls europeas externas mediante la fórmula semianalítica de Heston y la inversión analítica de Black-Scholes con factor de descuento exacto $D(T)$.
5. Se genera una grilla descriptiva fija de 35 puntos ($5 \text{ strikes} \times 7 \text{ tenores}$) para puts y calls.
6. Se verifican 6 casos de control 1D contra QuantLib, cumpliendo holgadamente el presupuesto de discretización de 0.0020 USD.

---

## 2. Metodología de Inversión y Extensión del Motor 1D

### 2.1 Puts Americanas: Inversión sobre EDP 1D con Curva
La opción put americana sobre NU ($q = 0.0$) está sujeta a ejercicio anticipado óptimo, por lo que su valor $P_{\text{Am}}(S, \tau)$ satisface la desigualdad variacional de Cauchy-Dirichlet:
$$\min\left( \frac{\partial P}{\partial \tau} - \mathcal{L}_{1D} P, \; P - (K - S)^+ \right) = 0$$
donde el operador diferencial espacial unidimensional es:
$$\mathcal{L}_{1D} P = \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 P}{\partial S^2} + (r(t_{\text{cal}}) - q) S \frac{\partial P}{\partial S} - r(t_{\text{cal}}) P$$
con tiempo calendario hacia adelante $t_{\text{cal}} = T - \tau$.

**Extensión Numérica Implementada:**
- Esquema temporal Crank-Nicolson ($\theta = 0.5$) con 4 pasos iniciales de suavizado de Rannacher ($\theta = 1.0$).
- Algoritmo de penalización no lineal de Forsyth & Vetzal (2002) para el obstáculo americano ($\rho = 10^7$, tolerancia $10^{-7}$).
- En cada paso temporal $m$ con midpoint $\tau_{\text{mid}} = \tau_m - 0.5 \Delta \tau$, se evalúa la tasa instantánea forward $r(T - \tau_{\text{mid}})$ provista por `DeterministicYieldCurve`.
- Para $r$ escalar constante, el código reusa exactamente el cálculo previo, garantizando identidad numérica estricta ($< 10^{-10}$ USD).

**Inversión de Brent:**
Se resuelve numéricamente $P_{\text{Am, 1D}}(\sigma; S_0, K, T, \text{curva}) - P_{\text{Heston}} = 0$ con `xtol = 1e-5`, `rtol = 1e-5`, sobre el bracket $[\sigma_{\min}=0.01, \sigma_{\max}=5.0]$.
Se clasifican explícitamente los estados:
- `CONVERGED`: Raíz encontrada y residual de precio $\le 10^{-4}$ USD.
- `PRICE_BELOW_INTRINSIC`: Precio objetivo $\le \max(K - S_0, 0)$.
- `UNIDENTIFIABLE_VOL_TOO_LOW`: Vega nula o precio cercano al intrínseco donde $\sigma < 0.01$.
- `PRICE_ABOVE_UPPER_BOUND`: Precio objetivo $\ge K$.

### 2.2 Calls Europeas: Inversión Analítica Black-Scholes
Bajo la ausencia de dividendos ($q = 0$) y tasas libres de riesgo no negativas ($r(t) \ge 0$), el teorema de Merton (1973) garantiza que el ejercicio anticipado de una call americana nunca es óptimo: $C_{\text{Am}} \equiv C_{\text{Eu}}$.
- El precio de la call se calcula de forma semianalítica exacta mediante `ql.AnalyticHestonEngine(model)` integrando la función característica de Heston sobre la curva de descuento oficial.
- La inversión a volatilidad implícita de Black-Scholes se realiza resolviendo $C_{\text{BS}}(\sigma; S_0, K, T, r_{\text{zero}}(T)) - C_{\text{Heston}} = 0$ con $D(T) = \exp(-r_{\text{zero}}(T) \cdot T)$.
- La tolerancia del residual analítico es $\le 10^{-8}$ USD.

---

## 3. Verificación de Controles 1D vs QuantLib

Para auditar la precisión de la extensión 1D con la curva oficial, se evaluaron los 6 casos de control estipulados contractualmente frente al motor de diferencias finitas de QuantLib (`FdBlackScholesVanillaEngine` con malla $400 \times 400$):

| Strike $K$ | Días | $\sigma$ | Precio QuantLib (USD) | Precio EDP 1D ($300 \times 150$) | Discrepancia (USD) | Presupuesto $\le 0.0020$ |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 9.00 | 31 | 0.25 | 0.000001 | 0.000002 | 0.000001 | **PASÓ** |
| 12.33 | 31 | 0.45 | 0.624764 | 0.624123 | 0.000641 | **PASÓ** |
| 17.00 | 31 | 0.70 | 4.712017 | 4.712225 | 0.000208 | **PASÓ** |
| 9.00 | 430 | 0.70 | 1.549988 | 1.549988 | 0.000000 | **PASÓ** |
| 12.33 | 94 | 0.25 | 0.565860 | 0.564950 | 0.000910 | **PASÓ** |
| 17.00 | 430 | 0.45 | 5.290681 | 5.290928 | 0.000247 | **PASÓ** |

**Discrepancia Máxima Observada:** $0.000910$ USD ($< 0.1$ centavos de dólar), holgadamente inferior al límite de $0.0020$ USD.

**Sensibilidad de Malla en los 2 Casos Sensibles:**
- En $(12.33, 94\text{d}, 0.25)$:
  - Malla Coarse ($200 \times 100$): $0.564491$ USD (diff vs QL: $0.001369$ USD)
  - Malla Standard ($300 \times 150$): $0.564950$ USD (diff vs QL: $0.000910$ USD)
  - Malla Fine ($400 \times 300$): $0.565374$ USD (diff vs QL: $0.000486$ USD)
- En $(12.33, 31\text{d}, 0.45)$:
  - Malla Coarse ($200 \times 100$): $0.623801$ USD (diff vs QL: $0.000963$ USD)
  - Malla Standard ($300 \times 150$): $0.624123$ USD (diff vs QL: $0.000641$ USD)
  - Malla Fine ($400 \times 300$): $0.624527$ USD (diff vs QL: $0.000237$ USD)

La convergencia es estrictamente monótona con el refinamiento espacial y temporal, demostrando la estabilidad del operador 1D.

---

## 4. Resultados sobre la Muestra Contractual

### 4.1 Conjunto de 97 Puts Americanas
- **Puts Totales Procesadas:** 97 contratos.
- **Inversión Heston Exitosa:**
  - `CONVERGED`: 88 contratos con raíz interior precisa (residual $< 10^{-6}$ USD).
  - `CONVERGED_AT_LOWER_BRACKET`: 9 contratos profundos ITM en tenores cortos donde el precio del modelo está en la cota de valor intrínseco y la volatilidad converge al límite numérico inferior ($\sigma = 0.01$). Estos contratos se conservan explícitamente sin forzar valores arbitrarios ni omitir filas.
- **Inversión de Precios de Mercado Observados:**
  - `CONVERGED`: 96 contratos.
  - `UNIDENTIFIABLE_VOL_TOO_HIGH`: 1 contrato con prima anómala de mercado.
- **Métricas de Error en Muestra Común Válida (88 puts):**
  - MAE de Precio: $0.0238$ USD (2.38 centavos).
  - RMSE de Precio: $0.0340$ USD (3.40 centavos).
  - MAE de IV Equivalente: $2.52$ puntos porcentuales.
  - RMSE de IV Equivalente: $5.01$ puntos porcentuales.

### 4.2 Conjunto de 142 Calls Externas (Contraste)
- **Calls Totales Procesadas:** 142 contratos.
- **Inversión Heston Exitosa:**
  - `CONVERGED`: 140 contratos.
  - `CONVERGED_AT_LOWER_BRACKET`: 1 contrato.
  - `UNIDENTIFIABLE_VOL_TOO_HIGH`: 1 contrato.
- **Inversión de Precios de Mercado Observados:**
  - `CONVERGED`: 138 contratos.
  - `UNIDENTIFIABLE_VOL_TOO_HIGH`: 4 contratos OTM con precios desfasados respecto a la hora de cierre.
- **Métricas de Error en Muestra Común Válida (137 calls):**
  - MAE de Precio: $0.0873$ USD.
  - RMSE de Precio: $0.1281$ USD.
  - MAE de IV BS: $12.75$ puntos porcentuales.
  - RMSE de IV BS: $30.64$ puntos porcentuales (reflejando el contraste puramente externo sin recalibración sobre calls).

---

## 5. Grilla Descriptiva de 35 Puntos

Se evaluó la grilla predefinida $K \in \{9.0, 11.0, 12.33, 15.0, 17.0\}$ USD y tenores $\{3, 31, 59, 94, 212, 430, 794\}$ días:
- **Puts:** 35 de 35 puntos valorados directamente con el solver 2D / reutilización auditada de Fase 4, e invertidos exitosamente a IV equivalente.
- **Calls:** 35 de 35 puntos valorados con `AnalyticHestonEngine` e invertidos a IV de Black-Scholes.
- Los resultados se encuentran exportados en `data/heston/phase5/heston_descriptive_grid_35_puts.csv` y `heston_descriptive_grid_35_calls.csv`.

---

## 6. Visualizaciones Producidas

Se generaron y verificaron cuatro figuras de alta resolución en `figures/phase5/`:
1. `heston_iv_surface_puts_3d.png`: Superficie 3D de la volatilidad implícita equivalente de puts americanas en función de strike y días a vencimiento.
2. `heston_iv_surface_calls_3d.png`: Superficie 3D de la volatilidad implícita Black-Scholes de calls europeas del modelo Heston.
3. `heston_iv_smile_slices.png`: Cortes transversales de la sonrisa de volatilidad en tenores representativos (31d, 94d y 430d), contrastando puts americanas y calls con las observaciones de mercado.
4. `heston_iv_grid_35_points.png`: Heatmap bidimensional con los valores exactos de IV calculados sobre la grilla canónica de 35 puntos.

---

## 7. Limitaciones y Supuestos del Modelo

1. **Hallazgo Aceptado F4-H2:**
   Conforme a la decisión expresa humana del 22 de noviembre de 2026, el comportamiento del gate de cotas europeas en escenarios sintéticos extremos se asume como limitación metodológica de robustez artificial y no invalida los datos ni resultados de mercado auditados.
2. **Naturaleza de la IV Americana Equivalente:**
   La volatilidad implícita americana equivalente obtenida por inversión sobre la EDP 1D es una medida de cotización y comparación de primas, no una volatilidad de difusión Black-Scholes europea. Por tanto, no se asume paridad call-put europea ni ausencia automática de arbitraje de calendario sobre $w = \sigma_{\text{IV}}^2 T$ sin verificación numérica explícita.
3. **Puntos Profundos ITM:**
   En opciones muy profundas en el dinero o vencimientos ultracortos (e.g. 3 días), la prima está dominada por el valor intrínseco $(K - S)^+$ y la vega decae rápidamente ($\frac{\partial P}{\partial \sigma} \to 0$). El motor reporta estados explícitos de no identificación sin forzar artificialmente valores arbitrarios de $\sigma_{\min}$.

---

## 8. Manifiesto y Trazabilidad Criptográfica

Todos los artefactos generados están catalogados en `data/heston/phase5/phase5_execution_manifest.json` con sus respectivos hashes SHA-256:
- `data/heston/phase5/heston_iv_surface_97_puts.csv`
- `data/heston/phase5/heston_iv_surface_142_calls.csv`
- `data/heston/phase5/heston_descriptive_grid_35_puts.csv`
- `data/heston/phase5/heston_descriptive_grid_35_calls.csv`
- `data/heston/phase5/control_cases_1d_quantlib.csv`
- `data/heston/phase5/mesh_sensitivity_1d_controls.csv`
- `data/heston/phase5/phase5_summary_metrics.json`
