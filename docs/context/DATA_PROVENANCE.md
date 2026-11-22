# Procedencia y límites

Referencia inspeccionada `3d81ff18cae3a9f8dc74c174015fed17031a8da8`. Original XLSX con dos hojas Yahoo/Bloomberg. Historial diario NU versionado. Fuente exacta y momento de descarga requieren evidencia en fase 0. Las afirmaciones de causa de ceros o corrupción del Excel del informe inicial se conservan como diagnóstico histórico pendiente de respaldo de fuente.

| Archivo | SHA-256 |
| --- | --- |
| data/raw/Opciones_Completo.xlsx | 306f8d3c1a52c7a67952d08881516bdc8632856e3abd6b33de373c4bc77ffb53 |
| data/processed/nu_historical_daily.csv | a510f9a48eaa0fc4f95cfbfcda491de09f4a6b14956efb0f3959c7c57ac5989a |

Valoración histórica 17-nov-2026 16:00 America/New_York, spot 12,33 USD compatible con cierre del historial. q=0 es hipótesis del proyecto. Multiplicador 100, ACT/365F y vencimiento contractual deben conciliar con calendario y marca horaria.

575 contratos originales y 201 contratos invertidos en R3, incluyendo 84 puts, son conteos históricos. Fase 0 debe recomputar puts aptas por strike y tenor. Parsing OCC, normalización Bloomberg y merge 1:1, reconstrucción de tau y filtros económicos están en data_cleaning.py. Conservar motivo por exclusión, sin imponer mínimo de 200 filas al conjunto Heston.

Últimos precios asíncronos, bid/ask mayormente cero o antiguos, años a vencimiento e IV Yahoo dañados. No inventar mid ejecutable ni spread observado. Bloomberg IV sirve de contraste externo, sin usarla como objetivo principal. El histórico de subyacente sirve a estimación física de volatilidad realizada. No existe panel de precios históricos de opciones.

La curva par manual R3 mezcla entradas que difieren del 17-nov de su fuente declarada. get_zero_rate convierte frecuencias e interpola, sin bootstrap de cupones. Fase 0 debe fijar fuente, timestamp de disponibilidad, convención, interpolación, extrapolación, D y F, y etiquetar la aproximación escogida.
[Fuente Treasury](https://home.treasury.gov/resource-center/data-chart-center/interest-rates/TextView?field_tdr_date_value_month=202611&type=daily_treasury_yield_curve).
La publicación del mismo día puede ser posterior a las 16:00. Si se elige un corte ex post, declararlo. Si se exige ex ante, usar datos disponibles a la hora fijada.

Calibración de Heston es Q con puts observadas. HAR-RV estima bajo P una variable diferente. Guardar manifiesto por ejecución con SHA, hashes de insumos, selección y curva consumida. No mezclar salidas R3 y Heston.
