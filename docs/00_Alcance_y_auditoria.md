# Auditoría Forense Inicial y Definición del Alcance

**Proyecto:** Superficie de Volatilidad Implícita, Stress Testing y Estrategias con Opciones Americanas sobre NU US Equity  
**Fecha de referencia base:** 17 de noviembre de 2026, 16:00 EST (America/New_York)  
**Spot de cierre base ($S_0$):** $12.33 USD (verificado en NYSE vía registros oficiales e histórico descargado)  
**Dividendos esperados ($q$):** 0.00 % anual ($q = 0$, Nu Holdings no ha pagado dividendos en su historia; confirmado en Formulario 6-K ante la SEC del 12-nov-2026)  
**Entorno de ejecución:** Python 3.12.6, NumPy 2.1.1, SciPy 1.18.0, Pandas 2.2.2, OpenPyXL 3.1.5, Pytest 9.2.0, MiKTeX (pdflatex / xelatex disponible)

---

## 1. Alcance Técnico y Requisitos Normativos (Puntos 46 a 56)

El presente proyecto responde a la necesidad de la mesa de derivados y del área de gestión de riesgos de una entidad financiera de superar las limitaciones del modelo de Black-Scholes-Merton (BSM) con volatilidad constante para la valoración y cobertura de opciones sobre acciones de **Nu Holdings Ltd. (NYSE: NU)**.

A continuación se detalla la correspondencia entre los puntos requeridos y los módulos de desarrollo:

| Punto | Requisito | Módulo en Arquitectura | Criterio de Verificación |
|---|---|---|---|
| **46** | Cadena de opciones (calls y puts, strikes, vencimientos) | `src/data_cleaning.py` | 575 contratos importados y analizados íntegramente. |
| **47** | Spot, tasas libres de riesgo y dividendos | `src/market_data.py` | $S_0=12.33$, curva del Tesoro 17-nov interpolada, $q=0$. |
| **48** | Black-Scholes analítico para opciones europeas | `src/pricing_bs.py` | Implementación exacta, monotonicidad y paridad put-call. |
| **49** | Inversión numérica a Volatilidad Implícita (IV) | `src/iv_inversion.py` | Algoritmo de Brent con bracketing riguroso y control de tolerancia. |
| **50** | Estructura de sonrisas, moneyness y skew | `src/surface.py` | Visualización en $k = \ln(K/F)$ y análisis de convexidad/sesgo. |
| **51** | Construcción de la superficie de volatilidad | `src/surface.py` | Parametrización Raw SVI y spline cúbico en varianza total $w(k,\tau)$. |
| **52** | **Stress Testing de la cadena fija** | `src/stress_testing.py` | 5 escenarios multifactoriales con revaloración americana completa. |
| **53** | **Portafolio y estrategias de trading de volatilidad** | `src/portfolio.py`, `src/strategies.py` | 2 estrategias hipotéticas bien fundamentadas con costos reales. |
| **54** | Comparación BS plano vs Superficie (4 modelos) | `src/model_comparison.py` | Matriz $2 \times 2$ (Europeo/Americano $\times$ Plano/IVS) sin circularidad. |
| **55** | Cálculo y análisis de Griegas y riesgo de skew | `src/greeks.py` | Delta, Gamma, Vega, Theta, Vanna, Volga con unidades explícitas. |
| **56** | Recomendaciones ejecutivas a la entidad | `docs/GUIA_EXPOSICION_10_MIN.md` | Diagnóstico cuantitativo y política de gestión de riesgos. |

---

## 2. Diagnóstico Forense del Archivo `Opciones_Completo.xlsx`

La inspección directa y reproducible de los datos originales arrojó los siguientes hallazgos numéricos inmutables:

### 2.1 Estructura General y Homologación de Hojas
* **Hoja 1 (`Hoja1`):** 575 filas $\times$ 23 columnas. Contiene datos de mercado de Yahoo Finance (`contractSymbol`, `strike`, `lastPrice`, `bid`, `ask`, `volume`, `openInterest`, `impliedVolatility`, `expirationDate`, `type`, `yearsToExpiry`, `midPrice`) y campos Bloomberg (`bloombergOptionTicker`, `exerciseType`, `ivMid`, `ivBestPrice`, `ivLast Trade`).
* **Hoja 2 (`Hoja2`):** 575 filas $\times$ 5 columnas. Contiene exclusivamente los campos Bloomberg (`Bloomberg Option Ticker`, `Exercise Type`, `IV Mid`, `IV Best Price`, `IV Last Trade`).
* **Correspondencia 1-a-1:** En la Hoja 1, los tickers Bloomberg utilizan coma decimal para los strikes no enteros (ej. `NU US 11/20/26 C1,0 Equity`), mientras que la Hoja 2 utiliza punto decimal (`NU US 11/20/26 C1.0 Equity`). Tras normalizar la coma por punto, la coincidencia fila a fila entre ambas hojas es del 100% (575 de 575 contratos).
* **Distribución por tipo:** 303 opciones Call (`C`) y 272 opciones Put (`P`).
* **Estructura de vencimientos:** Exactamente 16 vencimientos distintos, que cubren desde el 20 de noviembre de 2026 (ultra corto plazo, 3 días calendario desde el cierre) hasta el 19 de enero de 2029 (LEAPS a 2.17 años).

