import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,math
from scipy.stats import norm
from src.heston.solver_2d import Heston2DSolver,Grid2D
from src.heston.heston_model import HestonParams
from src.heston.pipeline_phase2 import get_phase1_poc_params
from src.heston.rates_curve import get_official_yield_curve
from src.pricing_american_fd import fd_american_price
s=Heston2DSolver();p=get_phase1_poc_params()
def crr(K,T,n):
 dt=T/n;u=math.exp(math.sqrt(.2*dt));d=1/u;prob=(math.exp(.05*dt)-d)/(u-d);assert 0<prob<1
 js=np.arange(n+1);asset=12.33*u**(2*js-n);vals=np.maximum(K-asset,0.);disc=math.exp(-.05*dt)
 for step in range(n-1,-1,-1):
  vals=disc*(prob*vals[1:]+(1-prob)*vals[:-1]);asset=12.33*u**(2*np.arange(step+1)-step);vals=np.maximum(vals,K-asset)
 return float(vals[0])
b=HestonParams(.2,2.,.2,0.,0.)
for K,T in ((12.33,94/365),(15.,31/365)):
 am=s.price(K,T,b,.05,is_american=True,m_t=200);eu=s.price(K,T,b,.05,is_american=False,m_t=200)
 vol=math.sqrt(.2);d1=(math.log(12.33/K)+(.05+.1)*T)/(vol*math.sqrt(T));d2=d1-vol*math.sqrt(T);bs=K*math.exp(-.05*T)*norm.cdf(-d2)-12.33*norm.cdf(-d1)
 print('XI_ZERO_COMPARE',K,T,'eu2d',eu.price,'BS',bs,'am2d',am.price,'CRR2500',crr(K,T,2500),'CRR5000',crr(K,T,5000),'FD1D',fd_american_price('P',12.33,K,T,.05,vol,M=800,N=800),flush=True)
T=94/365;h=.0001;r=s.price(12.33,T,p,.05,is_american=True,m_t=100);up=s.price(12.33,T+h,p,.05,is_american=True,m_t=100);down=s.price(12.33,T-h,p,.05,is_american=True,m_t=100)
print('THETA_PLACEHOLDER',r.theta,'INDEPENDENT_FLAT_CALENDAR_THETA',-(up.price-down.price)/(2*h),flush=True)
g=Grid2D(12.33,p.v0);rr=get_official_yield_curve().get_instantaneous_forward_rate(.04)
a1=.5*g.v[None,:]*g.s[1:-1,None]**2*g.st_s['delta'][1:-1,None]+rr*g.s[1:-1,None]*g.st_s['alpha'][1:-1,None]
a2=.5*p.xi*p.xi*g.v[1:-1]*g.st_v['delta'][1:-1]+p.kappa*(p.theta-g.v[1:-1])*g.st_v['alpha'][1:-1]
print('M_MATRIX_CLAIM_A1_GENERATOR_LOWER_MIN',a1.min(),'NEGATIVE_COUNT',np.sum(a1<0),'IMPLICIT_POSITIVE_OFFDIAGONAL',-(1/3)*(31/365/100)*a1.min(),flush=True)
print('M_MATRIX_CLAIM_A2_GENERATOR_LOWER_MIN',a2.min(),'NEGATIVE_COUNT',np.sum(a2<0),flush=True)
