"""Root reconstruction used by the published analysis. Pure derive() is reused by mutation fixtures."""
import pathlib,os,json,sqlite3,csv,collections,itertools,datetime,re,math
from ingest import BASE,WORK
C='2026-09-12';D='2023-12-31';good=lambda x:x not in ['',None,'INVALID'];date=lambda s:datetime.date.fromisoformat(s);plus=lambda s,n:(date(s)+datetime.timedelta(days=n)).isoformat()
BOROUGHS={'Brooklyn','Manhattan','Queens','Staten Island','Bronx'}
def future(r,L,F):
 return good(r['f']) and r['f']>L and (not r['a'] or good(r['a']) and r['a']>L) and (not r['p'] or good(r['p']) and r['p']>F)
def paa_class(r,L):
 f,a=r['f'],r['a']
 if good(f) and good(a):
  if f<=a:return 'qualify' if a<=L else 'future'
  return 'future' if f>L and a>L else 'ambiguous_order'
 if good(f) and f>L and (not good(a) or a>L):return 'future'
 if good(a) and a>L and not good(f):return 'future'
 return 'ambiguous_dates'
def derive(rows):
 # Duplicate collapse is by exact source record bytes, not selected fields.
 unique={r['recordsha']:r for r in rows};rr=sorted(unique.values(),key=lambda r:r['rn']);ini=[r for r in rr if r['valid'] and r['kind']=='I' and r['seq']==1]
 if len(ini)!=1:return None,'I1_identity_ambiguity'
 i=ini[0]
 if i['jt']!='Alteration':return None,'I1_not_Alteration'
 if i['borough'] not in BOROUGHS or not re.fullmatch('[1-5][0-9]{6}',i['bin']):return None,'I1_BIN_borough_invalid'
 if not good(i['f']):return None,'I1_filing_missing_invalid'
 if i['leg'].strip().upper()=='YES':return None,'explicit_I1_legalization'
 non=[r for r in rr if r['valid'] and r['kind'] in ['I','S']]
 ps=[r['p'] for r in non if good(r['p']) and r['p']<=C]
 if not ps:return None,'no_valid_observed_nonPAA_permit'
 F=min(ps)
 if i['f']>F:return None,'I1_filing_after_F'
 for r in non:
  if r['p']=='INVALID' and (not good(r['f']) or r['f']<=F):return None,'potential_earliest_permit_unparseable'
  if r['p']==F:
   if not good(r['f']) or r['f']>F:return None,'contributing_permit_filing_chronology'
   if r['a'] and (not good(r['a']) or not r['f']<=r['a']<=r['p']):return None,'contributing_permit_approval_chronology'
 L=plus(F,365)
 if L>C:return None,'landmark_after_C'
 if i['s']=='INVALID':return None,'I1_signoff_unparseable'
 if good(i['s']) and i['s']<F:return None,'I1_signoff_before_F'
 if good(i['s']) and i['s']<=L:return None,'I1_signoff_by_L'
 groups=collections.defaultdict(list)
 for r in rr:groups[r['fid']].append(r)
 for fid,rs in groups.items():
  if len(rs)>1:
   if all((paa_class(r,L)=='future' if r['kind']=='P' else future(r,L,F)) for r in rs):continue
   return None,'conflicting_relevant_filing_identifier'
 for r in rr:
  if not r['valid'] and not future(r,L,F):return None,'malformed_relevant_sibling'
 pqual=[];sfile=[];sapproved=[];nos=True
 for fid,rs in groups.items():
  r=rs[0]
  if not r['valid']:continue
  if r['kind']=='P':
   pc=paa_class(r,L)
   if pc.startswith('ambiguous'):return None,'PAA_history_'+pc
   if pc=='qualify':pqual.append(r)
  elif r['kind']=='S':
   if not good(r['f']) or r['f']<=L:nos=False
   if good(r['f']) and r['f']<=L:
    sfile.append(r)
    if good(r['a']) and r['f']<=r['a']<=L:sapproved.append(r)
 count=len(pqual);reviews={r['review'] for r in sfile if r['review'].strip()};lag=(date(F)-date(i['a'])).days if good(i['a']) and i['f']<=i['a']<=L else None;year=int(F[:4]);quarter=(int(F[5:7])-1)//3+1
 role='development' if 2017<=year<=2022 else 'validation_2023' if year==2023 else 'validation_2024' if year==2024 else 'excluded_'+str(year)
 if role=='development' and L>=D:role='development_zero_followup'
 feature={'root':i['root'],'bin':i['bin'],'role':role,'first_permit':F,'landmark':L,'borough':i['borough'],'review':i['review'] or None,'building':i['building'] or None,'year_centered':year-2020,'quarter':str(quarter),'filing_to_F':(date(F)-date(i['f'])).days,'approval_to_F':lag,'S_filed':len(sfile),'S_approved':len(sapproved),'S_review_diversity':len(reviews) if reviews or not sfile else None,'paa_category':str(min(count,3)),'paa_recency':(date(L)-date(max(r['a'] for r in pqual))).days if pqual else None,'paa_90':int(bool(pqual) and (date(L)-date(max(r['a'] for r in pqual))).days<=90),'no_observed_S':int(nos),'mature_2024':int(year==2024 and F<='2024-09-12')}
 end=min(plus(L,365),D) if role=='development' else C
 event=bool(good(i['s']) and L<i['s']<=end);stop=i['s'] if event else end
 outcome={'root':i['root'],'role':role,'landmark':L,'observation_end':end,'duration':(date(stop)-date(L)).days,'event':int(event),'observed_signoff':i['s'] if event else '', 'status_for_S1':i['status'] if role.startswith('validation') else ''}
 trace={'I1_raw_row':i['rn'],'I1_legalization_raw':i['leg'],'I1_job_type_raw':i['jt'],'first_permit_rows':'|'.join(str(r['rn']) for r in non if r['p']==F),'P_qualifying_rows':'|'.join(str(r['rn']) for r in pqual),'S_filed_rows':'|'.join(str(r['rn']) for r in sfile),'S_approved_rows':'|'.join(str(r['rn']) for r in sapproved)}
 return (feature,outcome,trace),'retained'
