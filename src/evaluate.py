"""Registered horizon metrics and paired 500-replicate evaluation-BIN bootstrap."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import pathlib,json,hashlib,subprocess,datetime,shutil
import numpy as np,pandas as pd
from scipy.special import expit,logit
from queue_utils import cluster_draw,queue_order,queue_selected
from ingest import BASE
RSCRIPT=os.environ.get('REPRO_RSCRIPT') or shutil.which('Rscript') or 'Rscript'
def predict_curve(X,model,grid=np.arange(366),late_X=None):
 coeff=pd.read_csv(model/'coefficients.csv').coefficient.to_numpy();bh=pd.read_csv(model/'baseline_cumulative_hazard.csv');times=bh.time.to_numpy();haz=bh.hazard.to_numpy();idx=np.searchsorted(times,grid,side='right')-1;H=np.where(idx>=0,haz[np.maximum(idx,0)],0)
 if late_X is None:return np.exp(-np.exp(X@coeff)[:,None]*H[None,:])
 base=X@coeff[:X.shape[1]];late=late_X@coeff[X.shape[1]:];idx180=np.searchsorted(times,180,side='right')-1;h180=haz[idx180] if idx180>=0 else 0
 return np.exp(-np.exp(base)[:,None]*np.minimum(H,h180)[None,:]-np.exp(base+late)[:,None]*np.maximum(H-h180,0)[None,:])
def calibration(y,s,w):
 total=w.sum();mean=(w*(s-y)).sum()/total;x=logit(np.clip(s,1e-6,1-1e-6))
 if (w*y).sum()==0 or (w*(1-y)).sum()==0:return mean,np.nan,np.nan,np.nan
 a=0.
 for _ in range(80):
  p=expit(x+a);h=(w*p*(1-p)).sum()
  if h<1e-15:return mean,np.nan,np.nan,np.nan
  delta=(w*(y-p)).sum()/h;a+=delta
  if abs(delta)<1e-10:break
 else:a=np.nan
 b=np.array([0.,1.])
 for _ in range(80):
  p=expit(b[0]+b[1]*x);v=w*p*(1-p);g=w*(y-p);h=np.array([[v.sum(),(v*x).sum()],[(v*x).sum(),(v*x*x).sum()]])
  try:step=np.linalg.solve(h,np.array([g.sum(),(g*x).sum()]))
  except np.linalg.LinAlgError:return mean,a,np.nan,np.nan
  b+=step
  if np.max(np.abs(step))<1e-10:break
 else:b[:]=np.nan
 return mean,a,b[0],b[1]
def auc_setup(y,s):
 risk=1-s;order=np.argsort(risk,kind='stable');starts=np.r_[0,np.flatnonzero(np.diff(risk[order]))+1];return y,order,starts
def auc_weighted(setup,w):
 y,order,starts=setup;cases=np.add.reduceat(w[order]*(1-y[order]),starts);controls=np.add.reduceat(w[order]*y[order],starts);den=cases.sum()*controls.sum()
 return (cases*(np.cumsum(controls)-.5*controls)).sum()/den if den else np.nan
def assess_cohort(out,work,roots,bins,days,time,event,S0,S1,horizons,ibs=False,status=None,discordance=False,reps=500,seed=20260916,workload=True):
 out.mkdir(parents=True,exist_ok=True);work.mkdir(parents=True,exist_ok=True);n=len(roots);grid=np.arange(S0.shape[1]);tau=max(horizons)
 if n==0:
  (out/'undefined.json').write_text(json.dumps({'reason':'Registered cohort empty; no replacement cohort selected'}));return
 event=np.asarray(event,bool);time=np.asarray(time,float)
 original_event=event.copy()
 if discordance:event=event & (np.asarray(status)=='LOC Issued')
 Y=(~event[:,None])|(time[:,None]>grid[None,:]);curves=[S0,S1];loss=[(Y-s)**2 for s in curves];integ=[np.trapezoid(l[:,:366],dx=1,axis=1)/365 for l in loss] if ibs else None
 for m,l in enumerate(loss):pd.DataFrame({'day':grid,'Brier_score':l.mean(axis=0)}).to_csv(out/('M'+str(m)+'_daily_Brier.csv'),index=False)
 rows=[];deciles=[];setup={};orders={}
 for h in horizons:
  y=Y[:,h].astype(float)
  for m,s in enumerate(curves):
   setup[(m,h)]=auc_setup(y,s[:,h]);orders[(m,h)]=queue_order(roots,days,s[:,h]);breaks=np.quantile(s[:,h],np.linspace(0,1,11),method='linear');groups=np.searchsorted(breaks[1:-1],s[:,h],side='left')+1
   for g in range(1,11):
    ix=groups==g;deciles.append({'model':'M'+str(m),'horizon':h,'decile':g,'n':int(ix.sum()),'predicted_persistence':float(s[ix,h].mean()) if ix.any() else None,'observed_persistence':float(y[ix].mean()) if ix.any() else None})
 pd.DataFrame(deciles).to_csv(out/'calibration.csv',index=False)
 def metrics(w):
  values={};den=w.sum()
  for m,s in enumerate(curves):
   prefix='M'+str(m)+'__'
   if ibs:values[prefix+'IBS']=float((w*integ[m]).sum()/den)
   for h in horizons:
    y=Y[:,h].astype(float);values[prefix+'BS_'+str(h)]=float((w*loss[m][:,h]).sum()/den);values[prefix+'AUC_'+str(h)]=auc_weighted(setup[(m,h)],w);cal=calibration(y,s[:,h],w)
    for k,v in zip(['mean_calibration_bias','offset_intercept','joint_intercept','slope'],cal):values[prefix+k+'_'+str(h)]=v
   if workload:
    h=tau;y=Y[:,h];sel=queue_selected(roots,days,s[:,h],w,orders[(m,h)]);flag=sel.sum();persisters=(sel*y).sum();allpersisters=(w*y).sum();values[prefix+'flagged']=int(flag);values[prefix+'realized_review_fraction']=flag/den;values[prefix+'persistence_among_flagged']=persisters/flag if flag else np.nan;values[prefix+'recall_persisters']=persisters/allpersisters if allpersisters else np.nan;values[prefix+'persisters_per_100_reviews']=100*persisters/flag if flag else np.nan
  for k in list(values):
   if k.startswith('M0__'):values['Delta__'+k[4:]]=values['M1__'+k[4:]]-values[k]
  if ibs:values['IBS_relative_reduction_percent']=100*(values['M0__IBS']-values['M1__IBS'])/values['M0__IBS'] if values['M0__IBS'] else np.nan
  return values
 point=metrics(np.ones(n,dtype=np.int32));rng=np.random.default_rng(seed);weights_path=work/'paired_weights.int32';records=[]
 with weights_path.open('wb') as f:
  for b in range(reps):
   w=cluster_draw(bins,rng).astype('<i4');f.write(w.tobytes());records.append({'replicate':b+1,**metrics(w)})
   if (b+1)%100==0:print(str(out.name)+': bootstrap '+str(b+1)+'/'+str(reps),flush=True)
 boot=pd.DataFrame(records)
 # Uno concordance is computed by the same registered survival package, with the identical paired weights.
 pd.DataFrame({'time':np.where(event,time,float(tau+1)),'event':event.astype(int),'risk0':1-S0[:,tau],'risk1':1-S1[:,tau]}).to_csv(work/'concordance_input.csv',index=False)
 relative=lambda p:os.path.relpath(p,BASE.parent)
 subprocess.run([RSCRIPT,relative(pathlib.Path(__file__).with_name('concordance_bootstrap.R')),relative(work/'concordance_input.csv'),relative(weights_path),str(tau),str(reps),relative(out/'concordance_bootstrap.csv')],check=True,cwd=BASE.parent)
 cc=pd.read_csv(out/'concordance_bootstrap.csv')
 for k,col in [('M0__Uno_C_'+str(tau),'M0'),('M1__Uno_C_'+str(tau),'M1'),('Delta__Uno_C_'+str(tau),'difference')]:point[k]=cc.iloc[0][col];boot[k]=cc.iloc[1:][col].to_numpy()
 boot.to_csv(out/'paired_BIN_bootstrap.csv',index=False,float_format='%.17g')
 for key,value in point.items():
  a=boot[key].to_numpy(float);valid=np.isfinite(a);ci=np.quantile(a[valid],[.025,.975],method='linear') if valid.any() else [np.nan,np.nan];rows.append({'metric':key,'estimate':value,'percentile_2_5':ci[0],'percentile_97_5':ci[1],'finite_replicates':int(valid.sum()),'requested_replicates':reps,'CI_scope':'Conditional on fixed fitted models; paired evaluation-BIN bootstrap'})
 pd.DataFrame(rows).to_csv(out/'performance.csv',index=False,float_format='%.17g')
 pd.DataFrame({'root':roots,'bin':bins,'landmark':days,**{f'M{m}_S{h}':s[:,h] for m,s in enumerate(curves) for h in horizons}}).to_csv(out/'horizon_predictions.csv',index=False,float_format='%.17g')
 (out/'evaluation_metadata.json').write_text(json.dumps({'roots':n,'BINs':len(set(bins)),'horizons':horizons,'IBS':ibs,'bootstrap_replicates':reps,'seed':seed,'bootstrap_weight_sha256':hashlib.sha256(weights_path.read_bytes()).hexdigest(),'fixed_daily_workload_target':tau,'discordance_scenario':discordance,'discordant_recorded_events_removed':int((original_event & ~event & (time<=tau)).sum()) if discordance else 0,'decile_rule':'Model-specific linear empirical quantiles; equal cutpoint scores in lower bin; empty bins disclosed','concordance':'survival::concordance timewt=n/G2, ymax=tau, signoff-risk orientation; complete horizon observation removes censor weighting need','queue_duplicate_rule':'Same root tie hash, deterministic copy index represented by multiplicity count; partial last-root copies allowed','calibration':'Diagnostics only; clipped [1e-6,1-1e-6] solely for logit; no recalibration'},indent=2))
 refs={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='ASSESSMENT_REFERENCE.json'}
 (out/'ASSESSMENT_REFERENCE.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hashes':refs},indent=2))
 return pd.DataFrame(rows)
