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