def an_reference(rows):
 # Exact reference operational rules, reconstructed from the same raw rows for reconciliation only.
 valid=[r for r in rows if re.fullmatch(r'[BMQSX][0-9]{8}-[ISP][1-9][0-9]*',r['rawfid'])];ini=[r for r in valid if r['kind']=='I' and r['seq']==1]
 if not any(r['jt']=='Alteration' for r in ini):return None
 if len(ini)!=1 or any(r['kind']=='I' and r['seq']!=1 for r in valid) or len(valid)!=len({r['rawfid'] for r in valid}):return None
 i=ini[0];bins={r['bin'] for r in valid};bm={'B':'Brooklyn','M':'Manhattan','Q':'Queens','S':'Staten Island','X':'Bronx'}
 if len(bins)!=1 or not all(re.fullmatch('[1-5][0-9]{6}',v) for v in bins) or {r['borough'] for r in valid}!={bm[i['root'][0]]} or len(valid)!=len(rows):return None
 non=[r for r in valid if r['kind'] in ['I','S']]
 if any(r['leg'].strip().upper()=='YES' for r in rows) or any(r['jt']!='Alteration' or 'certificate of operation' in r['status'].lower() for r in non):return None
 permits=[r['p'] for r in non if good(r['p']) and r['p']<=C]
 if not permits:return None
 F=min(permits)
 for r in non:
  if not good(r['f']):return None
  if any(r[k]=='INVALID' or good(r[k]) and r[k]>C for k in ['f','a','p','s']):return None
  if any(good(r[a]) and good(r[b]) and r[a]>r[b] for a,b in [('f','a'),('f','p'),('f','s'),('a','p'),('p','s')]):return None
 if i['f']>F or good(i['a']) and i['a']>F or good(i['s']) and i['s']<F:return None
 L=plus(F,365)
 if L>C or good(i['s']) and i['s']<=L:return None
 n=0
 for r in [z for z in valid if z['kind']=='P']:
  f,a=r['f'],r['a']
  if good(a) and a>L:continue
  if good(a) and a<=L:
   if good(f) and f<=a:n+=1
   else:return None
  elif not good(f) or f<=L:return None
 return {'exposed':n>0,'event':good(i['s']) and L<i['s']<=C}
