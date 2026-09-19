args<-commandArgs(trailingOnly=TRUE);suppressPackageStartupMessages(library(survival));options(digits=17)
d<-read.csv(args[1]);tau<-as.numeric(args[3]);reps<-as.integer(args[4]);f<-file(args[2],"rb");on.exit(close(f))
out<-matrix(NA_real_,nrow=reps+1,ncol=3);colnames(out)<-c("M0","M1","difference");response<-Surv(d$time,d$event)
for(b in 0:reps) {
 w<-if(b==0) rep(1L,nrow(d)) else readBin(f,integer(),n=nrow(d),size=4,endian="little")
 stopifnot(length(w)==nrow(d))
 keep<-w>0
 for(m in 0:1) {
  # Unsampled rows are absent from the registered resample. Positive weights retain exact copy multiplicities.
  # Verified against explicit duplicated-row samples; unused internal SE is replaced by the paired bootstrap.
  out[b+1,m+1]<-tryCatch(survival:::concordancefit(response[keep,,drop=FALSE],d[[paste0("risk",m)]][keep],weights=w[keep],reverse=TRUE,timewt="n/G2",ymax=tau,timefix=FALSE,std.err=FALSE)$concordance,error=function(e) NA_real_)
 }
 out[b+1,3]<-out[b+1,2]-out[b+1,1]
}
write.csv(data.frame(replicate=0:reps,out),args[5],row.names=FALSE)
