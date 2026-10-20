#!/usr/bin/env python3
"""Prespecified fresh-seed synthetic check. Never a model benchmark or award claim."""
from __future__ import annotations
import os
THREAD_KEYS = ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','VECLIB_MAXIMUM_THREADS')
for key in THREAD_KEYS:
    os.environ[key] = '1'
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import sys
import time
import numpy as np
from exact_checks import verify as verify_exact

ROOT = Path(__file__).resolve().parent
REGISTRATION_COMMIT = '7d5e4dabccace930c0de2cc41e7da847486f95a1'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def array_sha(a: np.ndarray) -> str:
    return sha(json.dumps([list(a.shape), a.dtype.str]).encode() + b'\n' + np.ascontiguousarray(a).tobytes())


def transforms(seed: int, n: int) -> dict[str,np.ndarray]:
    if type(n) is not int or n < 1 or n & (n-1):
        raise ValueError('Sylvester dimension must be a positive power of two')
    h = np.array([[1-2*((i&j).bit_count()%2) for j in range(n)] for i in range(n)],dtype=np.float64)
    signs = np.random.Generator(np.random.PCG64(seed+100000)).choice([-1.,1.],size=n)
    gaussian = np.random.Generator(np.random.PCG64(seed+300000)).standard_normal((n,n))
    q,r = np.linalg.qr(gaussian)
    q *= np.where(np.diag(r)<0,-1.,1.)[None,:]
    generator=np.random.Generator(np.random.PCG64(seed+400000))
    permutation=generator.permutation(n)
    p=np.eye(n)[:,permutation]*generator.choice([-1.,1.],size=n)[None,:]
    return {'original':np.eye(n),'randomized_hadamard':signs[:,None]*h/np.sqrt(n),
            'haar_orthogonal':q,'signed_permutation':p}


def quantize_groups(a: np.ndarray, group: int, axis: int) -> np.ndarray:
    a=np.asarray(a,dtype=np.float64)
    if a.ndim!=2 or axis not in (0,1) or type(group) is not int or group<1 or not a.size or not np.isfinite(a).all():
        raise ValueError('finite nonempty matrix, valid feature axis, positive integer group required')
    v=a if axis==1 else a.T
    if v.shape[1]%group:
        raise ValueError('group must divide the feature dimension')
    z=v.reshape(v.shape[0],-1,group)
    peak=np.max(np.abs(z),axis=-1,keepdims=True)
    scale=np.where(peak==0,1.,peak/7.)
    result=(np.clip(np.rint(z/scale),-7,7)*scale).reshape(v.shape)
    return result if axis==1 else result.T


def error(a: np.ndarray,b: np.ndarray) -> float:
    denom=float(np.sum(b*b))
    if denom<=0 or not np.isfinite(denom):
        raise ValueError('nonzero finite reference required')
    result=float(np.sum((a-b)**2)/denom)
    if not np.isfinite(result):
        raise ValueError('nonfinite error')
    return result


def summarize(records: list[dict], arms: list[str], seeds: list[int], draws: int, bootstrap_seed: int) -> list[dict]:
    if len(seeds)!=len(set(seeds)) or len(arms)!=len(set(arms)) or not seeds:
        raise ValueError('nonempty unique seed and arm identities required')
    positions=np.random.Generator(np.random.PCG64(bootstrap_seed)).integers(0,len(seeds),size=(draws,len(seeds)))
    groups={}
    for row in records:
        key=(row['case'],row['multiplier'],row['group'])
        cell=(row['seed'],row['arm'])
        cells=groups.setdefault(key,{})
        if cell in cells:
            raise ValueError('duplicate cell')
        cells[cell]=row['error']
    expected={(s,a) for s in seeds for a in arms}
    output=[]
    for key,cells in sorted(groups.items()):
        if set(cells)!=expected:
            raise ValueError('missing or unexpected cell')
        values={a:np.array([cells[s,a] for s in seeds],dtype=np.float64) for a in arms}
        result={'case':key[0],'multiplier':key[1],'group':key[2],'seeds':len(seeds),'arms':{}}
        for arm,v in values.items():
            if not np.isfinite(v).all() or np.any(v<0):
                raise ValueError('invalid error')
            delta=v-values['original']
            interval=np.quantile(delta[positions].mean(axis=1),[.025,.975],method='linear').tolist()
            result['arms'][arm]={'mean_error':float(v.mean()),'mean_delta_vs_original':float(delta.mean()),
                'paired_95_interval_vs_original':interval,'wins_vs_original':int(np.sum(delta<0)),
                'min_error':float(v.min()),'max_error':float(v.max())}
        if 'haar_orthogonal' in values and 'randomized_hadamard' in values:
            delta=values['randomized_hadamard']-values['haar_orthogonal']
            result['hadamard_minus_haar']={'mean':float(delta.mean()),
                'descriptive_paired_95_interval':np.quantile(delta[positions].mean(axis=1),[.025,.975],method='linear').tolist()}
        output.append(result)
    return output


def write_json(path: Path, obj: dict | list) -> None:
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n')
    temp.replace(path)


