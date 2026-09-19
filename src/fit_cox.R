args <- commandArgs(trailingOnly=TRUE)
Sys.setenv(TZ="America/New_York"); Sys.setlocale("LC_COLLATE","C")
suppressPackageStartupMessages(library(survival))
options(digits=17)
design <- read.csv(args[1],check.names=FALSE)
labels <- read.csv(args[2],stringsAsFactors=FALSE)
out <- args[3]; dir.create(out,recursive=TRUE,showWarnings=FALSE)
extended <- length(args)>=4 && args[4]=="extended"
stopifnot(nrow(design)==nrow(labels), all(labels$duration>0), all(is.finite(as.matrix(design))))
d <- design; d$duration <- labels$duration; d$event <- labels$event
predictors <- names(design)
if(extended) {
 count.columns <- strsplit(args[5],",",fixed=TRUE)[[1]]
 d1<-d;d1$start<-0;d1$stop<-pmin(d1$duration,180);d1$event<-as.integer(d$event==1 & d$duration<=180)
 d2<-d[d$duration>180,,drop=FALSE];d2$start<-180;d2$stop<-d2$duration
 d<-rbind(d1,d2)
 for(k in seq_along(count.columns)) d[[paste0("late_count_",k)]]<-d[[count.columns[k]]]*as.integer(d$start>=180)
 predictors<-c(predictors,paste0("late_count_",seq_along(count.columns)))
 form<-as.formula(paste("Surv(start,stop,event) ~",paste(predictors,collapse=" + ")))
} else form<-as.formula(paste("Surv(duration,event) ~",paste(predictors,collapse=" + ")))
warnings<-character()
fit<-withCallingHandlers(coxph(form,data=d,ties="efron",singular.ok=FALSE,x=TRUE,y=TRUE,model=TRUE,control=coxph.control(iter.max=100,eps=1e-9)),warning=function(w){warnings<<-c(warnings,conditionMessage(w));invokeRestart("muffleWarning")})
writeLines(c(capture.output(sessionInfo()),paste("formula",deparse(form)),paste("warnings",warnings),paste("iterations",fit$iter),paste("loglik",paste(fit$loglik,collapse=",")),paste("observations",fit$n),paste("events",fit$nevent)),file.path(out,"fit_diagnostics.txt"))
if(any(!is.finite(coef(fit))) || any(!is.finite(vcov(fit))) || any(grepl("infinite|did not converge|ran out",warnings,ignore.case=TRUE))) {
 writeLines("MODEL_FIT_FAILED",file.path(out,"FIT_FAILED.txt"));stop("Specified fit failed finite/convergence requirements; no alternate model")
}
write.csv(data.frame(column=names(coef(fit)),coefficient=as.numeric(coef(fit)),standard_error=sqrt(diag(vcov(fit)))),file.path(out,"coefficients.csv"),row.names=FALSE)
write.csv(vcov(fit),file.path(out,"variance.csv"),row.names=TRUE)
write.csv(basehaz(fit,centered=FALSE),file.path(out,"baseline_cumulative_hazard.csv"),row.names=FALSE)
saveRDS(fit,file.path(out,"model.rds"),compress="gzip")
writeLines("PASS",file.path(out,"FIT_STATUS.txt"))
