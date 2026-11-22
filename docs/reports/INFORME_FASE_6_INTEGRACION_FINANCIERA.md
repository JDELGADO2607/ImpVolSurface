# INFORME TÉCNICO FASE 6: INTEGRACIÓN FINANCIERA, COMPARACIÓN DE MODELOS, RIESGO DE CARTERA Y PRUEBAS DE ESTRÉS

**Proyecto:** Opciones Americanas NU Holdings Ltd. (Valuación de Referencia: 17-nov-2026 16:00 EST)  
**Fase:** Fase 6 (`PHASE_6`) e Integración de Cierre (Fases 7/8)  
**Modelo:** Heston Clásico 1993 bajo la medida neutral al riesgo $\mathbb{Q}$  
**Vector de Parámetros Calibrados (Benchmark PoC Conservado):**
- $v_0 = 0.186138$
- $\kappa = 2.725460$
- $\theta = 0.213680$
- $\xi = 0.481785$
- $\rho = -0.949807$
- Razón de Feller: $\frac{2\kappa\theta}{\xi^2} = 5.018 > 1$ (satisfecho estrictamente)  
**Curva de Descuento:** Curva determinista ex post a partir de tasas par CMT del US Treasury, con instrumentos sintéticos y aproximaciones de construcción; no un bootstrap completo de bonos cotizados (ACT/365 Fixed, $q = 0.00$, $S_0 = 12.33$ USD).

