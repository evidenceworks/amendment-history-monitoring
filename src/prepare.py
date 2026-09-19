"""prepared cohort label-isolated matrix build and pre-model integrity checks. No model fitting."""
import os,pathlib,json,hashlib,sqlite3,csv,copy,datetime,platform,sys,collections
import numpy as np,pandas as pd
from ingest import BASE,WORK
from cohort import derive,plus,paa_class,C,D
from preprocess import fit_maps,apply_maps
from queue_utils import cluster_draw,queue_order,queue_selected,tie
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fixtures():
 def r(kind,seq,**kw):
  d={'rn':seq+{'I':0,'P':10,'S':20,'':30}[kind],'fid':'B00000001-'+kind+str(seq),'rawfid':'B00000001-'+kind+str(seq),'root':'B00000001','kind':kind,'seq':seq,'valid':int(bool(kind)),'bin':'3000001','borough':'Brooklyn','jt':'Alteration','status':'Permit Entire','f':'2019-01-01','a':'2019-02-01','p':'','s':'','u':'2026-01-01','leg':'','review':'Standard Plan Examination','building':'Other','recordsha':kind+str(seq)};d.update(kw);return d
 rows=[r('I',1,p='2020-01-01',s='2022-01-01'),r('P',1,f='2020-06-01',a='2020-06-02'),r('S',2,f='2022-01-01',a='2022-01-02',p='2022-02-01')];base=derive(rows)[0][0]
 for field in ['cost','area','floor','work_on_floor','description','workmask','status','u']:
  modified=copy.deepcopy(rows)
  for z in modified:z[field]='EXCLUDED_MUTATION'
  assert derive(modified)[0][0]==base,field
 changed=copy.deepcopy(rows);changed[0]['s']='2025-06-01';assert derive(changed)[0][0]==base
 changed=copy.deepcopy(rows);changed[2].update(f='2023-01-01',a='2023-02-01',p='2023-03-01',status='Revoked');assert derive(changed)[0][0]==base
 changed=copy.deepcopy(rows);changed[1]['p']='2018-01-01';assert derive(changed)[0][0]['first_permit']=='2020-01-01'
 changed=copy.deepcopy(rows);changed.append(r('',3,f='2023-01-01',a='',p=''));assert derive(changed)[0][0]==base
 changed=copy.deepcopy(rows);changed[1].update(f='',a='');assert derive(changed)[0] is None and 'ambiguous' in derive(changed)[1]
 changed=[r('I',1,a='2020-02-01',p='2020-02-02'),r('S',1,f='2019-06-01',a='2019-07-01',p='2020-01-01')];assert derive(changed)[0][0]['approval_to_F']==-31
 assert plus('2020-02-29',365)=='2021-02-28' and plus('2023-03-01',365)=='2024-02-29'
 assert plus('2022-12-31',365)==D
 assert plus(plus('2024-09-12',365),365)==C and plus(plus('2024-09-13',365),365)>C
 roots=np.array(['a','b','c','d']);bins=['x','x','y','z'];w=cluster_draw(bins,np.random.default_rng(20260916));assert w[0]==w[1];assert np.array_equal(w,cluster_draw(bins,np.random.default_rng(20260916)))
 days=np.array(['2024-01-01']*3+['2024-01-02']);scores=np.array([.7,.7,.1,.2]);selected=queue_selected(roots,days,scores);assert selected.sum()==2 and selected[3]==1 and selected[0 if tie('a')<tie('b') else 1]==1
 weights=np.array([3,2,1,4]);sel=queue_selected(roots,days,scores,weights);assert sel[:3].sum()==2 and sel[3]==1
 expanded_roots=np.repeat(roots,weights);expanded_days=np.repeat(days,weights);expanded_scores=np.repeat(scores,weights);expanded_sel=queue_selected(expanded_roots,expanded_days,expanded_scores);assert np.array_equal(sel,np.array([expanded_sel[expanded_roots==x].sum() for x in roots]))
 return {'excluded_snapshot_field_mutations':True,'future_sibling_mutations':True,'post_L_signoff_predictor_mutation':True,'P_never_contributes_F':True,'cross_filing_signed_lag':True,'unknown_PAA_not_zero':True,'leap_boundaries':True,'paired_BIN_draws':True,'daily_queue_and_copy_ties':True}
