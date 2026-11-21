# Guía de Exposición Oral (10 Minutos) — Proyecto de Opciones Americanas de NU

**Público objetivo:** Comité de Riesgos, Mesa de Derivados y Dirección Cuantitativa de la entidad.  
**Tiempo total asignado:** 10 minutos (8 diapositivas de contenido, ~1:15 min por diapositiva).  
**Objetivo de la sesión:** Demostrar por qué el supuesto de volatilidad constante de Black-Scholes es inaceptable para la gestión de riesgos de NU Holdings (NYSE: NU) y presentar la arquitectura integral de valoración americana, superficie SVI, stress testing y estrategias cuantitativas.

---

## Estructura Temporal y Resumen Ejecutivo

| Diapositiva | Título del Bloque | Tiempo Asignado | Mensaje Clave |
|---|---|---|---|
| **1** | El Problema Financiero y el Caso Empresarial | 0:00 – 1:15 | Black-Scholes plano distorsiona precios y sensibilidades de NU. |
| **2** | Diagnóstico Forense y Auditoría de Datos | 1:15 – 2:30 | 575 contratos originales; filtrado riguroso a 201 opciones limpias. |
| **3** | Motor de Valoración Americano e Inversión Brent | 2:30 – 3:45 | BSM analítico en Calls ($q=0$) y Crank-Nicolson + Penalización en Puts. |
| **4** | Calibración de la Superficie de Volatilidad (SVI) | 3:45 – 5:00 | Parametrización Raw SVI libre de arbitraje ($g(k) \ge 0$) y validación OOS. |
| **5** | Comparación de los Cuatro Modelos de Pricing | 5:00 – 6:15 | Aislamiento del efecto sonrisa frente a la prima de ejercicio anticipado. |
| **6** | Portafolio Hipotético, Griegas y Stress Testing | 6:15 – 7:30 | La aproximación de Taylor falla en crisis; la revaloración PDE es mandatoria. |
| **7** | Estrategias Cuantitativas y Límites de Datos | 7:30 – 8:45 | Pronóstico HAR-RV (72.97%) vs IV ATM (44.02%) y Calendar Spread. |
| **8** | Recomendaciones Finales y Hoja de Ruta | 8:45 – 10:00 | Política de cuatro pilares para la mesa de derivados y control de riesgos. |

---

## Guion Detallado Diapositiva por Diapositiva

### Diapositiva 1: El Problema Financiero y el Caso Empresarial (0:00 – 1:15)
* **Contenido Visual:**
  * Diagrama de flujo del mandato institucional (Puntos 46 a 56).
  * Gráfico conceptual: Discrepancia entre la curva plana de Black-Scholes y los precios observados de mercado.
* **Guion del Expositor:**
  > "Buenos días, miembros del comité. Una mesa de derivados que utilice Black-Scholes clásico con una sola volatilidad constante para valorar y gestionar opciones sobre Nu Holdings comete dos errores estructurales: ignora la prima de ejercicio anticipado de las opciones americanas y desestima la sonrisa de volatilidad generada por el riesgo de cola y la asimetría del mercado. Nuestro objetivo es implementar una infraestructura cuantitativa rigurosa basada en diferencias finitas, calibrar una superficie de volatilidad implícita libre de arbitraje estático, someter una cartera fija a stress testing multifactorial y formular estrategias de volatilidad con supuestos de costos reales."

---

### Diapositiva 2: Diagnóstico Forense y Auditoría de Datos (1:15 – 2:30)
* **Contenido Visual:**
  * Tabla resumen de auditoría: 575 contratos brutos $\to$ 201 contratos limpios (16 vencimientos).
  * Visualización de anomalías detectadas: dispersión de `lastTradeDate` (291 transacciones el 17-nov-2026), reseteo de bid/ask a cero en 538 contratos y corrección de la madurez $\tau$ (3.0 días reales vs 1.0 día truncado en Excel).
* **Guion del Expositor:**
  > "Trabajamos sobre una cadena de 575 contratos reales de NU en 16 vencimientos. El examen forense reveló que ningún contrato negoció el 18 de noviembre: todas las operaciones líquidas ocurrieron el 17 de noviembre, cerrando a las 15:59:55 EST con $S_0 = 12.33$ USD. Por ende, fijar la fecha base en el cierre del 17 de noviembre es imperativo para evitar asincronías artificiales. Detectamos además que el 94% de las filas tenían bid y ask en cero por reseteo matutino de Yahoo, y que `yearsToExpiry` sufría corrupción por separador decimal y truncamiento a días enteros. Recalculamos $\tau$ bajo Act/365F continuo y clasificamos la base en cuatro Tiers: 201 contratos satisfacen estrictamente cotas de no arbitraje, valor tiempo positivo y condicionamiento $\kappa \le 5.0$ puntos de vol por centavo."