**Referencia de esta corrección documental:** Commit `2a9143ba55f1e17b165fa7132d954227635e6538` (PR #5). Resultados numéricos conservados; revisión humana final pendiente.

---

## 1. Resumen Ejecutivo y Objetivos

Conforme al encargo de Fase 6 y la directiva humana de mínima complejidad suficiente del 22 de noviembre de 2026, la Fase 6 consolida la integración financiera completa del modelo de Heston clásico sobre el libro de derivados de NU Holdings:

La calibración previa minimiza SSE no ponderada sobre **60 puts americanas de entrenamiento**. Las **22 puts de holdout por strike y 15 por vencimiento** no forman parte de esa función objetivo. Las métricas sobre 97 puts combinan entrenamiento y holdouts; las 142 calls son un contraste externo. La revisión humana final del conjunto permanece pendiente.

1. **Comparación Rigurosa de Cuatro Modelos:** Sobre el universo común congelado de 239 contratos (97 puts americanas y 142 calls externas), aislando la Prima por Ejercicio Anticipado (EEP) y el efecto de la sonrisa estocástica frente al benchmark plano del 44.0%.
2. **Cartera Hipotética y Griegas de Heston:** Valuación directa bajo Heston de las 5 patas predefinidas en `src/portfolio.py` (`PORTFOLIO_LEGS`), cálculo coherente de Delta, Gamma, sensibilidad a $\sigma_0 = \sqrt{v_0}$ y Theta diaria, determinación de la posición de cobertura delta-neutral en acciones de NU, y aproximación dinámica de capital/margen.
3. **Pruebas de Estrés Instantáneas:** Revaluación no lineal completa sobre 6 escenarios instantáneos ($\Delta t = 0$), incluyendo la verificación del escenario nulo con P&L numéricamente igual a $0.00$ USD por construcción y el contraste frente a la aproximación de Taylor de segundo orden.
4. **Cierre Defendible de 10 Minutos (Fases 7/8):** Estructuración de un guion de presentación oral de 10 minutos, resumen tabular unificado de métricas y registro de limitaciones metodológicas aceptadas (incluyendo `F4-H2` y la precisión sobre las grillas descriptivas de 35 puntos).

---

## 2. Comparación de Cuatro Modelos sobre Muestra Común

Se contrastaron cuatro columnas de valuación sobre los 239 contratos utilizando la curva determinista común:
- **M1 (Europeo Flat BS):** Fórmula de Black-Scholes con volatilidad ex-ante plana del 44.0% y descuento $D(T)$ de la curva.
- **M2 (Americano Flat 1D):** EDP 1D americana (Crank-Nicolson + penalización) con volatilidad plana del 44.0% y estructura temporal de tasas. Para calls bajo $q=0, r\ge 0$, coincide con M1 por el teorema de Merton (1973).
- **M3 (Europeo Heston):** Valuación semianalítica mediante integración numérica con tolerancia finita en `ql.AnalyticHestonEngine`, consumiendo la curva densa diaria (`curve.to_quantlib_term_structure(dense_daily=True)`).
- **M4 (Americano Heston):** Precios finos auditados del solver 2D para puts (Fase 4); para calls, idéntico a M3 ($C_{\text{Am}} \equiv C_{\text{Eu}}$).

### 2.1 Desempeño y Métricas de Error por Partición

| Segmento | Contratos | M1 (Eu Flat) MAE | M2 (Am Flat) MAE | M3 (Eu Heston) MAE | M4 (Am Heston) MAE | M4 RMSE | EEP Heston Medio |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **All Puts** | 97 | $0.0495$ | $0.0374$ | $0.0466$ | **$0.0238$** | $0.0340$ | $0.0287$ |
| Puts: Train (60) | 60 | $0.0557$ | $0.0383$ | $0.0557$ | **$0.0257$** | $0.0380$ | $0.0376$ |
| Puts: Strike Holdout (22) | 22 | $0.0389$ | $0.0348$ | $0.0290$ | **$0.0211$** | $0.0266$ | $0.0119$ |
| Puts: Tenor Holdout (15) | 15 | $0.0402$ | $0.0376$ | $0.0359$ | **$0.0203$** | $0.0262$ | $0.0178$ |
| **All Calls (Contraste 142)** | 142 | $0.0568$ | $0.0568$ | **$0.0873$** | **$0.0873$** | $0.1281$ | $0.0000$ |
| **Universo Común Total** | **239** | $0.0538$ | $0.0489$ | $0.0708$ | **$0.0615$** | $0.1011$ | $0.0117$ |

*Notas:*
1. En las 97 puts evaluadas (60 de entrenamiento y 37 holdout), el modelo Heston (M4) logra un MAE de **$0.0238$ USD** frente a **$0.0374$ USD** del modelo americano de volatilidad plana (M2), una **reducción del error del 36.21%**. Esta métrica conjunta no es exclusivamente in-sample ni exclusivamente fuera de muestra.
2. En las 142 calls externas out-of-sample (no utilizadas en calibración), Heston obtiene un MAE de **$0.0873$ USD** frente a **$0.0568$ USD** del benchmark plano ex-ante, resultando en un MAE combinado sobre los 239 contratos de **$0.0615$ USD** para Heston vs **$0.0489$ USD** para el flat americano. No se afirma superioridad global del modelo sobre todo tipo de contrato, reportándose ambos comportamientos con total transparencia académica.
3. La Prima por Ejercicio Anticipado ($\text{EEP} = P_{\text{Am}} - P_{\text{Eu}}$) promedia $0.0287$ USD ($2.87$ centavos) en las 97 puts, con un máximo de $0.5673$ USD en puts profundas ITM de tenores largos, confirmando la relevancia económica de la valoración americana. Para calls bajo $q=0, r\ge 0$, la EEP es idénticamente cero por el teorema de Merton (1973).

---

## 3. Cartera Hipotética de 5 Patas y Griegas Coherentes

Se conservaron sin modificación las 5 patas contractuales definidas en `PORTFOLIO_LEGS` (`src/portfolio.py`), ubicadas en los núcleos líquidos de 31 y 59 días, con valores y griegas extraídos directamente del archivo versionado `portfolio_greeks_and_valuation.csv`:

| Pata | Símbolo | Tipo | Strike | Días | Cantidad | Prima Obs. | Prima Heston | Delta Unit. | Gamma Unit. | Sens. $\sigma_0$ (1pp) | Theta Diaria |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| 1 | `NU261218C00012000` | Call | 12.0 | 31 | +5 | $0.8600$ | $0.8227$ | $+0.6452$ | $+0.2316$ | $+0.0119$ | $-0.0106$ |
| 2 | `NU261218C00014000` | Call | 14.0 | 31 | -5 | $0.1500$ | $0.1128$ | **$+0.1778$** | $+0.1963$ | $+0.0083$ | $-0.0059$ |
| 3 | `NU261218P00012000` | Put | 12.0 | 31 | +3 | $0.4700$ | $0.4524$ | $-0.3566$ | $+0.2337$ | $+0.0119$ | $-0.0093$ |
| 4 | `NU270115C00013000` | Call | 13.0 | 59 | +4 | $0.6000$ | $0.5919$ | $+0.4629$ | $+0.1947$ | $+0.0158$ | $-0.0076$ |
| 5 | `NU270115P00011000` | Put | 11.0 | 59 | -4 | $0.3000$ | $0.3284$ | $-0.2034$ | $+0.1185$ | $+0.0114$ | $-0.0055$ |
| **Hedge** | `NU_STOCK` | Stock | — | — | **-393** | $12.3300$ | $12.3300$ | $+1.0000$ | $0.0000$ | $0.0000$ | $0.0000$ |

*Nota:* Para la Pata 2 (Call K=14), la delta unitaria de la call es positiva ($+0.177780$); la cantidad corta ($-5$) es la que genera la delta de posición negativa ($-88.89$ acciones).

### 3.1 Agregación de Riesgos y Cobertura Delta-Neutral
- **Valor de Mercado de Opciones:** $+616.00$ USD.
- **Valor Heston de Opciones:** $+596.10$ USD (Diferencia Mark-to-Model: $-19.90$ USD).
- **Delta Neta de Opciones:** $+393.22$ acciones equivalentes.
- **Cobertura en Acciones:** Corto **$-393$ acciones** de NU Holdings Ltd. a $12.33$ USD (Valor: $-4,845.69$ USD).
- **Delta Residual de Cartera:** $+0.22$ acciones (delta-neutralidad aproximada por el redondeo discreto a enteros, $|\Delta_{\text{res}}| < 1.0$).
- **Gamma Neta de Cartera:** $+118.24$ acciones/USD (posición neta convexamente larga).
- **Sensibilidad a $\sigma_0$ (por 1 pp de vol inicial):** $+7.18$ USD / pp.  
  *Nota metodológica:* Representa la variación en valor por un punto porcentual en $\sigma_0 = \sqrt{v_0}$ del proceso de difusión de varianza de Heston; no es una vega de Black-Scholes sobre una IV estática.
- **Theta Diaria de Cartera:** $-6.00$ USD / día calendario (decaimiento temporal evaluado bajo la convención de acortamiento de vencimiento con curva congelada).
- **Aproximación Dinámica de Capital / Margen Inicial:** $5,613.88$ USD (estimación académica simplificada sobre primas del modelo y posiciones cortas; no es un cálculo regulatorio FINRA/OCC).

### 3.2 Verificación de Estabilidad de Derivadas ($h$ vs $h/2$)
Se evaluó la sensibilidad del paso de diferencias finitas centrales ($h = 0.01 \cdot S_0 = 0.1233$ USD frente a $h/2 = 0.06165$ USD) en las patas representativas 1 (Call 31d) y 3 (Put 31d), con valores tomados exactamente de `portfolio_convergence_checks.csv`:
- Pata 1 (Call 31d): $\Delta(h) = 0.645180$, $\Delta(h/2) = 0.645355$ ($\text{diff} = 0.000175$); $\Gamma(h) = 0.231603$, $\Gamma(h/2) = 0.231639$ ($\text{diff} = 0.000036$).
- Pata 3 (Put 31d): $\Delta(h) = -0.356629$, $\Delta(h/2) = -0.356449$ ($\text{diff} = 0.000180$); $\Gamma(h) = 0.233692$, $\Gamma(h/2) = 0.233726$ ($\text{diff} = 0.000034$).  
Todas las discrepancias entre $h$ y $h/2$ son inferiores a $0.0002$, certificando la estabilidad de las derivadas.

---

## 4. Pruebas de Estrés en Seis Escenarios Instantáneos

Se evaluó la cartera delta-hedged revaluando numéricamente cada contrato bajo el motor Heston respectivo ($\Delta t = 0$, parámetros $\kappa, \theta, \xi, \rho$ congelados):

| ID Escenario | Descripción | Shock $S$ | Shock $\sigma_0$ | P&L Opciones Reval. | P&L Hedge Acciones | P&L Total Hedged | P&L Total Taylor 2º | Divergencia Taylor |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **S0** | Baseline Null Shock | $0.0\%$ | $0.0$ pp | **$0.00$** | **$0.00$** | **$0.00$** | **$0.00$** | **$0.00$** |
| **S1** | Spot Down -5% | $-5.0\%$ | $0.0$ pp | $-216.03$ | $+242.28$ | **$+26.26$** | $+22.33$ | $+3.92$ |
| **S2** | Spot Up +5% | $+5.0\%$ | $0.0$ pp | $+260.82$ | $-242.28$ | **$+18.54$** | $+22.61$ | $-4.07$ |
| **S3** | Vol Spike (+5 pp) | $0.0\%$ | $+5.0$ pp | $+34.80$ | $0.00$ | **$+34.80$** | $+35.89$ | $-1.09$ |
| **S4** | Severe Crisis (-20% / +12pp) | $-20.0\%$ | $+12.0$ pp | $-476.93$ | $+969.14$ | **$+492.21$** | $+445.11$ | **$+47.10$** |
| **S5** | Bullish Rally (+15% / -8pp) | $+15.0\%$ | $-8.0$ pp | $+824.03$ | $-726.85$ | **$+97.18$** | $+145.21$ | **$-48.03$** |

### 4.1 Análisis Financiero del Estrés
1. **Comportamiento Delta-Neutral:** En los shocks moderados de spot ($\pm 5\%$, S1 y S2), la cobertura reduce la exposición lineal. La gamma positiva local es consistente con P&L positivos de $+26.26$ y $+18.54$ USD, respectivamente; la revaloración completa no es simétrica.
2. **Residuo de Aproximación de Taylor:** En los shocks de spot de $\pm 5\%$, la diferencia entre revaloración y Taylor es menor a $4.1$ USD. En S4 ($-20\%$ de spot y $+12$ pp de $\sigma_0$), la revaloración completa da $+492.21$ USD y Taylor $+445.11$ USD: el residuo es **$+47.10$ USD**. Taylor incluye segundo orden en spot y primer orden en $\sigma_0$; omite términos cruzados, curvatura en volatilidad y órdenes superiores. El residuo no puede atribuirse exclusivamente a convexidad ni interpretarse como una ganancia independiente.
3. **Escenario S5 (Rally con Vol Crush):** El P&L revalorado es $+97.18$ USD frente a $+145.21$ USD de Taylor. El residuo de **$-48.03$ USD** corresponde a la aproximación conjunta de los shocks; no permite aislar una contribución exclusiva de vega o convexidad.

---

## 5. Cierre Defendible de 10 Minutos (Fases 7/8)

### 5.1 Guion de Exposición Oral (10 Minutos)

- **Minuto 0:00 – 1:30 | Introducción y Contexto Empírico:**
  - Presentar a NU Holdings Ltd. como subyacente de alta liquidez en NYSE ($S_0 = 12.33$ USD al 17-nov-2026).
  - Justificar la necesidad de migrar de la parametrización ad-hoc de SVI a un modelo estructural estocástico clásico bajo $\mathbb{Q}$ (Heston 1993).
- **Minuto 1:30 – 3:30 | Calibración y Condición de Feller:**
  - Explicar la función objetivo **SSE no ponderada sobre 60 puts americanas de entrenamiento**, $\sum_{i\in\mathrm{train}}(P_i^{\mathrm{Am,Heston}}-P_i^{\mathrm{obs}})^2$. Las otras 37 puts se reservan: 22 para holdout por strike y 15 por vencimiento. La evaluación abarca 97 puts, pero no todas se usan para calibrar. Se utiliza una curva determinista CMT ex post con instrumentos sintéticos y aproximaciones de bootstrap, sin demostrar disponibilidad exacta a las 16:00.
  - Mostrar los parámetros seleccionados, sin afirmar optimalidad global: $v_0 = 0.1861$, $\kappa = 2.7255$, $\theta = 0.2137$, $\xi = 0.4818$, $\rho = -0.9498$.
  - Resaltar la satisfacción estricta de la condición de Feller ($2\kappa\theta/\xi^2 = 5.018 > 1$), que garantiza que la varianza instantánea nunca toca cero. Recordar que el pricer semianalítico de QuantLib opera bajo integración numérica con tolerancia finita y no aritmética exacta.
- **Minuto 3:30 – 5:30 | Superficie de Volatilidad Implícita Equivalente:**
  - Detallar la extensión 1D con la curva determinista $r(t = T - \tau)$ y los 6 controles contra QuantLib (discrepancia $< 0.001$ USD).
  - Aclarar la naturaleza de la IV americana equivalente frente a Black-Scholes.
  - *Precisión documental:* En cada grilla descriptiva de 35 puntos, 29 puts y 33 calls exhiben inversión interior convergente (`CONVERGED`); las otras filas conservan estados de frontera o no identificación, incluido un `PRICE_BELOW_INTRINSIC` en puts.
- **Minuto 5:30 – 7:30 | Comparación de Modelos y Cartera Delta-Hedged:**
  - Contrastar los 4 modelos sobre 239 contratos: Heston reduce el MAE de $3.74$ centavos a $2.38$ centavos en puts americanas (mejora del $36.21\%$), mientras que en calls externas no calibradas el modelo plano se mantiene en $5.68$¢ frente a $8.73$¢ de Heston (combinado $4.89$¢ vs $6.15$¢).
  - La prima de ejercicio anticipado en puts promedia $2.87$ centavos (máximo $56.7$ centavos en puts ITM).
  - Mostrar la estructura de 5 patas y la posición de cobertura: corto 393 acciones para neutralizar una delta de $+393.22$ acciones (delta residual $+0.22$ por redondeo entero), con gamma positiva ($+118.24$).
  - Distinguir esta cartera de cinco patas, integrada con Heston, de las estrategias históricas straddle y calendar spread, que no fueron migradas a Heston ni constituyen un backtest de rentabilidad histórica.
- **Minuto 7:30 – 9:00 | Pruebas de Estrés y Aproximación de Taylor:**
  - Evidenciar la robustez del escenario nulo ($PnL = 0.00$ USD exacto).
  - Explicar el shock de crisis ($-20\%$ / $+12$ pp): revaloración completa de $+492.21$ USD frente a $+445.11$ USD de Taylor, con **$47.10$ USD de residuo de aproximación**, sin atribuirlo exclusivamente a convexidad. Taylor ya incorpora gamma local, pero omite términos cruzados, volga y órdenes superiores. Recordar que estos PnL son instantáneos e hipotéticos, sin modelar financiación, fricciones ni probabilidades históricas.
- **Minuto 9:00 – 10:00 | Limitaciones Aceptadas y Conclusiones:**
  - Resumir las limitaciones aceptadas: asincronía de precios, identificación paramétrica, precisión de IV en 3d, curva ex post y `F4-H2` abierto en escenarios sintéticos extremos.
  - Concluir que el modelo es parsimonioso, matemáticamente riguroso y defendible ante un panel académico y de riesgo.

### 5.2 Tabla Sinóptica Final de Resultados

| Métrica Global | Valor Obtenido | Estado / Tolerancia |
| :--- | :---: | :---: |
| Parámetros Calibrados Heston | $(0.1861, 2.7255, 0.2137, 0.4818, -0.9498)$ | Aprobado (PoC Régimen A) |
| Razón de Feller ($2\kappa\theta/\xi^2$) | $5.018$ | Cumple ($> 1$) |
| MAE Puts Americanas Heston (97 puts) | **$0.0238$ USD** ($2.38$ ¢) | Reducción 36.21% vs Flat Am ($0.0374$) |
| RMSE Puts Americanas Heston (97 puts) | **$0.0340$ USD** ($3.40$ ¢) | Evaluación total: 60 train + 37 holdout |
| MAE Calls Externas Heston (142 calls) | **$0.0873$ USD** ($8.73$ ¢) | Out-of-Sample (vs $0.0568$ Flat) |
| MAE Combinado (239 contratos) | **$0.0615$ USD** ($6.15$ ¢) | vs $0.0489$ USD Flat Am |
| Discrepancia Máx. 1D vs QuantLib (6 casos) | **$0.000910$ USD** | Cumple ($\le 0.0020$ USD) |
| P&L Escenario Estrés Nulo (S0) | **$0.000000$ USD** | Exacto por construcción |
| Delta Residual Cartera (Stock + Opciones) | **$+0.22$ acciones** | Neutral aproximado ($|\Delta| < 1.0$) |
| Capital Inicial Aproximado (Académico) | **$5,613.88$ USD** | Estimación sobre primas Heston |
| Pruebas Automatizadas de Regresión | **100 de 100 aprobadas (100%)** | PASS Total (Fases 0 a 6) |

---

## 6. Limitaciones Formales y Supuestos Académicos

1. **Limitación F4-H2 Aceptada:**
   Conforme a la instrucción humana de coordinación del 22 de noviembre de 2026, el comportamiento de las cotas europeas sobre escenarios sintéticos extremos se conserva como limitación de robustez artificial y no compromete los datos ni conclusiones financieras de los contratos reales de NU.
2. **No Recalibración en Estrés y Naturaleza Instantánea:**
   Los escenarios de estrés perturban el spot $S$ y la volatilidad instantánea $\sigma_0 = \sqrt{v_0}$ manteniendo constantes los parámetros estructurales $(\kappa, \theta, \xi, \rho)$. Los P&L resultantes son instantáneos e hipotéticos ($\Delta t = 0$), sin modelar el paso del tiempo, costes de financiación, fricciones ni probabilidades históricas.
3. **Aproximación de Margen y Theta:**
   El margen de capital inicial reportado ($5,613.88$ USD) es una estimación académica basada en primas del modelo Heston y regla de margen simplificada, no un cálculo regulatorio FINRA/OCC ni basado en primas observadas de mercado. La theta diaria asume acortamiento de vencimiento con curva congelada.
4. **Delta-Neutralidad y Expansión de Taylor:**
   La delta-neutralidad es aproximada ($+0.22$ acciones de residuo) debido al redondeo entero de las acciones de cobertura ($-393$ acciones). La aproximación de Taylor incluye términos de segundo orden en spot $S$ y primer orden en $\sigma_0$, sin incluir términos cruzados de vanna ni volga completos.
5. **Grillas Descriptivas de 35 Puntos y Tenor Ultracorto:**
   En cada grilla de 35 puntos de Fase 5, 29 puts y 33 calls tienen IV interior identificada. En puts quedan 5 estados `CONVERGED_AT_LOWER_BRACKET` y 1 `PRICE_BELOW_INTRINSIC`; en calls, 2 `CONVERGED_AT_LOWER_BRACKET`. No se cuentan como raíces interiores. Se mantiene la limitación de precisión en la put de 3 días (`NU261120P00012500`).
6. **Asincronía, Identificación Paramétrica y Curva Ex Post:**
   Las últimas transacciones de opciones no forman una cadena sincronizada y ejecutable. Una sola sección transversal no garantiza identificación única de los cinco parámetros; $\rho$ queda próximo al límite de búsqueda. La curva usa CMT del día de valoración y aproximaciones sobre instrumentos sintéticos, sin demostrar disponibilidad exacta a las 16:00. Los parámetros son neutrales al riesgo, no estimaciones de la dinámica física.
7. **Alcance de las Estrategias:**
   El estrés Heston de esta fase corresponde a la cartera hipotética de cinco patas. Las estrategias históricas straddle y calendar spread se conservan en sus módulos previos, sin integración equivalente con Heston ni validación de rentabilidad histórica.

---

## 7. Manifiesto y Trazabilidad Criptográfica

Todos los artefactos de la Fase 6 están catalogados en `data/heston/phase6/phase6_execution_manifest.json` con sus respectivos hashes SHA-256:
- `data/heston/phase6/models_comparison_detailed.csv` (239 filas)
- `data/heston/phase6/models_comparison_summary.csv` (6 filas)
- `data/heston/phase6/portfolio_greeks_and_valuation.csv` (6 filas)
- `data/heston/phase6/portfolio_convergence_checks.csv` (2 filas)
- `data/heston/phase6/portfolio_stress_scenarios.csv` (6 filas)
- `data/heston/phase6/portfolio_stress_leg_detail.csv` (30 filas)
- `data/heston/phase6/phase6_summary_metrics.json`
- Figuras: `figures/phase6/models_comparison_errors_by_partition.png`, `figures/phase6/early_exercise_premium_profile.png`, `figures/phase6/portfolio_stress_pnl_profile.png`, `figures/phase6/stress_taylor_vs_revaluation.png`.