### 2.2 Patrón Temporal y Falsa Simultaneidad de Cotizaciones
* **Fecha real de las transacciones (`lastTradeDate`):** 
  * 291 contratos registraron su última transacción el **17 de noviembre de 2026** (entre las 14:30 y las 20:59:55 UTC / 15:59:55 EST).
  * 284 contratos registraron su última transacción en fechas anteriores (desde septiembre de 2025 hasta el 16 de noviembre de 2026).
  * **Cero (0) contratos transaron el 18 de noviembre de 2026.**
* **Anomalía del libro de órdenes (`bid` / `ask`):**
  * 538 contratos tienen `bid = 0` y `ask = 0` (93.57 % de la muestra). Esto ocurre porque Yahoo Finance reinicia las cotizaciones bid/ask fuera de horario de mercado y previo a la apertura.
  * Solo 32 contratos presentan `bid > 0` y `ask > 0`. Sin embargo, la auditoría demuestra que estas cotizaciones provienen de sesiones antiguas (febrero a octubre de 2026) y son completamente obsoletas; muchas de ellas violan flagrantemente el valor intrínseco.
  * **Decisión técnica fundamental:** Descartar el filtro ingenuo `bid > 0`. La base de valoración primaria para la calibración debe ser el `lastPrice` depurado de las transacciones del 17 de noviembre, verificado contra cotas económicas de no arbitraje.

### 2.3 Corrupción por Localización Regional en Excel
* **`yearsToExpiry`:** 77 registros con madurez $\ge 1$ año sufrieron una corrupción por separador de miles en Excel, multiplicando el valor por factores de $10^{16}$ (ej. 1.0027 se importó como $1.0027 \times 10^{16}$).
* **Truncamiento de madurez:** En los 13 vencimientos inferiores a 1 año, `yearsToExpiry` truncó el tiempo a días enteros hasta medianoche ($\lfloor T - t \rfloor / 365.25$). Para el primer vencimiento (20-nov), asigna 1.0 día en lugar de los 3.0 días calendario reales desde el cierre del 17-nov hasta el cierre contractual de las 16:00 EST del 20-nov, introduciendo un error de subestimación de tiempo de más del 50% que inflaría artificialmente la IV calculada.
* **`impliedVolatility` de Yahoo:** 271 registros presentan valores mayores a 5.0 (500%), incluyendo artefactos de $10^{11}$ y patrones diádicos ($0.500005, 0.2500075$) propios de una bisección fallida sobre precios cero. Esta columna queda formalmente excluida de cualquier cálculo de superficie.

### 2.4 Valores de Bloomberg
* **Disponibilidad:** `ivMid` (512 válidos, 63 `#N/A`), `ivBestPrice` (489 válidos, 86 `#N/A`), `ivLast Trade` (507 válidos, 68 `#N/A`).
* **Rol en el proyecto:** Las volatilidades de Bloomberg se reservan **exclusivamente como contraste externo no circular**. La superficie y todas las decisiones de gestión de riesgos se sustentan únicamente en el cálculo propio de IV mediante Crank-Nicolson + Penalización + Brent.

---

## 3. Matriz de Decisiones Metodológicas Iniciales

| ID | Tema | Decisión Adoptada | Alternativa Descartada y Justificación |
|---|---|---|---|
| **D01** | Fecha y Hora Base | 17 de noviembre de 2026, 16:00 EST. | 18 de noviembre (hora descarga): no hubo trades en esa fecha; usar 18-nov induciría asincronía y pricing artificial. |
| **D02** | Spot de Referencia | $S_0 = 12.33$ USD (cierre oficial NYSE 17-nov). | Precios intradía no observables para toda la cadena simultáneamente. |
| **D03** | Cálculo de $\tau$ | Act/365F continuo con marca horaria 16:00 EST. | Reutilizar `yearsToExpiry` del Excel (corrupto y truncado). |
| **D04** | Precio Objetivo | `lastPrice` del 17-nov verificado contra cotas. | `midPrice` (nulo en 94% de contratos y obsoleto en los restantes). |
| **D05** | Pricing de Calls | Black-Scholes analítico ($q=0, r \ge 0$). | EDP numérica para calls: matemáticamente idéntica por no ejercicio anticipado, pero analítica es $1000\times$ más rápida y libre de error de discretización. |
| **D06** | Pricing de Puts | Crank-Nicolson + Penalización + Rannacher. | Modelo de árbol CRR como motor principal: se conserva CRR solo como validador independiente de convergencia. |
| **D07** | Inversión de IV | Algoritmo de Brent en intervalo $[0.01, 5.00]$. | Newton-Raphson (puede divergir si Vega es muy pequeña en alas profundas). |
| **D08** | Calibración de Superficie | Raw SVI por rebanadas de madurez + Spline. | Modelo de Heston: descartado para implementación por exigir calibración $\mathbb{P}$ imposible con una sola fecha transversal y por costo 2D. |
| **D09** | Stress Testing | Revaloración americana completa sobre cadena fija. | Delta-Gamma Taylor: solo como comparación local, incapaz de capturar saltos severos o no linealidades del ejercicio anticipado. |
| **D10** | Estrategias | Hipotéticas basadas en pronóstico HAR-RV y Calendar Spread. | Backtest histórico de opciones con datos sintéticos no observables: metodológicamente inválido. |

---

## 4. Estado de Verificación del Entorno

* **Python:** 3.12.6 listo en el entorno.
* **Bibliotecas numéricas:** `numpy`, `scipy`, `pandas`, `matplotlib`, `pytest`, `openpyxl` verificadas y operativas.
* **Compilador LaTeX:** `pdflatex` y `xelatex` confirmados en `MiKTeX/miktex/bin/x64`.
* **Archivos fuente:** `Opciones_Completo.xlsx` respaldado en `data/raw/` (solo lectura).