---

### Diapositiva 3: Motor de Valoración Americano e Inversión Brent (2:30 – 3:45)
* **Contenido Visual:**
  * Ecuación de Black-Scholes para Calls y formulación de Complementariedad Lineal (LCP) para Puts americanas.
  * Esquema numérico: Crank-Nicolson con suavizado de Rannacher y método de penalización (Forsyth & Vetzal, 2002).
  * Tabla de validación independiente: Discrepancia PDE vs árbol CRR ($N=1000$) menor a $\$0.0005$ USD ($< 0.05$ centavos).
* **Guion del Expositor:**
  > "Para la valoración diferenciamos la naturaleza económica de los contratos. Dado que NU no paga dividendos ($q=0$) y las tasas son positivas ($r > 0$), el teorema de Merton demuestra que el ejercicio anticipado de una Call americana nunca es óptimo; por ende, utilizamos la fórmula cerrada de Black-Scholes, exacta y computacionalmente instantánea. Para las Puts americanas, donde el cobro inmediato del strike puede ser óptimo, implementamos un esquema de diferencias finitas Crank-Nicolson con suavizado de Rannacher para amortiguar oscilaciones del payoff y el método de penalización cuadrático de Forsyth & Vetzal. Validamos el motor contra un árbol CRR de 1000 pasos, logrando una concordancia de medio milésimo de dólar. La inversión a volatilidad implícita se ejecuta mediante el algoritmo de Brent, garantizando convergencia sin riesgo de división por cero."

---

### Diapositiva 4: Calibración de la Superficie de Volatilidad (SVI) (3:45 – 5:00)
* **Contenido Visual:**
  * Figura 1: [smile_2d_slices.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/smile_2d_slices.png) (Cortes de sonrisa 2D por vencimiento).
  * Figura 2: [surface_3d_volatility.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/surface_3d_volatility.png) (Superficie 3D en coordenadas $(k, \tau)$).
  * Métricas de validación cruzada Leave-One-Strike-Out: MAE IV = 2.48 pp, RMSE IV = 4.69 pp, MAE Precio = $\$0.039$ USD.
* **Guion del Expositor:**
  > "Proyectamos la cadena en coordenadas estandarizadas de log-forward moneyness $k = \ln(K/F)$ y varianza total $w(k,\tau) = \sigma^2 \tau$. Calibramos la parametrización Raw SVI de Gatheral por cortes temporales, restringiendo los parámetros para garantizar ausencia de arbitraje mariposa ($g(k) \ge 0$, verificado en el 100% del soporte líquido). En la dimensión temporal, interpolamos mediante splines monótonos PCHIP para asegurar $\partial w / \partial \tau \ge 0$, eliminando el arbitraje de calendario. Sometimos la superficie a una validación cruzada Leave-One-Out sobre 196 contratos fuera de muestra: el error medio absoluto en precio fue de apenas 3.9 centavos de dólar, demostrando una excelente capacidad de generalización sin sobreajuste."

---

### Diapositiva 5: Comparación de los Cuatro Modelos de Pricing (5:00 – 6:15)
* **Contenido Visual:**
  * Figura: [model_comparison_errors.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/model_comparison_errors.png) (Comparación de MAE entre los 4 modelos por segmento).
  * Tabla comparativa:
    * M1 (Europeo Plano): MAE = $\$0.0536$
    * M2 (Europeo Superficie): MAE = $\$0.0306$
    * M3 (Americano Plano): MAE = $\$0.0482$
    * M4 (Americano Superficie): MAE = $\$0.0299$
* **Guion del Expositor:**
  > "Para cuantificar con precisión matemática el impacto de cada supuesto, evaluamos la matriz $2 \times 2$ entre tipo de ejercicio (Europeo vs Americano) y estructura de volatilidad (Plana vs Superficie). En Calls, el Modelo 1 coincide exactamente con el Modelo 3, y el Modelo 2 con el Modelo 4, ratificando la teoría. En Puts, la prima de ejercicio anticipado alcanza hasta 2.5 centavos en contratos ITM. Sin embargo, el efecto más dominante es la sonrisa de volatilidad: pasar de volatilidad plana a la superficie SVI reduce el error de pricing en más del 44% general y en más del 54% en contratos dentro del dinero (ITM), recortando el MAE de $\$0.0854$ a $\$0.0396$. Black-Scholes plano subvalora sistemáticamente las alas OTM y distorsiona el valor de las coberturas."

---

