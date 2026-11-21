# Registro Vivo de Decisiones Metodológicas y Limitaciones del Proyecto

Este documento registra formalmente cada decisión de diseño cuantitativo, financiero y computacional adoptada a lo largo del proyecto, contrastándola con las alternativas evaluadas, los motivos técnicos de la elección, la evidencia cuantitativa obtenida y las limitaciones residuales.

---

## 1. Registro Sistemático de Decisiones

### DEC-001: Selección del Estado de Mercado Base y Fecha de Valoración
* **Decisión:** Fijar la fecha y hora de referencia para el caso base en el **17 de noviembre de 2026 a las 16:00 EST (America/New_York)**, con un precio spot de cierre de **$S_0 = 12.33$ USD**.
* **Alternativas evaluadas:**
  1. Utilizar la fecha y hora de descarga del archivo Excel (18 de noviembre de 2026, 09:52 COT / 09:52 EST).
  2. Ajustar el spot a cada transacción individual según la marca de tiempo de `lastTradeDate`.
* **Motivo de la elección:** La inspección forense de los 575 contratos demostró que **cero contratos transaron el 18 de noviembre**. Los 291 contratos más líquidos transaron durante la sesión del 17 de noviembre, culminando exactamente a las 15:59:55 EST. Asignar como fecha de valoración el 18 de noviembre cuando los precios provienen del 17 de noviembre introduciría una asincronía artificial de casi 1 día entero que distorsionaría severamente las madureces cortas (por ejemplo, el vencimiento del 20 de noviembre pasaría de 3 días a 2 días, un error de tiempo del 33%).
* **Evidencia:** Registro histórico de Yahoo Finance y NYSE confirma que NU cerró el 17-nov en $12.33 USD (High: 12.83, Low: 12.24, Open: 12.73). El 18-nov abrió en 12.33 y cayó a 12.08.
* **Limitaciones:** Los 284 contratos con última transacción anterior al 17 de noviembre arrastran un desfase temporal respecto a $S_0 = 12.33$. Dichos contratos deben ser identificados y clasificados en niveles de menor confianza (Tiers 3 y 4).

### DEC-002: Descarte del Filtro `bid > 0` y Selección de la Fuente de Precio de Mercado
* **Decisión:** Utilizar como precio objetivo observado $P_{\text{obs}}$ la columna `lastPrice` del 17 de noviembre, sujeta a filtros rigurosos de cotas económicas de no arbitraje y valor tiempo mínimo ($TV \ge 0.01$). Descartar el filtro ingenuo `bid > 0`.
* **Alternativas evaluadas:**
  1. Exigir `bid > 0` y usar `midPrice = (bid + ask) / 2`.
  2. Usar las volatilidades nativas de Yahoo Finance (`impliedVolatility`).
  3. Calibrar directamente contra Bloomberg `IV Mid`.
* **Motivo de la elección:** En el archivo, 538 de los 575 contratos (93.57%) presentan `bid = 0` y `ask = 0` debido a que Yahoo Finance resetea las cotizaciones bilaterales tras el cierre. Exigir `bid > 0` destruiría el 94% de la muestra y dejaría únicamente 32 contratos con cotizaciones obsoletas de hace meses. Por su parte, la `impliedVolatility` de Yahoo presenta valores espurios de $10^{11}$ y patrones diádicos, mientras que calibrar contra Bloomberg violaría la instrucción central de que nuestra superficie provenga exclusivamente de nuestro propio motor numérico.
* **Evidencia:** Análisis forense en `outputs/data_diagnostics/dump_Hoja1.csv`.
* **Limitaciones:** `lastPrice` incorpora el rebote de la última transacción entre el bid y el ask (bid-ask bounce). Por ende, se exige un condicionamiento numérico $\kappa = 0.01 / \text{Vega}$ para asegurar que un error de un centavo no distorsione la volatilidad implícita en más de 3 puntos porcentuales.

### DEC-003: Recálculo Exacto de la Madurez Temporal $\tau$
* **Decisión:** Calcular la madurez en años $\tau$ bajo la convención **Act/365F continuo**, midiendo el tiempo exacto en días calendario desde el cierre del 17-nov-2026 (16:00 EST) hasta las 16:00 EST de la fecha de vencimiento contractual.
* **Alternativas evaluadas:**
  1. Conservar la columna `yearsToExpiry` del Excel.
  2. Dividir por 360 o contar días hábiles (Bus/252).
* **Motivo de la elección:** La columna `yearsToExpiry` del Excel sufre dos defectos críticos: 77 filas están corruptas por escala de localización ($10^{16}$) y las restantes sufrieron un truncamiento a días enteros a medianoche ($\lfloor T - t \rfloor / 365.25$). Esto reducía el plazo del primer vencimiento de 3 días a 1 día, introduciendo un sesgo de subestimación del -55.7% en $\tau$ y duplicando artificialmente la volatilidad implícita. En derivados sobre acciones de EE.UU., el estándar contractual del OCC descuenta el tiempo continuo calendario (Act/365).
* **Evidencia:** Comparación directa entre $\tau_{\text{recalculado}}$ y `yearsToExpiry`.

