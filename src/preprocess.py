"""Label-free development-only mappings and deterministic design construction."""
import numpy as np,collections
M0_ORDER=['borough','review','building','year_centered','quarter','filing_to_F','approval_to_F','S_filed','S_approved','S_review_diversity']
CATEGORICAL={'borough','review','building','quarter'}
SPLINE={'filing_to_F','approval_to_F'}
MANDATORY={'borough','year_centered','quarter','filing_to_F'}
def transform(k,x):
 x=np.asarray(x,dtype=float)
 if k in ['filing_to_F','S_filed','S_approved','paa_recency']:return np.log1p(x)
 if k=='approval_to_F':return np.sign(x)*np.log1p(np.abs(x))
 return x
def rcs(x,knots):
 x=np.asarray(x,float)
 if len(set(knots))<3:return x[:,None]
 a,b,c=knots;h=(np.maximum(x-a,0)**3-(c-a)/(c-b)*np.maximum(x-b,0)**3+(b-a)/(c-b)*np.maximum(x-c,0)**3)/(c-a)**2
 return np.column_stack([x,h])
def ordered_rank(X,names,preserve=0,tol=1e-10):
 keep=[];removed=[];q=[]
 for j in range(X.shape[1]):
  x=X[:,j];v=x.copy()
  if np.ptp(x)==0:removed.append({'column':names[j],'reason':'constant'});continue
  if q:
   Q=np.column_stack(q)
   for _ in range(2):v-=Q@(Q.T@v)
  n=np.linalg.norm(v)
  if n<=tol*max(1,np.linalg.norm(x)):removed.append({'column':names[j],'reason':'left_to_right_linear_dependence'});continue
  keep.append(j);q.append(v/n)
 assert all(j in keep for j in range(preserve)),'Shared M0 column was not preserved'
 return keep,removed
def fit_maps(df):
 maps={'fit_roots':df.root.tolist(),'M0_order':M0_ORDER,'variables':{},'median_space':'Specified transformed numeric variable; knots use nonmissing transformed values','rank_tolerance':1e-10}
 for k in M0_ORDER:
  missing=df[k].isna().to_numpy();frac=float(missing.mean());v={'missing_fraction':frac,'missing_indicator':frac>=.01,'drop':frac>.4 and k not in MANDATORY,'categorical':k in CATEGORICAL}
  if v['drop']:maps['variables'][k]=v;continue
  if k in MANDATORY:assert not missing.any(),k
  if k in CATEGORICAL:
   a=df[k].dropna().astype(str);freq=a.value_counts().to_dict();mode=sorted(freq,key=lambda z:(-freq[z],z))[0];filled=df[k].fillna(mode).astype(str);counts=filled.value_counts().to_dict();rare=sorted(z for z,n in counts.items() if n/len(df)<.005);pooled=filled.map(lambda z:'Other' if z in rare else z);levels=pooled.value_counts().to_dict();reference=sorted(levels,key=lambda z:(-levels[z],z))[0]
   v.update({'mode':mode,'observed_levels':sorted(counts),'rare_levels':rare,'retained_levels':sorted(levels),'reference':reference})
  else:
   a=transform(k,df[k].to_numpy());obs=a[np.isfinite(a)];assert len(obs),k;v['median']=float(np.median(obs));v['knots']=np.quantile(obs,[.1,.5,.9],method='linear').tolist() if k in SPLINE else None
  maps['variables'][k]=v
 rec=transform('paa_recency',df.loc[df.paa_category.astype(str)!='0','paa_recency'].to_numpy());assert len(rec)>0
 maps['recency_knots']=np.quantile(rec,[.1,.5,.9],method='linear').tolist();maps['PAA_development_categories']=sorted(df.paa_category.astype(str).unique().tolist());maps['M0_keep']=None;maps['M1_keep']=None
 x0,x1,n0,n1,_=apply_maps(df,maps,rank_filter=False);keep0,rm0=ordered_rank(x0,n0);maps['M0_keep']=keep0;maps['M0_removed']=rm0
 x0=x0[:,keep0];n0=[n0[j] for j in keep0];extra=x1[:,len(maps['raw_M0_columns']):];nextra=n1[len(maps['raw_M0_columns']):];x1=np.column_stack([x0,extra]);n1=n0+nextra;keep1,rm1=ordered_rank(x1,n1,preserve=len(n0));maps['M1_keep']=keep1;maps['M1_removed']=rm1;maps['M0_columns']=n0;maps['M1_columns']=[n1[j] for j in keep1];return maps
def apply_maps(df,maps,rank_filter=True):
 columns=[];names=[];unseen={}
 for k in M0_ORDER:
  v=maps['variables'][k]
  if v['drop']:continue
  missing=df[k].isna().to_numpy()
  if v['categorical']:
   a=df[k].fillna(v['mode']).astype(str).to_numpy();unknown=~np.isin(a,v['observed_levels']);unseen[k]=int(unknown.sum());a=np.array(['Other' if z in v['rare_levels'] else z for z in a],dtype=object);a[unknown]='Other' if 'Other' in v['retained_levels'] else v['reference']
   for lev in v['retained_levels']:
    if lev!=v['reference']:columns.append((a==lev).astype(float));names.append(k+'__'+lev)
  else:
   a=transform(k,df[k].to_numpy());a=np.where(np.isfinite(a),a,v['median']);basis=rcs(a,v['knots']) if v['knots'] is not None else a[:,None]
   for j in range(basis.shape[1]):columns.append(basis[:,j]);names.append(k+('__rcs'+str(j+1) if v['knots'] is not None else ''))
  if v['missing_indicator']:columns.append(missing.astype(float));names.append('I1 dated approval unavailable by landmark' if k=='approval_to_F' else k+'__missing')
 x0=np.column_stack(columns);rawnames=names.copy();maps['raw_M0_columns']=rawnames
 if rank_filter:x0=x0[:,maps['M0_keep']];names=[names[j] for j in maps['M0_keep']]
 cat=df.paa_category.astype(str).to_numpy();extra=[(cat==k).astype(float) for k in ['1','2','3']];enames=['PAA_count_1','PAA_count_2','PAA_count_3plus'];exposed=cat!='0';rec=np.zeros(len(df));rec[exposed]=transform('paa_recency',df.loc[exposed,'paa_recency'].to_numpy());basis=rcs(rec,maps['recency_knots']);basis[~exposed,:]=0
 for j in range(basis.shape[1]):extra.append(basis[:,j]);enames.append('PAA_recency_rcs'+str(j+1))
 extra.append(df.paa_90.to_numpy(float));enames.append('PAA_final_90_days');x1=np.column_stack([x0,*extra]);n1=names+enames
 if rank_filter:x1=x1[:,maps['M1_keep']];n1=[n1[j] for j in maps['M1_keep']]
 return np.ascontiguousarray(x0),np.ascontiguousarray(x1),names,n1,unseen