def main():
 con=sqlite3.connect(WORK/'source.sqlite');con.row_factory=sqlite3.Row;rootflow=collections.Counter();an=collections.Counter();exp=collections.defaultdict(collections.Counter);ends=collections.defaultdict(collections.Counter);members=collections.Counter();potentials=collections.defaultdict(list);files=[];writers={}
 def writer(name,fields):
  f=(BASE/'cohort_reconstruction'/name).open('w',encoding='utf8',newline='');files.append(f);w=csv.DictWriter(f,fieldnames=fields);w.writeheader();return w
 ledger=writer('root_reconciliation.csv',['root','reference_member','study_member','study_decision','raw_rows','exact_duplicate_excess'])
 quarantine=writer('quarantine.csv',['root','reason','raw_rows']);duplicates=writer('duplicate_records.csv',['root','record_sha256','multiplicity','raw_rows']);featurew=outcomew=tracew=None
 for rt,g in itertools.groupby(con.execute("SELECT * FROM filings WHERE root!='' ORDER BY root,rn"),lambda r:r['root']):
  rows=[dict(r) for r in g];selected=any(r['valid'] and r['kind']=='I' and r['seq']==1 and r['jt']=='Alteration' for r in rows)
  if not selected:continue
  rawgroups=collections.defaultdict(list)
  for r in rows:rawgroups[r['recordsha']].append(r['rn'])
  for h,ns in rawgroups.items():
   if len(ns)>1:duplicates.writerow({'root':rt,'record_sha256':h,'multiplicity':len(ns),'raw_rows':'|'.join(map(str,ns))})
  ar=an_reference(rows)
  if ar is not None:an['risk_roots']+=1;an['exposed_roots']+=ar['exposed'];an['overall_events']+=ar['event']
  result,reason=derive(rows);rootflow[reason]+=1
  ledger.writerow({'root':rt,'reference_member':int(ar is not None),'study_member':int(result is not None),'study_decision':reason,'raw_rows':'|'.join(str(r['rn']) for r in rows),'exact_duplicate_excess':len(rows)-len(rawgroups)})
  if result is None:quarantine.writerow({'root':rt,'reason':reason,'raw_rows':'|'.join(str(r['rn']) for r in rows)});continue
  feature,outcome,trace=result
  if featurew is None:featurew=writer('event_time_features.csv',list(feature));outcomew=writer('outcomes_separate.csv',list(outcome));tracew=writer('contributing_row_trace.csv',['root']+list(trace))
  featurew.writerow(feature);outcomew.writerow(outcome);tracew.writerow({'root':rt,**trace});role=feature['role'];members[role]+=1;exp[role][feature['paa_category']]+=1
  ends[role]['roots']+=1;ends[role]['events_applicable_window']+=outcome['event'];ends[role]['censored_applicable_window']+=1-outcome['event'];potentials[role].append((date(outcome['observation_end'])-date(feature['landmark'])).days)
 for f in files:f.close()
 expected={'risk_roots':218978,'exposed_roots':52895,'overall_events':119453};reconcile={'reference_reconstructed':dict(an),'reference_expected':expected,'reference_exact_match':dict(an)==expected,'study_decisions':dict(rootflow),'temporal_memberships':dict(members)}
 (BASE/'cohort_reconstruction/flow_reconciliation.json').write_text(json.dumps(reconcile,indent=2))
 for name,rows in [('exposure_only_support.csv',[{'role':r,'PAA_category':k,'roots':v} for r,d in exp.items() for k,v in sorted(d.items())]),('endpoint_only_support.csv',[{'role':r,**dict(d),'minimum_potential_days':min(potentials[r]),'maximum_potential_days':max(potentials[r])} for r,d in ends.items()])]:
  w=writer(name,list(rows[0]));w.writerows(rows)
 for f in files:
  if not f.closed:f.close()
 con.close();print(json.dumps(reconcile,indent=2),flush=True)
if __name__=='__main__':main()
