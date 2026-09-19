"""Full local reproduction: source guard, primary analysis, representation audit, and final figures."""
import argparse, pathlib, subprocess, sys
def main():
    p=argparse.ArgumentParser(); p.add_argument('--source',required=True,type=pathlib.Path); p.add_argument('--output',required=True,type=pathlib.Path); p.add_argument('--rscript',default='Rscript'); a=p.parse_args()
    root=pathlib.Path(__file__).resolve().parent; out=a.output.resolve()
    if out.exists(): raise SystemExit('output directory must not already exist')
    subprocess.run([sys.executable,str(root/'verification/verify_science.py')],check=True)
    subprocess.run([sys.executable,str(root/'scripts/check_runtime.py'),'--rscript',a.rscript],check=True)
    subprocess.run([sys.executable,str(root/'scripts/check_source.py'),str(a.source)],check=True)
    subprocess.run([sys.executable,str(root/'scripts/run_full.py'),'--source',str(a.source),'--output',str(out/'primary')],check=True,env={**__import__('os').environ,'REPRO_RSCRIPT':a.rscript})
    subprocess.run([sys.executable,str(root/'scripts/representation.py'),'--primary-output',str(out/'primary'),'--output',str(out/'representation'),'--rscript',a.rscript],check=True)
    subprocess.run([sys.executable,str(root/'scripts/check_figures.py'),'--output',str(out/'figure_reproduction')],check=True)
    subprocess.run([sys.executable,str(root/'verification/compare_results.py'),'--reproduced',str(out),'--reference',str(root/'results/reference'),'--json-out',str(out/'parity_comparison.json')],check=True)
    print('Full reproduction and strict parity comparison complete.')
if __name__=='__main__': main()