### Diapositiva 6: Portafolio Hipotético, Griegas y Stress Testing (6:15 – 7:30)
* **Contenido Visual:**
  * Estructura de cartera: 5 patas de opciones reales en 31 y 59 días + cobertura delta con -354 acciones de NU.
  * Figura 1: [stress_test_pnl_waterfall.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/stress_test_pnl_waterfall.png) (P&L por escenario: Revaloración PDE vs Taylor).
  * Figura 2: [stress_crisis_leg_breakdown.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/stress_crisis_leg_breakdown.png) (Desglose por pata en el Escenario 3 de Crisis Severa).
* **Guion del Expositor:**
  > "Construimos una cartera hipotética de 5 patas reales de NU representativa de una mesa institucional: spreads verticales, straddles y calendars, neutralizada en delta inicial mediante una posición corta de 354 acciones de NU. Sometimos esta cadena fija a cinco escenarios de estrés multifactorial. El hallazgo más crítico para el área de riesgos es la ruptura de la aproximación de Taylor por griegas: en un shock de crisis del -20% en spot con empinamiento de skew (+12 pp vol), la aproximación local de Taylor estima erróneamente una ganancia de $+\$3,699$ USD debido al término positivo de Gamma ($\frac{1}{2}\Gamma \Delta S^2$). Sin embargo, la revaloración completa con el motor PDE americano revela un P&L real de $+\$446$ USD, una discrepancia de más de $\$3,250$ USD. Esto ocurre porque las Calls pierden toda su delta al caer a cero y los Puts cortos sufren riesgo de asignación anticipada acelerada. La revaloración completa por EDP es insustituible."

---

### Diapositiva 7: Estrategias Cuantitativas y Límites de Datos (7:30 – 8:45)
* **Contenido Visual:**
  * Figura 1: [nu_historical_vol_and_forecasts.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/nu_historical_vol_and_forecasts.png) (Serie histórica y pronóstico HAR-RV).
  * Figura 2: [strategy1_payoff_scenarios.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/strategy1_payoff_scenarios.png) (Curvas de P&L de la Estrategia 1 bajo tres regímenes de fricción).
  * Figura 3: [strategy2_calendar_payoff.png](file:///C:/Users/CAROL/orca/workspaces/ImpVolSurface/rockling/outputs/figures/strategy2_calendar_payoff.png) (Payoff del Calendar Spread explotando la varianza forward).
* **Guion del Expositor:**
  > "Desarrollamos dos estrategias cuantitativas defendibles. En la Estrategia 1, modelamos la serie histórica de NU mediante el modelo econométrico HAR-RV de Corsi con validación walk-forward (QLIKE = 0.1813). Al 17 de noviembre, el pronóstico de volatilidad a 21 días se ubicó en 72.97%, frente a una IV ATM de 44.02%, generando una señal $z = +0.505 > 0$. Esto indicó que las opciones estaban baratas frente a la volatilidad proyectada tras los resultados trimestrales, justificando un Straddle ATM largo delta-neutral. En la Estrategia 2, extrajimos la volatilidad forward implícita entre el vencimiento de 31 días y 59 días ($\sigma_{\text{fwd}} = 38.15\%$) mediante un Calendar Spread vega-ponderado en strike 13.00. Modelamos tres regímenes de costos de transacción: en el régimen conservador, el punto de equilibrio del straddle exige un movimiento de spot superior al 12% para compensar fricciones. Resaltamos con honestidad académica que, al no disponer de series históricas de cadenas intradía completas, no presentamos backtests retrospectivos espurios."

---

### Diapositiva 8: Recomendaciones Finales y Hoja de Ruta (8:45 – 10:00)
* **Contenido Visual:**
  * Matriz ejecutiva de gobernanza: Cuatro pilares de adopción cuantitativa para la entidad.
  * Hoja de ruta técnica de despliegue a producción.
* **Guion del Expositor:**
  > "En conclusión, respondemos a la pregunta ejecutiva de la entidad con cuatro recomendaciones innegociables:
  > 1. **Eliminar Black-Scholes con volatilidad plana** de la tarificación y de las métricas de capital regulatorio; induce sesgos de hasta el 54% en ITM y distorsiona la cobertura delta.
  > 2. **Adoptar la superficie SVI calibrada diariamente** como la fuente oficial de marcado a modelo (*mark-to-model*), garantizando ausencia de arbitraje estático.
  > 3. **Instituir la revaloración completa americana por diferencias finitas en las pruebas de estrés periódicas**, reservando las griegas únicamente para monitoreo intradía de movimientos menores a 1 desvío estándar.
  > 4. **Acondicionar las estrategias algorítmicas a filtros de iliquidez estrictos** ($\kappa \le 3.0$ pp/¢) y descontar rigurosamente el costo de bid-ask bounce y márgenes de garantía.
  > Muchas gracias. Quedamos a su disposición para la sesión de preguntas."
