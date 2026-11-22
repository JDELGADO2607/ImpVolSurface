# Marco matemático

Estado existente BS europeo, EDP americana 1D, Brent y SVI. Estado actualizado: PoC Heston QuantLib aprobada en654d1c2; solver2D propio pendiente de fase2.

En BS, dS=(r-q)S dt+sigma S dW y V_tau=L_BS V, con L_BS=0.5 sigma² S² V_SS+(r-q)S V_S-rV. Calls q=0 con tasas no negativas admiten la valoración europea. Puts requieren ejercicio óptimo, payoff g=(K-S)^+ y V=sup E_Q[D g(S_exercise)]. El motor existente combina Crank–Nicolson, Rannacher y penalización. CRR ofrece contraste independiente. Brent resuelve P_constante(sigma)-P_objetivo=0 con bracket y diagnóstico de error de precio separado del error EDP.

Bajo Q, Heston usa dS=(r(t)-q)S dt+sqrt(v)S dW_S, dv=kappa(theta-v)dt+xi sqrt(v)dW_v, correlación rho. v0 es varianza inicial, kappa velocidad de reversión, theta varianza de largo plazo, xi volatilidad de varianza y rho correlación. v0,theta,kappa,xi positivos y |rho|<1 describen el dominio inicial de calibración. La condición 2 kappa theta>=xi² asegura inaccesibilidad de cero bajo hipótesis CIR apropiadas. Su incumplimiento no elimina la existencia de una solución no negativa, pero exige tratar v=0.

Para tau=T-t, el operador es
L V=0.5 v S² V_SS+(r(t)-q)S V_S+0.5 xi² v V_vv+kappa(theta-v)V_v+rho xi v S V_Sv-r(t)V.
La opción europea satisface V_tau-LV=0. La americana satisface V>=g, V_tau-LV>=0 y (V-g)(V_tau-LV)=0. Inicializar V(S,v,0)=g(S). Especificar compatibilidad de fronteras, truncamiento y ecuación degenerada en v=0 antes de resolver.

En malla uniforme, V_S≈(V_i+1,j−V_i−1,j)/(2hS), V_SS≈(V_i+1,j−2V_i,j+V_i−1,j)/hS² y V_Sv≈(V_i+1,j+1−V_i+1,j−1−V_i−1,j+1+V_i−1,j−1)/(4hS hv). Para malla no uniforme derivar pesos a partir del stencil usado. Tratar deriva y degeneración con justificación. ADI separa sistemas implícitos en S y v y corrige el término mixto. Modified Craig-Sneyd con un tratamiento de obstáculo publicado, como Ikonen–Toivanen, es candidato historico PROPOSED, sustituido para implementacion experimental por H-005A ACCEPTED. Elegir coeficientes y verificar convergencia, sin atribuir a una proyección aislada la precisión del problema complementario.

La función inicial es sum_i (P_Am_Heston(Theta)-P_obs_i)^2 en USD por acción. Cinco parámetros globales, varios inicios, semillas, fronteras, criterio de parada y malla registrados. Holdout se retira antes de ajustar selección y parámetros. Identificación se estudia con dispersión multistart y sensibilidad o perfil de la función objetivo. Parámetros Q no identifican la dinámica física de HAR-RV.

IV put americana equivale a sigma de la EDP 1D que reproduce P_Am_Heston. IV call europea usa BS sobre precio europeo Heston. sqrt(v0), sqrt(theta), sqrt(v_t) e IV son objetos distintos. Para xi=0 y v0=theta la varianza permanece constante, adecuado límite BS.

Griegas deben especificar perturbación, unidad, malla y regla de recalibración. Sensibilidad a v0 difiere de vega por pp de IV. Stress modifica variables interpretables bajo una parametrización común y separa marca inicial de P&L. Escenario nulo y reconciliación por patas son controles obligatorios.

Fuentes para diseñar el método, aún sin solver implementado
- [In ’t Hout y Foulon, ADI Heston](https://arxiv.org/abs/0811.3427).
- [Haentjens e In ’t Hout, ADI para americanas](https://arxiv.org/abs/1309.0110).
- [QuantLib, pruebas de motores](https://github.com/lballabio/QuantLib/blob/master/test-suite/fdheston.cpp).
