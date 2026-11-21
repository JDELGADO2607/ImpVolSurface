"""Independent refits of selected whole call/put groups using the production API."""
import sys
from pathlib import Path
import pandas as pd
root=Path(sys.argv[1]).resolve()
sys.path.insert(0,str(root))
from src.surface import VolatilitySurface
from src.market_data import SPOT_PRICE, get_zero_rate
from src.pricing_american_fd import price_american_option
data=pd.read_csv(root/"outputs/tables/options_with_iv.csv")
published=pd.read_csv(root/"outputs/tables/surface_final_holdout_validation.csv").set_index("contractSymbol")
for day, strike in [(31,10.),(31,12.),(59,13.),(794,3.)]:
    held=data.tau_days.sub(day).abs().lt(1e-8)&data.strike.eq(strike)
    train,test=data.loc[~held],data.loc[held]
    assert not ((train.expirationDate.eq(test.expirationDate.iloc[0]))&train.strike.eq(strike)).any()
    s=VolatilitySurface(train)
    for row in test.itertuples():
        t=row.tau_recalc
        res=s.surface_iv(row.k_log_moneyness,t)
        p=price_american_option(row.type,SPOT_PRICE,strike,t,get_zero_rate(t),res["iv"],q=0.)
        record=published.loc[row.contractSymbol]
        print(row.contractSymbol,day,strike,"true_refit",res["iv"]*100,p,"errors",res["iv"]*100-row.our_iv_pct,p-row.lastPrice,
              "published",record.pred_iv_pct,record.pred_price,"policy",res["is_production_ready"],res["quality"],flush=True)
