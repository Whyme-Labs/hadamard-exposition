"""Independent receipt/coverage/summary audit; does not import the experiment."""
import csv
import hashlib
import json
import math
from pathlib import Path
import sys
import numpy as np


def verify(directory: Path) -> dict:
    receipt=json.loads((directory/'receipt.json').read_text())
    if receipt['status']!='passed':
        raise ValueError('study did not complete')
    for name,expected in receipt['output_sha256'].items():
        if Path(name).name!=name:
            raise ValueError('unsafe output name')
        if hashlib.sha256((directory/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('output digest mismatch: '+name)
    with (directory/'cells.csv').open() as f:
        cells=list(csv.DictReader(f))
    seeds=list(range(1000,1100))
    arms=('original','randomized_hadamard','haar_orthogonal','signed_permutation')
    expected={(s,'gaussian_outlier',a,g,r) for s in seeds for a in (1,2,4,8,16,32) for g in (128,32,16) for r in arms}
    expected|={(s,'quantizer_grid',0,128,r) for s in seeds for r in arms}
    actual={}
    for row in cells:
        key=(int(row['seed']),row['case'],int(row['multiplier']),int(row['group']),row['arm'])
        if key in actual: raise ValueError('duplicate cell')
        v=float(row['error'])
        if not math.isfinite(v) or v<0: raise ValueError('bad error')
        actual[key]=v
    if set(actual)!=expected or len(cells)!=7600:
        raise ValueError('coverage differs from frozen protocol')
    summaries=json.loads((directory/'summary.json').read_text())
    expected_settings={(c,a,g) for _,c,a,g,_ in expected}
    if {(r['case'],r['multiplier'],r['group']) for r in summaries}!=expected_settings or len(summaries)!=19:
        raise ValueError('summary setting coverage mismatch')
    idx=np.random.Generator(np.random.PCG64(20261021)).integers(0,100,size=(10000,100))
    checks=0
    for setting in summaries:
        c,a,g=setting['case'],setting['multiplier'],setting['group']
        for r in arms:
            v=[actual[s,c,a,g,r] for s in seeds]
            original=[actual[s,c,a,g,'original'] for s in seeds]
            differences=[x-y for x,y in zip(v,original)]
            record=setting['arms'][r]
            if not math.isclose(math.fsum(v)/100,record['mean_error'],abs_tol=2e-15,rel_tol=2e-13): raise ValueError('mean mismatch')
            if sum(x<0 for x in differences)!=record['wins_vs_original']: raise ValueError('win-count mismatch')
            # Independent sorted-percentile calculation rather than np.quantile.
            boots=np.sort(np.asarray(differences)[idx].mean(axis=1))
            percentiles=[]
            for p in (.025,.975):
                pos=p*9999; lo=math.floor(pos); hi=math.ceil(pos)
                percentiles.append(float(boots[lo]+(boots[hi]-boots[lo])*(pos-lo)))
            if not np.allclose(percentiles,record['paired_95_interval_vs_original'],rtol=2e-13,atol=2e-15): raise ValueError('interval mismatch')
            checks+=3
    return {'status':'passed','cells':len(cells),'settings':len(summaries),'independent_summary_checks':checks,
            'scope':'Independent file integrity, complete coverage, mean, win-count and bootstrap-interval reconstruction from raw cells.'}


if __name__=='__main__':
    print(json.dumps(verify(Path(sys.argv[1])),indent=2))
