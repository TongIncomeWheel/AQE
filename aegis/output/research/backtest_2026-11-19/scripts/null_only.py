"""Re-run only the permutation null for a mode (the combined run hit the background time limit)."""
import sys, numpy as np, pandas as pd
import recipe as R
from multiprocessing import Pool
if __name__ == '__main__':
    rec = R.search(R.TRAIN)
    with Pool(4) as p: null = np.array(p.map(R._perm, range(1000, 1000 + R.NPERM)))
    nd = dict(real_train_obj=rec['train_obj'], null_mean=null.mean(), null_p95=np.percentile(null, 95), null_max=null.max(),
              p_value=(1 + (null >= rec['train_obj']).sum()) / (1 + len(null)), n_perm=len(null), recipes_tried_per_search=rec['tried'], features_screened_for_pool=len(R.FE))
    pd.Series(nd).to_csv(R.D + f'tables/permutation_null_{R.MODE}.csv'); pd.Series(null).to_csv(R.D + f'tables/permutation_null_draws_{R.MODE}.csv', index=False)
    print(pd.Series(nd).to_string())