def main():
 out=BASE/'prepared_cohort';config=json.loads((BASE/'src/config.json').read_text());tests=[]
 def test(name,ok,detail):tests.append({'invariant':name,'pass':bool(ok),'detail':detail})
 reconciliation=json.loads((BASE/'cohort_reconstruction/flow_reconciliation.json').read_text());audit=json.loads((BASE/'cohort_reconstruction/source_schema_audit.json').read_text());receipt=json.loads((BASE/'config/source_check.json').read_text())
 test('QA1_source_mapping',receipt['source_rows']==audit['rows']==956139 and not audit['date_failures'] and reconciliation['reference_exact_match'],'Exact raw hash/row verification, raw record hashes, duplicate/quarantine logs, reference reference exact reconciliation')
 fixture_results=fixtures();(out/'synthetic_fixture_results.json').write_text(json.dumps(fixture_results,indent=2));test('QA2_clock_and_parentage',True,'Leap-year, earliest-nonPAA, signed cross-filing and no-parent-inference fixtures')
 df=pd.read_csv(BASE/'cohort_reconstruction/event_time_features.csv',dtype={'root':str,'bin':str,'role':str,'quarter':str,'paa_category':str,'first_permit':str,'landmark':str});outcomes=pd.read_csv(BASE/'cohort_reconstruction/outcomes_separate.csv',dtype={'root':str,'role':str,'landmark':str,'observation_end':str,'status_for_S1':str}).fillna({'status_for_S1':''});assert df.root.tolist()==outcomes.root.tolist()
 train=df.loc[df.role=='development'].copy();maps=fit_maps(train);members={};matrices={};unseen={}
 for role in ['development','validation_2023','validation_2024']:
  part=df.loc[df.role==role].copy();x0,x1,n0,n1,unseen[role]=apply_maps(part,maps);assert np.isfinite(x0).all() and np.isfinite(x1).all();matrices[role]=(x0,x1);part[['root','bin','role','first_permit','landmark','mature_2024','no_observed_S']].to_csv(out/(role+'_membership.csv'),index=False);members[role]=part.root.tolist()
  np.save(out/(role+'_M0.npy'),x0,allow_pickle=False);np.save(out/(role+'_M1.npy'),x1,allow_pickle=False)
  # R consumes numbered columns; the feature ledger preserves scientific names.
  for name,mat in [('M0',x0),('M1',x1)]:np.savetxt(out/(role+'_'+name+'.csv'),mat,delimiter=',',header=','.join('x'+str(j+1) for j in range(mat.shape[1])),comments='',fmt='%.17g')
  outcomes.loc[outcomes.role==role].to_csv(out/(role+'_outcomes.csv'),index=False)
 with (out/'preprocessing_maps.json').open('w') as f:json.dump(maps,f,indent=2)
 (out/'unseen_level_frequencies.json').write_text(json.dumps(unseen,indent=2));(out/'formulas.json').write_text(json.dumps({'M0':maps['M0_columns'],'M1':maps['M1_columns'],'likelihood':'Cox Efron unpenalized','no_intercept':True},indent=2))
 # Independent source-row timing checks on every contributor, without accessing outcome labels.
 con=sqlite3.connect(WORK/'source.sqlite');lookup={r[0]:r[1:] for r in con.execute('SELECT rn,kind,f,a,p FROM filings')};timing=True;nonpaa=True
 with (BASE/'cohort_reconstruction/contributing_row_trace.csv').open(newline='',encoding='utf8') as f:
  for trace,(_,fr) in zip(csv.DictReader(f),df.iterrows()):
   assert trace['root']==fr.root
   for name in ['first_permit_rows','P_qualifying_rows','S_filed_rows','S_approved_rows']:
    for rn in filter(None,trace[name].split('|')):
     kind,filing,approval,permit=lookup[int(rn)]
     if name=='first_permit_rows':nonpaa &= kind in ['I','S'] and permit==fr.first_permit
     elif name=='P_qualifying_rows':timing &= kind=='P' and filing<=approval<=fr.landmark
     elif name=='S_filed_rows':timing &= kind=='S' and filing<=fr.landmark
     else:timing &= kind=='S' and filing<=approval<=fr.landmark
 con.close();del lookup
 test('QA3_historical_contributors',timing and nonpaa,'All actual dated P/S contributors checked against the fixed landmark and raw row map')
 test('QA4_future_snapshot_and_outcome_mutations',all(fixture_results.values()),'Pure construction invariant fixtures; no excluded source field is read by the feature constructor')
 dev=outcomes.loc[outcomes.role=='development'];expected_end=np.minimum((pd.to_datetime(dev.landmark)+pd.Timedelta(days=365)).dt.strftime('%Y-%m-%d').to_numpy(),np.array([D]*len(dev)))
 cutoffok=(dev.landmark<D).all() and (dev.duration>0).all() and np.array_equal(expected_end,dev.observation_end.to_numpy()) and (dev.observation_end<=D).all() and (dev.loc[dev.event==1,'observed_signoff']<=dev.loc[dev.event==1,'observation_end']).all() and (dev.status_for_S1=='').all()
 test('QA5_and_A_training_cutoff',cutoffok,'Positive training follow-up; end=min(L+365,2023-12-31); no post-cutoff signoff/status labels in development artifacts')
 shared=all(x0.tobytes()==np.ascontiguousarray(x1[:,:x0.shape[1]]).tobytes() for x0,x1 in matrices.values());test('QA6_and_D_shared_block',shared,'Shared design columns byte-identical for all three temporal roles')
 recidx=[j for j,n in enumerate(maps['M1_columns']) if n.startswith('PAA_recency') or n=='PAA_final_90_days'];ordered=all(np.all(matrices[role][1][df.loc[df.role==role,'paa_category'].to_numpy()=='0'][:,recidx]==0) for role in matrices)
 test('QA6_recency_gating',ordered and set(maps['PAA_development_categories'])=={'0','1','2','3'},'Structural-zero recency for unexposed; fixed PAA category support checked')
 test('E_validation_isolation',set(maps['fit_roots'])==set(members['development']) and not set(maps['fit_roots'])&(set(members['validation_2023'])|set(members['validation_2024'])),'Only positive-follow-up development feature rows fit all maps, levels, knots and ranks; no outcomes passed to preprocessing')
 v23=df[df.role=='validation_2023'];v24=df[df.role=='validation_2024'];mature= v24.first_permit<='2024-09-12';mature_arithmetic=(pd.to_datetime(v24.landmark)+pd.Timedelta(days=365)).dt.strftime('%Y-%m-%d')<=C
 maturity=((pd.to_datetime(v23.landmark)+pd.Timedelta(days=365)).dt.strftime('%Y-%m-%d')<=C).all() and ((pd.to_datetime(v24.landmark)+pd.Timedelta(days=180)).dt.strftime('%Y-%m-%d')<=C).all() and np.array_equal(mature,mature_arithmetic)
 test('QA7_and_F_calendar_maturity',maturity,'2023 365-day, 2024 180-day, mature-2024 exact calendar equivalence')
 forbidden=['floor','cost','area','height','stories','units','workmask','status','signoff','duration','event','description'];test('excluded_snapshot_fields_and_outcomes_absent',all(not any(k in n.lower() for k in forbidden) for n in maps['M1_columns']),'Whitelist-only feature ledger; outcomes are separately stored')
 disjoint=not(set(members['development'])&set(members['validation_2023']) or set(members['development'])&set(members['validation_2024']) or set(members['validation_2023'])&set(members['validation_2024']));test('QA8_split_and_bootstrap_queue',disjoint and fixture_results['paired_BIN_draws'] and fixture_results['daily_queue_and_copy_ties'],'Root-disjoint splits; BIN overlap descriptive, never prohibited')
 overlap={r:len(set(train.bin)&set(df.loc[df.role==r,'bin'])) for r in ['validation_2023','validation_2024']};(out/'BIN_overlap.json').write_text(json.dumps(overlap,indent=2))
 ledger=[]
 for n in maps['M1_columns']:ledger.append({'column':n,'block':'M0_shared' if n in maps['M0_columns'] else 'M1_PAA','class':'procedural_context' if n.startswith(('borough','review','building')) else 'dated_event','source_timing':'I1 procedural context or contributing recorded event <= landmark'})
 ledger += [{'column':n,'block':'excluded','class':'unversioned_snapshot' if n not in ['signoff','duration','event'] else 'outcome','source_timing':'Never in feature matrices'} for n in forbidden]
 pd.DataFrame(ledger).to_csv(out/'feature_ledger.csv',index=False)
 (BASE/'config/environment_lock.json').write_text(json.dumps({'python':sys.version,'numpy':np.__version__,'pandas':pd.__version__,'platform':platform.platform(),'locale':'NYC calendar arithmetic; deterministic lexical ordering','R_expected':'4.6.1, survival 3.8-6','commands':'Python ingest.py; cohort.py; bundled Python prepare.py; ordered subsequent phases'},indent=2))
 passed=all(t['pass'] for t in tests);(out/'invariant_tests.json').write_text(json.dumps({'passed':passed,'tests':tests},indent=2));(out/'PREPARATION_STATUS.txt').write_text('PASS\n' if passed else 'PREPARATION_FAIL\n')
 hashes={p.relative_to(BASE).as_posix():sha(p) for parent in ['config','cohort_reconstruction','prepared_cohort','code'] for p in sorted((BASE/parent).rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.name!='prepared_cohort_manifest.json'}
 (out/'prepared_cohort_manifest.json').write_text(json.dumps({'released_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'passed':passed,'hashes':hashes},indent=2));print(json.dumps({'prepared_cohort_pass':passed,'failed':[t for t in tests if not t['pass']],'design_columns_M0':maps['M0_columns'],'design_columns_M1':maps['M1_columns']},indent=2),flush=True)
if __name__=='__main__':main()