def run(out: Path) -> dict:
    out.mkdir(parents=True,exist_ok=False)
    start=time.perf_counter()
    protocol=json.loads((ROOT/'protocol-v2.json').read_text())
    sources={p.name:sha(p.read_bytes()) for p in sorted(ROOT.iterdir()) if p.is_file() and p.suffix in ('.py','.json')}
    receipt={'schema':'hadamard-strengthening-results.v2','status':'running',
        'registration_commit':REGISTRATION_COMMIT,'started_utc':datetime.now(timezone.utc).isoformat(),
        'source_sha256':sources,'environment':{'python':sys.version,'numpy':np.__version__,'platform':platform.platform(),
        'thread_env':{k:os.environ[k] for k in THREAD_KEYS}},'scope':'Fresh pseudorandom samples within the same synthetic family. No new algorithm, model result or award claim.'}
    write_json(out/'receipt.json',receipt)
    try:
        seeds=list(range(protocol['seeds']['first'],protocol['seeds']['last_inclusive']+1))
        n=protocol['shape']['input_features']; t=protocol['shape']['activation_rows']; m=protocol['shape']['output_features']
        arms=protocol['arms']; groups=protocol['groups']; amps=protocol['outlier_multipliers']
        rows=[]; inputs=[]; peak_ortho=peak_invariance=peak_permutation=0.
        for seed in seeds:
            rng=np.random.Generator(np.random.PCG64(seed))
            xbase=rng.standard_normal((t,n)); w=rng.standard_normal((n,m))/np.sqrt(n)
            qs=transforms(seed,n)
            inputs.append({'seed':seed,'base_x_sha256':array_sha(xbase),'w_sha256':array_sha(w),
                'q_sha256':{a:array_sha(q) for a,q in qs.items()},
                'q_largest_absolute_entry':{a:float(np.abs(q).max()) for a,q in qs.items()}})
            for q in qs.values():
                peak_ortho=max(peak_ortho,float(np.max(np.abs(q@q.T-np.eye(n)))))
            datasets=[]
            for amp in amps:
                x=xbase.copy(); x[:,0]*=amp
                datasets.append(('gaussian_outlier',amp,x,w,groups))
            grng=np.random.Generator(np.random.PCG64(seed+200000))
            gx=grng.integers(-7,8,size=(t,n)).astype(np.float64)
            gw=grng.integers(-7,8,size=(n,m)).astype(np.float64)
            gx[:,0]=7.; gw[0,:]=7.
            datasets.append(('quantizer_grid',0,gx,gw,[128]))
            inputs[-1]['grid_x_sha256']=array_sha(gx); inputs[-1]['grid_w_sha256']=array_sha(gw)
            for case,amp,x,weight,group_set in datasets:
                y=x@weight
                errors={}
                for arm,q in qs.items():
                    xr,wr=(x,weight) if arm=='original' else (x@q,q.T@weight)
                    discrepancy=np.sqrt(error(xr@wr,y))
                    peak_invariance=max(peak_invariance,float(discrepancy))
                    for group in group_set:
                        observed=error(quantize_groups(xr,group,1)@quantize_groups(wr,group,0),y)
                        errors[group,arm]=observed
                        rows.append({'seed':seed,'case':case,'multiplier':amp,'group':group,'arm':arm,'error':observed})
                peak_permutation=max(peak_permutation,abs(errors[128,'original']-errors[128,'signed_permutation']))
                if case=='quantizer_grid' and max(errors[128,'original'],errors[128,'signed_permutation'])>1e-27:
                    raise ArithmeticError('grid/permutation control failed')
            if time.perf_counter()-start > protocol['resource_limits']['outer_seconds']:
                raise TimeoutError('internal study time limit exceeded')
        limits=protocol['arithmetic_controls']
        if peak_ortho>limits['orthogonality_max_absolute_limit'] or peak_invariance>limits['full_precision_relative_norm_limit'] or peak_permutation>limits['permutation_group128_error_invariance_absolute_limit']:
            raise ArithmeticError('numerical control exceeded protocol limit')
        expected_count=len(seeds)*(len(amps)*len(groups)+1)*len(arms)
        if len(rows)!=expected_count:
            raise ArithmeticError('wrong number of cells')
        summary=summarize(rows,arms,seeds,protocol['bootstrap']['draws'],protocol['bootstrap']['seed'])
        primary=next(s for s in summary if s['case']=='gaussian_outlier' and s['multiplier']==32 and s['group']==32)
        numerical_seconds=time.perf_counter()-start
        exact=verify_exact(protocol['exact_conjecture_checks']['paley_primes'])
        write_json(out/'exact-checks.json',exact)
        write_json(out/'inputs.json',inputs)
        write_json(out/'summary.json',summary)
        with (out/'cells.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=['seed','case','multiplier','group','arm','error'],lineterminator='\n')
            writer.writeheader(); writer.writerows(rows)
        if sources!={p.name:sha(p.read_bytes()) for p in sorted(ROOT.iterdir()) if p.is_file() and p.suffix in ('.py','.json')}:
            raise RuntimeError('source changed during execution')
        receipt.update(status='passed',cells=len(rows),settings=len(summary),primary=primary,
            directional_confirmation_within_synthetic_family=primary['arms']['randomized_hadamard']['paired_95_interval_vs_original'][1]<0,
            controls={'orthogonality_max_absolute':peak_ortho,'full_precision_max_relative_norm':peak_invariance,
                      'signed_permutation_group128_max_error_difference':peak_permutation},
            numerical_and_summary_seconds=numerical_seconds,
            output_sha256={p.name:sha(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='receipt.json'})
    except Exception as exc:
        receipt.update(status='failed',error={'type':type(exc).__name__,'message':str(exc)})
        raise
    finally:
        receipt.update(finished_utc=datetime.now(timezone.utc).isoformat(),wall_seconds=time.perf_counter()-start)
        write_json(out/'receipt.json',receipt)
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.output)
    print(json.dumps({'status':result['status'],'cells':result['cells'],'seconds':result['wall_seconds'],'primary':result['primary']},indent=2))
