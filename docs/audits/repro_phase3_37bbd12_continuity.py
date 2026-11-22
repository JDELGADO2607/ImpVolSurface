import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np
from src.heston.solver_2d import Heston2DSolver
from src.heston.pipeline_phase3 import get_phase1_poc_params
from src.heston.rates_curve import get_official_yield_curve
s=Heston2DSolver();p=get_phase1_poc_params();c=get_official_yield_curve();T=60.5/300
for h in (1e-6,1e-8,1e-10):
 a=s.price(12.33,T-h,p,c);b=s.price(12.33,T+h,p,c)
 print('ADAPTIVE_TIME_GRID_JUMP',h,'steps',a.m_t,b.m_t,'left',a.price,'right',b.price,'price_difference',b.price-a.price,'quotient',(b.price-a.price)/(2*h),flush=True)

T=60.5/300;h=1e-10
a=s.price(12.33,T-h,p,c,m_t=120);b=s.price(12.33,T+h,p,c,m_t=120)
print('FIXED_M120_CONTINUITY',a.price,b.price,b.price-a.price,(b.price-a.price)/(2*h),flush=True)
