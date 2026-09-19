"""Raw-only analysis package ingestion, including byte-equivalent record hashes and unmodified identifiers."""
import pathlib,csv,sqlite3,re,json,datetime,functools,collections,hashlib,os
BASE=pathlib.Path(os.environ.get('REPRO_OUTPUT',str(pathlib.Path(__file__).resolve().parents[1])))
WORK=pathlib.Path(os.environ.get('REPRO_WORK',str(BASE.parent/'REPRO_WORK')))
SRC_ENV=os.environ.get('REPRO_SOURCE')
if not SRC_ENV: raise RuntimeError('REPRO_SOURCE must point to the exact archived source CSV')
SRC=pathlib.Path(SRC_ENV)
def main():
 WORK.mkdir(exist_ok=True,parents=True);db=WORK/'source.sqlite';assert not db.exists(),'Refusing to overwrite ingestion'
 con=sqlite3.connect(db);con.execute('PRAGMA journal_mode=OFF');con.execute('PRAGMA synchronous=OFF')
 cols=['rn','fid','rawfid','root','kind','seq','valid','bin','borough','jt','status','f','a','p','s','u','leg','review','building','recordsha']
 con.execute('CREATE TABLE filings('+','.join(k+(' INTEGER' if k in ['rn','seq','valid'] else ' TEXT') for k in cols)+')')
 class Capture:
  def __init__(self,f):self.f=f;self.lines=[]
  def __iter__(self):return self
  def __next__(self):s=next(self.f);self.lines.append(s);return s
 @functools.lru_cache(maxsize=300000)
 def dt(x):
  if not x.strip():return ''
  try:return datetime.datetime.fromisoformat(x.replace('Z','+00:00')).date().isoformat()
  except ValueError:pass
  for fmt in ['%m/%d/%Y %I:%M:%S %p','%m/%d/%y %I:%M:%S %p','%m/%d/%Y']:
   try:return datetime.datetime.strptime(' '.join(x.split()),fmt).date().isoformat()
   except ValueError:pass
  return 'INVALID'
 norm=lambda s:' '.join(s.upper().split());patterns=collections.Counter();bad=[];dateforms=collections.defaultdict(collections.Counter);batch=[];labels=collections.defaultdict(collections.Counter)
 with SRC.open(encoding='utf-8-sig',newline='') as f:
  cap=Capture(f);rd=csv.DictReader(cap);schema=rd.fieldnames;cap.lines=[]
  for n,r in enumerate(rd,1):
   rawrecord=''.join(cap.lines).encode('utf8');cap.lines=[];assert None not in r and all(v is not None for v in r.values())
   fid=norm(r['job_filing_number']);m=re.fullmatch(r'([A-Z0-9]+)-([ISP])([0-9]+)',fid);m=m if m and int(m[3])>0 else None
   lexical=re.match(r'^([A-Z0-9]+)-',fid);root=m[1] if m else lexical[1] if lexical else ''
   dates=[]
   for k in ['filing_date','approved_date','first_permit_date','signoff_date','current_status_date']:
    v=r[k];d=dt(v);dates.append(d);dateforms[k]['blank' if not v.strip() else 'US_slash_calendar' if '/' in v else 'ISO_calendar']+=1
    if d=='INVALID':bad.append({'raw_row':n,'field':k,'raw_value':v})
   patterns[re.sub('[0-9]+','#',fid)]+=1
   for k in ['job_type','request_legalization','filing_status']:labels[k][r[k]]+=1
   batch.append([n,fid,r['job_filing_number'],root,m[2] if m else '',int(m[3]) if m else None,int(m is not None),r['bin'].strip(),r['borough'].strip(),r['job_type'],r['filing_status'],*dates,r['request_legalization'],r['filing_review_type'],r['building_type'],hashlib.sha256(rawrecord).hexdigest()])
   if len(batch)>=10000:con.executemany('INSERT INTO filings VALUES ('+','.join('?' for _ in cols)+')',batch);batch=[]
  if batch:con.executemany('INSERT INTO filings VALUES ('+','.join('?' for _ in cols)+')',batch)
 assert n==956139
 con.execute('CREATE INDEX root_idx ON filings(root,rn)');con.execute('CREATE INDEX rn_idx ON filings(rn)');con.commit();con.close()
 out={'rows':n,'columns':schema,'parser':'^([A-Z0-9]+)-([ISP])([0-9]+)$, numeric suffix >0','identifier_normalization':'Whitespace trim/collapse and uppercase only; raw identifiers retained','date_map':dict(dateforms),'date_semantics':'Calendar date as recorded, interpreted NYC local calendar; source contains date/no-zone local timestamps; no invented within-day ordering','date_failures':bad,'suffix_patterns':dict(patterns),'labels':dict(labels),'byte_equivalent_duplicate_basis':'SHA256 of source record UTF-8 bytes including quoting/newlines; all original row positions retained'}
 (BASE/'cohort_reconstruction/source_schema_audit.json').write_text(json.dumps(out,indent=2));print('analysis package source ingestion complete: '+str(n),flush=True)
if __name__=='__main__':main()
