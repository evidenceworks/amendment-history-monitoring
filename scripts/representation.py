"""Reproduce the post-primary base -> any -> count -> history representation audit."""
import argparse, hashlib, json, pathlib, shutil, subprocess, tempfile
import numpy as np, pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
PAIRS=[('M_any','M_base'),('M_count','M_any'),('M_history','M_count'),('M_count','M_base'),('M_history','M_any'),('M_history','M_base')]
def q(a): return np.quantile(np.asarray(a,float),[.025,.975],method='linear')
def auc(y,s,w):
    risk=1-s; order=np.argsort(risk,kind='stable'); r=risk[order]; starts=np.r_[0,np.flatnonzero(np.diff(r))+1]
    cases=np.add.reduceat(w[order]*(1-y[order]),starts); ctrls=np.add.reduceat(w[order]*y[order],starts); den=cases.sum()*ctrls.sum()
    return float((cases*(np.cumsum(ctrls)-.5*ctrls)).sum()/den) if den else np.nan
def deciles(y,s,h,model):
    cuts=np.quantile(s,np.linspace(0,1,11),method='linear'); group=np.searchsorted(cuts[1:-1],s,side='left')+1; rows=[]
    for g in range(1,11):
        z=group==g; rows.append({'model':model,'horizon':h,'decile':g,'n':int(z.sum()),'predicted_persistence':float(s[z].mean()) if z.any() else np.nan,'observed_persistence':float(y[z].mean()) if z.any() else np.nan})
    return rows
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--primary-output',required=True,type=pathlib.Path); ap.add_argument('--output',required=True,type=pathlib.Path); ap.add_argument('--rscript',default='Rscript'); a=ap.parse_args()
    P=a.primary_output.resolve(); O=a.output.resolve()
    if O.exists(): raise SystemExit('output directory must not already exist')
    for d in ['fit','tables','bootstrap','diagnostics','figure']: (O/d).mkdir(parents=True,exist_ok=True)
    R=P/'analysis_results'; W=P/'working_data'
    dev=pd.read_csv(R/'prepared_cohort/development_M1.csv'); dev23=dev.iloc[:,:23]; design=O/'fit/development_M_count.csv'; dev23.to_csv(design,index=False)
    # R on Windows may not reliably parse a non-ASCII working path. Use an
    # ASCII-only scratch directory, then copy outputs into the requested tree.
    fit=O/'fit/M_count'
    with tempfile.TemporaryDirectory(prefix='representation_R_ASCII_') as scratch_name:
        scratch=pathlib.Path(scratch_name); rdesign=scratch/'development_M_count.csv'; routcomes=scratch/'development_outcomes.csv'; rfit=scratch/'M_count'
        shutil.copy2(design,rdesign); shutil.copy2(R/'prepared_cohort/development_outcomes.csv',routcomes)
        subprocess.run([a.rscript,str(R/'src/fit_cox.R'),str(rdesign),str(routcomes),str(rfit)],check=True)
        shutil.copytree(rfit,fit)
    coeff=pd.read_csv(fit/'coefficients.csv').coefficient.to_numpy(); bh=pd.read_csv(fit/'baseline_cumulative_hazard.csv'); times=bh.time.to_numpy(); haz=bh.hazard.to_numpy(); grid=np.arange(366); ix=np.searchsorted(times,grid,side='right')-1; H=np.where(ix>=0,haz[np.maximum(ix,0)],0)
    absrows=[]; conrows=[]; bootrows=[]; diagrows=[]; decrows=[]
    specs=[('validation_2023','2023',['IBS_0_365','Brier_180','Brier_365'],None,'validation_2023',[180,365]),('validation_2024','full_2024',['Brier_180'],None,'validation_2024',[180]),('validation_2024','mature_2024',['IBS_0_365','Brier_365'],'mature','mature_365',[365])]
    for pop,label,losses,subset,wkey,horizons in specs:
        mem=pd.read_csv(R/'prepared_cohort'/f'{pop}_membership.csv',dtype={'root':str,'bin':str}); lab=pd.read_csv(R/'prepared_cohort'/f'{pop}_outcomes.csv')
        sel=np.ones(len(mem),bool) if subset is None else mem.mature_2024.to_numpy(bool)
        z0=np.load(R/'primary_models/predictions'/f'{pop}.npz'); za=np.load(R/'sensitivity_analyses/S5/predictions'/f'{pop}.npz'); X1=np.load(R/'prepared_cohort'/f'{pop}_M1.npy')[:,:23]
        count=np.exp(-np.exp(X1@coeff)[:,None]*H[None,:]); curves={'M_base':z0['M0'],'M_any':za['M1'],'M_count':count,'M_history':z0['M1']}; curves={k:v[sel] for k,v in curves.items()}
        time=lab.duration.to_numpy(float)[sel]; event=lab.event.to_numpy(bool)[sel]; n=len(time); Y=((~event[:,None])|(time[:,None]>grid[None,:])).astype(float); vec={}
        for name,S in curves.items():
            sq=(Y-S)**2
            for loss in losses: vec[(name,loss)]=np.trapezoid(sq[:,:366],dx=1,axis=1)/365 if loss=='IBS_0_365' else sq[:,int(loss.split('_')[1])]
        point={k:float(v.mean()) for k,v in vec.items()}
        wp=W/'evaluation'/'primary_models'/wkey/'paired_weights.int32'; weights=np.fromfile(wp,dtype='<i4').reshape(500,n)
        reps=[]
        for i,w in enumerate(weights,1):
            den=w.sum(); vals={k:float(w@v/den) for k,v in vec.items()}; row={'population':label,'replicate':i}; row.update({f'{m}__{l}':x for (m,l),x in vals.items()})
            for A,B in PAIRS:
                for loss in losses: row[f'{A}_minus_{B}__{loss}']=vals[(A,loss)]-vals[(B,loss)]
            reps.append(row)
        boot=pd.DataFrame(reps); bootrows.extend(reps)
        for name in curves:
            for loss in losses:
                lo,hi=q(boot[f'{name}__{loss}']); absrows.append({'population':label,'model':name,'loss':loss,'estimate':point[(name,loss)],'percentile_2_5':lo,'percentile_97_5':hi,'finite_replicates':500,'requested_replicates':500})
        for A,B in PAIRS:
            for loss in losses:
                col=f'{A}_minus_{B}__{loss}'; lo,hi=q(boot[col]); conrows.append({'population':label,'loss':loss,'contrast':f'{A} - {B}','estimate':point[(A,loss)]-point[(B,loss)],'percentile_2_5':lo,'percentile_97_5':hi,'finite_replicates':500,'requested_replicates':500,'orientation':'first model loss minus second model loss; negative favors first'})
        for hor in horizons:
            y=Y[:,hor]
            for name,S in curves.items():
                diagrows.append({'population':label,'model':name,'horizon':hor,'AUC_event_risk_orientation':auc(y,S[:,hor],np.ones(n)),'mean_predicted_minus_observed_persistence':float((S[:,hor]-y).mean())})
                decrows.extend({**row,'population':label} for row in deciles(y,S[:,hor],hor,name))
    absdf=pd.DataFrame(absrows); condf=pd.DataFrame(conrows); absdf.to_csv(O/'tables/losses.csv',index=False,float_format='%.17g'); condf.to_csv(O/'tables/contrasts.csv',index=False,float_format='%.17g'); pd.DataFrame(bootrows).to_csv(O/'bootstrap/bootstrap.csv',index=False,float_format='%.17g'); pd.DataFrame(diagrows).to_csv(O/'diagnostics/diagnostics.csv',index=False,float_format='%.17g'); pd.DataFrame(decrows).to_csv(O/'diagnostics/calibration.csv',index=False,float_format='%.17g')
    src=condf[((condf.population=='2023')&(condf.loss=='IBS_0_365') | ((condf.population=='full_2024')&(condf.loss=='Brier_180'))) & condf.contrast.isin(['M_any - M_base','M_count - M_any','M_history - M_count'])].copy(); src.to_csv(O/'figure/representation_comparison_figure_source.csv',index=False,float_format='%.17g')
    print('representation audit complete')
if __name__=='__main__': main()
