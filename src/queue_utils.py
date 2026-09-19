"""Registered paired BIN resampling and fixed daily workload, also used by prepared cohort fixtures."""
import numpy as np,hashlib
_TIE_PREFIX=bytes.fromhex('414c31412d7469657c')
def tie(root):return hashlib.sha256(_TIE_PREFIX+str(root).encode()).hexdigest()
def cluster_draw(bins,rng):
 labels,inverse=np.unique(np.asarray(bins,dtype=str),return_inverse=True);sample=rng.integers(0,len(labels),len(labels));counts=np.bincount(sample,minlength=len(labels));return counts[inverse]
def queue_order(roots,days,scores):
 return np.lexsort((np.array([tie(r) for r in roots]),-np.asarray(scores),np.asarray(days,dtype=str)))
def queue_selected(roots,days,scores,weights=None,order=None):
 n=len(roots);weights=np.ones(n,dtype=int) if weights is None else np.asarray(weights,dtype=int);order=queue_order(roots,days,scores) if order is None else order;days=np.asarray(days);selected=np.zeros(n,dtype=int)
 for indices in np.split(order,np.flatnonzero(days[order][1:]!=days[order][:-1])+1):
  w=weights[indices];slots=int(np.ceil(.2*w.sum()));before=np.cumsum(w)-w;selected[indices]=np.minimum(w,np.maximum(0,slots-before))
 return selected
