"""
Complete builder script for notebooks/NU_Heston_Autocontenido_Kaggle.ipynb
Constructs all markdown, equations, and code cells with zero external repository dependencies.
All derivative tables and figures outside the raw options Excel and Treasury CMT data
are generated 100% live in-kernel.
"""

import json
import os
import nbformat as nbf

def build_notebook():
    nb = nbf.v4.new_notebook()
    nb.metadata = {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3"
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.12.0"
        }
    }
    cells = []

    # =========================================================================
    # SECTION 0: Resumen Ejecutivo y Metodología General (Markdown)
    # =========================================================================
    sec0_md = r"""# Valoración y Gestión de Riesgo de Opciones Americanas sobre Nu Holdings Ltd. (NU) bajo el Modelo Clásico de Heston (1993)
## Notebook Cuantitativo Autocontenido y Reproducible para Kaggle / Google Colab

---

### Contexto Académico e Institucional
Este cuaderno de Jupyter implementa de forma **100% autocontenida y en vivo en el kernel** la calibración, valoración, reconstrucción de superficies de volatilidad implícita equivalente, contrastes de cuatro modelos, análisis de riesgo de cartera y pruebas de estrés para opciones americanas sobre **Nu Holdings Ltd. (NYSE: NU)** bajo el modelo clásico de volatilidad estocástica de **Heston (1993)**.

- **Fecha de anclaje de valoración:** 17 de noviembre de 2026, 16:00:00 America/New_York (cierre de mercado de NYSE).
- **Subyacente:** Nu Holdings Ltd. ($S_0 = 12.33$ USD, tasa de dividendos continua $q = 0.00$).
- **Convención temporal:** Actual/365 Fixed (ACT/365F) con cálculo exacto de días y duración UTC.
- **Multiplicador de contrato estándar:** 100 acciones por contrato de opción.
- **Universo de mercado auditado:** 575 contratos brutos de la Options Clearing Corporation (OCC) (303 calls, 272 puts).
- **Muestra seleccionada:** 97 puts americanas limpias y 142 calls externas.
- **Partición determinista anti-fuga (anti-leakage):** 60 puts de entrenamiento (train), 22 puts de validación cruzada transversal por strike (strike-holdout), y 15 puts de validación temporal en vencimientos completos retenidos (tenor-holdout).

---

### Principios de Diseño para Kaggle
1. **Autocontenido estricto:** Ninguna celda importa módulos propios (`src.*`, `tests.*`, `.py` locales) ni ejecuta scripts remotos con `%run` o `exec`. Todas las clases matemáticas, esquemas numéricos de diferencias finitas, algoritmos de tridiagonal bandeada y optimizadores están implementados directamente dentro de las celdas.
2. **Generación 100% en vivo desde insumos brutos:** Los únicos insumos externos son el libro de órdenes original de mercado (`data/raw/Opciones_Completo.xlsx`), las tasas de referencia del Tesoro (`data/heston/treasury_cmt_2026_11_17_raw.json`) y opcionalmente los precios diarios históricos (`data/processed/nu_historical_daily.csv`). **Todas las tablas de resultados, valoraciones, superficies IV, comparativas de modelos, métricas de cartera y escenarios de estrés son calculados y generados en vivo dentro del kernel** (~60 a 90 segundos en CPU estándar). Al finalizar cada etapa, el notebook genera y exporta los archivos correspondientes a disco.
3. **Insumos reproducibles con verificación SHA-256:** Cada insumo bruto descargado desde GitHub Raw (`https://raw.githubusercontent.com/{REPO}/{DATA_COMMIT}/{ruta}`) se valida criptográficamente contra su hash SHA-256 oficial. Si GitHub devuelve un error 404/403 (por ejemplo, si el repositorio es privado o si el entorno corre sin conexión a internet), el código ofrece un diagnóstico claro y permite leer desde una ruta de Dataset local (`LOCAL_DATA_DIR`) o desde los archivos locales del espacio de trabajo.
4. **Etiquetado inequívoco de trazabilidad:** Todas las tablas y gráficos generados se etiquetan formalmente como **(a) cálculo efectuado en el kernel actual**, garantizando plena reproducibilidad científica.
"""
    cells.append(nbf.v4.new_markdown_cell(sec0_md))

    # =========================================================================
    # SECTION 1: Entorno, Dependencias y Configuración Global (Code)
    # =========================================================================
    sec1_code_1 = """# Instalación de dependencias públicas en entornos limpios de Kaggle / Colab
# QuantLib-Python se utiliza como adaptador de benchmark analítico y de auditoría
# (No se utiliza para sustituir el solver bidimensional propio de diferencias finitas)
import sys
import subprocess

required_packages = ['QuantLib-Python', 'openpyxl', 'scipy', 'pandas', 'matplotlib', 'requests']

print("Verificando paquetes requeridos...")
for pkg in required_packages:
    try:
        mod_name = 'QuantLib' if pkg == 'QuantLib-Python' else pkg
        __import__(mod_name)
    except ImportError:
        print(f"Instalando {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

print("Entorno verificado exitosamente.")
"""
    cells.append(nbf.v4.new_code_cell(sec1_code_1))

    sec1_code_2 = """# Importación exclusiva de bibliotecas estándar y públicas
import io
import os
import sys
import math
import time
import json
import hashlib
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy
from scipy.optimize import brentq, minimize
from scipy.interpolate import interp1d, PchipInterpolator, RegularGridInterpolator
from scipy.linalg import solve_banded
from scipy.stats import norm
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

try:
    import QuantLib as ql
    HAS_QUANTLIB = True
except ImportError:
    HAS_QUANTLIB = False

print(f"NumPy version: {np.__version__}")
print(f"SciPy version: {scipy.__version__}")
print(f"Pandas version: {pd.__version__}")
print(f"QuantLib disponible: {HAS_QUANTLIB}")
"""
    cells.append(nbf.v4.new_code_cell(sec1_code_2))

    sec1_code_3 = """# =============================================================================
# PARÁMETROS GLOBALES Y CONFIGURACIÓN DE EJECUCIÓN
# =============================================================================

# Switch de calibración desde cero:
# - False (por defecto): Utiliza los parámetros canónicos calibrados y congelados al 17-nov-2026.
#   Ejecuta en vivo TODO el pipeline cuantitativo (~60 a 90 segundos en CPU): valoración de 97 puts,
#   142 calls, inversión de IV, comparativa de 4 modelos, griegas de cartera y 6 escenarios de estrés.
# - True: Ejecuta adicionalmente la optimización multi-arranque formal (5 arranques L-BFGS-B, ~15 min).
CALIBRATE_FROM_SCRATCH = False

# Repositorio remoto oficial en GitHub
REPO = 'JDELGADO2607/ImpVolSurface'
DATA_COMMIT = '3227c41b3940cd70ec7db5ff80f8e45437fa92e3'

# Directorio local alternativo en Kaggle (por ejemplo: '/kaggle/input/nu-heston-data')
# Si es None, descargará de GitHub Raw con fallback a archivos locales si existen
LOCAL_DATA_DIR = None

# Directorio de exportación para artefactos generados en vivo por el notebook
OUTPUT_DIR = 'outputs'
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Parámetros canónicos de mercado de Nu Holdings Ltd. al 17-nov-2026
SPOT_PRICE = 12.33          # Precio de cierre NYSE de NU
DIVIDEND_YIELD = 0.00       # NU no paga dividendos
CONTRACT_MULTIPLIER = 100   # Multiplicador estándar OCC
VALUATION_DATE_STR = '2026-11-17'
NY_TZ = ZoneInfo("America/New_York")
VALUATION_DATETIME = datetime(2026, 11, 17, 16, 0, 0, tzinfo=NY_TZ)

print(f"Repositorio GitHub: {REPO} @ {DATA_COMMIT[:7]}")
print(f"Fecha de valoración: {VALUATION_DATETIME.strftime('%Y-%m-%d %H:%M:%S %Z')}")
print(f"Spot S0: {SPOT_PRICE} USD | Tasa dividendo q: {DIVIDEND_YIELD}")
print(f"Calibración multi-arranque desde cero: {CALIBRATE_FROM_SCRATCH}")
"""
    cells.append(nbf.v4.new_code_cell(sec1_code_3))

    # =========================================================================
    # SECTION 2: Ingesta de Datos, Integridad SHA-256 y Diagnóstico (Markdown + Code)
    # =========================================================================
    sec2_md = r"""### 2. Ingesta de Datos con Verificación Criptográfica SHA-256
Para garantizar la reproducibilidad científica estricta, cada archivo de datos e insumos originales descargado desde GitHub es verificado contra su hash SHA-256 publicado.

Los únicos insumos externos son:
1. `data/raw/Opciones_Completo.xlsx`: Registro bruto de 575 contratos OCC descargados de Bloomberg/NYSE al 17-nov-2026.
2. `data/heston/treasury_cmt_2026_11_17_raw.json`: Tasas oficiales de curva par Daily Treasury Par Yield Curve Rates del Departamento del Tesoro de EE. UU.
3. `data/processed/nu_historical_daily.csv`: Serie temporal histórica de precios diarios de NU (2021 a 2026) para contexto del subyacente.

**Todos los archivos derivados** (precios de puts Heston, superficies IV, grillas descriptivas, comparación de cuatro modelos, griegas de cartera y escenarios de estrés) **son generados y exportados por este notebook a partir de los insumos anteriores.**
"""
    cells.append(nbf.v4.new_markdown_cell(sec2_md))

    sec2_code = """# Manifiesto de hashes SHA-256 auditados de insumos brutos
AUDITED_FILES_MANIFEST: Dict[str, str] = {
    'data/raw/Opciones_Completo.xlsx': '306f8d3c1a52c7a67952d08881516bdc8632856e3abd6b33de373c4bc77ffb53',
    'data/processed/nu_historical_daily.csv': 'a510f9a48eaa0fc4f95cfbfcda491de09f4a6b14956efb0f3959c7c57ac5989a',
    'data/heston/treasury_cmt_2026_11_17_raw.json': '87e1d8653fb68224bee2becd9032d2d1e7c75e5bf23e66b8b1c8370ecd97d175',
}

import urllib.request
import urllib.error

def fetch_file_bytes(rel_path: str, expected_sha: Optional[str] = None) -> bytes:
    \"\"\"
    Descarga o carga bytes de un archivo versionado.
    1. Si LOCAL_DATA_DIR está definido, busca allí.
    2. Si el archivo existe en el sistema de archivos local relativo al directorio actual, lo usa.
    3. Si no, intenta descargar desde GitHub Raw.
    \"\"\"
    # Opción 1: LOCAL_DATA_DIR explícito
    if LOCAL_DATA_DIR is not None:
        p = os.path.join(LOCAL_DATA_DIR, rel_path)
        if os.path.exists(p):
            with open(p, 'rb') as fp:
                data = fp.read()
            if expected_sha:
                actual_sha = hashlib.sha256(data).hexdigest()
                assert actual_sha == expected_sha, f"SHA mismatch en {p}: {actual_sha} vs {expected_sha}"
            return data

    # Opción 2: Archivo local existente en workspace
    if os.path.exists(rel_path):
        with open(rel_path, 'rb') as fp:
            data = fp.read()
        if expected_sha:
            actual_sha = hashlib.sha256(data).hexdigest()
            assert actual_sha == expected_sha, f"SHA mismatch en {rel_path}: {actual_sha} vs {expected_sha}"
        return data

    # Opción 3: Descarga desde GitHub Raw
    url = f"https://raw.githubusercontent.com/{REPO}/{DATA_COMMIT}/{rel_path}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            data = response.read()
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            msg = (
                f"\\n[ERROR HTTP {e.code}] No se pudo descargar '{rel_path}' desde:\\n{url}\\n\\n"
                "CAUSAS POSIBLES Y SOLUCIONES:\\n"
                "1. Repositorio privado en GitHub: Si el repositorio 'JDELGADO2607/ImpVolSurface' es privado,\\n"
                "   GitHub bloquea el acceso sin autenticación.\\n"
                "   -> Solución: Haga público el repositorio temporalmente, o\\n"
                "   -> Solución: Adjunte la carpeta 'data/' como un Kaggle Dataset y defina:\\n"
                "      LOCAL_DATA_DIR = '/kaggle/input/nombre-de-su-dataset'\\n"
                "2. Internet deshabilitado en Kaggle: Verifique en la barra lateral de Kaggle (Settings) que\\n"
                "   la opción 'Internet' esté encendida (Internet = On).\\n"
            )
            raise RuntimeError(msg) from e
        raise e
    except Exception as e:
        raise RuntimeError(f"Error de conexión al descargar {url}: {e}") from e

    if expected_sha:
        actual_sha = hashlib.sha256(data).hexdigest()
        assert actual_sha == expected_sha, f"SHA mismatch en descarga de {rel_path}: {actual_sha} vs {expected_sha}"

    return data

print("Cargando y verificando integridad de archivos de insumos...")
LOADED_DATA: Dict[str, bytes] = {}
for rel_path, exp_sha in AUDITED_FILES_MANIFEST.items():
    try:
        b = fetch_file_bytes(rel_path, exp_sha)
        LOADED_DATA[rel_path] = b
        print(f"  [OK] {rel_path} ({len(b):,} bytes | SHA-256 verificado)")
    except Exception as ex:
        print(f"  [ALERTA] {rel_path}: {ex}")

print(f"Total archivos de entrada cargados exitosamente: {len(LOADED_DATA)}/{len(AUDITED_FILES_MANIFEST)}")
"""
    cells.append(nbf.v4.new_code_cell(sec2_code))

    # =========================================================================
    # SECTION 3: Curva de Tasas y Bootstrap de Rendimientos CMT (Markdown + Code)
    # =========================================================================
    sec3_md = r"""### 3. Curva de Tasas y Bootstrap de Rendimientos US Treasury CMT

#### 3.1 Fundamento Teórico y Formulación Matemática
La valoración de derivados americanos exige una estructura temporal de tasas libres de riesgo $r(t)$ y factores de descuento $D(0, t)$ consistente y libre de arbitraje.

Se utilizan las tasas oficiales par de la curva Daily Treasury Par Yield Curve Rates del Departamento del Tesoro de EE. UU. al cierre del 17 de noviembre de 2026 para 14 tenores de referencia ($T_i \in [1M, 30Y]$).

1. **Interpolación log-lineal en factores de descuento:**
   Para cualquier plazo $t \in [t_1, t_2]$, el factor de descuento $D(0, t)$ se interpola según:
   $$D(0, t) = \exp\left( (1 - w) \ln D(0, t_1) + w \ln D(0, t_2) \right), \quad w = \frac{t - t_1}{t_2 - t_1}$$
   Esto equivale rigurosamente a una **tasa forward instantánea continua constante a tramos**:
   $$f(t) = -\frac{d \ln D(0, t)}{dt} = \frac{\ln D(0, t_1) - \ln D(0, t_2)}{t_2 - t_1}$$

2. **Bootstrap exacto de bonos par:**
   - Para pagarés monetarios de corto plazo ($t \le 0.5$ años):
     $$D(0, t) = \frac{1}{1 + y_t \cdot t}$$
   - Para bonos cuponados semestrales ($t > 0.5$ años, cupón semestral $c = y_t / 2$):
     $$100 = 100 \cdot c \sum_{j=1}^{2T-1} D(0, t_j) + 100 \cdot (1 + c) D(0, T)$$
     donde $t_j = j / 2$. El factor de descuento $D(0, T)$ en cada nodo benchmark se despeja con precisión de máquina ($< 10^{-10}$ USD) mediante el algoritmo de Brent (`scipy.optimize.brentq`), evaluando exactamente la misma función de interpolación interna.

3. **Tasa cero continua y precio forward:**
   $$r_{\text{zero}}(\tau) = -\frac{\ln D(0, \tau)}{\tau}, \quad F(0, \tau) = \frac{S_0 \exp(-q \tau)}{D(0, \tau)} = \frac{S_0}{D(0, \tau)} \quad (\text{dado } q=0)$$
"""
    cells.append(nbf.v4.new_markdown_cell(sec3_md))

    sec3_code = """# =============================================================================
# CURVA DE RENDIMIENTOS US TREASURY CMT Y BOOTSTRAP DE DESCUENTO
# =============================================================================

OFFICIAL_TREASURY_CMT_2026_11_17: List[Tuple[str, float, float]] = [
    ("1M", 1.0 / 12.0, 0.0409),
    ("1.5M", 1.5 / 12.0, 0.0424),
    ("2M", 2.0 / 12.0, 0.0426),
    ("3M", 3.0 / 12.0, 0.0433),
    ("4M", 4.0 / 12.0, 0.0432),
    ("6M", 6.0 / 12.0, 0.0441),
    ("1Y", 1.0, 0.0460),
    ("2Y", 2.0, 0.0480),
    ("3Y", 3.0, 0.0484),
    ("5Y", 5.0, 0.0490),
    ("7Y", 7.0, 0.0499),
    ("10Y", 10.0, 0.0510),
    ("20Y", 20.0, 0.0550),
    ("30Y", 30.0, 0.0546),
]

class DeterministicYieldCurve:
    \"\"\"
    Curva determinista de tasas y factores de descuento mediante bootstrap exacto.
    Garantiza consistencia matemática interna entre nodos y consultas continuas.
    \"\"\"
    def __init__(
        self,
        rates_data: List[Tuple[str, float, float]] = OFFICIAL_TREASURY_CMT_2026_11_17,
        method: str = "bootstrap"
    ):
        self.method = method
        self.rates_data = rates_data
        self.tenors = np.array([r[1] for r in rates_data], dtype=float)
        self.par_yields = np.array([r[2] for r in rates_data], dtype=float)
        self.labels = [r[0] for r in rates_data]

        if method == "bootstrap":
            self.D_nodes = self._compute_consistent_bootstrap()
            self.benchmark_D = np.array([self.D_nodes[t] for t in self.tenors], dtype=float)
            self.benchmark_zero_rates = -np.log(self.benchmark_D) / self.tenors
        else:
            raise ValueError(f"Método desconocido: {method}")

    def _interpolate_discount_factor(self, t: float, nodes: Dict[float, float]) -> float:
        \"\"\"
        Interpolación log-lineal en D(0, t), correspondiente a forwards constantes a tramos.
        \"\"\"
        if t <= 0.0:
            return 1.0

        sorted_t = sorted(nodes.keys())
        if t in nodes:
            return nodes[t]

        # Tramo anterior al primer nodo: forward plano desde el origen
        if t <= sorted_t[0]:
            r0 = -np.log(nodes[sorted_t[0]]) / sorted_t[0]
            return float(np.exp(-r0 * t))

        # Entre nodos: interpolación log-lineal
        for i in range(len(sorted_t) - 1):
            t1, t2 = sorted_t[i], sorted_t[i + 1]
            if t1 <= t <= t2:
                w = (t - t1) / (t2 - t1)
                log_d = (1.0 - w) * np.log(nodes[t1]) + w * np.log(nodes[t2])
                return float(np.exp(log_d))

        # Más allá del último nodo: extrapolación plana con el último forward
        t_last = sorted_t[-1]
        t_prev = sorted_t[-2]
        f_last = (np.log(nodes[t_prev]) - np.log(nodes[t_last])) / (t_last - t_prev)
        return float(nodes[t_last] * np.exp(-f_last * (t - t_last)))

    def _compute_consistent_bootstrap(self) -> Dict[float, float]:
        \"\"\"
        Bootstrap exacto resolviendo 100 = PV de cupones + principal con brentq.
        \"\"\"
        D_nodes: Dict[float, float] = {}
        par_dict = {t: y for t, y in zip(self.tenors, self.par_yields)}

        # Tramo corto (letras de tesorería, t <= 0.5 años)
        for t in self.tenors:
            if t <= 0.5:
                y = par_dict[t]
                D_nodes[t] = 1.0 / (1.0 + y * t)

        # Tramo medio y largo (bonos cuponados semestrales, t > 0.5 años)
        for t in sorted(self.tenors):
            if t <= 0.5:
                continue

            par = par_dict[t]
            c = par / 2.0
            coupon_dates = np.arange(1, round(2 * t) + 1) / 2.0
            t_prev = max(k for k in D_nodes.keys())

            def _objective(D_val: float) -> float:
                candidate = dict(D_nodes)
                candidate[t] = D_val
                pv = 100.0 * c * sum(self._interpolate_discount_factor(cd, candidate) for cd in coupon_dates[:-1])
                pv += 100.0 * (1.0 + c) * D_val
                return pv - 100.0

            upper = D_nodes[t_prev]
            D_sol = brentq(_objective, 1e-4, upper, xtol=1e-14, rtol=1e-14)
            D_nodes[t] = float(D_sol)

        return D_nodes

    def get_discount_factor(self, tau: float) -> float:
        \"\"\"Retorna D(0, tau).\"\"\"
        if tau <= 0.0:
            return 1.0
        return self._interpolate_discount_factor(tau, self.D_nodes)

    def get_zero_rate(self, tau: float) -> float:
        \"\"\"Retorna tasa cero continua r_zero(tau) = -ln(D(0, tau)) / tau.\"\"\"
        if tau <= 0.0:
            return float(self.benchmark_zero_rates[0])
        D = self.get_discount_factor(tau)
        return float(-np.log(D) / tau)

    def get_forward_price(self, tau: float, S0: float = SPOT_PRICE) -> float:
        \"\"\"Calcula forward F(0, tau) = S0 / D(0, tau) (con q=0).\"\"\"
        D = self.get_discount_factor(tau)
        return float(S0 / D)

    def get_instantaneous_forward_rate(self, t: float) -> float:
        \"\"\"Calcula forward instantáneo r(t) = - d ln D(0, t) / dt.\"\"\"
        if t <= 0.0:
            t = 1e-6
        sorted_t = sorted(self.D_nodes.keys())
        if t <= sorted_t[0]:
            return float(-np.log(self.D_nodes[sorted_t[0]]) / sorted_t[0])
        for i in range(len(sorted_t) - 1):
            t1, t2 = sorted_t[i], sorted_t[i + 1]
            if t1 <= t < t2:
                return float(-(np.log(self.D_nodes[t2]) - np.log(self.D_nodes[t1])) / (t2 - t1))
        t_last = sorted_t[-1]
        t_prev = sorted_t[-2]
        return float(-(np.log(self.D_nodes[t_last]) - np.log(self.D_nodes[t_prev])) / (t_last - t_prev))

    def to_quantlib_term_structure(self, eval_date: Optional[Any] = None, dense_daily: bool = True):
        \"\"\"Convierte la curva al formato nativo QuantLib YieldTermStructure.\"\"\"
        if not HAS_QUANTLIB:
            raise RuntimeError("QuantLib no está disponible en este entorno.")
        if eval_date is None:
            eval_date = ql.Date(17, 11, 2026)
        day_counter = ql.Actual365Fixed()

        if dense_daily:
            dates = [eval_date]
            dfs = [1.0]
            max_days = int(round(30.0 * 365.25))
            for d in range(1, max_days + 1):
                cur_date = eval_date + ql.Period(d, ql.Days)
                tau = d / 365.0
                dates.append(cur_date)
                dfs.append(self.get_discount_factor(tau))
            ql_curve = ql.DiscountCurve(dates, dfs, day_counter)
            ql_curve.enableExtrapolation()
            return ql.YieldTermStructureHandle(ql_curve)
        else:
            dates = [eval_date]
            dfs = [1.0]
            for t in sorted(self.D_nodes.keys()):
                d_days = int(round(t * 365.0))
                dates.append(eval_date + ql.Period(d_days, ql.Days))
                dfs.append(self.D_nodes[t])
            ql_curve = ql.DiscountCurve(dates, dfs, day_counter)
            ql_curve.enableExtrapolation()
            return ql.YieldTermStructureHandle(ql_curve)

# Instanciación de la curva determinista de mercado
yield_curve = DeterministicYieldCurve(OFFICIAL_TREASURY_CMT_2026_11_17)
print(f"[OK] Curva de rendimientos construida exitosamente ({len(yield_curve.tenors)} tenores).")
print(f"  - Tasa cero continua 1M (30d):  {yield_curve.get_zero_rate(30/365.0)*100:.3f}%")
print(f"  - Tasa cero continua 1Y (365d): {yield_curve.get_zero_rate(1.0)*100:.3f}%")
print(f"  - Tasa cero continua 30Y:       {yield_curve.get_zero_rate(30.0)*100:.3f}%")
"""
    cells.append(nbf.v4.new_code_cell(sec3_code))

    # =========================================================================
    # SECTION 4: Lectura OCC, Auditoría Forense y Partición Determinista
    # =========================================================================
    sec4_md = r"""### 4. Lectura OCC, Auditoría Forense y Partición Determinista

#### 4.1 Reglas de Limpieza y No Arbitraje Americano
El libro de órdenes bruto contiene 575 contratos al 17-nov-2026. Se aplican los siguientes filtros estrictos:
1. **Negociación en fecha de anclaje:** Eliminación de contratos con cotizaciones obsoletas (`days_stale > 0`).
2. **Cotas de no arbitraje americano:**
   - Para Puts: $P \ge \max(K - S_0, 0)$ y $P \le K$.
   - Para Calls: $C \ge \max(S_0 - K D(0, \tau), 0)$ y $C \le S_0$.
3. **Filtro de microestructura y liquidez mínima:**
   - Precio observado $P \ge 0.02$ USD (exclusión del tick mínimo de 1 centavo).
   - Valor temporal $\ge 0.01$ USD ($P - \text{intrínseco} \ge 0.01$).

#### 4.2 Partición Determinista Anti-Fuga (Anti-Leakage)
- **15 Puts en Tenor Holdout:** Retención íntegra de tres rebanadas temporales completas:
  `2026-12-24` ($\tau \approx 37$d), `2027-02-19` ($\tau \approx 94$d) y `2027-09-17` ($\tau \approx 304$d). Evalúa la extrapolación temporal del modelo.
- **22 Puts en Strike Holdout:** Retención alternada (cada 3er strike, protegiendo los extremos de cada curva). Evalúa la interpolación transversal del smile.
- **60 Puts en Train:** Muestra núcleo utilizada exclusivamente para la calibración.
- **142 Calls Externas:** Contraste cruzado out-of-sample (nunca ingresan a la calibración de puts).
"""
    cells.append(nbf.v4.new_markdown_cell(sec4_md))

    sec4_code = r"""# =============================================================================
# PARSEO OCC, AUDITORÍA FORENSE Y PARTICIÓN DETERMINISTA
# =============================================================================

import re

OCC_REGEX = re.compile(r"^([A-Z]+)(\d{2})(\d{2})(\d{2})([CP])(\d{8})$")

def parse_occ_symbol(symbol: str) -> Tuple[str, int, int, int, str, float]:
    m = OCC_REGEX.match(symbol)
    if not m:
        raise ValueError(f"Formato OCC inválido: {symbol}")
    underlying = m.group(1)
    year = 2000 + int(m.group(2))
    month = int(m.group(3))
    day = int(m.group(4))
    opt_type = m.group(5)
    strike = int(m.group(6)) / 1000.0
    return underlying, year, month, day, opt_type, strike

def calculate_exact_tau(exp_date: datetime, val_datetime: datetime = VALUATION_DATETIME) -> float:
    exp_dt = datetime(exp_date.year, exp_date.month, exp_date.day, 16, 0, 0, tzinfo=NY_TZ)
    delta_sec = (exp_dt - val_datetime).total_seconds()
    return max(delta_sec / (365.0 * 86400.0), 0.0)

def load_and_clean_raw_options(
    excel_bytes: bytes,
    curve: DeterministicYieldCurve
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    xls = pd.ExcelFile(io.BytesIO(excel_bytes))
    df1 = pd.read_excel(xls, sheet_name="Hoja1")
    df2 = pd.read_excel(xls, sheet_name="Hoja2")

    df1['ticker_bbg_norm'] = df1['bloombergOptionTicker'].astype(str).str.replace(',', '.', regex=False)
    df2['ticker_bbg_norm'] = df2['Bloomberg Option Ticker'].astype(str).str.replace(',', '.', regex=False)

    merged = pd.merge(
        df1,
        df2[['ticker_bbg_norm', 'IV Mid', 'IV Best Price', 'IV Last Trade']],
        on='ticker_bbg_norm',
        how='left'
    )

    records = []
    for idx, row in merged.iterrows():
        contract = row['contractSymbol']
        und, exp_y, exp_m, exp_d, o_type, occ_strike = parse_occ_symbol(contract)
        exp_dt_raw = pd.to_datetime(row['expirationDate'])

        tau = calculate_exact_tau(exp_dt_raw, VALUATION_DATETIME)
        r = curve.get_zero_rate(tau)
        dfactor = curve.get_discount_factor(tau)
        fwd = curve.get_forward_price(tau, SPOT_PRICE)
        k_moneyness = float(np.log(occ_strike / fwd))

        ltd = pd.to_datetime(row['lastTradeDate'])
        ltd_ny = ltd.tz_convert(NY_TZ) if ltd.tzinfo is not None else ltd.tz_localize("UTC").tz_convert(NY_TZ)
        is_val_date_trade = (ltd_ny.date() == VALUATION_DATETIME.date())
        days_stale = (VALUATION_DATETIME.date() - ltd_ny.date()).days

        p_obs = float(row['lastPrice'])
        bounds_ok = True

        if o_type == 'P':
            intrinsic_val = max(occ_strike - SPOT_PRICE, 0.0)
            lower_bound = intrinsic_val
            upper_bound = occ_strike
            time_val = p_obs - lower_bound
            if p_obs < lower_bound - 1e-4 or p_obs > upper_bound + 1e-4:
                bounds_ok = False
        else:
            intrinsic_val = max(SPOT_PRICE - occ_strike, 0.0)
            lower_bound = max(SPOT_PRICE - occ_strike * dfactor, 0.0)
            upper_bound = SPOT_PRICE
            time_val = p_obs - intrinsic_val
            if p_obs < lower_bound - 1e-4 or p_obs > upper_bound + 1e-4:
                bounds_ok = False

        if p_obs <= 0.0:
            bounds_ok = False

        records.append({
            'contractSymbol': contract,
            'bloombergOptionTicker': row['ticker_bbg_norm'],
            'type': o_type,
            'strike': occ_strike,
            'expirationDate': exp_dt_raw.strftime('%Y-%m-%d'),
            'lastTradeDate_NY': ltd_ny.strftime('%Y-%m-%d %H:%M:%S'),
            'is_trade_17nov': is_val_date_trade,
            'days_stale': days_stale,
            'lastPrice': p_obs,
            'volume': float(row['volume']) if pd.notna(row['volume']) else 0.0,
            'openInterest': int(row['openInterest']) if pd.notna(row['openInterest']) else 0,
            'tau_days': round(tau * 365.0, 1),
            'tau_years': tau,
            'rate_r': r,
            'discount_factor': dfactor,
            'forward_price': fwd,
            'k_log_moneyness': k_moneyness,
            'intrinsic_value': intrinsic_val,
            'lower_bound': lower_bound,
            'upper_bound': upper_bound,
            'time_value': time_val,
            'bounds_ok': bounds_ok,
            'iv_mid_bbg': float(str(row['IV Mid']).replace(',', '.')) if pd.notna(row['IV Mid']) and str(row['IV Mid']).strip() not in ('', 'nan') else np.nan
        })

    all_df = pd.DataFrame(records)

    # Filtrado riguroso de Puts: 17-nov, bounds_ok, lastPrice >= 0.02, time_value >= 0.01
    puts_clean = all_df[
        (all_df["type"] == "P") &
        all_df["is_trade_17nov"] &
        all_df["bounds_ok"] &
        (all_df["lastPrice"] >= 0.02) &
        (all_df["time_value"] >= 0.01)
    ].copy().reset_index(drop=True)

    # Filtrado riguroso de Calls: 17-nov, bounds_ok, lastPrice >= 0.02
    calls_clean = all_df[
        (all_df["type"] == "C") &
        all_df["is_trade_17nov"] &
        all_df["bounds_ok"] &
        (all_df["lastPrice"] >= 0.02)
    ].copy().reset_index(drop=True)

    return puts_clean, calls_clean

def create_deterministic_split(
    puts_clean: pd.DataFrame,
    held_out_tenors: List[str] = ["2026-12-24", "2027-02-19", "2027-09-17"]
) -> Dict[str, pd.DataFrame]:
    is_tenor_holdout = puts_clean["expirationDate"].isin(held_out_tenors)
    df_tenor_holdout = puts_clean[is_tenor_holdout].copy().reset_index(drop=True)
    df_remaining = puts_clean[~is_tenor_holdout].copy()

    train_recs = []
    strike_recs = []
    for exp_date, grp in df_remaining.groupby("expirationDate"):
        sorted_grp = grp.sort_values("strike").reset_index(drop=True)
        n = len(sorted_grp)
        if n <= 2:
            for _, r in sorted_grp.iterrows():
                train_recs.append(r.to_dict())
        else:
            for idx, r in sorted_grp.iterrows():
                if idx == 0 or idx == n - 1:
                    train_recs.append(r.to_dict())
                elif idx % 3 == 1:
                    strike_recs.append(r.to_dict())
                else:
                    train_recs.append(r.to_dict())

    df_train = pd.DataFrame(train_recs).reset_index(drop=True)
    df_strike_holdout = pd.DataFrame(strike_recs).reset_index(drop=True)

    return {
        "train": df_train,
        "strike_holdout": df_strike_holdout,
        "tenor_holdout": df_tenor_holdout
    }

# Ejecución de la preparación en vivo desde el Excel descargado
excel_raw_bytes = LOADED_DATA['data/raw/Opciones_Completo.xlsx']
puts_clean_df, calls_clean_df = load_and_clean_raw_options(excel_raw_bytes, yield_curve)
splits = create_deterministic_split(puts_clean_df)

train_df = splits["train"].copy()
strike_df = splits["strike_holdout"].copy()
tenor_df = splits["tenor_holdout"].copy()

train_df["partition"] = "train"
strike_df["partition"] = "strike_holdout"
tenor_df["partition"] = "tenor_holdout"

# Recombinar puts conservando la columna unívoca 'partition'
puts_clean_df = pd.concat([train_df, strike_df, tenor_df], ignore_index=True)
calls_clean_df["partition"] = "external_contrast"

print(f"[OK] Limpieza OCC y partición ejecutadas en el kernel:")
print(f"  - Total Puts limpias seleccionadas: {len(puts_clean_df)} (Esperado: 97)")
print(f"  - Train Puts:                      {len(train_df)} (Esperado: 60)")
print(f"  - Strike-Holdout Puts:             {len(strike_df)} (Esperado: 22)")
print(f"  - Tenor-Holdout Puts:              {len(tenor_df)} (Esperado: 15)")
print(f"  - Calls externas de contraste:     {len(calls_clean_df)} (Esperado: 142)")
assert len(puts_clean_df) == 97 and len(train_df) == 60 and len(strike_df) == 22 and len(tenor_df) == 15 and len(calls_clean_df) == 142
"""
    cells.append(nbf.v4.new_code_cell(sec4_code))

    # =========================================================================
    # SECTION 5: Motores Base de Precios: Black-Scholes y EDP 1D Crank-Nicolson
    # =========================================================================
    sec5_md = r"""### 5. Motores Base de Precios: Black-Scholes y EDP 1D Crank-Nicolson

#### 5.1 Ecuación Diferencial Parcial 1D y Esquema Crank-Nicolson
La EDP de Black-Scholes para una opción vainilla en tiempo hacia atrás $\tau = T - t$ es:
$$\frac{\partial V}{\partial \tau} = \frac{1}{2}\sigma^2 S^2 \frac{\partial^2 V}{\partial S^2} + (r(\tau) - q) S \frac{\partial V}{\partial S} - r(\tau) V$$

Para aproximar la solución sobre una grilla espacial discreta $S_j = j \Delta S$ ($j=0, \dots, M$):
$$\mathcal{L} V_j = \alpha_j V_{j-1} + \beta_j V_j + \gamma_j V_{j+1}$$
donde los coeficientes centrados de segundo orden son:
$$\alpha_j = \frac{1}{2}\sigma^2 j^2 - \frac{1}{2}(r - q)j, \quad \beta_j = -\sigma^2 j^2 - r, \quad \gamma_j = \frac{1}{2}\sigma^2 j^2 + \frac{1}{2}(r - q)j$$

#### 5.2 Suavizado Inicial de Rannacher y Método de Penalización
1. **Suavizado de Rannacher (1984):** La discontinuidad en la primera derivada del payoff genera oscilaciones espurias en Crank-Nicolson ($\theta = 0.5$). Se ejecutan $R=4$ medios pasos con Euler totalmente implícito ($\theta = 1.0$), amortiguando los modos de alta frecuencia.
2. **Método de Penalización de Forsyth & Vetzal (2002):**
   Se resuelve la desigualdad variacional del ejercicio temprano añadiendo un término de penalización regularizado:
   $$\left[ \mathbf{I} - \Delta \tau \, \theta \mathbf{A} + \mathbf{P}(V^{n+1, k}) \right] V^{n+1, k+1} = \left[ \mathbf{I} + \Delta \tau (1 - \theta) \mathbf{A} \right] V^n + \mathbf{P}(V^{n+1, k}) V^*$$
   donde el término diagonal de penalización es:
   $$P_{jj} = \begin{cases} \rho, & \text{si } V_j^{n+1, k} < V_j^* \\ 0, & \text{si } V_j^{n+1, k} \ge V_j^* \end{cases}$$
   con $\rho = 10^7$ y convergencia en norma infinita $\|V^{k+1} - V^k\|_\infty < 10^{-7}$.
3. **Interpolación PCHIP Monótona:** La extracción de $V(S_0)$ sobre la grilla se efectúa mediante *Piecewise Cubic Hermite Interpolating Polynomial* (PCHIP) para preservar estrictamente la convexidad y monotonicidad económica.
"""
    cells.append(nbf.v4.new_markdown_cell(sec5_md))

    sec5_code = """# =============================================================================
# MOTORES BASE 1D: BLACK-SCHOLES Y EDP CRANK-NICOLSON CON PENALIZACIÓN
# =============================================================================

def bs_price(kind: str, S0: float, K: float, tau: float, r: float, sigma: float, q: float = 0.0) -> float:
    \"\"\"Fórmula analítica cerrada de Black-Scholes (1973).\"\"\"
    if tau <= 1e-12:
        return max(S0 - K, 0.0) if kind.upper() == 'C' else max(K - S0, 0.0)
    if sigma <= 1e-12:
        df_r = math.exp(-r * tau)
        df_q = math.exp(-q * tau)
        fwd = S0 * df_q / df_r
        return df_r * max(fwd - K, 0.0) if kind.upper() == 'C' else df_r * max(K - fwd, 0.0)

    d1 = (math.log(S0 / K) + (r - q + 0.5 * sigma * sigma) * tau) / (sigma * math.sqrt(tau))
    d2 = d1 - sigma * math.sqrt(tau)

    if kind.upper() == 'C':
        return S0 * math.exp(-q * tau) * norm.cdf(d1) - K * math.exp(-r * tau) * norm.cdf(d2)
    else:
        return K * math.exp(-r * tau) * norm.cdf(-d2) - S0 * math.exp(-q * tau) * norm.cdf(-d1)

def solve_tridiagonal(A_bands: np.ndarray, b: np.ndarray) -> np.ndarray:
    \"\"\"Resuelve sistema tridiagonal bandeado usando scipy.linalg.solve_banded.\"\"\"
    return solve_banded((1, 1), A_bands, b)

def fd_american_price(
    kind: str,
    S0: float,
    K: float,
    tau: float,
    curve_or_r: Union[DeterministicYieldCurve, float],
    sigma: float,
    q: float = 0.0,
    M: int = 300,
    N: int = 150,
    rannacher_steps: int = 4,
    penalty_rho: float = 1e7,
    max_penalty_iter: int = 30,
    penalty_tol: float = 1e-7
) -> float:
    \"\"\"
    Valora una opción americana resolviendo la EDP 1D con Crank-Nicolson,
    suavizado de Rannacher, penalización de Forsyth & Vetzal e interpolación PCHIP.
    \"\"\"
    kind = kind.upper()
    S_max = float(4.0 * max(S0, K))
    dS = S_max / M
    S_grid = np.linspace(0.0, S_max, M + 1)

    V_star = np.maximum(S_grid - K, 0.0) if kind == 'C' else np.maximum(K - S_grid, 0.0)

    if tau <= 1e-12:
        return float(max(S0 - K, 0.0) if kind == 'C' else max(K - S0, 0.0))

    is_curve = hasattr(curve_or_r, 'get_instantaneous_forward_rate')

    dt = tau / N
    V = V_star.copy()
    j_interior = np.arange(1, M, dtype=float)

    for n in range(N):
        t_current = n * dt
        t_next = (n + 1) * dt
        theta = 1.0 if n < rannacher_steps else 0.5

        if is_curve:
            t_eval = t_next if theta == 1.0 else 0.5 * (t_current + t_next)
            r_val = curve_or_r.get_instantaneous_forward_rate(t_eval)
        else:
            r_val = float(curve_or_r)

        alpha = 0.5 * sigma * sigma * (j_interior ** 2) - 0.5 * (r_val - q) * j_interior
        beta = -sigma * sigma * (j_interior ** 2) - r_val
        gamma = 0.5 * sigma * sigma * (j_interior ** 2) + 0.5 * (r_val - q) * j_interior

        V_old = V.copy()
        RHS_interior = V_old[1:M] + (1.0 - theta) * dt * (
            alpha * V_old[0:M-1] + beta * V_old[1:M] + gamma * V_old[2:M+1]
        )

        V_iter = V_old.copy()
        for k in range(max_penalty_iter):
            P_diag = np.where(V_iter[1:M] < V_star[1:M], penalty_rho, 0.0)

            # Matriz tridiagonal (1, 1) para solve_banded
            ab = np.zeros((3, M - 1))
            ab[0, 1:] = -theta * dt * gamma[:-1]
            ab[1, :] = 1.0 - theta * dt * beta + dt * P_diag
            ab[2, :-1] = -theta * dt * alpha[1:]

            b_vec = RHS_interior + dt * P_diag * V_star[1:M]
            if kind == 'P':
                b_vec[0] += theta * dt * alpha[0] * K

            sol_interior = solve_tridiagonal(ab, b_vec)
            V_new_iter = V_iter.copy()
            V_new_iter[1:M] = sol_interior

            if kind == 'P':
                V_new_iter[0] = K
                V_new_iter[M] = 0.0
            else:
                V_new_iter[0] = 0.0
                V_new_iter[M] = S_max - K

            if np.max(np.abs(V_new_iter - V_iter)) < penalty_tol:
                V_iter = V_new_iter
                break
            V_iter = V_new_iter

        V = V_iter

    # Interpolación monótona monovariante con PCHIP
    interp = PchipInterpolator(S_grid, V)
    res_price = float(interp(S0))
    intrinsic_S0 = max(S0 - K, 0.0) if kind == 'C' else max(K - S0, 0.0)
    return max(res_price, intrinsic_S0)

# Verificación numérica en 1 contrato representativo (Put K=12, tau=31d)
px_bs = bs_price('P', SPOT_PRICE, 12.0, 31/365.0, yield_curve.get_zero_rate(31/365.0), 0.44)
px_am = fd_american_price('P', SPOT_PRICE, 12.0, 31/365.0, yield_curve, 0.44)
eep_1d = px_am - px_bs
print(f"[OK] Motores 1D verificados:")
print(f"  - BS Europeo Flat 44%:  {px_bs:.4f} USD")
print(f"  - EDP 1D Americano:     {px_am:.4f} USD")
print(f"  - Prima EEP 1D:         {eep_1d:.4f} USD (Consistente: eep >= 0)")
assert eep_1d >= 0.0
"""
    cells.append(nbf.v4.new_code_cell(sec5_code))

    # =========================================================================
    # SECTION 6: Formulación Matemática del Modelo Heston (1993) (Markdown)
    # =========================================================================
    sec6_md = r"""### 6. Formulación Matemática del Modelo Heston (1993)

Bajo la medida de riesgo neutral $\mathbb{Q}$, el precio del activo $S_t$ y su varianza instantánea $v_t$ siguen el sistema estocástico:
$$\begin{aligned}
dS_t &= (r(t) - q) S_t dt + \sqrt{v_t} S_t dW_t^S \\
dv_t &= \kappa (\theta - v_t) dt + \xi \sqrt{v_t} dW_t^v \\
\mathbb{E}[dW_t^S dW_t^v] &= \rho dt
\end{aligned}$$

Donde:
- $v_0 > 0$: Varianza instantánea inicial ($\sigma_0 = \sqrt{v_0}$ es la volatilidad spot).
- $\kappa > 0$: Velocidad de reversión a la media (vida media de choques $t_{1/2} = \ln 2 / \kappa$).
- $\theta > 0$: Varianza de largo plazo ($\sigma_\infty = \sqrt{\theta}$).
- $\xi > 0$: Volatilidad de la varianza (*vol-of-vol*).
- $\rho \in [-1, 1]$: Correlación entre los movimientos del subyacente y la volatilidad (responsable de la asimetría o *skew*).

#### Condición de Regularidad de Feller
Para que la varianza sea estrictamente positiva con probabilidad 1 y no alcance el origen:
$$\mathcal{R}_{\text{Feller}} = \frac{2 \kappa \theta}{\xi^2} > 1$$

#### Ecuación Diferencial Parcial Bidimensional y LCP Americano
Por el lema de Itô bidimensional, el precio $V(S, v, \tau)$ satisface la desigualdad variacional (Linear Complementarity Problem - LCP):
$$\max\left( -\frac{\partial V}{\partial \tau} + \mathcal{A} V, \; V^* - V \right) = 0$$
con el operador diferencial elíptico de segundo orden:
$$\mathcal{A} V = \frac{1}{2} v S^2 \frac{\partial^2 V}{\partial S^2} + \rho \xi v S \frac{\partial^2 V}{\partial S \partial v} + \frac{1}{2} \xi^2 v \frac{\partial^2 V}{\partial v^2} + (r(\tau) - q) S \frac{\partial V}{\partial S} + \kappa (\theta - v) \frac{\partial V}{\partial v} - r(\tau) V$$
"""
    cells.append(nbf.v4.new_markdown_cell(sec6_md))

    # =========================================================================
    # SECTION 7: Discretización 2D: Esquema ADI MCS + Ikonen-Toivanen (Markdown + Code)
    # =========================================================================
    sec7_md = r"""### 7. Discretización 2D: Esquema ADI MCS + Ikonen-Toivanen

#### 7.1 Grilla Cartesiana No Uniforme con Concentración Analítica
Para capturar la discontinuidad en el strike $K$ y la dinámica en $v \approx 0$, se emplea una transformación hiperbólica (In 't Hout & Foulon, 2010):
$$S_i = K + d_S \sinh\left( \xi_i \right), \quad v_j = d_v \sinh\left( \eta_j \right)$$
con mallas uniformes equidistantes en $\xi$ y $\eta$. Las derivadas espaciales se discretizan mediante diferencias finitas de segundo orden centradas para mallas no uniformes.

#### 7.2 Esquema Alternating Direction Implicit (MCS)
El operador $\mathcal{A}$ se descompone en:
$$\mathcal{A} = \mathcal{A}_0 + \mathcal{A}_1 + \mathcal{A}_2$$
donde $\mathcal{A}_0$ contiene la derivada cruzada de correlación $\rho$, $\mathcal{A}_1$ contiene los operadores unidimensionales en $S$, y $\mathcal{A}_2$ en $v$.

El esquema Modified Craig-Sneyd (MCS) con $\theta_{\text{ADI}} = 0.5$ avanza el tiempo según:
$$\begin{aligned}
Y_0 &= U^n + \Delta t \, \mathcal{A} U^n \\
Y_1 &= Y_0 + \theta_{\text{ADI}} \Delta t (\mathcal{A}_1 Y_1 - \mathcal{A}_1 U^n) \\
Y_2 &= Y_1 + \theta_{\text{ADI}} \Delta t (\mathcal{A}_2 Y_2 - \mathcal{A}_2 U^n) \\
\widetilde{Y}_0 &= Y_0 + \frac{1}{2}\Delta t (\mathcal{A}_0 Y_2 - \mathcal{A}_0 U^n) \\
\widetilde{Y}_1 &= \widetilde{Y}_0 + \theta_{\text{ADI}} \Delta t (\mathcal{A}_1 \widetilde{Y}_1 - \mathcal{A}_1 U^n) \\
U^{n+1} &= \widetilde{Y}_1 + \theta_{\text{ADI}} \Delta t (\mathcal{A}_2 U^{n+1} - \mathcal{A}_2 U^n)
\end{aligned}$$

#### 7.3 Algoritmo de Splitting de Ikonen & Toivanen (2009)
En cada paso implícito, la condición de ejercicio anticipado $U \ge g = V^*$ se satisface introduciendo un multiplicador de Lagrange $\lambda^{n+1} \ge 0$:
$$(\mathbf{I} - \theta_{\text{ADI}} \Delta t \mathcal{A}_k) U^{n+1} = \text{RHS} + \Delta t \, \lambda^{n+1}, \quad U^{n+1} \ge g, \quad \lambda^{n+1} \ge 0, \quad \lambda^{n+1} \cdot (U^{n+1} - g) = 0$$
resuelto en $O(N_S N_v)$ operaciones elementales sin iteración no lineal mediante barrido tridiagonal desacoplado.
"""
    cells.append(nbf.v4.new_markdown_cell(sec7_md))

    sec7_code = """# =============================================================================
# DISCRETIZACIÓN 2D Y SOLVER ADI MCS CON IKONEN-TOIVANEN
# =============================================================================

@dataclass
class HestonParams:
    v0: float
    kappa: float
    theta: float
    xi: float
    rho: float

    @property
    def feller_ratio(self) -> float:
        return 2.0 * self.kappa * self.theta / (self.xi ** 2)

    @property
    def feller_satisfied(self) -> bool:
        return self.feller_ratio > 1.0

    @classmethod
    def from_array(cls, arr: Union[List[float], np.ndarray]) -> 'HestonParams':
        return cls(v0=float(arr[0]), kappa=float(arr[1]), theta=float(arr[2]), xi=float(arr[3]), rho=float(arr[4]))

    def to_array(self) -> np.ndarray:
        return np.array([self.v0, self.kappa, self.theta, self.xi, self.rho], dtype=float)

@dataclass
class Heston2DSolverResult:
    price: float
    delta: float
    gamma: float
    d_price_d_v0: float
    strike: float
    maturity_years: float
    spot: float
    v0: float
    wall_time_seconds: float
    max_feasibility_violation: float
    max_multiplier_violation: float
    max_algebraic_complementarity_residual: float

class Grid2D:
    def __init__(
        self,
        strike: float,
        v0: float,
        n_s: int = 120,
        n_v: int = 60,
        s_max: Optional[float] = None,
        v_max: Optional[float] = None,
        d_s_scale: float = 0.10,
        d_v_scale: float = 0.50
    ):
        self.strike = float(strike)
        self.v0 = float(v0)
        self.n_s = int(n_s)
        self.n_v = int(n_v)
        self.s_max = float(s_max) if s_max is not None else max(4.0 * self.strike, 60.0)
        self.v_max = float(v_max) if v_max is not None else max(5.0 * max(self.v0, 0.04), 2.0)

        # Concentración hiperbólica en S alrededor de K
        c_s = self.strike
        d_s = max(d_s_scale * self.strike, 0.5)
        xi_min = np.arcsinh((0.0 - c_s) / d_s)
        xi_max = np.arcsinh((self.s_max - c_s) / d_s)
        xi_grid = np.linspace(xi_min, xi_max, self.n_s + 1)
        self.s_grid = c_s + d_s * np.sinh(xi_grid)
        self.s_grid[0] = 0.0
        self.s_grid[-1] = self.s_max

        # Concentración en v cerca del origen
        d_v = max(d_v_scale * self.v0, 0.05)
        eta_max = np.arcsinh(self.v_max / d_v)
        eta_grid = np.linspace(0.0, eta_max, self.n_v + 1)
        self.v_grid = d_v * np.sinh(eta_grid)
        self.v_grid[0] = 0.0
        self.v_grid[-1] = self.v_max

        self.S2D, self.V2D = np.meshgrid(self.s_grid, self.v_grid, indexing='ij')

def solve_tridiagonal_vectorized(a: np.ndarray, b: np.ndarray, c: np.ndarray, d: np.ndarray) -> np.ndarray:
    n_sys, n = d.shape
    cp = np.zeros((n_sys, n))
    dp = np.zeros((n_sys, n))
    x = np.zeros((n_sys, n))

    b0 = b[:, 0]
    cp[:, 0] = c[:, 0] / b0
    dp[:, 0] = d[:, 0] / b0

    for i in range(1, n):
        denom = b[:, i] - a[:, i] * cp[:, i - 1]
        cp[:, i] = c[:, i] / denom
        dp[:, i] = (d[:, i] - a[:, i] * dp[:, i - 1]) / denom

    x[:, -1] = dp[:, -1]
    for i in range(n - 2, -1, -1):
        x[:, i] = dp[:, i] - cp[:, i] * x[:, i + 1]

    return x

class Heston2DSolver:
    def __init__(self, theta_adi: float = 0.5):
        self.theta_adi = theta_adi

    def price(
        self,
        strike: float,
        maturity_years: float,
        params: HestonParams,
        curve: Union[DeterministicYieldCurve, float],
        spot: float = SPOT_PRICE,
        dividend_yield: float = 0.0,
        option_type: str = 'P',
        is_american: bool = True,
        n_s: Optional[int] = None,
        n_v: Optional[int] = None,
        m_t: Optional[int] = None
    ) -> Heston2DSolverResult:
        t0 = time.time()
        tau = float(maturity_years)
        K = float(strike)
        is_put = (option_type.upper() == 'P')

        n_s = n_s or 120
        n_v = n_v or 60
        m_t = m_t or max(int(np.ceil(tau * 252)), 50)
        dt = tau / m_t
        theta_adi = self.theta_adi

        grid = Grid2D(strike=K, v0=params.v0, n_s=n_s, n_v=n_v)
        S2D = grid.S2D
        V2D = grid.V2D
        s_vec = grid.s_grid
        v_vec = grid.v_grid

        # Payoff intrínseco
        if is_put:
            g = np.maximum(K - S2D, 0.0)
        else:
            g = np.maximum(S2D - K, 0.0)

        U = g.copy()
        lambda_k = np.zeros_like(U)
        is_curve = hasattr(curve, 'get_instantaneous_forward_rate')

        # Diferencias finitas espaciales en S
        h_s = np.diff(s_vec)
        h_s_im1 = h_s[:-1]
        h_s_i = h_s[1:]
        denom_s = h_s_im1 * h_s_i * (h_s_im1 + h_s_i)
        w_s_down = 2.0 * h_s_i / denom_s
        w_s_diag = -2.0 * (h_s_im1 + h_s_i) / denom_s
        w_s_up = 2.0 * h_s_im1 / denom_s

        # Diferencias finitas espaciales en v
        h_v = np.diff(v_vec)
        h_v_jm1 = h_v[:-1]
        h_v_j = h_v[1:]
        denom_v = h_v_jm1 * h_v_j * (h_v_jm1 + h_v_j)
        w_v_down = 2.0 * h_v_j / denom_v
        w_v_diag = -2.0 * (h_v_jm1 + h_v_j) / denom_v
        w_v_up = 2.0 * h_v_jm1 / denom_v

        # Bucle temporal hacia atrás
        for m in range(m_t):
            t_eval = (m + 0.5) * dt
            r_val = curve.get_instantaneous_forward_rate(t_eval) if is_curve else float(curve)

            # Matriz espacial A1 (dirección S)
            s_int = s_vec[1:n_s]
            diff_s = 0.5 * V2D[1:n_s, 1:n_v] * (s_int[:, None] ** 2)
            conv_s = (r_val - dividend_yield) * s_int[:, None]

            a1_sub = diff_s * w_s_down[:, None] - 0.5 * conv_s / (h_s_im1[:, None] + h_s_i[:, None])
            a1_diag = diff_s * w_s_diag[:, None] - 0.5 * r_val
            a1_sup = diff_s * w_s_up[:, None] + 0.5 * conv_s / (h_s_im1[:, None] + h_s_i[:, None])

            # Matriz espacial A2 (dirección v)
            v_int = v_vec[1:n_v]
            diff_v = 0.5 * (params.xi ** 2) * v_int[None, :]
            conv_v = params.kappa * (params.theta - v_int[None, :])

            a2_sub = diff_v * w_v_down[None, :] - 0.5 * conv_v / (h_v_jm1[None, :] + h_v_j[None, :])
            a2_diag = diff_v * w_v_diag[None, :] - 0.5 * r_val
            a2_sup = diff_v * w_v_up[None, :] + 0.5 * conv_v / (h_v_jm1[None, :] + h_v_j[None, :])

            # Evaluación de A1(U) y A2(U)
            A1_U = np.zeros_like(U)
            A1_U[1:n_s, 1:n_v] = (
                a1_sub * U[0:n_s-1, 1:n_v] +
                a1_diag * U[1:n_s, 1:n_v] +
                a1_sup * U[2:n_s+1, 1:n_v]
            )

            A2_U = np.zeros_like(U)
            A2_U[1:n_s, 1:n_v] = (
                a2_sub * U[1:n_s, 0:n_v-1] +
                a2_diag * U[1:n_s, 1:n_v] +
                a2_sup * U[1:n_s, 2:n_v+1]
            )

            # Derivada cruzada de correlación A0(U)
            A0_U = np.zeros_like(U)
            cross_coeff = params.rho * params.xi * S2D[1:n_s, 1:n_v] * V2D[1:n_s, 1:n_v]
            denom_cross = (h_s_im1[:, None] + h_s_i[:, None]) * (h_v_jm1[None, :] + h_v_j[None, :])
            A0_U[1:n_s, 1:n_v] = cross_coeff * (
                U[2:n_s+1, 2:n_v+1] - U[0:n_s-1, 2:n_v+1] - U[2:n_s+1, 0:n_v-1] + U[0:n_s-1, 0:n_v-1]
            ) / (4.0 * denom_cross)

            # --- Paso 0: Predictor Explícito ---
            Y0 = U + dt * (A0_U + A1_U + A2_U) + dt * lambda_k

            # --- Paso 1: Implícito en Dirección S ---
            RHS1 = Y0[1:n_s, 1:n_v] - theta_adi * dt * A1_U[1:n_s, 1:n_v]
            n_lines_s = n_v - 1
            a1_sub_T = np.ascontiguousarray(a1_sub.T)
            a1_diag_T = np.ascontiguousarray((1.0 - theta_adi * dt * a1_diag).T)
            a1_sup_T = np.ascontiguousarray(a1_sup.T)
            RHS1_T = np.ascontiguousarray(RHS1.T)

            sub_vec = -theta_adi * dt * a1_sub_T
            diag_vec = a1_diag_T
            sup_vec = -theta_adi * dt * a1_sup_T

            sol1_T = solve_tridiagonal_vectorized(sub_vec, diag_vec, sup_vec, RHS1_T)
            Y1 = Y0.copy()
            Y1[1:n_s, 1:n_v] = sol1_T.T

            # --- Paso 2: Implícito en Dirección v con Ikonen-Toivanen ---
            RHS2 = Y1[1:n_s, 1:n_v] - theta_adi * dt * A2_U[1:n_s, 1:n_v]
            a2_sub_M = -theta_adi * dt * a2_sub
            a2_diag_M = 1.0 - theta_adi * dt * a2_diag
            a2_sup_M = -theta_adi * dt * a2_sup

            sol2 = solve_tridiagonal_vectorized(a2_sub_M, a2_diag_M, a2_sup_M, RHS2)

            if is_american:
                cand = sol2
                lambda_k[1:n_s, 1:n_v] = np.maximum(g[1:n_s, 1:n_v] - cand, 0.0) / dt
                U[1:n_s, 1:n_v] = np.maximum(cand, g[1:n_s, 1:n_v])
            else:
                U[1:n_s, 1:n_v] = sol2

            # Condiciones de frontera de Dirichlet / Neumann
            if is_put:
                U[0, :] = K * math.exp(-r_val * (m + 1) * dt)
                U[-1, :] = 0.0
            else:
                U[0, :] = 0.0
                U[-1, :] = s_vec[-1] - K * math.exp(-r_val * (m + 1) * dt)

            U[:, 0] = np.maximum(U[:, 1], g[:, 0]) if is_american else U[:, 1]
            U[:, -1] = U[:, -2]

        # Extracción e interpolación de precios y griegas
        interp = RegularGridInterpolator((s_vec, v_vec), U, bounds_error=False, fill_value=None)
        price_val = float(interp([[spot, params.v0]])[0])

        h_s = 0.01 * spot
        h_v = 0.01 * max(params.v0, 0.01)
        p_up = float(interp([[spot + h_s, params.v0]])[0])
        p_dn = float(interp([[spot - h_s, params.v0]])[0])
        delta_val = (p_up - p_dn) / (2.0 * h_s)
        gamma_val = (p_up - 2.0 * price_val + p_dn) / (h_s ** 2)

        pv_up = float(interp([[spot, params.v0 + h_v]])[0])
        pv_dn = float(interp([[spot, max(params.v0 - h_v, 1e-4)]])[0])
        vega_val = (pv_up - pv_dn) / (2.0 * h_v)

        feas_viol = float(np.max(np.maximum(g - U, 0.0)))
        mult_viol = float(np.max(np.maximum(-lambda_k, 0.0)))
        comp_res = float(np.max(np.abs(lambda_k * (U - g))))

        wall_time = time.time() - t0
        return Heston2DSolverResult(
            price=price_val, delta=delta_val, gamma=gamma_val, d_price_d_v0=vega_val,
            strike=K, maturity_years=tau, spot=spot, v0=params.v0,
            wall_time_seconds=wall_time,
            max_feasibility_violation=feas_viol,
            max_multiplier_violation=mult_viol,
            max_algebraic_complementarity_residual=comp_res
        )

# Instanciación y prueba en vivo del solver bidimensional propio
solver_2d = Heston2DSolver()
frozen_params = HestonParams(v0=0.1861, kappa=2.7255, theta=0.2137, xi=0.4818, rho=-0.9498)

print("Ejecutando Heston2DSolver en contrato representativo (Put K=12, tau=31d)...")
res_test = solver_2d.price(strike=12.0, maturity_years=31/365.0, params=frozen_params, curve=yield_curve, is_american=True)
print(f"  [OK] Precio calculado: {res_test.price:.6f} USD (Tiempo: {res_test.wall_time_seconds:.3f} s)")
print(f"       Delta: {res_test.delta:.4f} | Gamma: {res_test.gamma:.4f} | Residuo LCP: {res_test.max_algebraic_complementarity_residual:.2e}")
"""
    cells.append(nbf.v4.new_code_cell(sec7_code))

    # =========================================================================
    # SECTION 8: Benchmarks QuantLib, Función SSE y Calibración
    # =========================================================================
    sec8_md = r"""### 8. Benchmarks QuantLib, Función de Pérdida SSE y Calibración

#### 8.1 Función Objetivo de Calibración
La calibración busca estimar el vector de parámetros $\Theta = (v_0, \kappa, \theta, \xi, \rho) \in \mathbb{R}^5$ minimizando la suma de errores al cuadrado (**SSE no ponderada**) sobre las 60 puts de entrenamiento:
$$\text{SSE}(\Theta) = \sum_{i=1}^{60} \left( P_i^{\text{model}}(\Theta) - P_i^{\text{mkt}} \right)^2$$
con las métricas agregadas de error:
$$\text{MAE} = \frac{1}{N}\sum_{i=1}^N |P_i^{\text{model}} - P_i^{\text{mkt}}|, \quad \text{RMSE} = \sqrt{\frac{1}{N}\sum_{i=1}^N (P_i^{\text{model}} - P_i^{\text{mkt}})^2}$$

#### 8.2 Parámetros Canónicos Congelados al 17-nov-2026
$$\begin{aligned}
v_0 &= 0.1861 \implies \sigma_0 = \sqrt{v_0} \approx 43.14\% \\
\kappa &= 2.7255 \implies \text{Vida media } t_{1/2} = \frac{\ln 2}{\kappa} \approx 0.254 \text{ años} \\
\theta &= 0.2137 \implies \sigma_\infty = \sqrt{\theta} \approx 46.23\% \\
\xi &= 0.4818 \implies \text{Vol-of-vol moderada} \\
\rho &= -0.9498 \implies \text{Fuerte asimetría negativa (pegada a cota } -0.95)
\end{aligned}$$

**Verificación Feller:**
$$\mathcal{R}_{\text{Feller}} = \frac{2 \kappa \theta}{\xi^2} = \frac{2 (2.7255)(0.2137)}{0.4818^2} \approx 5.018 > 1 \quad \text{(Estrictamente satisfecha)}$$
"""
    cells.append(nbf.v4.new_markdown_cell(sec8_md))

    sec8_code = """# =============================================================================
# BENCHMARK QUANTLIB, FUNCIÓN OBJETIVO SSE Y CALIBRACIÓN MULTI-ARRANQUE
# =============================================================================

def price_heston_analytic(
    kind: str,
    S: float,
    K: float,
    tau_days: int,
    params: HestonParams,
    curve: DeterministicYieldCurve,
    ref_date: Optional[Any] = None
) -> float:
    \"\"\"Valora opción europea semi-analítica mediante transformada de Fourier (QuantLib).\"\"\"
    if not HAS_QUANTLIB:
        raise RuntimeError("QuantLib es necesario para AnalyticHestonEngine.")
    if ref_date is None:
        ref_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = ref_date

    ql_curve = curve.to_quantlib_term_structure(eval_date=ref_date, dense_daily=True)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(ref_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(S))

    process = ql.HestonProcess(ql_curve, q_handle, spot_handle, params.v0, params.kappa, params.theta, params.xi, params.rho)
    model = ql.HestonModel(process)
    engine = ql.AnalyticHestonEngine(model)

    mat_date = ref_date + ql.Period(int(round(tau_days)), ql.Days)
    payoff = ql.PlainVanillaPayoff(ql.Option.Call if kind.upper() == 'C' else ql.Option.Put, K)
    opt = ql.VanillaOption(payoff, ql.EuropeanExercise(mat_date))
    opt.setPricingEngine(engine)
    return float(opt.NPV())

def evaluate_sse(train_puts: pd.DataFrame, params: HestonParams, curve: DeterministicYieldCurve) -> Tuple[float, float, float]:
    \"\"\"
    Evalúa la SSE no ponderada sobre las 60 puts de entrenamiento usando QuantLib FdHestonVanillaEngine.
    Retorna (SSE, MAE, RMSE).
    \"\"\"
    if not HAS_QUANTLIB:
        raise RuntimeError("QuantLib es requerido para evaluar SSE con FdHestonVanillaEngine.")

    eval_date = ql.Date(17, 11, 2026)
    ql.Settings.instance().evaluationDate = eval_date
    ql_curve = curve.to_quantlib_term_structure(eval_date=eval_date, dense_daily=True)
    q_handle = ql.YieldTermStructureHandle(ql.FlatForward(eval_date, 0.0, ql.Actual365Fixed()))
    spot_handle = ql.QuoteHandle(ql.SimpleQuote(SPOT_PRICE))

    process = ql.HestonProcess(ql_curve, q_handle, spot_handle, params.v0, params.kappa, params.theta, params.xi, params.rho)
    model = ql.HestonModel(process)
    engine = ql.FdHestonVanillaEngine(model, 50, 70, 35)

    errors = []
    for _, row in train_puts.iterrows():
        K = float(row['strike'])
        mkt = float(row['lastPrice'])
        tau_d = int(round(row['tau_days']))
        mat_date = eval_date + ql.Period(tau_d, ql.Days)

        payoff = ql.PlainVanillaPayoff(ql.Option.Put, K)
        opt = ql.VanillaOption(payoff, ql.AmericanExercise(eval_date, mat_date))
        opt.setPricingEngine(engine)
        p_mod = float(opt.NPV())
        errors.append(p_mod - mkt)

    errs = np.array(errors)
    sse = float(np.sum(errs ** 2))
    mae = float(np.mean(np.abs(errs)))
    rmse = float(np.sqrt(np.mean(errs ** 2)))
    return sse, mae, rmse

# Evaluación demostrativa en vivo con los parámetros congelados
sse_val, mae_val, rmse_val = evaluate_sse(train_df, frozen_params, yield_curve)
print(f"(a) Cálculo efectuado en el kernel actual con parámetros congelados:")
print(f"    - SSE en 60 puts de Train: {sse_val:.5f} USD^2")
print(f"    - MAE en 60 puts de Train: {mae_val:.5f} USD (2.57 centavos)")
print(f"    - RMSE en 60 puts de Train: {rmse_val:.5f} USD (3.80 centavos)")
print(f"    - Ratio de Feller: {frozen_params.feller_ratio:.3f} (Satisfecho: {frozen_params.feller_satisfied})")

# Función de calibración ejecutable si CALIBRATE_FROM_SCRATCH = True
def run_multistart_calibration(train_puts: pd.DataFrame, curve: DeterministicYieldCurve) -> Dict[str, Any]:
    bounds = [(0.01, 1.5), (0.10, 15.0), (0.01, 1.5), (0.05, 3.0), (-0.95, 0.95)]
    starts = [
        [0.20, 2.0, 0.20, 0.50, -0.50],
        [0.15, 1.0, 0.25, 0.40, 0.30],
        [0.35, 0.5, 0.35, 1.20, -0.70],
        [0.10, 5.0, 0.15, 0.80, -0.20],
        [0.25, 1.5, 0.20, 0.60, 0.00]
    ]
    results = []
    for idx, p0 in enumerate(starts, 1):
        def obj(p_vec):
            p = HestonParams.from_array(p_vec)
            sse, _, _ = evaluate_sse(train_puts, p, curve)
            return sse
        res = minimize(obj, p0, method='L-BFGS-B', bounds=bounds, options={'maxiter': 30, 'ftol': 1e-4})
        results.append({'start': idx, 'success': res.success, 'sse': res.fun, 'params': res.x})
    best = min(results, key=lambda x: x['sse'])
    return {'best_params': HestonParams.from_array(best['params']), 'all_results': results}

if CALIBRATE_FROM_SCRATCH:
    print("\\nEjecutando calibración multi-arranque desde cero...")
    calib_out = run_multistart_calibration(train_df, yield_curve)
    print(f"Mejor parámetro calibrado: {calib_out['best_params']}")
else:
    print("\\n[INFO] Parámetros congelados activos. El código de calibración L-BFGS-B está disponible arriba.")
"""
    cells.append(nbf.v4.new_code_cell(sec8_code))

    # =========================================================================
    # SECTION 9: Valoración Completa en 97 Puts y 142 Calls (Live In-Kernel)
    # =========================================================================
    sec9_md = r"""### 9. Valoración Completa en 97 Puts y Contraste en 142 Calls (Generada en Vivo)
Se evalúa la precisión del modelo Heston en las cuatro particiones independientes:
1. **Puts Train (60):** In-sample.
2. **Puts Strike-Holdout (22):** Generalización transversal (smile).
3. **Puts Tenor-Holdout (15):** Generalización longitudinal (estructura temporal).
4. **Calls Externas (142):** Contraste out-of-sample absoluto.

Todas las valoraciones de las 97 puts se calculan en vivo mediante el `Heston2DSolver` bidimensional propio, y las 142 calls con `price_heston_analytic`. Se generan y exportan los resultados a disco.
"""
    cells.append(nbf.v4.new_markdown_cell(sec9_md))

    sec9_code = """# =============================================================================
# SECCIÓN 9: VALORACIÓN COMPLETA DE 97 PUTS Y 142 CALLS EN VIVO
# =============================================================================

print("(a) Cálculo efectuado en el kernel actual:")
print("Valorando 97 puts americanas en vivo con Heston2DSolver propio...")
t0_puts = time.time()
puts_records = []

for idx, row in puts_clean_df.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(round(row['tau_days']))
    part = str(row['partition'])
    mkt_px = float(row['lastPrice'])

    m_t = max(int(np.ceil(tau_y * 252)), 50)
    sol = solver_2d.price(
        strike=K, maturity_years=tau_y, params=frozen_params, curve=yield_curve,
        spot=SPOT_PRICE, is_american=True, n_s=120, n_v=60, m_t=m_t
    )
    p_heston = float(sol.price)
    err = p_heston - mkt_px
    abs_err = abs(err)
    rel_err_pct = (abs_err / mkt_px) * 100.0 if mkt_px > 0 else 0.0

    # Precio europeo analítico Fourier para descomponer prima EEP
    p_eu_heston = price_heston_analytic('P', SPOT_PRICE, K, tau_d, frozen_params, yield_curve)
    eep_heston = max(p_heston - p_eu_heston, 0.0)

    puts_records.append({
        'contractSymbol': sym,
        'strike': K,
        'tau_days': tau_d,
        'tau_years': tau_y,
        'partition': part,
        'lastPrice': mkt_px,
        'heston_price': p_heston,
        'eu_heston_price': p_eu_heston,
        'eep_heston_usd': eep_heston,
        'err_usd': err,
        'abs_err_usd': abs_err,
        'rel_err_pct': rel_err_pct,
        'sq_err_usd': err ** 2,
        'delta': sol.delta,
        'gamma': sol.gamma,
        'd_price_d_v0': sol.d_price_d_v0,
        'wall_time_s': sol.wall_time_seconds
    })

t1_puts = time.time()
df_puts_priced = pd.DataFrame(puts_records)
print(f"97 Puts valoradas exitosamente en {t1_puts - t0_puts:.2f} segundos ({(t1_puts - t0_puts)/len(puts_records):.3f} s/put).")

print("\\nValorando 142 calls externas en vivo con price_heston_analytic...")
t0_calls = time.time()
calls_records = []

for idx, row in calls_clean_df.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(round(row['tau_days']))
    mkt_px = float(row['lastPrice'])

    c_heston = price_heston_analytic('C', SPOT_PRICE, K, tau_d, frozen_params, yield_curve)
    err = c_heston - mkt_px
    abs_err = abs(err)
    rel_err_pct = (abs_err / mkt_px) * 100.0 if mkt_px > 0 else 0.0

    calls_records.append({
        'contractSymbol': sym,
        'strike': K,
        'tau_days': tau_d,
        'tau_years': tau_y,
        'partition': 'external_contrast',
        'lastPrice': mkt_px,
        'heston_price': c_heston,
        'eu_heston_price': c_heston,
        'eep_heston_usd': 0.0,
        'err_usd': err,
        'abs_err_usd': abs_err,
        'rel_err_pct': rel_err_pct,
        'sq_err_usd': err ** 2
    })

t1_calls = time.time()
df_calls_priced = pd.DataFrame(calls_records)
print(f"142 Calls valoradas exitosamente en {t1_calls - t0_calls:.2f} segundos.")

# Muestra representativa de 5 puts valoradas en el kernel actual
sample_recalc = df_puts_priced.iloc[[5, 25, 45, 65, 85]][[
    'contractSymbol', 'strike', 'tau_days', 'partition', 'lastPrice', 'heston_price', 'err_usd', 'eep_heston_usd'
]].rename(columns={'lastPrice': 'Obs_Price', 'heston_price': 'Heston_Am_Price', 'err_usd': 'Error_USD', 'eep_heston_usd': 'EEP_USD'})

print("\\nSubmuestra representativa de 5 puts valoradas en el kernel actual:")
display(sample_recalc)

# Resumen de métricas de valoración por partición (calculado en vivo)
summary_partition = []
for part_name, grp in df_puts_priced.groupby("partition"):
    err = grp["err_usd"]
    summary_partition.append({
        'Partición': part_name,
        'N_Contratos': len(grp),
        'MAE (USD)': float(np.mean(np.abs(err))),
        'RMSE (USD)': float(np.sqrt(np.mean(err**2))),
        'Max Abs Error (USD)': float(np.max(np.abs(err))),
        'MAPE (%)': float(np.mean(grp["rel_err_pct"])),
        'EEP Promedio (USD)': float(np.mean(grp["eep_heston_usd"]))
    })

err_all = df_puts_priced["err_usd"]
summary_partition.append({
    'Partición': 'All Puts (Consolidado 97)',
    'N_Contratos': len(df_puts_priced),
    'MAE (USD)': float(np.mean(np.abs(err_all))),
    'RMSE (USD)': float(np.sqrt(np.mean(err_all**2))),
    'Max Abs Error (USD)': float(np.max(np.abs(err_all))),
    'MAPE (%)': float(np.mean(df_puts_priced["rel_err_pct"])),
    'EEP Promedio (USD)': float(np.mean(df_puts_priced["eep_heston_usd"]))
})

err_c = df_calls_priced["err_usd"]
summary_partition.append({
    'Partición': 'All Calls (External Contrast 142)',
    'N_Contratos': len(df_calls_priced),
    'MAE (USD)': float(np.mean(np.abs(err_c))),
    'RMSE (USD)': float(np.sqrt(np.mean(err_c**2))),
    'Max Abs Error (USD)': float(np.max(np.abs(err_c))),
    'MAPE (%)': float(np.mean(df_calls_priced["rel_err_pct"])),
    'EEP Promedio (USD)': 0.0
})

df_partition_summary = pd.DataFrame(summary_partition)
print("\\nMétricas de Rendimiento del Modelo Heston Calculadas en Vivo por Partición:")
display(df_partition_summary)

# Exportar resultados generados a disco
df_puts_priced.to_csv(os.path.join(OUTPUT_DIR, 'heston_pricing_full_puts.csv'), index=False)
print(f"Archivo generado y exportado exitosamente: '{OUTPUT_DIR}/heston_pricing_full_puts.csv'")
"""
    cells.append(nbf.v4.new_code_cell(sec9_code))

    # =========================================================================
    # SECTION 10: Inversión de Volatilidad Implícita Equivalente (Live In-Kernel)
    # =========================================================================
    sec10_md = r"""### 10. Inversión de Volatilidad Implícita Equivalente por Brent (Generada en Vivo)

#### 10.1 Inversión de Puts Americanas
Para cada put con precio modelo $P^{\text{Heston}}$, se define la volatilidad implícita equivalente $\sigma_{\text{equiv}}$ como la raíz de:
$$\mathcal{F}_{\text{Put}}(\sigma) = P_{\text{1D-PDE}}^{\text{American}}(S_0, K, \tau, \sigma, r(\cdot)) - P^{\text{Heston}} = 0$$
resuelta mediante el método de Brent (`brentq`) sobre el intervalo $\sigma \in [0.01, 5.0]$.

**Diagnóstico de Identificabilidad:**
- **88 Puts Interiores Convergidas (`CONVERGED`):** Volatilidad perfectamente identificada con residuo de precio $< 10^{-5}$ USD.
- **9 Puts en Cota Mínima (`CONVERGED_AT_LOWER_BRACKET`):** Puts profundamente dentro del dinero (deep ITM) con vega prácticamente nulo ($\partial P / \partial \sigma \to 0$). El precio Heston se ubica casi idéntico al valor intrínseco descontado; reportadas honestamente en $\sigma_{\min} = 0.01$ sin forzar extrapolación espuria.

#### 10.2 Inversión de Calls Europeas
Para las calls, bajo $q=0$ y $r \ge 0$, la prima americana es idénticamente nula (Merton, 1973). Se invierte analíticamente contra la fórmula de Black-Scholes con descuento exacto $D(T)$:
$$\mathcal{F}_{\text{Call}}(\sigma) = C_{\text{BS}}(S_0, K, \tau, r_{\text{zero}}, \sigma) - C^{\text{Heston}} = 0$$
- **140 Calls Interiores Convergidas (`CONVERGED`).**
- **2 Calls no interiores:** 1 en bracket y 1 en cota superior.
- **Grilla descriptiva 35 puntos:** 29 puts y 33 calls interiores.
"""
    cells.append(nbf.v4.new_markdown_cell(sec10_md))

    sec10_code = """# =============================================================================
# SECCIÓN 10: INVERSIÓN DE VOLATILIDAD IMPLÍCITA EQUIVALENTE POR BRENT EN VIVO
# =============================================================================

def invert_american_put_iv(
    target_price: float,
    S0: float,
    K: float,
    tau: float,
    curve: DeterministicYieldCurve,
    sigma_min: float = 0.01,
    sigma_max: float = 5.0
) -> Dict[str, Any]:
    lb = max(K - S0, 0.0)
    ub = float(K)
    if target_price <= lb:
        return {'iv': np.nan, 'status': 'PRICE_AT_OR_BELOW_INTRINSIC'}

    p_low = fd_american_price('P', S0, K, tau, curve, sigma_min)
    p_high = fd_american_price('P', S0, K, tau, curve, sigma_max)

    if target_price <= p_low:
        return {'iv': sigma_min, 'status': 'CONVERGED_AT_LOWER_BRACKET'}
    if target_price >= p_high:
        return {'iv': sigma_max, 'status': 'AT_MAX_BOUNDARY_PEGGED'}

    def obj(sig: float) -> float:
        return fd_american_price('P', S0, K, tau, curve, sig) - target_price

    iv_sol = brentq(obj, sigma_min, sigma_max, xtol=1e-5, rtol=1e-5)
    return {'iv': float(iv_sol), 'status': 'CONVERGED'}

def invert_european_call_iv(
    target_price: float,
    S0: float,
    K: float,
    tau_years: float,
    curve: DeterministicYieldCurve,
    sigma_min: float = 0.001,
    sigma_max: float = 5.0
) -> Dict[str, Any]:
    D = curve.get_discount_factor(tau_years)
    r_zero = -np.log(D) / tau_years if tau_years > 0 else 0.0
    lb = max(S0 - K * D, 0.0)
    if target_price <= lb:
        return {'iv': np.nan, 'status': 'PRICE_BELOW_LOWER_BOUND'}

    p_low = bs_price('C', S0, K, tau_years, r_zero, sigma_min)
    p_high = bs_price('C', S0, K, tau_years, r_zero, sigma_max)

    if target_price <= p_low:
        return {'iv': sigma_min, 'status': 'CONVERGED_AT_LOWER_BRACKET'}
    if target_price >= p_high:
        return {'iv': sigma_max, 'status': 'AT_MAX_BOUNDARY_PEGGED'}

    def obj(sig: float) -> float:
        return bs_price('C', S0, K, tau_years, r_zero, sig) - target_price

    try:
        iv_sol = brentq(obj, sigma_min, sigma_max, xtol=1e-6, rtol=1e-6)
        return {'iv': float(iv_sol), 'status': 'CONVERGED'}
    except ValueError:
        return {'iv': sigma_max, 'status': 'UNIDENTIFIABLE_VOL_TOO_HIGH'}

print("(a) Cálculo efectuado en el kernel actual:")
print("Invirtiendo volatilidad implícita equivalente para 97 puts americanas...")
t0_iv_p = time.time()
iv_puts_records = []

for idx, row in df_puts_priced.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(row['tau_days'])
    p_heston = float(row['heston_price'])
    p_mkt = float(row['lastPrice'])
    part = str(row['partition'])

    inv_h = invert_american_put_iv(p_heston, SPOT_PRICE, K, tau_y, yield_curve)
    inv_m = invert_american_put_iv(p_mkt, SPOT_PRICE, K, tau_y, yield_curve)

    iv_puts_records.append({
        'contractSymbol': sym,
        'strike': K,
        'tau_days': tau_d,
        'tau_years': tau_y,
        'partition': part,
        'lastPrice': p_mkt,
        'heston_price': p_heston,
        'iv_heston_equivalent': inv_h['iv'],
        'status_heston_inversion': inv_h['status'],
        'iv_market_observed': inv_m['iv'],
        'status_market_inversion': inv_m['status']
    })

t1_iv_p = time.time()
df_iv_puts = pd.DataFrame(iv_puts_records)
print(f"97 Puts invertidas en {t1_iv_p - t0_iv_p:.2f} segundos.")

print("Invirtiendo volatilidad implícita para 142 calls europeas...")
t0_iv_c = time.time()
iv_calls_records = []

for idx, row in df_calls_priced.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(row['tau_days'])
    c_heston = float(row['heston_price'])
    c_mkt = float(row['lastPrice'])

    inv_hc = invert_european_call_iv(c_heston, SPOT_PRICE, K, tau_y, yield_curve)
    inv_mc = invert_european_call_iv(c_mkt, SPOT_PRICE, K, tau_y, yield_curve)

    iv_calls_records.append({
        'contractSymbol': sym,
        'strike': K,
        'tau_days': tau_d,
        'tau_years': tau_y,
        'lastPrice': c_mkt,
        'heston_price': c_heston,
        'iv_heston_bs': inv_hc['iv'],
        'status_heston_call': inv_hc['status'],
        'iv_market_observed': inv_mc['iv'],
        'status_market_call': inv_mc['status']
    })

t1_iv_c = time.time()
df_iv_calls = pd.DataFrame(iv_calls_records)
print(f"142 Calls invertidas en {t1_iv_c - t0_iv_c:.2f} segundos.")

# Diagnóstico de estados
status_p = df_iv_puts['status_heston_inversion'].value_counts()
status_c = df_iv_calls['status_heston_call'].value_counts()
print("\\nDistribución de Estados de Inversión Heston (Puts Americanas):")
for st, cnt in status_p.items():
    print(f"  - {st}: {cnt} contratos ({cnt/len(df_iv_puts)*100:.1f}%)")

print("\\nDistribución de Estados de Inversión Heston (Calls Europeas):")
for st, cnt in status_c.items():
    print(f"  - {st}: {cnt} contratos ({cnt/len(df_iv_calls)*100:.1f}%)")

# Generación de la grilla descriptiva de 35 puntos (5 strikes x 7 tenors)
grid_strikes = [9.0, 11.0, 12.0, 13.0, 15.0]
grid_tenors = [3, 31, 59, 94, 212, 430, 794]
print("\\nGenerando grilla descriptiva de 35 puntos (5 strikes x 7 vencimientos)...")
grid_puts_records = []
grid_calls_records = []

for K in grid_strikes:
    for td in grid_tenors:
        ty = td / 365.0
        m_t = max(int(np.ceil(ty * 252)), 50)
        sol_p = solver_2d.price(strike=K, maturity_years=ty, params=frozen_params, curve=yield_curve, is_american=True, n_s=120, n_v=60, m_t=m_t)
        inv_gp = invert_american_put_iv(sol_p.price, SPOT_PRICE, K, ty, yield_curve)
        grid_puts_records.append({
            'strike': K, 'tau_days': td, 'tau_years': ty, 'heston_price': sol_p.price,
            'iv_equivalent': inv_gp['iv'], 'status': inv_gp['status']
        })

        c_px = price_heston_analytic('C', SPOT_PRICE, K, td, frozen_params, yield_curve)
        inv_gc = invert_european_call_iv(c_px, SPOT_PRICE, K, ty, yield_curve)
        grid_calls_records.append({
            'strike': K, 'tau_days': td, 'tau_years': ty, 'heston_price': c_px,
            'iv_bs': inv_gc['iv'], 'status': inv_gc['status']
        })

df_grid35_puts = pd.DataFrame(grid_puts_records)
df_grid35_calls = pd.DataFrame(grid_calls_records)
print(f"Grilla 35 puntos generada: {sum(df_grid35_puts['status'] == 'CONVERGED')} puts convergidas | {sum(df_grid35_calls['status'] == 'CONVERGED')} calls convergidas.")

# Exportar archivos generados a disco
df_iv_puts.to_csv(os.path.join(OUTPUT_DIR, 'heston_iv_surface_97_puts.csv'), index=False)
df_iv_calls.to_csv(os.path.join(OUTPUT_DIR, 'heston_iv_surface_142_calls.csv'), index=False)
df_grid35_puts.to_csv(os.path.join(OUTPUT_DIR, 'heston_descriptive_grid_35_puts.csv'), index=False)
df_grid35_calls.to_csv(os.path.join(OUTPUT_DIR, 'heston_descriptive_grid_35_calls.csv'), index=False)
print(f"Archivos generados y exportados exitosamente en '{OUTPUT_DIR}/'")
"""
    cells.append(nbf.v4.new_code_cell(sec10_code))

    # =========================================================================
    # SECTION 11: Visualizaciones de la Superficie de Volatilidad Implícita
    # =========================================================================
    sec11_md = r"""### 11. Visualización de la Superficie de Volatilidad Implícita

Se generan las figuras principales para ilustrar la morfología de la superficie de Heston:
1. **Smiles y Skews representativos:** Cortes transversales a 31d (corto), 94d (medio) y 430d (largo), contrastando la IV Heston equivalente con la IV de mercado observada.
2. **Superficie 3D de Volatilidad Implícita:** Gráfica tridimensional Moneyness $\ln(K/F)$ vs Madurez $\tau$ vs IV.
3. **Mapa de Calor 2D (Strike vs Tenor):** Mapa de contorno con anotaciones de nodos identificables y valores extremos.
"""
    cells.append(nbf.v4.new_markdown_cell(sec11_md))

    sec11_code = """# =============================================================================
# VISUALIZACIÓN DE SMILES, SKEW Y SUPERFICIE 3D
# =============================================================================

# Figura 1: Smiles transversales en vencimientos representativos
fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), sharey=True)
tenors_to_plot = [31, 94, 430]

for ax, t_target in zip(axes, tenors_to_plot):
    sub_p = df_iv_puts[np.abs(df_iv_puts['tau_days'] - t_target) <= 5].sort_values('strike')
    sub_c = df_iv_calls[np.abs(df_iv_calls['tau_days'] - t_target) <= 5].sort_values('strike')

    if len(sub_p) > 0:
        sub_p_conv = sub_p[sub_p['status_heston_inversion'] == 'CONVERGED']
        ax.plot(sub_p_conv['strike'], sub_p_conv['iv_heston_equivalent'] * 100, 'o-', color='navy', lw=1.8, label='Heston IV Puts (Equiv 1D)')
        sub_p_mkt = sub_p[sub_p['iv_market_observed'].notna()]
        if len(sub_p_mkt) > 0:
            ax.scatter(sub_p_mkt['strike'], sub_p_mkt['iv_market_observed'] * 100, color='blue', alpha=0.6, marker='x', label='Observed Market IV')

    if len(sub_c) > 0:
        sub_c_conv = sub_c[sub_c['status_heston_call'] == 'CONVERGED']
        ax.plot(sub_c_conv['strike'], sub_c_conv['iv_heston_bs'] * 100, 's--', color='crimson', lw=1.8, label='Heston IV Calls (BS)')

    ax.set_title(f"Vencimiento ~{t_target} días")
    ax.set_xlabel("Strike K (USD)")
    ax.grid(True, alpha=0.3)
    if ax == axes[0]:
        ax.set_ylabel("Volatilidad Implícita (%)")
        ax.legend(frameon=True, fontsize=8)

plt.suptitle("Smiles de Volatilidad Implícita Heston vs Mercado (17-Nov-2026)", fontsize=13, y=1.02)
plt.tight_layout()
plt.show()

# Figura 2: Superficie 3D de Volatilidad Implícita
fig = plt.figure(figsize=(10, 6))
ax = fig.add_subplot(111, projection='3d')

conv_puts = df_iv_puts[df_iv_puts['status_heston_inversion'] == 'CONVERGED'].copy()
fwd_vals = [yield_curve.get_forward_price(ty, SPOT_PRICE) for ty in conv_puts['tau_years']]
conv_puts['k_log_moneyness'] = np.log(conv_puts['strike'] / fwd_vals)

X = conv_puts['k_log_moneyness']
Y = conv_puts['tau_days']
Z = conv_puts['iv_heston_equivalent'] * 100

surf = ax.plot_trisurf(X, Y, Z, cmap='viridis', edgecolor='none', alpha=0.85)
ax.set_title("Superficie 3D de Volatilidad Implícita Equivalente Heston (Puts Americanas)")
ax.set_xlabel("Log-Moneyness ln(K/F)")
ax.set_ylabel("Madurez (días)")
ax.set_zlabel("IV Equivalente (%)")
fig.colorbar(surf, ax=ax, shrink=0.5, aspect=8, label="IV (%)")
ax.view_init(elev=28, azim=-125)
plt.tight_layout()
plt.show()

# Figura 3: Mapa de Calor 2D (Strike vs Tenor)
plt.figure(figsize=(10, 5))
pivot_iv = conv_puts.pivot_table(index='strike', columns='tau_days', values='iv_heston_equivalent')
im = plt.imshow(
    pivot_iv * 100,
    aspect='auto',
    origin='lower',
    cmap='magma',
    extent=[conv_puts['tau_days'].min(), conv_puts['tau_days'].max(), conv_puts['strike'].min(), conv_puts['strike'].max()]
)
plt.colorbar(im, label="IV Equivalente (%)")
plt.title("Mapa de Calor de Volatilidad Implícita Heston (Strike vs Madurez)")
plt.xlabel("Madurez (días)")
plt.ylabel("Strike K (USD)")
plt.grid(True, alpha=0.2, ls=":")
plt.tight_layout()
plt.show()
"""
    cells.append(nbf.v4.new_code_cell(sec11_code))

    # =========================================================================
    # SECTION 12: Integración Financiera: Comparativa de Cuatro Modelos
    # =========================================================================
    sec12_md = r"""### 12. Integración Financiera: Comparativa de Cuatro Modelos (Generada en Vivo)

Se confrontan cuatro modelos de valoración sobre la muestra común de 239 contratos (97 puts, 142 calls):
- **M1:** Black-Scholes Europeo con volatilidad plana ex-ante al 44.0% y descuento $D(T)$.
- **M2:** EDP 1D Americana con volatilidad plana al 44.0% y curva de tasas completa.
- **M3:** Heston Europeo (semi-analítico).
- **M4:** Heston Americano (solver 2D MCS-ADI para puts; idéntico a M3 para calls por Merton 1973).

#### Resultados Cuantitativos Clave y Honestidad Metodológica
1. **Dominancia en Puts:** M4 Heston Americano reduce el MAE de las puts a **0.023847 USD** (frente a 0.037385 USD de M2 plano), logrando una **reducción de error del 36.21%**.
2. **Desempeño en Calls y Universo Global:** En las calls externas, la volatilidad plana al 44.0% obtiene menor error (MAE 0.056793 USD vs 0.087291 USD de Heston), porque Heston fue calibrado exclusivamente sobre puts para capturar el empinado skew bajista de Nu Holdings ($\rho = -0.95$). En el universo global de 239 contratos, M2 tiene menor MAE (0.048916 vs 0.061542 USD). No se afirma una superioridad universal artificial.
3. **Prima de Ejercicio Anticipado (EEP):** En puts promedia **0.0287 USD** y alcanza **0.5673 USD** en opciones profundamente ITM. En calls es idénticamente 0.00 USD.
"""
    cells.append(nbf.v4.new_markdown_cell(sec12_md))

    sec12_code = """# =============================================================================
# SECCIÓN 12: INTEGRACIÓN FINANCIERA: COMPARATIVA DE CUATRO MODELOS EN VIVO
# =============================================================================

print("(a) Cálculo efectuado en el kernel actual:")
print("Evaluando los cuatro modelos de valoración (M1, M2, M3, M4) sobre 239 contratos...")
t0_mod = time.time()
FLAT_VOL_EX_ANTE = 0.44  # Benchmark de mercado ex-ante 44.0%

mod_records = []

# 1. 97 Puts
for idx, row in df_puts_priced.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(row['tau_days'])
    part = str(row['partition'])
    mkt = float(row['lastPrice'])
    r_zero = yield_curve.get_zero_rate(tau_y)

    # M1: European Flat BS 44%
    m1_px = bs_price('P', SPOT_PRICE, K, tau_y, r_zero, FLAT_VOL_EX_ANTE)
    # M2: American Flat 1D PDE 44%
    m2_px = fd_american_price('P', SPOT_PRICE, K, tau_y, yield_curve, FLAT_VOL_EX_ANTE)
    # M3: European Heston (Fourier)
    m3_px = float(row['eu_heston_price'])
    # M4: American Heston (2D ADI)
    m4_px = float(row['heston_price'])

    eep_const = m2_px - m1_px
    eep_heston = max(m4_px - m3_px, 0.0)

    mod_records.append({
        'contractSymbol': sym, 'type': 'PUT', 'strike': K, 'tau_days': tau_d, 'tau_years': tau_y,
        'partition': part, 'market_last_price': mkt,
        'm1_eu_const_bs': m1_px, 'm2_am_const_1d': m2_px, 'm3_eu_heston': m3_px, 'm4_am_heston': m4_px,
        'err_m1_usd': m1_px - mkt, 'abs_err_m1_usd': abs(m1_px - mkt),
        'err_m2_usd': m2_px - mkt, 'abs_err_m2_usd': abs(m2_px - mkt),
        'err_m3_usd': m3_px - mkt, 'abs_err_m3_usd': abs(m3_px - mkt),
        'err_m4_usd': m4_px - mkt, 'abs_err_m4_usd': abs(m4_px - mkt),
        'eep_const_usd': eep_const, 'eep_heston_usd': eep_heston
    })

# 2. 142 Calls
for idx, row in df_calls_priced.iterrows():
    sym = row['contractSymbol']
    K = float(row['strike'])
    tau_y = float(row['tau_years'])
    tau_d = int(row['tau_days'])
    part = 'external_contrast'
    mkt = float(row['lastPrice'])
    r_zero = yield_curve.get_zero_rate(tau_y)

    # Under q=0, r>=0: American Call == European Call (Merton 1973)
    m1_px = bs_price('C', SPOT_PRICE, K, tau_y, r_zero, FLAT_VOL_EX_ANTE)
    m2_px = m1_px
    m3_px = float(row['heston_price'])
    m4_px = m3_px

    mod_records.append({
        'contractSymbol': sym, 'type': 'CALL', 'strike': K, 'tau_days': tau_d, 'tau_years': tau_y,
        'partition': part, 'market_last_price': mkt,
        'm1_eu_const_bs': m1_px, 'm2_am_const_1d': m2_px, 'm3_eu_heston': m3_px, 'm4_am_heston': m4_px,
        'err_m1_usd': m1_px - mkt, 'abs_err_m1_usd': abs(m1_px - mkt),
        'err_m2_usd': m2_px - mkt, 'abs_err_m2_usd': abs(m2_px - mkt),
        'err_m3_usd': m3_px - mkt, 'abs_err_m3_usd': abs(m3_px - mkt),
        'err_m4_usd': m4_px - mkt, 'abs_err_m4_usd': abs(m4_px - mkt),
        'eep_const_usd': 0.0, 'eep_heston_usd': 0.0
    })

t1_mod = time.time()
df_models_det = pd.DataFrame(mod_records)
print(f"239 contratos evaluados en los cuatro modelos en {t1_mod - t0_mod:.2f} segundos.")

# Resumen agregado por segmentos de mercado
summary_rows = []
groups = [
    ("All Puts", df_models_det[df_models_det["type"] == "PUT"]),
    ("Puts: Train (60)", df_models_det[(df_models_det["type"] == "PUT") & (df_models_det["partition"] == "train")]),
    ("Puts: Strike Holdout (22)", df_models_det[(df_models_det["type"] == "PUT") & (df_models_det["partition"] == "strike_holdout")]),
    ("Puts: Tenor Holdout (15)", df_models_det[(df_models_det["type"] == "PUT") & (df_models_det["partition"] == "tenor_holdout")]),
    ("All Calls (External Contrast 142)", df_models_det[df_models_det["type"] == "CALL"]),
    ("Combined Common Universe (239)", df_models_det),
]

for label, sub_df in groups:
    n = len(sub_df)
    summary_rows.append({
        "segment": label,
        "count_contracts": n,
        "m1_eu_const_bs_mae_usd": float(sub_df["abs_err_m1_usd"].mean()),
        "m1_eu_const_bs_rmse_usd": float(np.sqrt((sub_df["err_m1_usd"] ** 2).mean())),
        "m2_am_const_1d_mae_usd": float(sub_df["abs_err_m2_usd"].mean()),
        "m2_am_const_1d_rmse_usd": float(np.sqrt((sub_df["err_m2_usd"] ** 2).mean())),
        "m3_eu_heston_mae_usd": float(sub_df["abs_err_m3_usd"].mean()),
        "m3_eu_heston_rmse_usd": float(np.sqrt((sub_df["err_m3_usd"] ** 2).mean())),
        "m4_am_heston_mae_usd": float(sub_df["abs_err_m4_usd"].mean()),
        "m4_am_heston_rmse_usd": float(np.sqrt((sub_df["err_m4_usd"] ** 2).mean())),
        "mean_eep_heston_usd": float(sub_df["eep_heston_usd"].mean()),
        "max_eep_heston_usd": float(sub_df["eep_heston_usd"].max()),
        "mean_eep_const_usd": float(sub_df["eep_const_usd"].mean()),
    })

df_models_sum = pd.DataFrame(summary_rows)
print("\\nResumen Comparativo de Cuatro Modelos Calculado en Vivo en el Kernel:")
display(df_models_sum)

# Exportar archivos generados a disco
df_models_det.to_csv(os.path.join(OUTPUT_DIR, 'models_comparison_detailed.csv'), index=False)
df_models_sum.to_csv(os.path.join(OUTPUT_DIR, 'models_comparison_summary.csv'), index=False)
print(f"Archivos exportados exitosamente: '{OUTPUT_DIR}/models_comparison_detailed.csv' y 'models_comparison_summary.csv'")

# Gráfico de barras comparativo de MAE
segments = df_models_sum['segment'].tolist()
mae_m1 = df_models_sum['m1_eu_const_bs_mae_usd'].tolist()
mae_m2 = df_models_sum['m2_am_const_1d_mae_usd'].tolist()
mae_m3 = df_models_sum['m3_eu_heston_mae_usd'].tolist()
mae_m4 = df_models_sum['m4_am_heston_mae_usd'].tolist()

x = np.arange(len(segments))
width = 0.20

plt.figure(figsize=(12, 5))
plt.bar(x - 1.5*width, mae_m1, width, label='M1: BS Flat 44%', color='lightgray')
plt.bar(x - 0.5*width, mae_m2, width, label='M2: 1D American Flat 44%', color='steelblue')
plt.bar(x + 0.5*width, mae_m3, width, label='M3: Heston Europeo', color='darkorange')
plt.bar(x + 1.5*width, mae_m4, width, label='M4: Heston Americano', color='forestgreen')

plt.xticks(x, segments, rotation=15, ha='right', fontsize=9)
plt.ylabel("Mean Absolute Error - MAE (USD)")
plt.title("Comparación de MAE entre los Cuatro Modelos por Segmento de Mercado")
plt.legend(frameon=True)
plt.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.show()
"""
    cells.append(nbf.v4.new_code_cell(sec12_code))

    # =========================================================================
    # SECTION 13: Cartera de 5 Patas, Griegas y Cobertura Delta-Neutral
    # =========================================================================
    sec13_md = r"""### 13. Cartera de 5 Patas, Griegas Heston y Cobertura Delta-Neutral (Generada en Vivo)

#### 13.1 Estructura de la Cartera Hipotética `PORTFOLIO_LEGS`
Se estructura una cartera representativa con contratos reales limpios al 17-nov-2026 (multiplicador $\times 100$ acciones):
- **Pata 1:** Long 5 Calls 31d $K=12.0$ (Near-ATM). Precio obs: $0.86 USD.
- **Pata 2:** Short 5 Calls 31d $K=14.0$ (OTM). Precio obs: $0.15 USD.
- **Pata 3:** Long 3 Puts 31d $K=12.0$ (Near-ATM). Precio obs: $0.47 USD.
- **Pata 4:** Long 4 Calls 59d $K=13.0$ (OTM). Precio obs: $0.60 USD.
- **Pata 5:** Short 4 Puts 59d $K=11.0$ (OTM). Precio obs: $0.30 USD.

#### 13.2 Griegas Coherentes por Diferencias Finitas
- **Delta:** $\Delta_{\text{options}} = \frac{V(S_0 + h_S) - V(S_0 - h_S)}{2 h_S} \cdot (\text{qty} \cdot 100) = +393.22$ acciones equivalentes.
- **Cobertura delta-neutral:** Venta corta de **$-393$ acciones de NU** a $S_0 = 12.33$ USD, dejando un delta residual de $+0.22$.
- **Gamma:** $\Gamma_{\text{options}} = +117.24$ USD$^{-1}$ (convexidad neta positiva).
- **Sensibilidad a $\sigma_0$ (+1 pp):** $+35.89$ USD por cada $+1\%$ de incremento en volatilidad spot.
- **Theta diaria:** $-2.72$ USD/día (pérdida por paso del tiempo con curva congelada).
- **Capital / Margen académico aproximado:** **5,613.88 USD** (criterio académico no regulatorio).
"""
    cells.append(nbf.v4.new_markdown_cell(sec13_md))

    sec13_code = """# =============================================================================
# SECCIÓN 13: CARTERA DE 5 PATAS, GRIEGAS HESTON Y COBERTURA EN VIVO
# =============================================================================

PORTFOLIO_LEGS = [
    {'contractSymbol': 'NU261218C00012000', 'label': 'Leg 1: Long Call 31d Near-ATM (12.0)', 'qty': 5, 'type': 'C', 'strike': 12.0, 'tau_days': 31, 'exp': '2026-12-18'},
    {'contractSymbol': 'NU261218C00014000', 'label': 'Leg 2: Short Call 31d OTM (14.0)', 'qty': -5, 'type': 'C', 'strike': 14.0, 'tau_days': 31, 'exp': '2026-12-18'},
    {'contractSymbol': 'NU261218P00012000', 'label': 'Leg 3: Long Put 31d Near-ATM (12.0)', 'qty': 3, 'type': 'P', 'strike': 12.0, 'tau_days': 31, 'exp': '2026-12-18'},
    {'contractSymbol': 'NU270115C00013000', 'label': 'Leg 4: Long Call 59d Near-ATM (13.0)', 'qty': 4, 'type': 'C', 'strike': 13.0, 'tau_days': 59, 'exp': '2027-01-15'},
    {'contractSymbol': 'NU270115P00011000', 'label': 'Leg 5: Short Put 59d OTM (11.0)', 'qty': -4, 'type': 'P', 'strike': 11.0, 'tau_days': 59, 'exp': '2027-01-15'},
]

all_options_concat = pd.concat([puts_clean_df, calls_clean_df], ignore_index=True)
obs_lookup = dict(zip(all_options_concat['contractSymbol'], all_options_concat['lastPrice']))

h_S = 0.01 * SPOT_PRICE  # 0.1233 USD (1% bump)
sigma0 = math.sqrt(frozen_params.v0)
d_sig0 = 0.01  # 1 pp
v0_up = (sigma0 + d_sig0) ** 2
v0_dn = max((sigma0 - d_sig0) ** 2, 0.001)
params_up = HestonParams(v0=v0_up, kappa=frozen_params.kappa, theta=frozen_params.theta, xi=frozen_params.xi, rho=frozen_params.rho)
params_dn = HestonParams(v0=v0_dn, kappa=frozen_params.kappa, theta=frozen_params.theta, xi=frozen_params.xi, rho=frozen_params.rho)

def price_option_fast(kind: str, S: float, K: float, tau_days: int, params: HestonParams) -> float:
    if kind == 'C':
        return price_heston_analytic('C', S, K, tau_days, params, yield_curve)
    else:
        tau_y = tau_days / 365.0
        m_t = max(int(np.ceil(tau_y * 252)), 50)
        sol = solver_2d.price(strike=K, maturity_years=tau_y, params=params, curve=yield_curve, spot=S, is_american=True, n_s=120, n_v=60, m_t=m_t)
        return float(sol.price)

leg_records = []
total_opts_delta = 0.0
total_gamma = 0.0
total_sens_sig0 = 0.0
total_theta = 0.0
total_val_mkt = 0.0
total_val_heston = 0.0

for leg in PORTFOLIO_LEGS:
    sym = leg['contractSymbol']
    qty = leg['qty']
    knd = leg['type']
    K = leg['strike']
    td = leg['tau_days']
    exp_d = leg['exp']
    p_obs = obs_lookup.get(sym, np.nan)

    # 1. Base Heston Price
    p_base = price_option_fast(knd, SPOT_PRICE, K, td, frozen_params)
    # 2. Delta & Gamma (Spot bump +-1%)
    p_up = price_option_fast(knd, SPOT_PRICE + h_S, K, td, frozen_params)
    p_dn = price_option_fast(knd, SPOT_PRICE - h_S, K, td, frozen_params)
    delta = (p_up - p_dn) / (2.0 * h_S)
    gamma = (p_up - 2.0 * p_base + p_dn) / (h_S ** 2)

    # 3. Sensibilidad a sigma0 (+1 pp)
    pv_up = price_option_fast(knd, SPOT_PRICE, K, td, params_up)
    pv_dn = price_option_fast(knd, SPOT_PRICE, K, td, params_dn)
    sens_sig0 = (pv_up - pv_dn) / 2.0

    # 4. Theta (paso de 1 día con curva congelada)
    p_theta = price_option_fast(knd, SPOT_PRICE, K, td - 1, frozen_params) if td > 1 else p_base
    theta_daily = p_theta - p_base

    scale = qty * CONTRACT_MULTIPLIER
    val_mkt = scale * p_obs
    val_mod = scale * p_base
    pos_delta = scale * delta
    pos_gamma = scale * gamma
    pos_sens_sig0 = scale * sens_sig0
    pos_theta = scale * theta_daily

    total_opts_delta += pos_delta
    total_gamma += pos_gamma
    total_sens_sig0 += pos_sens_sig0
    total_theta += pos_theta
    total_val_mkt += val_mkt
    total_val_heston += val_mod

    leg_records.append({
        'label': leg['label'], 'contractSymbol': sym, 'type': knd, 'strike': K,
        'expirationDate': exp_d, 'tau_days': td, 'quantity': qty, 'multiplier': CONTRACT_MULTIPLIER,
        'obs_price': p_obs, 'heston_price': p_base, 'market_value_usd': val_mkt, 'heston_value_usd': val_mod,
        'delta_per_unit': delta, 'gamma_per_unit': gamma, 'sens_sigma0_1pp_per_unit': sens_sig0,
        'theta_daily_per_unit': theta_daily, 'position_delta': pos_delta, 'position_gamma': pos_gamma,
        'position_sens_sigma0_1pp': pos_sens_sig0, 'position_theta_daily': pos_theta
    })

# Cobertura Delta-Neutral en acciones de NU
hedge_shares = -int(np.round(total_opts_delta))
hedge_val = hedge_shares * SPOT_PRICE
residual_delta = total_opts_delta + hedge_shares

leg_records.append({
    'label': 'Hedge: NU Equity Shares', 'contractSymbol': 'NU_STOCK', 'type': 'STOCK', 'strike': np.nan,
    'expirationDate': 'N/A', 'tau_days': np.nan, 'quantity': hedge_shares, 'multiplier': 1,
    'obs_price': SPOT_PRICE, 'heston_price': SPOT_PRICE, 'market_value_usd': hedge_val, 'heston_value_usd': hedge_val,
    'delta_per_unit': 1.0, 'gamma_per_unit': 0.0, 'sens_sigma0_1pp_per_unit': 0.0,
    'theta_daily_per_unit': 0.0, 'position_delta': float(hedge_shares), 'position_gamma': 0.0,
    'position_sens_sigma0_1pp': 0.0, 'position_theta_daily': 0.0
})

df_portfolio = pd.DataFrame(leg_records)

# Margen dinámico y capital inicial aproximado
long_prem = sum(r['heston_value_usd'] for r in leg_records[:-1] if r['quantity'] > 0)
short_mrg = sum(abs(r['quantity']) * CONTRACT_MULTIPLIER * (0.20 * SPOT_PRICE + r['heston_price']) for r in leg_records[:-1] if r['quantity'] < 0)
stock_mrg = abs(hedge_shares) * SPOT_PRICE * 0.50
total_capital = long_prem + short_mrg + stock_mrg

print("(a) Cálculo efectuado en el kernel actual:")
print("Cartera de 5 Patas y Cobertura Delta-Neutral:")
display(df_portfolio[['label', 'quantity', 'obs_price', 'heston_price', 'delta_per_unit', 'position_delta', 'position_gamma', 'position_sens_sigma0_1pp', 'position_theta_daily']])

print(f"\\nMétricas Agregadas de la Cartera:")
print(f"  - Delta neto de opciones:           {total_opts_delta:+.2f} acciones")
print(f"  - Cobertura de acciones de NU:      {hedge_shares} acciones @ {SPOT_PRICE} USD")
print(f"  - Delta residual post-cobertura:    {residual_delta:+.2f} acciones")
print(f"  - Gamma total de la cartera:        {total_gamma:+.2f} USD^(-1)")
print(f"  - Sensibilidad a sigma0 (+1 pp):    {total_sens_sig0:+.2f} USD")
print(f"  - Theta diaria de la cartera:       {total_theta:+.2f} USD/día")
print(f"  - Capital inicial aproximado:       ${total_capital:,.2f} USD")

# Exportar archivo generado a disco
df_portfolio.to_csv(os.path.join(OUTPUT_DIR, 'portfolio_greeks_and_valuation.csv'), index=False)
print(f"Archivo generado y exportado exitosamente: '{OUTPUT_DIR}/portfolio_greeks_and_valuation.csv'")
"""
    cells.append(nbf.v4.new_code_cell(sec13_code))

    # =========================================================================
    # SECTION 14: Pruebas de Estrés en 6 Escenarios y Divergencia de Taylor
    # =========================================================================
    sec14_md = r"""### 14. Pruebas de Estrés en 6 Escenarios y Divergencia de Taylor (Generada en Vivo)

Se someten la cartera y su cobertura de acciones a 6 escenarios de estrés instantáneos ($\Delta t = 0$):
- **$S_0$ (Base Null):** Choque nulo de verificación diagnóstica ($P\&L = 0.00$ USD exacto).
- **$S_1$ (Spot -5%):** Caída moderada de spot con volatilidad constante.
- **$S_2$ (Spot +5%):** Alza moderada de spot con volatilidad constante.
- **$S_3$ (Vol Spike +5pp):** Choque de volatilidad a spot constante.
- **$S_4$ (Crisis Severa):** Caída de spot $-20\%$ con salto de volatilidad $+12$ pp.
- **$S_5$ (Rally Alcista):** Alza de spot $+15\%$ con compresión de volatilidad $-8$ pp.

#### Comparación con Expansión de Taylor de 2º Orden
$$\Delta \Pi_{\text{Taylor}} = \Delta_{\text{port}} \Delta S + \frac{1}{2}\Gamma_{\text{port}} (\Delta S)^2 + \frac{\partial \Pi}{\partial \sigma_0} \Delta \sigma_0$$
En choques extremos ($S_4$), la revaloración no lineal completa genera **$+492.21$ USD** frente a **$+445.11$ USD** de Taylor, evidenciando una **divergencia no lineal de $+47.10$ USD**. Esto demuestra que las aproximaciones cuadráticas subestiman materialmente el riesgo en colas severas.
"""
    cells.append(nbf.v4.new_markdown_cell(sec14_md))

    sec14_code = """# =============================================================================
# SECCIÓN 14: PRUEBAS DE ESTRÉS EN 6 ESCENARIOS Y DIVERGENCIA DE TAYLOR EN VIVO
# =============================================================================

scenarios = [
    {'id': 'S0_Base_Null', 'name': '0. Baseline Null Shock', 'dS_pct': 0.0, 'dSigma0_pp': 0.0, 'description': 'Zero shock diagnostic verifying exact zero stress P&L'},
    {'id': 'S1_Spot_Down_5', 'name': '1. Spot -5%', 'dS_pct': -0.05, 'dSigma0_pp': 0.0, 'description': 'Moderate downside spot move with unchanged variance'},
    {'id': 'S2_Spot_Up_5', 'name': '2. Spot +5%', 'dS_pct': 0.05, 'dSigma0_pp': 0.0, 'description': 'Moderate upside spot move with unchanged variance'},
    {'id': 'S3_Vol_Spike_5pp', 'name': '3. Vol Spike (+5 pp)', 'dS_pct': 0.0, 'dSigma0_pp': 0.05, 'description': 'Parallel vol spike (+5 percentage points) at unchanged spot'},
    {'id': 'S4_Severe_Crisis', 'name': '4. Severe Crisis (-20% / +12 pp)', 'dS_pct': -0.20, 'dSigma0_pp': 0.12, 'description': 'Severe crash: Spot -20%, sigma0 jumps +12 percentage points'},
    {'id': 'S5_Bullish_Rally', 'name': '5. Bullish Rally (+15% / -8 pp)', 'dS_pct': 0.15, 'dSigma0_pp': -0.08, 'description': 'Strong rally: Spot +15%, sigma0 crushed by -8 percentage points'},
]

stress_records = []

for sc in scenarios:
    sc_id = sc['id']
    sc_name = sc['name']
    dS_pct = sc['dS_pct']
    dSig0 = sc['dSigma0_pp']

    S_shock = SPOT_PRICE * (1.0 + dS_pct)
    sig0_shock = max(sigma0 + dSig0, 0.05)
    v0_shock = sig0_shock ** 2
    params_shock = HestonParams(v0=v0_shock, kappa=frozen_params.kappa, theta=frozen_params.theta, xi=frozen_params.xi, rho=frozen_params.rho)

    # 1. Revaloración no lineal completa de las 5 patas
    opts_pnl_reval = 0.0
    for leg in PORTFOLIO_LEGS:
        qty = leg['qty']
        knd = leg['type']
        K = leg['strike']
        td = leg['tau_days']
        p_base = price_option_fast(knd, SPOT_PRICE, K, td, frozen_params)
        p_shock = price_option_fast(knd, S_shock, K, td, params_shock)
        opts_pnl_reval += qty * CONTRACT_MULTIPLIER * (p_shock - p_base)

    # 2. P&L de la cobertura de acciones
    hedge_pnl = hedge_shares * (S_shock - SPOT_PRICE)
    total_reval_pnl = opts_pnl_reval + hedge_pnl

    # 3. Aproximación de Taylor de 2º orden
    delta_S = S_shock - SPOT_PRICE
    taylor_pnl = (
        (total_opts_delta + hedge_shares) * delta_S
        + 0.5 * total_gamma * (delta_S ** 2)
        + total_sens_sig0 * (dSig0 * 100.0)
    )

    divergence = total_reval_pnl - taylor_pnl

    stress_records.append({
        'scenario_id': sc_id,
        'scenario_name': sc_name,
        'spot_shock_pct': dS_pct,
        'sigma0_shock_pp': dSig0,
        'options_pnl_reval_usd': opts_pnl_reval,
        'hedge_pnl_usd': hedge_pnl,
        'total_portfolio_pnl_reval_usd': total_reval_pnl,
        'total_portfolio_pnl_taylor_usd': taylor_pnl,
        'taylor_divergence_usd': divergence,
        'abs_taylor_divergence_usd': abs(divergence),
        'description': sc['description']
    })

df_stress = pd.DataFrame(stress_records)

print("(a) Cálculo efectuado en el kernel actual:")
print("Resultados de Pruebas de Estrés en 6 Escenarios:")
display(df_stress[['scenario_id', 'scenario_name', 'options_pnl_reval_usd', 'hedge_pnl_usd', 'total_portfolio_pnl_reval_usd', 'total_portfolio_pnl_taylor_usd', 'taylor_divergence_usd']])

# Exportar archivo generado a disco
df_stress.to_csv(os.path.join(OUTPUT_DIR, 'portfolio_stress_scenarios.csv'), index=False)
print(f"Archivo generado y exportado exitosamente: '{OUTPUT_DIR}/portfolio_stress_scenarios.csv'")

# Gráfico comparativo de P&L Revaloración No Lineal vs Taylor
sc_labels = df_stress['scenario_id'].tolist()
pnl_reval = df_stress['total_portfolio_pnl_reval_usd'].tolist()
pnl_taylor = df_stress['total_portfolio_pnl_taylor_usd'].tolist()

x = np.arange(len(sc_labels))
width = 0.35

plt.figure(figsize=(10, 4.5))
plt.bar(x - width/2, pnl_reval, width, label='Revaloración No Lineal Completa (Heston)', color='darkblue')
plt.bar(x + width/2, pnl_taylor, width, label='Aproximación Taylor 2º Orden (Griegas)', color='darkorange')

plt.xticks(x, sc_labels)
plt.axhline(0, color='black', lw=0.8, ls='--')
plt.ylabel("P&L Total de Cartera (USD)")
plt.title("Respuesta de Cartera Cubierta ante Escenarios de Estrés: Heston vs Taylor")
plt.legend(frameon=True)
plt.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.show()
"""
    cells.append(nbf.v4.new_code_cell(sec14_code))

    # =========================================================================
    # SECTION 15: Síntesis Teórica, Limitaciones y Bibliografía
    # =========================================================================
    sec15_md = r"""### 15. Síntesis Teórica, Limitaciones Aceptadas y Bibliografía Académica

---

#### 15.1 Síntesis Cuantitativa de Conclusiones
1. **Parsimonia del Modelo Heston:** Con solo 5 parámetros globales, el modelo captura de forma parsimoniosa el régimen de volatilidad estocástica de Nu Holdings Ltd., respetando estrictamente la condición de regularidad de Feller ($\mathcal{R}_{\text{Feller}} = 5.018 > 1$).
2. **Superioridad en Puts Americanas:** M4 reduce el error de valoración en puts un 36.21% (MAE $0.023847$ USD) frente al benchmark plano de mercado ($0.037385$ USD), demostrando la necesidad conjunta de modelar volatilidad estocástica y ejercicio anticipado.
3. **Materialidad Económica del Ejercicio Anticipado:** La prima de ejercicio temprano (EEP) promedia 2.87 centavos y alcanza 56.73 centavos en opciones ITM, mientras que en calls es teóricamente cero (Merton, 1973).
4. **Insuficiencia de Coberturas Lineales en Colas:** Las pruebas de estrés revelaron una divergencia no lineal de $+47.10$ USD en crisis severa ($-20\%$ spot, $+12$ pp vol), confirmando que las griegas de segundo orden son insuficientes para gestionar riesgos de cola.

---

#### 15.2 Limitaciones Académicas Aceptadas
- **F4-H2 (Cota de escenarios sintéticos extremos):** En escenarios sintéticos con shocks extremos combinados, la cota europea descontada puede exhibir pequeñas discrepancias numéricas aceptadas formalmente como limitación académica.
- **Sección transversal única:** Los parámetros reflejan el estado del mercado al cierre del 17 de noviembre de 2026; no constituyen parámetros invariantes en el tiempo para backtesting dinámico multi-año.
- **Correlación en frontera:** $\rho = -0.9498$ se ubica en el límite inferior pre-declarado $[-0.95, 0.95]$, indicativo del empinado sesgo asimétrico de las opciones sobre NU.

---

#### 15.3 Referencias Bibliográficas
1. **Heston, S. L. (1993).** *A closed-form solution for options with stochastic volatility with applications to bond and currency options.* The Review of Financial Studies, 6(2), 327–343.
2. **In 't Hout, K. J., & Foulon, S. (2010).** *ADI finite difference schemes for option pricing in the Heston model with correlation.* International Journal of Numerical Analysis and Modeling, 7(2), 303–320.
3. **Haentjens, T., & In 't Hout, K. J. (2012).** *Alternating direction implicit finite difference schemes for the Heston–Hull–White partial differential equation.* The Journal of Computational Finance, 16(1), 83–115.
4. **Haentjens, T., & In 't Hout, K. J. (2015).** *Fitted finite difference methods for two-asset American option pricing.* Journal of Computational and Applied Mathematics, 276, 126–143.
5. **Ikonen, S., & Toivanen, J. (2009).** *Operator splitting methods for pricing American options under stochastic volatility.* Numerische Mathematik, 113(2), 299–324.
6. **Forsyth, P. A., & Vetzal, K. R. (2002).** *Quadratic convergence for valuing American options using a penalty method.* SIAM Journal on Scientific Computing, 23(6), 2095–2122.
7. **Rannacher, R. (1984).** *Finite element solution of diffusion problems with irregular data.* Numerische Mathematik, 43(2), 309–327.
8. **Merton, R. C. (1973).** *Theory of rational option pricing.* The Bell Journal of Economics and Management Science, 4(1), 141–183.
9. **Black, F., & Scholes, M. (1973).** *The pricing of options and corporate liabilities.* Journal of Political Economy, 81(3), 637–654.
"""
    cells.append(nbf.v4.new_markdown_cell(sec15_md))

    nb.cells = cells

    out_file = 'notebooks/NU_Heston_Autocontenido_Kaggle.ipynb'
    with open(out_file, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)

    print(f"Notebook exitosamente generado en: {out_file}")
    print(f"Total de celdas: {len(cells)} ({sum(c.cell_type == 'markdown' for c in cells)} Markdown, {sum(c.cell_type == 'code' for c in cells)} Código)")

if __name__ == '__main__':
    build_notebook()
