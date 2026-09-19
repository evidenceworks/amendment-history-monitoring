"""Regenerate accepted Figures 1-4 in an isolated output tree."""
import argparse, pathlib, shutil, subprocess, sys
def main():
 p=argparse.ArgumentParser(); p.add_argument('--output',required=True,type=pathlib.Path); a=p.parse_args(); root=pathlib.Path(__file__).resolve().parents[1]; out=a.output.resolve()
 if out.exists(): raise SystemExit('output directory must not already exist')
 (out/'scripts').mkdir(parents=True); shutil.copy2(root/'scripts/make_figures.py',out/'scripts/make_figures.py'); shutil.copytree(root/'figures/data',out/'data'); (out/'figures').mkdir()
 subprocess.run([sys.executable,str(out/'scripts/make_figures.py')],check=True)
 print('figure reproduction complete')
if __name__=='__main__': main()
