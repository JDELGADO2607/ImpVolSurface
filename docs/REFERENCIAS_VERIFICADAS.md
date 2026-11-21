# Referencias Bibliográficas Verificadas

A continuación se presenta el catálogo de la literatura académica primaria y metodológica utilizada y citada en el proyecto, con sus identificadores digitales de objeto (DOI), metadatos bibliográficos completos y relevancia metodológica específica en el desarrollo del motor cuantitativo.

---

### 1. Valoración Analítica y Fundamentos de Derivados

1. **Black, F., & Scholes, M. (1973).** *The Pricing of Options and Corporate Liabilities.* **Journal of Political Economy**, 81(3), 637–654.
   * **DOI:** [10.1086/260062](https://doi.org/10.1086/260062)
   * **Relevancia:** Derivación de la ecuación diferencial parcial (EDP) parabólica bajo cartera de réplica delta-neutral y ausencia de arbitraje. Fórmula analítica cerrada para opciones europeas utilizada como motor primario para Calls sin dividendos ($q=0$).

2. **Merton, R. C. (1973).** *Theory of Rational Option Pricing.* **The Bell Journal of Economics and Management Science**, 4(1), 141–183.
   * **DOI:** [10.2307/3003143](https://doi.org/10.2307/3003143)
   * **Relevancia:** Teorema de no ejercicio anticipado de opciones Call americanas cuando $q = 0$ y $r \ge 0$, demostrando que $C_{\text{American}} \equiv C_{\text{European}}$. Extensión de dividendos continuos y condiciones de frontera.

---

### 2. Métodos Numéricos para Opciones Americanas y EDPs

3. **Brennan, M. J., & Schwartz, E. S. (1977).** *The Valuation of American Put Options.* **The Journal of Finance**, 32(2), 449–462.
   * **DOI:** [10.1111/j.1540-6261.1977.tb03284.x](https://doi.org/10.1111/j.1540-6261.1977.tb03284.x)
   * **Relevancia:** Formulación pionera de la valoración de puts americanas mediante diferencias finitas y problema de frontera libre.

4. **Cox, J. C., Ross, S. A., & Rubinstein, M. (1979).** *Option Pricing: A Simplified Approach.* **Journal of Financial Economics**, 7(3), 229–263.
   * **DOI:** [10.1016/0304-405X(79)90015-1](https://doi.org/10.1016/0304-405X(79)90015-1)
   * **Relevancia:** Modelo de árbol binomial recombinante con convergencia débil al proceso de difusión lognormal. Implementado en `src/pricing_crr.py` como validador numérico independiente del motor de diferencias finitas.

5. **Forsyth, P. A., & Vetzal, K. R. (2002).** *Quadratic Convergence for Valuing American Options Using a Penalty Method.* **SIAM Journal on Scientific Computing**, 23(6), 2095–2122.
   * **DOI:** [10.1137/S1064827500382324](https://doi.org/10.1137/S1064827500382324)
   * **Relevancia:** Formulación del método de penalización para el problema de complementariedad lineal (LCP) de opciones americanas discretizadas con Crank-Nicolson, garantizando convergencia cuadrática e incondicional vía iteración de Newton/política. Motor central de `src/pricing_american_fd.py`.

6. **Rannacher, R. (1984).** *Finite Element Solution of Diffusion Problems with Irregular Data.* **Numerische Mathematik**, 43(2), 309–327.
   * **DOI:** [10.1007/BF01390499](https://doi.org/10.1007/BF01390499)
   * **Relevancia:** Procedimiento de suavizado temporal para Crank-Nicolson (reemplazar los primeros pasos temporales con sub-pasos implícitos puros de Euler), amortiguando oscilaciones espurias de alta frecuencia provocadas por la discontinuidad de la derivada del payoff en $S = K$.

---

### 3. Superficies de Volatilidad Implícita y No Arbitraje

7. **Gatheral, J. (2004).** *A Parsimonious Model of Volatility Smiles and Its Applications.* **Global Derivatives & Risk Management Conference**, Madrid.
   * **Relevancia:** Introducción de la parametrización Raw SVI (Stochastic Volatility Inspired) para la varianza total implícita $w(k) = a + b[\rho(k-m) + \sqrt{(k-m)^2 + \eta^2}]$, lineal en las alas y coherente con Heston asintótico.

8. **Gatheral, J., & Jacquier, A. (2014).** *Arbitrage-Free SVI Volatility Surfaces.* **Quantitative Finance**, 14(1), 59–71.
   * **DOI:** [10.1080/14697688.2013.819986](https://doi.org/10.1080/14697688.2013.819986)
   * **Relevancia:** Condiciones analíticas y algorítmicas de ausencia de arbitraje estático (arbitraje mariposa vía densidad $g(k) \ge 0$ y arbitraje de dispersión temporal $\partial w / \partial \tau \ge 0$).

9. **Cont, R., & da Fonseca, J. (2002).** *Dynamics of Implied Volatility Surfaces.* **Quantitative Finance**, 2(1), 45–60.
   * **DOI:** [10.1088/1469-7688/2/1/304](https://doi.org/10.1088/1469-7688/2/1/304)
   * **Relevancia:** Análisis empírico de la estructura transversal y dinámica temporal de la superficie de volatilidad (descomposición en factores de nivel, inclinación/skew y curvatura).

---

### 4. Stress Testing y Gestión de Riesgos en Derivados

10. **Breuer, T., Jandačka, M., Rheinberger, K., & Summer, M. (2009).** *How to Find Plausible, Severe, and Useful Stress Scenarios.* **International Journal of Central Banking**, 5(3), 205–224.
    * **Enlace:** [https://www.ijcb.org/journal/v5n3/how-find-plausible-severe-and-useful-stress-scenarios](https://www.ijcb.org/journal/v5n3/how-find-plausible-severe-and-useful-stress-scenarios)
    * **Relevancia:** Marco conceptual para la definición de escenarios de tensión macroeconómicos y de mercado multifactoriales severos pero plausibles, superando los shocks univariados o paralelos ingenuos.

---

### 5. Econometría de Volatilidad y Estrategias Cuantitativas

11. **Corsi, F. (2009).** *A Simple Approximate Long-Memory Model of Realized Volatility.* **Journal of Financial Econometrics**, 7(2), 174–196.
    * **DOI:** [10.1093/jjfinec/nbp001](https://doi.org/10.1093/jjfinec/nbp001)
    * **Relevancia:** Modelo autorregresivo heterogéneo de volatilidad realizada (HAR-RV), combinando componentes de corto plazo (diario), intermedio (semanal) y largo plazo (mensual) para capturar memoria larga aparente y estabilidad fuera de muestra. Implementado en `src/forecasts.py`.

12. **Goyal, A., & Saretto, A. (2009).** *Cross-Section of Option Returns and Volatility.* **Journal of Financial Economics**, 94(2), 310–326.
    * **DOI:** [10.1016/j.jfineco.2009.01.001](https://doi.org/10.1016/j.jfineco.2009.01.001)
    * **Relevancia:** Evidencia empírica sobre retornos de estrategias de opciones condicionadas por la discrepancia entre volatilidad realizada histórica y volatilidad implícita ATM (prima de riesgo de volatilidad en acciones individuales).
