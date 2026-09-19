"""Run the accepted primary analysis and six retained sensitivities from the exact source."""
import argparse, os, pathlib, shutil, subprocess, sys
from check_source import inspect
def main():
    p=argparse.ArgumentParser(); p.add_argument('--source',required=True,type=pathlib.Path); p.add_argument('--output',required=True,type=pathlib.Path); a=p.parse_args()
    source=a.source.resolve(); inspect(source); root=pathlib.Path(__file__).resolve().parents[1]; out=a.output.resolve()
    if out.exists(): raise SystemExit('output directory must not already exist')
    results=out/'analysis_results'; work=out/'working_data'; results.mkdir(parents=True); work.mkdir()
    shutil.copytree(root/'src',results/'src'); shutil.copytree(root/'config',results/'config')
    for d in ['cohort_reconstruction','prepared_cohort','primary_models','validation_2023','validation_2024','sensitivity_analyses','reference_results']:(results/d).mkdir()
    env=dict(os.environ,REPRO_OUTPUT=str(results),REPRO_WORK=str(work),REPRO_SOURCE=str(source),OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',REPRO_PARALLEL_SENSITIVITIES='3')
    for script in ['ingest.py','cohort.py','audit.py','prepare.py','analysis.py']:
        subprocess.run([sys.executable,str(results/'src'/script)],check=True,env=env)
    print('primary reproduction complete')
if __name__=='__main__': main()
