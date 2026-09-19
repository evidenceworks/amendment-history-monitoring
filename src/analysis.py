"""ordered analysis orchestration; all sensitivities are mandatory and retained."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
import pathlib,json,hashlib,subprocess,datetime,shutil,sys,concurrent.futures
import numpy as np,pandas as pd
from ingest import BASE,WORK
from preprocess import fit_maps,apply_maps,ordered_rank
from evaluate import predict_curve,assess_cohort,RSCRIPT
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
CODE=pathlib.Path(__file__).resolve().parent
def rrun(script,*args):
 # Relative ASCII paths avoid R command-argument locale corruption of the Unicode workspace prefix.
 command=[RSCRIPT,os.path.relpath(CODE/script,BASE.parent),*[os.path.relpath(a,BASE.parent) if isinstance(a,pathlib.Path) else str(a) for a in args]]
 subprocess.run(command,check=True,cwd=BASE.parent)
def input_data():
 dtype={'root':str,'bin':str,'role':str,'quarter':str,'paa_category':str,'first_permit':str,'landmark':str};f=pd.read_csv(BASE/'cohort_reconstruction/event_time_features.csv',dtype=dtype);o=pd.read_csv(BASE/'cohort_reconstruction/outcomes_separate.csv',dtype={'root':str,'role':str,'landmark':str,'status_for_S1':str}).fillna({'status_for_S1':''});assert f.root.tolist()==o.root.tolist();return f,o
def save_design(path,df,matrices,labels,maps):
 path.mkdir(parents=True,exist_ok=True)
 for m,x in matrices.items():np.savetxt(path/(m+'.csv'),x,delimiter=',',header=','.join('x'+str(j+1) for j in range(x.shape[1])),comments='',fmt='%.17g')
 labels.to_csv(path/'outcomes.csv',index=False);df[['root','bin','role']].to_csv(path/'membership.csv',index=False);(path/'maps.json').write_text(json.dumps(maps,indent=2))
def model_fit(model,design,labels,extended=False,count_columns=None):
 model.mkdir(parents=True,exist_ok=True)
 rrun('fit_cox.R',design,labels,model,*(['extended',','.join(count_columns)] if extended else []))
def predictions(phases,features,models,maps,mode='primary',reuse0=None):
 dest=phases/'predictions';dest.mkdir(parents=True,exist_ok=True);result={};manifest={}
 for role in ['validation_2023','validation_2024']:
  part=features[features.role==role].copy();x0,x1,n0,n1,_=apply_maps(part,maps)
  if mode=='binary':x1=np.column_stack([x0,(part.paa_category.astype(str)!='0').to_numpy(float)])
  late=x1[:,[n1.index(n) for n in ['PAA_count_1','PAA_count_2','PAA_count_3plus']]] if mode=='extended' else None
  s0=predict_curve(x0,models[0]);s1=predict_curve(x1,models[1],late_X=late)
  path=dest/(role+'.npz');np.savez_compressed(path,roots=part.root.to_numpy(dtype=str),M0=s0,M1=s1);manifest[path.relative_to(BASE).as_posix()]=digest(path);result[role]=(part,s0,s1)
 (dest/'PREDICTIONS_REFERENCE.json').write_text(json.dumps({'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'hashes':manifest,'validation_labels_not_read_by_prediction_function':True},indent=2));return result
def evaluate_all(phases,features,outcomes,preds,primary=False,discordance=False):
 locations={'validation_2023':BASE/'validation_2023' if primary else phases/'validation_2023','validation_2024':BASE/'validation_2024/full_180' if primary else phases/'validation_2024/full_180'}
 summaries={}
 for role in ['validation_2023','validation_2024']:
  part,s0,s1=preds[role];lab=outcomes.set_index('root').loc[part.root];dest=locations[role];horizons=[180,365] if role.endswith('2023') else [180];stop=366 if role.endswith('2023') else 181
  summaries[role]=assess_cohort(dest,WORK/'evaluation'/phases.name/role,part.root.to_numpy(),part.bin.to_numpy(),part.landmark.to_numpy(),lab.duration.to_numpy(),lab.event.to_numpy(),s0[:,:stop],s1[:,:stop],horizons,ibs=role.endswith('2023'),status=lab.status_for_S1.to_numpy(),discordance=discordance)
  if role.endswith('2024'):
   mask=part.mature_2024.to_numpy()==1;dp=BASE/'validation_2024/mature_365' if primary else phases/'validation_2024/mature_365'
   assess_cohort(dp,WORK/'evaluation'/phases.name/'mature_365',part.root.to_numpy()[mask],part.bin.to_numpy()[mask],part.landmark.to_numpy()[mask],lab.duration.to_numpy()[mask],lab.event.to_numpy()[mask],s0[mask],s1[mask],[365],ibs=True,status=lab.status_for_S1.to_numpy()[mask],discordance=discordance,workload=False)
 return summaries
def freeze_results():
 out=BASE/'reference_results';out.mkdir(exist_ok=True);roots=['primary_models','validation_2023','validation_2024','sensitivity_analyses'];files=[p for name in roots for p in sorted((BASE/name).rglob('*')) if p.is_file()];hashes={p.relative_to(BASE).as_posix():digest(p) for p in files};(out/'result_manifest.json').write_text(json.dumps(hashes,indent=2));index=[{'path':n,'sha256':h,'type':'model' if n.endswith('.rds') else 'figure' if n.endswith('.png') else 'table' if n.endswith('.csv') else 'data_or_metadata'} for n,h in hashes.items()];(out/'results_index.json').write_text(json.dumps(index,indent=2))
 p23=pd.read_csv(BASE/'validation_2023/performance.csv').set_index('metric');p24=pd.read_csv(BASE/'validation_2024/full_180/performance.csv').set_index('metric');a=p23.loc['Delta__IBS'];b=p24.loc['Delta__BS_180']
 if a.percentile_2_5>0:classification='deterioration'
 elif a.percentile_97_5<-.002 and b.percentile_97_5<0:classification='replicated nontrivial score gain'
 elif a.percentile_2_5>-.002:classification='margin-excluding near-null'
 elif a.percentile_2_5<=-.002<=a.percentile_97_5:classification='inconclusive'
 elif -.002<a.estimate<0 and a.percentile_97_5<0:classification='small increment'
 else:classification='inconclusive'
 (out/'mechanical_interpretation.json').write_text(json.dumps({'classification':classification,'Delta_IBS_2023':a.to_dict(),'Delta_BS180_2024':b.to_dict(),'rule':'Registered score-margin classification only; no publication, deployment or managerial utility verdict'},indent=2));return classification
def main():
 assert (BASE/'prepared_cohort/PREPARATION_STATUS.txt').read_text().strip()=='PASS'
 f,o=input_data();maps=json.loads((BASE/'prepared_cohort/preprocessing_maps.json').read_text());primary=BASE/'primary_models';primary.mkdir(exist_ok=True)
 single=os.environ.get('REPRO_SINGLE_SENSITIVITY')
 if not (primary/'prefit_code_hashes.json').exists():(primary/'prefit_code_hashes.json').write_text(json.dumps({p.name:digest(p) for p in sorted(CODE.iterdir()) if p.is_file()},indent=2))
 if single:
  assert single in ['S1','S2','S3','S4','S5','S6'];preds={}
  for role in ['validation_2023','validation_2024']:
   part=f[f.role==role].copy();arr=np.load(primary/'predictions'/(role+'.npz'));assert np.array_equal(arr['roots'],part.root.to_numpy(dtype=str));preds[role]=(part,arr['M0'],arr['M1'])
 else:
  for name in ['M0','M1']:
   if not (primary/name/'FIT_STATUS.txt').is_file():model_fit(primary/name,BASE/'prepared_cohort'/('development_'+name+'.csv'),BASE/'prepared_cohort/development_outcomes.csv')
  preds=predictions(primary,f,[primary/'M0',primary/'M1'],maps)
  for name in ['M0','M1']:rrun('ph_diagnostics.R',primary/name/'model.rds',primary/name/'PH_diagnostics')
  evaluate_all(primary,f,o,preds,primary=True)
  print('Primary validation retained; starting all six registered sensitivities',flush=True)
  workers=int(os.environ.get('REPRO_PARALLEL_SENSITIVITIES','1'))
  if workers>1:
   def execute_one(s):
    print('Registered sensitivity dispatched: '+s,flush=True);env=dict(os.environ,REPRO_SINGLE_SENSITIVITY=s,REPRO_PARALLEL_SENSITIVITIES='1');subprocess.run([sys.executable,str(CODE/'analysis.py')],env=env,check=True)
   with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
    futures=[pool.submit(execute_one,s) for s in ['S1','S2','S3','S4','S5','S6']]
    for future in futures:future.result()
   classification=freeze_results();print('analysis complete: '+classification,flush=True);return
 for sensitivity in ([single] if single else ['S1','S2','S3','S4','S5','S6']):
  phases=BASE/'sensitivity_analyses'/sensitivity;phases.mkdir(parents=True,exist_ok=True);ff=f.copy();oo=o.copy();mode='primary';models=[primary/'M0',primary/'M1'];smaps=maps
  if sensitivity=='S1':spreds=preds
  elif sensitivity in ['S2','S3','S6']:
   if sensitivity=='S2':ff=ff[ff.no_observed_S==1]
   elif sensitivity=='S3':ff=ff[~((ff.role=='development') & ff.first_permit.str[:4].isin(['2020','2021']))]
   elif sensitivity=='S6':ff=ff[(ff.role!='development')|ff.first_permit.str[:4].isin(['2021','2022'])]
   train=ff[ff.role=='development'];smaps=fit_maps(train);x0,x1,*_=apply_maps(train,smaps);lab=oo.set_index('root').loc[train.root].reset_index();design=phases/'development_design';save_design(design,train,{'M0':x0,'M1':x1},lab,smaps);models=[phases/'M0',phases/'M1']
   for name,model in zip(['M0','M1'],models):model_fit(model,design/(name+'.csv'),design/'outcomes.csv')
   spreds=predictions(phases,ff,models,smaps)
  else:
   train=ff[ff.role=='development'];x0,x1,n0,n1,_=apply_maps(train,maps);lab=oo[oo.role=='development'];design=phases/'development_design'
   if sensitivity=='S4':mode='extended';save_design(design,train,{'M1':x1},lab,maps);countcols=['x'+str(n1.index(k)+1) for k in ['PAA_count_1','PAA_count_2','PAA_count_3plus']];model_fit(phases/'M1',design/'M1.csv',design/'outcomes.csv',extended=True,count_columns=countcols)
   else:mode='binary';x1=np.column_stack([x0,(train.paa_category.astype(str)!='0').to_numpy(float)]);keep,removed=ordered_rank(x1,n0+['PAA_any'],preserve=len(n0));assert keep==list(range(x1.shape[1]));save_design(design,train,{'M1':x1},lab,{'M0':maps,'M1_columns':n0+['PAA_any']});model_fit(phases/'M1',design/'M1.csv',design/'outcomes.csv')
   models=[primary/'M0',phases/'M1'];spreds=predictions(phases,ff,models,maps,mode=mode)
  (phases/'sensitivity_scope.json').write_text(json.dumps({'sensitivity':sensitivity,'development_roots':int((ff.role=='development').sum()),'validation_2023_roots':int((ff.role=='validation_2023').sum()),'validation_2024_roots':int((ff.role=='validation_2024').sum()),'M0_reference':str(models[0].relative_to(BASE)),'M1_reference':str(models[1].relative_to(BASE)),'fixed_predictions':sensitivity=='S1','mode':mode,'unchanged_development_cutoff':'2023-12-31'},indent=2))
  evaluate_all(phases,ff,oo,spreds,discordance=sensitivity=='S1');print(sensitivity+' complete',flush=True)
 if not single:
  classification=freeze_results();print('analysis complete: '+classification,flush=True)
if __name__=='__main__':main()
