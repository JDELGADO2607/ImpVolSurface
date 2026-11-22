# NU: valoración de opciones americanas con Heston

Proyecto académico sobre opciones de NU Holdings Ltd.: calibración de Heston a precios de puts americanas, valoración mediante diferencias finitas, volatilidad implícita equivalente, comparación de modelos y riesgo de una cartera hipotética. El modelo clásico utiliza una única parametrización global bajo la medida neutral al riesgo. Raw SVI se conserva como benchmark histórico.

**Estado:** implementación final del [PR #5](https://github.com/JDELGADO2607/ImpVolSurface/pull/5), con revisión humana final pendiente. Esta actualización documental parte del commit `2a9143ba55f1e17b165fa7132d954227635e6538`; no modifica resultados ni autoriza un merge.

## Datos y calibración

- Fecha de valoración: 17 de noviembre de 2026, 16:00 America/New_York; spot de referencia: **12,33 USD**. Hipótesis de dividendos nulos, multiplicador de 100 y ACT/365 Fixed.
- Muestra final: **97 puts** y **142 calls** externas. La calibración minimiza **SSE no ponderada en precios sobre 60 puts americanas**. Se reservan 22 puts para holdout por strike y 15 por vencimiento; las calls no participan en la calibración.
- Curva determinista construida a partir de tasas par CMT del Treasury, con instrumentos sintéticos y aproximaciones en el tramo corto. No equivale a un bootstrap completo de bonos efectivamente cotizados ni a tasas cero observadas. Es una curva **ex post**: su disponibilidad exacta a las 16:00 no está demostrada.
- Parámetros seleccionados `(v0, kappa, theta, xi, rho)`: `(0.18613778, 2.72546037, 0.21367970, 0.48178473, -0.94980666)`. El registro completo está en [heston_calibrated_parameters.json](data/heston/phase4/heston_calibrated_parameters.json). Son parámetros bajo Q, no estimaciones de la dinámica física.

## Dependencias y ejecución

Entorno de referencia: Python **3.12.6** y QuantLib **1.44**. Los dos archivos de dependencias son complementarios: Heston necesita QuantLib y la generación de figuras necesita matplotlib del archivo general.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt -r requirements-heston.txt
python run_all.py --heston
```

Ejecutar desde la raíz del repositorio con los insumos y parámetros versionados. `run_all.py --heston` ejecuta **la integración financiera de fase 6**: comparación de cuatro modelos, valoración y griegas de la cartera, cobertura delta, estrés y figuras. Lee los parámetros de fase 4 y tablas previas; **no recalibra Heston ni reconstruye la superficie de IV de fase 5 ni ejecuta las pruebas**. Las salidas se escriben en `data/heston/phase6/` y `figures/phase6/`.

Para regenerar la superficie de IV con la calibración existente:

```powershell
python -m src.heston.pipeline_phase5
```

Sin `--heston`, `python run_all.py` ejecuta el pipeline histórico SVI. No es la ruta de cierre Heston.

### Reproducción de la calibración: operación separada y costosa

Reproducir tablas con parámetros guardados no es repetir la optimización. Para repetir los cinco arranques de la prueba de concepto, los refinamientos y las evaluaciones posteriores, desde los insumos y la partición versionados:

```powershell
python -c "from src.heston.pipeline_phase1 import run_phase1_pipeline; run_phase1_pipeline(reuse_existing_multistart=False)"
python -m src.heston.run_refinements --optimize all
python -m src.heston.pipeline_phase4
python -m src.heston.pipeline_phase5
python run_all.py --heston
```

El primer comando fuerza cinco optimizaciones nuevas; la ejecución normal de `pipeline_phase1` reutiliza los resultados guardados y verifica su objetivo. Los refinamientos A/B/C usan sus puntos iniciales declarados en `run_refinements.py` y hasta 35 iteraciones por defecto. `pipeline_phase4` reevalúa y selecciona candidatos, pero no ejecuta por sí solo esos refinamientos. Esta secuencia sobrescribe artefactos de trabajo: usar una copia separada para conservar la evidencia publicada. No se garantiza igualdad bit a bit entre versiones o plataformas, ni optimalidad global de la solución seleccionada.

La alternativa `python -m src.heston.run_refinements --replay-only` reproduce los objetivos de los refinamientos guardados; **no realiza optimizaciones nuevas**. No es necesario ejecutar ninguna de estas operaciones para consultar los resultados finales.

## Arquitectura

| Componente | Responsabilidad |
| --- | --- |
| `src/heston/rates_curve.py` | Curva determinista, descuentos y parámetros de mercado compartidos |
| `src/heston/heston_model.py`, `calibration.py` | Referencia QuantLib y calibración directa de puts americanas |
| `src/heston/solver_2d.py` | Solver propio de puts Heston: diferencias finitas 2D, ADI Modified Craig–Sneyd y tratamiento del obstáculo americano Ikonen–Toivanen |
| `src/pricing_american_fd.py`, `src/heston/equivalent_iv.py` | Motor americano de volatilidad constante 1D e inversión mediante Brent; IV BS para calls europeas |
| `src/heston/pipeline_phase4.py`, `pipeline_phase5.py` | Selección/evaluación de parámetros y superficie de IV equivalente |
| `src/heston/financial_integration.py`, `pipeline_phase6.py` | Comparación, cartera de cinco patas, griegas y estrés Heston |
| `src/surface.py`, `src/strategies.py`, `src/forecasts.py` | SVI, estrategias y HAR-RV históricos conservados; no constituyen una nueva simulación histórica Heston |

La calibración utiliza el motor americano de referencia de QuantLib; el solver propio se contrasta con esa referencia. Para las puts, la IV equivalente reproduce el precio americano Heston en el motor 1D de volatilidad constante. Para las calls, bajo dividendos nulos y tasas no negativas, se utiliza el precio europeo Heston y se invierte Black–Scholes. Estas IV no son la volatilidad instantánea `sqrt(v0)` ni la varianza de largo plazo `theta`.

## Resultados finales y alcance financiero

MAE en USD por opción, según [models_comparison_summary.csv](data/heston/phase6/models_comparison_summary.csv):

| Muestra | Contratos | Volatilidad plana americana (44 %) | Heston americano |
| --- | ---: | ---: | ---: |
| Puts, incluyendo entrenamiento y holdouts | 97 | 0,03738 | 0,02385 |
| Calls externas | 142 | 0,05679 | 0,08729 |
| Universo agregado común | 239 | 0,04892 | 0,06154 |

**Heston mejora el MAE de puts un 36,21 %, pero empeora el MAE de calls y del universo agregado.** No se concluye superioridad global. Los holdouts de puts tienen MAE de 0,02111 USD (22 por strike) y 0,02030 USD (15 por vencimiento); no deben confundirse con el ajuste de entrenamiento.

Las grillas descriptivas tienen 35 precios por tipo de opción, con **29 IV interiores identificadas de puts y 33 de calls**. Las filas restantes conservan estados de frontera o no identificación; no representan IV interiores válidas.

La integración Heston incluye **una cartera hipotética de cinco patas**, cobertura de −393 acciones y seis escenarios instantáneos de estrés. Su capital aproximado es 5.613,88 USD, mediante una regla académica sobre primas del modelo, no margen regulatorio exacto. Las sensibilidades a `sqrt(v0)` no son vega respecto de la IV cotizada. La diferencia entre revaloración completa y Taylor es un **residuo de aproximación**: Taylor incluye segundo orden en spot y primer orden en volatilidad inicial, sin todos los términos cruzados ni volga.

Las estrategias **straddle y calendar spread** pertenecen a los módulos históricos y no están integradas con Heston como la cartera de cinco patas. Sus escenarios no constituyen evidencia de rentabilidad histórica; no existe un panel histórico de opciones que permita ese backtest.

## Limitaciones aceptadas

- Precios de últimas transacciones asíncronos y bid/ask insuficientes: el ajuste no equivale a valorar una cadena sincronizada y ejecutable.
- Identificación paramétrica limitada en una sola sección transversal; correlación cercana al límite de búsqueda y ausencia de garantía de unicidad u óptimo global.
- Precisión de IV ultracorta limitada, en particular la put de tres días `NU261120P00012500`. Los seis controles 1D publicados no prueban precisión uniforme en todo el dominio.
- Curva CMT ex post y aproximaciones de construcción; no se afirma disponibilidad ex ante exacta al instante de valoración.
- **F4-H2 permanece abierto como limitación aceptada** del control de cotas europeas en casos sintéticos extremos. No se presenta como reparado; no se ha demostrado impacto sobre los resultados reales publicados.
- La IV no se identifica cerca de regiones de vega nula. Los valores del límite numérico inferior no son estimaciones económicas de volatilidad. Las comprobaciones sobre mallas finitas no prueban ausencia global de arbitraje.
- Estrés hipotético sin probabilidades, financiación ni fricciones; theta con curva congelada y Taylor parcial. HAR-RV bajo la medida física es distinto de la calibración neutral al riesgo.

## Documentación y resultados

- [Fase 5: superficie e IV equivalente](docs/reports/INFORME_FASE_5_SUPERFICIE_IV_HESTON.md).
- [Fase 6: comparación, cartera, estrés y guion de diez minutos](docs/reports/INFORME_FASE_6_INTEGRACION_FINANCIERA.md).
- Artefactos: `data/heston/phase4/`, `data/heston/phase5/`, `data/heston/phase6/`; figuras: `figures/phase5/` y `figures/phase6/`.
- [Contexto](CONTEXT.md), [continuidad](HANDOFF.md) y [plan](PLAN.md). Los informes históricos conservan sus conclusiones para el SHA examinado; no sustituyen la revisión humana final del PR.
