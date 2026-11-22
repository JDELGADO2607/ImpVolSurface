import sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,math
from src.heston.solver_2d import Heston2DSolver,Grid2D,solve_tridiagonal_vectorized
from src.heston.heston_model import HestonParams
from src.heston.rates_curve import get_official_yield_curve
from src.heston.pipeline_phase2 import get_phase1_poc_params
s=Heston2DSolver();p=get_phase1_poc_params();c=get_official_yield_curve()
# Independent dense linear solve confirms tridiagonal implementation.
rng=np.random.default_rng(472);n=19;columns=4;a=rng.uniform(-.3,.3,(n-1,columns));b=np.full((n,columns),2.);cc=rng.uniform(-.3,.3,(n-1,columns));z=rng.normal(size=(n,columns));got=solve_tridiagonal_vectorized(a,b,cc,z)
print('THOMAS_DENSE_MAX',max(np.max(abs(got[:,j]-np.linalg.solve(np.diag(b[:,j])+np.diag(a[:,j],-1)+np.diag(cc[:,j],1),z[:,j]))) for j in range(columns)),flush=True)
# Grow the domain with approximately constant transformed-coordinate resolution.
for T in (94/365,794/365):
 base=s.price(12.33,T,p,c,is_american=True,n_s=120,n_v=60,m_t=150)
 ds=max(12.33*.10,.5);dv=max(p.v0*.5,.05)
 ls=lambda top: np.arcsinh((top-12.33)/ds)-np.arcsinh(-12.33/ds)
 ns=int(round(120*ls(160.)/ls(base.s_max)));nv=int(round(60*np.arcsinh(20/dv)/np.arcsinh(base.v_max/dv)))
 grown=s.price(12.33,T,p,c,is_american=True,n_s=ns,n_v=nv,m_t=150,s_max=160.,v_max=20.)
 print('DOMAIN_GROWTH',T,'grids',(120,60,ns,nv),'base',base.price,'grown',grown.price,'delta',grown.price-base.price,flush=True)
# Independent temporal/PDE defect, interior nodes only; this is a trapezoidal consistency diagnostic, not the exact MCS step residual.
def derivative_weights(x,order):
 w=[]
 for i in range(1,len(x)-1):
  dx=x[i-1:i+2]-x[i];mat=np.stack((np.ones(3),dx,dx*dx));target=np.array([0.,1.,0.]) if order==1 else np.array([0.,0.,2.]);w.append(np.linalg.solve(mat,target))
 return np.asarray(w)
def L(r):
 U=r.grid_v_surface;S=r.grid_s;v=r.grid_v;a=derivative_weights(S,1);b=derivative_weights(S,2);d=derivative_weights(v,1);e=derivative_weights(v,2)
 ds=sum(a[:,j,None]*U[j:len(S)-2+j,:] for j in range(3));dss=sum(b[:,j,None]*U[j:len(S)-2+j,:] for j in range(3))
 dv=sum(d[None,:,j]*U[:,j:len(v)-2+j] for j in range(3));dvv=sum(e[None,:,j]*U[:,j:len(v)-2+j] for j in range(3));mixed=sum(d[None,:,j]*ds[:,j:len(v)-2+j] for j in range(3))
 SS=S[1:-1,None];vv=v[None,1:-1];u=U[1:-1,1:-1]
 return .5*vv*SS**2*dss[:,1:-1]+.05*SS*ds[:,1:-1]+.5*p.xi**2*vv*dvv[1:-1,:]+p.kappa*(p.theta-vv)*dv[1:-1,:]+p.rho*p.xi*vv*SS*mixed-.05*u
for N in (20,40,80):
 T=.25;dt=T/N;r=s.price(12.33,T,p,.05,is_american=True,n_s=80,n_v=40,m_t=N);prev=s.price(12.33,T-dt,p,.05,is_american=True,n_s=80,n_v=40,m_t=N-1)
 u=r.grid_v_surface[1:-1,1:-1];up=prev.grid_v_surface[1:-1,1:-1];lam=.5*(r.grid_lambda+prev.grid_lambda)[1:-1,1:-1]
 defect=u-up-dt*(.5*(L(r)+L(prev))+lam);mask=(r.grid_s[1:-1,None]>8)&(r.grid_s[1:-1,None]<18)&(r.grid_v[None,1:-1]>.04)&(r.grid_v[None,1:-1]<.4)
 print('PDE_STEP_DEFECT',N,'reported_comp',r.max_complementarity_residual,'max_price_step_defect_core',np.max(abs(defect[mask])),'norm_per_year',np.max(abs(defect[mask]))/dt,flush=True)
print('DONE',flush=True)
