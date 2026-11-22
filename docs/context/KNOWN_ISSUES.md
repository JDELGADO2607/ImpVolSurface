# Hallazgos y aplicabilidad

Referencia vigente [auditoría R3](https://github.com/JDELGADO2607/ImpVolSurface/blob/e1b4f5bf9b306e2213a4858598499ef45d284d66/docs/audits/CODEX_AUDIT_R3_3d81ff1.md), evidencia y scripts enlazados dentro de ella. No se declara ningún problema eliminado hasta probar la ruta Heston implementada. Módulos y líneas exactas constan en el informe fijado.

| R3 ID | Severidad | Estado | Evidencia / módulo | Aplicabilidad Heston |
| --- | --- | --- | --- | --- |
| B-R3-1 | BLOCKER | Abierto, SVI congelado | Mariposas negativas 290,476d K≈9,68, surface.py | Repetir propiedades de precios, no portar armonización SVI |
| H-R3-1 | HIGH | Abierto | Extrapolación desplaza 31d/K10 y 430d/K5 | Política de dominio y selección sí, fórmula SVI histórica |
| H-R3-2 | HIGH | Parcialmente resuelto | strict y flags difieren, LEAPS, 3d | Comprobar cuarentena en todos los consumidores |
| H-R3-3 | HIGH | Abierto | Holdout difiere de refit productivo | Reconstrucción de calibración completa y cobertura |
| H-R3-4 | HIGH | Abierto | Curva manual y conversión par/zero | Vigente en fase 0 |
| M-R3-1 | MEDIUM | Parcialmente resuelto | Nulos y etapas vacías pasan run_all | Vigente |
| M-R3-2 | MEDIUM | Parcialmente resuelto | Pytest reescribe siete salidas | Vigente |
| M-R3-3 | MEDIUM | Abierto | Capital y P&L usan distintas carteras | Vigente en integración |
| M-R3-4 | MEDIUM | Abierto | Métricas y documentación distintas | Vigente |
| L-R3-1 | LOW | Parcialmente resuelto | w != tau IV² junto a nodos, plazo negativo | Propiedades de nueva API, no copiar interpolación |
| L-R3-2 | LOW | Abierto | HAR muestra corta sin orígenes elegibles | Vigente si se reutiliza forecast |

SHA de detección de todas estas filas `3d81ff18cae3a9f8dc74c174015fed17031a8da8`.
R2 en 855eb1cfbd300ddf488bd02d348883f5eac756b8 tenía B1/H1–H5/M1–M3/L1–L2. La matriz completa de resolución y reproducción está en el informe R3. H5 (put K14,75 a 31/37d), M3 (fuga HAR corta) y L1 (cifras straddle Base) se resolvieron en sus contraejemplos concretos. H5 no es demostración global. M3 dejó el nuevo error de muestra vacía L-R3-2. Las restantes resoluciones son parciales o abiertas según esa matriz.

Estados admitidos Abierto, Resuelto, Parcialmente resuelto, No verificable y Obsoleto por cambio metodológico. Congelar SVI no convierte automáticamente sus hallazgos en obsoletos para el benchmark histórico.

## Estado especifico Heston al aprobar fase1

F0-01/F0-02/F0-03 cerrados para la linea base en0fb8758. F1-01,F1-02,F1-03,F1-04 cerrados para PoC en654d1c2; evidencia y reproduccion en HESTON_PHASE_1_654d1c2.md y sus referencias historicas. Los cierres no se trasladan al benchmark SVI ni a modulos financieros aun no integrados. Limitaciones abiertas de datos/identificacion se aceptan para viabilidad, sin prometer parametros unicos ni exactitud global.

## Fase2, SHAcd5ed3e, antes de reparacion1

F2-M1 MEDIUM Abierto: interfaz C con frontera de put (43.9339USD frente a cota77.7222 en prueba de interfaz), theta0 no calculada y dP/dv0 ambiguamente vega. F2-M2 MEDIUM Abierto: identidad IT presentada como resolucion exacta del LCP, garantia M-matriz contradicha por signo de coeficientes y orden de fases confundido. F2-L1 LOW aceptado como limitacion inicial: overshoot cubico~2e-6USD y frontera europea no exacta~1.28e-5USD en caso probado. No defectos materiales de los12 precios puts smoke. Evidencia y scripts HESTON_PHASE_2_cd5ed3e.md. F2-M1/M2 aplican a Heston, no provienen automaticamente de SVI.

Actualizacion posterior fase2, SHAea0df6f: F2-M1 RESUELTO (API puts,thetaNone,sensibilidad varianza explicita). F2-M2 RESUELTO en controles materiales de identidad IT/diagnostico diferencial y M-matrices; residuo editorial se conserva como F2-L2 LOW Abierto, borrador de guion no aprobado para defensa y cifras menores a reconciliar antes de fase8. F2-L1 LOW sigue abierto como limitacion inicial aceptada. Ninguno equivale a un fallo material demostrado de los12precios puts; validacion amplia de fase3 pendiente. Evidencia HESTON_PHASE_2_ea0df6f.md.
