# Auditoria independiente Heston fase 0 — reparacion 1

SHA 0fb87583c6f4023049a4e6f4ae5c36c7aad247d3, PR #5.
Dictamen PHASE_APPROVED para preparacion de datos y baseline. Autoriza PHASE_1 bajo la especificacion publicada de PoC. No certifica un motor Heston aun inexistente.

Extraccion limpia. Ocho tests aprobados en 14,90s. Pipeline fase 0 codigo 0 en 10,11s, directorio aislado. Trece CSV reproducidos con igualdad exacta de valores.

## Resolucion

F0-01 RESOLVED para la curva Python de instrumentos nocionales. Bootstrap resuelve cada D(T) con cupones bajo la misma interpolacion log-lineal. Repricing independiente PV=100*(y/2)*sum_j D(j/2)+100*D(T), con cupon incluyendo el terminal. Residuos 1Y/2Y/3Y/5Y/20Y cero a precision mostrada; 7Y 2,84e-14; 10Y -2,84e-14; 30Y -1,71e-13 USD. Esto prueba consistencia interna de instrumentos sinteticos, no recuperacion unica de los bonos Treasury negociados. Corto plazo mantiene aproximacion money market explicitada.

F0-02 RESOLVED. Ahora misma sigma y motor al comparar tasas. Maximo efecto puro AmericanFlat QuantLib 0,00090434 USD; SVI RepoPDE 0,00090817 USD. Diferencia SVI QuantLib menos RepoPDE maxima 0,00239632 USD queda separada. Benchmark R3 publicado conservado. No se infiere causa unica del sesgo SVI.

F0-03 PARTIALLY_RESOLVED y limitacion aceptada para preparacion. requirements-heston fija QuantLib 1.44 y se detecta version real. Fuente Treasury con tabla y hash persistente, parametros y referencia SVI trazados. El archivo llamado raw se genera desde constantes con timestamp de recuperacion literal. Sirve como transcripcion de fila, no como captura HTTP original. En fase 1 preservar la transcripcion como insumo y distinguir su fecha original de ejecucion sin simular nueva recuperacion.

## Pendientes del gate de fase 1

La conversion a QuantLib redondea t*365 a dias pero conserva D de t original. Mi barrido de dias 1–794 encontro max |D_QL-D_Python|=0,0000631505 en dia183. En 31d salen 0,9964859341 y 0,9965312494. Es pequeno para precios del caso pero no es identidad exacta. Antes de calibrar fijar una curva de consumo comun y contrastar descuentos en fechas contractuales e instantes de ejercicio, explicando la conversion. No aceptar afirmar curvas identicas si no lo son.

Los benchmarks americanos fase 0 todavia usan FlatForward por contrato con r(T). Son aproximacion identificada del baseline, no dinamica comun de fase1. El PoC debera consumir la curva temporal unica y recalcular el benchmark constante comparable bajo ella.

Muestra sigue 97 seleccionadas, particion 60 train/22 strike/15 tenor, 142 calls de contraste. Fijar reglas y split sin cambios oportunistas. Muestra comun SVI 84, no confundir precision en 97 con mejora sobre 84.

## Gate PoC fijado antes del ajuste

Numerico objetivo 0,002 USD por accion, quinta parte de granularidad de 0,01, sin interpretar granularidad como spread. Medir con tres mallas y refinamiento separado pertinente. Si una excepcion supera presupuesto, localizar, refinar y documentar antes de aprobar, sin clipping de precios.

Train MAE<=0,080 USD y RMSE<=0,120; cada holdout MAE<=0,100 USD. Reportar N, cobertura, distribucion de precios y errores por tenor/moneyness. Brecha relativa 30% y maximo relativo ATM 10% son diagnosticos, no rechazo automatico aislado por composicion o denominador pequeno. Comparar benchmark constante en identica muestra/curva y SVI solo donde cubre, sin exigir ganarle in-sample.

Cinco starts dispersos. Positividad v0/theta/kappa/xi, correlacion en [-0,95;0,95] para no imponer signo como ley economica. Rango inicial v0/theta [0,01;1,5], kappa [0,1;15], xi [0,05;3] es dominio de busqueda predeclarado, no frontera teorica. Reportar soluciones pegadas y sensibilidad, Feller sin filtro automatico. Optimizar solo train. Tiempo/evaluaciones registrados sin limite rigido de 60s. No iniciar solver propio antes de viabilidad economica, predictiva y computacional auditada.
