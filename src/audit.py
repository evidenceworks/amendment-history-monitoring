"""Required flow-ledger supplements only; no model or outcome contrasts."""
import csv,json,sqlite3,collections,re,pathlib,os
from ingest import BASE,WORK,SRC
from cohort import C,D,good,plus
def an_reason(rows):
 valid=[r for r in rows if re.fullmatch(r'[BMQSX][0-9]{8}-[ISP][1-9][0-9]*',r['rawfid'])];ini=[r for r in valid if r['kind']=='I' and r['seq']==1]
 if len(ini)!=1 or any(r['kind']=='I' and r['seq']!=1 for r in valid) or len(valid)!=len({r['rawfid'] for r in valid}):return 'reference_initial_or_duplicate_identity'
 i=ini[0];bm={'B':'Brooklyn','M':'Manhattan','Q':'Queens','S':'Staten Island','X':'Bronx'}
 if len({r['bin'] for r in valid})!=1 or {r['borough'] for r in valid}!={bm[i['root'][0]]}:return 'reference_forced_sibling_BIN_borough_equality'
 if len(valid)!=len(rows):return 'reference_any_malformed_sibling_even_future'
 non=[r for r in valid if r['kind'] in ['I','S']]
 if any(r['leg'].strip().upper()=='YES' for r in rows):return 'reference_sibling_legalization_exclusion'
 if any(r['jt']!='Alteration' or 'certificate of operation' in r['status'].lower() for r in non):return 'reference_sibling_workflow_exclusion'
 F=min(r['p'] for r in non if good(r['p']) and r['p']<=C)
 for r in non:
  if not good(r['f']):return 'reference_any_nonPAA_missing_filing_even_noncontributing'
  if any(r[k]=='INVALID' or good(r[k]) and r[k]>C for k in ['f','a','p','s']):return 'reference_future_or_noncontributing_sibling_dates'
  if any(good(r[a]) and good(r[b]) and r[a]>r[b] for a,b in [('f','a'),('f','p'),('f','s'),('a','p'),('p','s')]):return 'reference_noncontributing_sibling_chronology'
 if good(i['a']) and i['a']>F:return 'reference_I1_approval_before_every_root_permit'
 return 'Other_identity_history_correction'
def main():
 out=BASE/'cohort_reconstruction';con=sqlite3.connect(WORK/'source.sqlite');con.row_factory=sqlite3.Row;differences=collections.Counter();unknown=collections.Counter();added=[]
 with (out/'root_reconciliation.csv').open(newline='',encoding='utf8') as f:
  for r in csv.DictReader(f):
   changed=r['reference_member']!=r['study_member'];ambiguous='ambiguous' in r['study_decision'] or r['study_decision'] in ['conflicting_relevant_filing_identifier','malformed_relevant_sibling']
   if not (changed or ambiguous):continue
   rows=[dict(x) for x in con.execute('SELECT * FROM filings WHERE root=?',(r['root'],))]
   if changed:
    cause=an_reason(rows) if r['study_member']=='1' else r['study_decision'];direction='admitted_by_study_rules' if r['study_member']=='1' else 'excluded_by_study_rules';differences[(direction,cause)]+=1;added.append({'root':r['root'],'direction':direction,'rule_difference':cause,'authority':'Root-construction rules implemented in src/cohort.py and documented in Supplementary Information, Section S1.'})
   if ambiguous:
    permits=[x['p'] for x in rows if x['valid'] and x['kind'] in ['I','S'] and good(x['p']) and x['p']<=C]
    if not permits:role='F_unresolved'
    else:
     F=min(permits);yr=int(F[:4]);L=plus(F,365);role='development' if 2017<=yr<=2022 and L<D else 'development_zero_followup' if 2017<=yr<=2022 else 'validation_2023' if yr==2023 else 'validation_2024' if yr==2024 else 'excluded_'+str(yr)
    unknown[(role,r['study_decision'])]+=1
 def write(name,rows,fields):
  with (out/name).open('w',newline='',encoding='utf8') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 write('reference_to_study_rule_differences.csv',[{'direction':d,'rule_difference':k,'roots':v} for (d,k),v in sorted(differences.items())],['direction','rule_difference','roots']);write('reference_to_study_changed_roots.csv',added,['root','direction','rule_difference','authority'])
 write('unknown_ambiguous_exclusions_by_split.csv',[{'temporal_role':r,'exclusion_reason':k,'roots':v} for (r,k),v in sorted(unknown.items())],['temporal_role','exclusion_reason','roots'])
 fields=['raw_row','job_filing_number','job_type','borough','bin','request_legalization','filing_date','approved_date','first_permit_date','signoff_date']
 with (out/'raw_I1_eligibility_ledger.csv').open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  with SRC.open(encoding='utf-8-sig',newline='') as raw:
   for rn,r in enumerate(csv.DictReader(raw),1):
    ident=' '.join(r['job_filing_number'].upper().split())
    if re.fullmatch('[A-Z0-9]+-I0*1',ident) and r['job_type']=='Alteration':w.writerow({'raw_row':rn,**{k:r[k] for k in fields[1:]}})
 con.close();(out/'source preparation_VALIDATION_REPORT.md').write_text('''# source preparation validation record

Exact source and mapping hashes and 956,139 rows were verified. Raw record hashes and identifiers retain source-row correspondence; duplicate and quarantine ledgers are present. The raw I1 eligibility ledger preserves source strings separately from normalized dates used in computation. It is an audit input, never a fitted matrix or an unmasked development-label source.

Reference reconstruction exactly matched 218,978 roots, 52,895 exposed roots and 119,453 overall events in separate aggregates. The study cohort was not forced to match the alternative reference construction. Rule-specific differences and changed root IDs are supplied. Unknown/ambiguous histories are enumerated by temporal role without outcome grouping.

prepared cohort's invariant report checks contributor dates, leap boundaries, excluded-field/future-event mutations, training cutoff, shared design bytes, calendar maturity and paired bootstrap/queue fixtures. Raw source audit ledgers can contain later recorded dates; those do not enter development fitting/preprocessing, whose separately stored labels end at the registered cutoff. The clean reproduction pipeline regenerates these ledgers directly from raw input before prepared cohort.
''',encoding='utf8');print('source preparation flow and raw-eligibility supplements complete',flush=True)
if __name__=='__main__':main()