### DEC-004: Arquitectura de Valoración Diferenciada (Calls vs Puts sin Dividendos)
* **Decisión:** Valorar opciones Call americanas mediante la fórmula analítica cerrada de Black-Scholes para opciones europeas ($q = 0, r \ge 0$). Valorar opciones Put americanas mediante Diferencias Finitas (Crank-Nicolson con suavizado de Rannacher y método de penalización).
* **Alternativas evaluadas:**
  1. Resolver la EDP de diferencias finitas tanto para Calls como para Puts.
  2. Utilizar el árbol de Cox-Ross-Rubinstein (CRR) para todas las opciones.
* **Motivo de la elección:** Es un teorema fundamental de no arbitraje (Merton, 1973) que para una opción Call americana sobre una acción que no paga dividendos ($q = 0$) y con tasas de interés no negativas ($r \ge 0$), el ejercicio anticipado nunca es óptimo antes del vencimiento, de modo que $C_{\text{American}}(S, K, \tau) \equiv C_{\text{European}}(S, K, \tau)$. La solución analítica de Black-Scholes es exacta, libre de error de discretización y computacionalmente instantánea ($1000\times$ más rápida). Por el contrario, en las Puts americanas el ejercicio anticipado sí puede ser óptimo para cobrar el strike $K$ y generar intereses, requiriendo resolver la frontera libre mediante Crank-Nicolson + Penalización. CRR se mantiene como validador numérico de convergencia independiente.
* **Evidencia:** Demostración matemática detallada en el Manual Matemático y pruebas unitarias de convergencia.

### DEC-005: Algoritmo de Inversión de Volatilidad Implícita (Brent vs Newton)
* **Decisión:** Implementar el algoritmo de Brent sobre el intervalo de búsqueda $\sigma \in [0.01, 5.00]$ con tolerancia absoluta de precio de $10^{-6}$ USD.
* **Alternativas evaluadas:**
  1. Newton-Raphson estándar: $\sigma_{n+1} = \sigma_n - \frac{f(\sigma_n)}{\nu(\sigma_n)}$.
  2. Bisección pura.
* **Motivo de la elección:** Newton-Raphson diverge o da pasos descontrolados cuando la opción está profundamente OTM o ITM, ya que la Vega $\nu \to 0$, haciendo que el denominador tienda a cero. Brent combina interpolación cuadrática inversa, secante y bisección garantizada, asegurando convergencia superlineal cuando el comportamiento es suave y convergencia garantizada en el bracket sin riesgo de división por cero.
* **Evidencia:** Pruebas de recuperación de volatilidad sintética en `tests/test_iv_recovery.py`.

---

## 2. Limitaciones Identificadas y Mitigaciones Metodológicas

1. **Ausencia de Cotizaciones Bid-Ask Simultáneas en Tiempo Real:**
   * *Limitación:* Yahoo Finance no conserva las cotizaciones bilaterales vivas de la sesión regular una vez cerrado el mercado.
   * *Mitigación:* Se utiliza `lastPrice` del 17 de noviembre, pero se filtra rigurosamente mediante el condicionamiento $\kappa = 0.01 / \text{Vega} \le 3.0$ puntos porcentuales. Todo contrato con Vega microscópica donde un tick de un centavo mueva la IV en más de 3 pp queda etiquetado como no apto para la calibración central de la superficie.

2. **Asincronía Temporal con Bloomberg:**
   * *Limitación:* Los campos de Bloomberg provienen de una captura del 18 de noviembre a las 12:52 COT (~21 horas después del cierre del 17 de noviembre), cuando el spot de NU se había movido de $12.33 a ~$12.08 USD.
   * *Mitigación:* Se documenta explícitamente esta asincronía. Las diferencias entre nuestras IVs y Bloomberg no se interpretan como un error de cálculo, sino como el efecto conjunto de: (i) caída del spot, (ii) paso del tiempo ($\Delta t \approx 0.88$ días), (iii) base de precio (last vs mid), y (iv) ligera diferencia en la curva de descuento (Tesoro vs SOFR).

3. **Restricción de Backtesting Histórico Libre de Sesgos:**
   * *Limitación:* No se dispone de la serie histórica diaria de la cadena completa de opciones ni de los contratos expirados.
   * *Mitigación:* Se descarta la fabricación de backtests espurios basados en contratos supervivientes (survivorship bias). Las estrategias del Punto 53 se formulan como estrategias prospectivas hipotéticas, sustentadas en la econometría de series temporales del subyacente NU (HAR-RV validado rigurosamente fuera de muestra) y en la extracción analítica de la varianza forward de la curva ATM.
