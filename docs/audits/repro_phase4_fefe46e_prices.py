import sys,json,time,contextlib,io,tempfile
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
import numpy as np,pandas as pd,QuantLib as ql
from src.heston.rates_curve import get_official_yield_curve
import src.heston.pipeline_phase4 as p
base=Path('data/heston/phase4');names=['v0','kappa','theta','xi','rho']
w=json.loads((base/'heston_calibrated_parameters.json').read_text());candidates=pd.read_csv(base/'heston_candidates_fine_eval.csv')
exact=np.array([.18613777847584,2.7254603668370714,.2136796992000426,.4817847258429695,-.9498066630129804]);rounded=np.array(w['calibrated_parameters_raw']);a=candidates.iloc[0][names].to_numpy(float)
curve=get_official_yield_curve();ts=curve.to_quantlib_term_structure(dense_daily=True);date=ql.Date(17,11,2026);ql.Settings.instance().evaluationDate=date
div=ql.YieldTermStructureHandle(ql.FlatForward(date,0.,ql.Actual365Fixed()));spot=ql.QuoteHandle(ql.SimpleQuote(12.33))
models={n:ql.HestonModel(ql.HestonProcess(ts,div,spot,*map(float,v))) for n,v in [('poc_exact',exact),('poc_rounded',rounded),('refinement_A',a)]}
records=[]
for days in [31,94,430,794]:
 for k in [9.,12.33,17.]:
  r={'days':days,'strike':k}
  for name,model in models.items():
   opt=ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put,k),ql.AmericanExercise(date,date+days));opt.setPricingEngine(ql.FdHestonVanillaEngine(model,max(120,round(700*days/365)),280,140));r[name]=opt.NPV()
  records.append(r)
out=pd.DataFrame(records);out.to_csv('audit_phase4_prices.csv',index=False)
print('INDEPENDENT_QL_12_CONTRACTS',out.to_json(orient='records'),flush=True)
print('ROUNDING_MAX_USD',abs(out.poc_exact-out.poc_rounded).max(),'REFINEMENT_A_POC_MAX_USD',abs(out.refinement_A-out.poc_exact).max(),flush=True)
# Selection routine exercised on a small real contract fixture, all optimized candidates marked failed.
orig=p.PHASE4_DIR;cfg=p.load_config();ref=pd.read_csv(base/'heston_local_refinements.csv');ref.loc[ref.start_index.ne(0),['status','success']]=[2,False]
train=pd.read_csv('data/heston/puts_selected_clean.csv').iloc[:1].copy()
with tempfile.TemporaryDirectory() as t:
 p.PHASE4_DIR=Path(t)
 with contextlib.redirect_stdout(io.StringIO()):d,win=p.step4_evaluate_candidates_fine_and_select(ref,train,ts,cfg)
 print('ALL_LOCAL_REFINEMENTS_FAILED_SELECTION',win['selection_status'],'eligible_nonbenchmark',int(d[d.start_index.ne(0)].eligible_for_selection.sum()),flush=True)
p.PHASE4_DIR=orig
print('DONE',flush=True)
