#!/usr/bin/env python3
from pathlib import Path
from io import BytesIO
import re
import hashlib
import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
from PIL import Image
import fitz

ROOT = Path(__file__).resolve().parents[1]
SD = ROOT / 'data'
OUT = ROOT / 'figures'
OUT.mkdir(exist_ok=True)

# Publication-scale defaults: full-width figures, readable at final placement.
mpl.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Liberation Sans', 'Arial', 'DejaVu Sans'],
    'font.size': 9.2,
    'axes.titlesize': 10.0,
    'axes.labelsize': 9.2,
    'xtick.labelsize': 8.6,
    'ytick.labelsize': 8.6,
    'legend.fontsize': 8.6,
    'pdf.fonttype': 42,
    'ps.fonttype': 42,
    'svg.fonttype': 'none',
    'svg.hashsalt': 'publication-main-figures',
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.7,
    'ytick.major.width': 0.7,
})

# Okabe-Ito-inspired restrained palette; shapes also carry meaning for grayscale.
BLUE = '#0072B2'
ORANGE = '#D55E00'
DARK = '#333333'
MID = '#777777'
LIGHT = '#D9D9D9'
GRID = '#E6E6E6'
PALE_BLUE = '#EAF3F8'


def strip_pdf_metadata(path: Path):
    doc = fitz.open(path)
    doc.set_metadata({})
    tmp = path.with_suffix('.clean.pdf')
    doc.save(tmp, garbage=4, deflate=True)
    doc.close()
    tmp.replace(path)

    # PyMuPDF assigns a fresh trailer ID on each save. Canonicalize that
    # non-content identifier so reruns are byte-reproducible.
    raw = path.read_bytes()
    pattern = rb'/ID\s*\[[^\]]+\]'
    masked = re.sub(pattern, b'/ID[<00000000000000000000000000000000><00000000000000000000000000000000>]', raw, count=1)
    if masked == raw:
        # If no trailer ID is present, keep the scrubbed PDF as-is.
        path.write_bytes(raw)
        return
    digest = hashlib.sha256(masked).hexdigest().upper()
    replacement = f'/ID[<{digest[:32]}><{digest[32:64]}>]'.encode('ascii')
    raw2 = re.sub(pattern, replacement, raw, count=1)
    path.write_bytes(raw2)


def strip_svg_metadata(path: Path):
    text = path.read_text(encoding='utf-8')
    text = re.sub(r'\s*<metadata>.*?</metadata>\s*', '\n', text, flags=re.S)
    path.write_text(text, encoding='utf-8')


def scrub_raster_metadata(path: Path, dpi: int, destination: Path | None = None):
    with Image.open(path) as im:
        data = im.copy()
    target = destination or path
    if path.suffix.lower() == '.png':
        data.save(target, format='PNG', dpi=(dpi, dpi), optimize=True)
    elif path.suffix.lower() in {'.tif', '.tiff'}:
        data.save(target, format='TIFF', dpi=(dpi, dpi), compression='tiff_lzw')


def save_all(fig, stem: str):
    pdf = OUT / f'{stem}.pdf'
    svg = OUT / f'{stem}.svg'
    png = OUT / f'{stem}.png'
    tif = OUT / f'{stem}.tif'
    tif_buffer = BytesIO()
    # Tight bounding is used consistently across formats.
    fig.savefig(pdf, bbox_inches='tight', pad_inches=0.06)
    fig.savefig(svg, bbox_inches='tight', pad_inches=0.06)
    fig.savefig(png, dpi=300, bbox_inches='tight', pad_inches=0.06)
    fig.savefig(tif_buffer, format='tiff', dpi=600, bbox_inches='tight', pad_inches=0.06)
    plt.close(fig)
    strip_pdf_metadata(pdf)
    strip_svg_metadata(svg)
    scrub_raster_metadata(png, 300)
    tif_buffer.seek(0)
    with Image.open(tif_buffer) as image:
        tif_data = image.copy()
    tif_data.save(tif, format='TIFF', dpi=(600, 600), compression='tiff_lzw')


def panel_label(ax, letter, y=1.03):
    ax.text(0.0, y, letter, transform=ax.transAxes, ha='left', va='bottom',
            fontsize=10.2, fontweight='bold')


def figure1():
    src = pd.read_csv(SD/'figure1.csv')
    # Fail loudly if core fixed semantics are missing from the included source data.
    assert (src.element_id == 'L').any() and src.loc[src.element_id=='L','semantic_value'].iloc[0] == 'F + 365'
    assert src.loc[src.element_id=='development','semantic_value'].iloc[0] == '2017-2022'

    fig = plt.figure(figsize=(7.2, 5.9))
    gs = fig.add_gridspec(2, 1, height_ratios=[1.15, 0.95], hspace=0.35)

    # Panel A: root grouping + landmark timeline.
    ax = fig.add_subplot(gs[0])
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis('off')
    panel_label(ax, 'A. Root and landmark construction', y=0.98)

    root = FancyBboxPatch((3, 61), 39, 30, boxstyle='round,pad=0.7,rounding_size=1.8',
                          linewidth=1.0, edgecolor=DARK, facecolor='white')
    ax.add_patch(root)
    ax.text(5, 87.3, 'Alteration application root', fontsize=9.4, fontweight='bold', ha='left', va='center')
    box_specs=[(6,'I1\ninitial filing'),(18.5,'S\nfiling(s)'),(31,'PAA\nrecord(s)')]
    for x,lab in box_specs:
                # Microrepair: widen only the I1 box slightly so the text has clearer side padding.
        if lab.startswith('I1'):
            bx, bw = 5.5, 10.0
            tx = bx + bw/2
        else:
            bx, bw = x, 9
            tx = x + 4.5
        b=FancyBboxPatch((bx,64),bw,15,boxstyle='round,pad=0.4,rounding_size=1.0',
                         linewidth=0.9, edgecolor=MID, facecolor='#F7F7F7')
        ax.add_patch(b); ax.text(tx,71.5,lab,ha='center',va='center',fontsize=8.7)
    ax.text(22.5, 57.0, 'Grouped identifiers; no parent edge is inferred', ha='center', va='center', fontsize=8.1, color=MID)

    # Timeline: no parent-child arrows among filing types.
    y=31
    ax.plot([6,95],[y,y],color=DARK,lw=1.0)
    marks=[(8,'I1 filing',MID),(31,'F\nearliest non-PAA\nI/S permit',BLUE),(68,'L\nday-365 checkpoint',BLUE),(91,'Later recorded\nI1 signoff',DARK)]
    for x,lab,c in marks:
        ax.plot([x,x],[y-4.0,y+4.0],color=c,lw=1.4)
        ax.text(x,y-7.2,lab,ha='center',va='top',fontsize=8.2)
    # Approved PAA examples can occur before or after F, but only through L.
    for x in [24,49,60]:
        ax.scatter([x],[y],s=30,marker='D',facecolor=ORANGE,edgecolor='white',linewidth=0.5,zorder=4)
    ax.plot([20,67.5],[38.0,38.0],color=ORANGE,lw=1.0,alpha=0.8)
    ax.text(49, 39.5, 'Qualifying approved PAA history through L', ha='center', va='bottom', fontsize=8.2, color=DARK)
    ax.text(24, 33.0, 'pre-F approval', ha='center', va='bottom', fontsize=7.8, color=ORANGE)
    # 365-day arrow safely separated from root box and timeline labels.
    ax.annotate('', xy=(67.5,46.5), xytext=(31.5,46.5), arrowprops=dict(arrowstyle='<->', lw=1.0, color=DARK))
    ax.text(49.5,49.8,'365 calendar days',ha='center',va='bottom',fontsize=8.7)
    ax.text(96, 5.0, 'Schematic', ha='right', va='bottom', fontsize=7.8, color=MID, style='italic')

    # Panel B: temporal roles.
    ax2 = fig.add_subplot(gs[1])
    panel_label(ax2, 'B. Temporal evaluation', y=1.03)
    ax2.set_xlim(2016.7, 2026.75); ax2.set_ylim(-0.1, 3.25)
    ax2.spines[['top','right','left']].set_visible(False)
    ax2.set_yticks([])
    ax2.set_xticks(range(2017,2027))
    ax2.tick_params(axis='x', length=3)
    ax2.grid(False)

    # Cohort bars show first-permit year roles; horizon text is explicit.
    ax2.add_patch(Rectangle((2017,2.35),6.0,0.34,facecolor=BLUE,edgecolor='none',alpha=0.9))
    ax2.text(2020,2.52,'Development first permits: 2017-2022',ha='center',va='center',fontsize=8.2,color='white',fontweight='bold')
    ax2.add_patch(Rectangle((2023,1.45),1.0,0.34,facecolor=BLUE,edgecolor='none',alpha=0.72))
    ax2.text(2023.88,1.84,'2023 validation (primary)',ha='right',va='bottom',fontsize=8.3)
    ax2.text(2023.5,1.36,'365-day assessment',ha='center',va='top',fontsize=7.9,color=MID)
    ax2.add_patch(Rectangle((2024,0.55),1.0,0.34,facecolor=BLUE,edgecolor='none',alpha=0.52))
    ax2.text(2024.5,0.96,'Full 2024 validation',ha='center',va='bottom',fontsize=8.3)
    ax2.text(2024.5,0.48,'180-day assessment',ha='center',va='top',fontsize=7.9,color=MID)
    ax2.text(2024.5,0.18,'Mature-2024 subset: F <= 12 Sep 2024; 365-day assessment',ha='center',va='center',fontsize=7.9,color=MID)
    # Two reference dates.
    ax2.axvline(2024.0, color=MID, ls=(0,(3,2)), lw=0.9, ymin=0.55, ymax=0.93)
    ax2.text(2023.94,3.13,'Development outcome-information cutoff\n31 Dec 2023',ha='right',va='top',fontsize=7.6,color=MID)
    # Place Sep-2026 line proportionally in 2026.
    cutoff=2026 + (255/365)
    ax2.axvline(cutoff, color=MID, ls=(0,(3,2)), lw=0.9, ymin=0.07, ymax=0.93)
    ax2.text(cutoff-0.03,3.13,'Archived source state\n12 Sep 2026',ha='right',va='top',fontsize=7.6,color=MID)
    ax2.set_xlabel('Calendar year of first permit and later information windows', labelpad=7)

    save_all(fig,'figure1')


def figure2():
    score = pd.read_csv(SD/'figure2_scores.csv')
    work = pd.read_csv(SD/'figure2_workload.csv')
    order=['Primary','S1','S2','S3','S4','S5','S6']
    label_map={
        'Primary':'Primary specification',
        'S1':'S1 endpoint recoding',
        'S2':'S2 no observed S filing',
        'S3':'S3 omit 2020-2021 development',
        'S4':'S4 day-180 interaction',
        'S5':'S5 any approved PAA only',
        'S6':'S6 development 2021-2022 only',
    }

    fig = plt.figure(figsize=(7.2, 8.4))
    outer=fig.add_gridspec(2,1,height_ratios=[1.65,0.78],hspace=0.34)
    top=outer[0].subgridspec(1,2,wspace=0.22)
    axes=[]
    for j,(ass,title) in enumerate([
        ('2023_primary','2023 validation (primary)\nIBS over 0-365 days'),
        ('full_2024_corroboration','Full 2024 validation (corroboration)\nBrier score at day 180'),
    ]):
        ax=fig.add_subplot(top[0,j]); axes.append(ax)
        d=score[score.assessment_id==ass].set_index('specification_id').loc[order].reset_index()
        y=np.arange(len(order))[::-1]
        colors=[BLUE if s=='Primary' else '#5C9EAD' for s in order]
        for yi,(_,r),c in zip(y,d.iterrows(),colors):
            ax.errorbar(r.estimate, yi, xerr=[[r.estimate-r.ci_low],[r.ci_high-r.estimate]], fmt='o',
                        ms=5.5 if r.specification_id=='Primary' else 4.7,
                        color=c, ecolor=c, elinewidth=1.3, capsize=2.6,
                        markeredgecolor='white' if r.specification_id=='Primary' else c,
                        markeredgewidth=0.5, zorder=3)
        ax.axvline(0,color=DARK,lw=0.9)
        ax.set_title(title,pad=8,fontweight='bold' if j==0 else 'normal')
        ax.set_yticks(y)
        if j==0:
            ax.set_yticklabels([label_map[s] for s in order])
        else:
            ax.set_yticklabels([])
        ax.set_ylim(-0.7,len(order)-0.3)
        # Separate metric scales; never imply direct comparability.
        lo=float(d.ci_low.min()); hi=0.0
        pad=(hi-lo)*0.08
        ax.set_xlim(lo-pad, hi+pad*0.45)
        ax.grid(axis='x',color=GRID,lw=0.7)
        ax.set_xlabel('M1 - M0 score difference')
        ax.spines[['top','right']].set_visible(False)
        ax.ticklabel_format(axis='x',style='plain',useOffset=False)
        # Highlight primary row without hiding sensitivities.
        ax.axhspan(y[0]-0.42,y[0]+0.42,color=PALE_BLUE,zorder=0)
    panel_label(axes[0],'A. Score improvement and S1-S6 robustness',y=1.16)
    fig.text(0.52,0.940,'Negative differences favor amendment history; panels use different prespecified metrics.',
             ha='center',va='top',fontsize=8.1,color=MID)

    # Workload panel.
    ax=fig.add_subplot(outer[1])
    panel_label(ax,'B. Equal-workload enrichment',y=1.08)
    rows=[('2023_primary','2023 validation\n(primary)'),('full_2024_corroboration','Full 2024 validation\n(corroboration)')]
    y=[1,0]
    for yi,(ass,lab) in zip(y,rows):
        r=work[work.assessment_id==ass].iloc[0]
        x0=float(r.m0_persisters_per_100); x1=float(r.m1_persisters_per_100)
        ax.plot([x0,x1],[yi,yi],color=LIGHT,lw=3.2,zorder=1)
        ax.scatter([x0],[yi],s=50,marker='o',facecolor=MID,edgecolor='white',linewidth=0.6,zorder=3)
        ax.scatter([x1],[yi],s=58,marker='D',facecolor=BLUE,edgecolor='white',linewidth=0.6,zorder=3)
        ax.text(x0,yi+0.17,f'{x0:.2f}',ha='center',va='bottom',fontsize=8.2,color=MID)
        ax.text(x1,yi+0.17,f'{x1:.2f}',ha='center',va='bottom',fontsize=8.2,color=BLUE,fontweight='bold')
        ax.text(91.4,yi,f'+{r.yield_difference:.2f} [{r.yield_ci_low:.2f}, {r.yield_ci_high:.2f}]',
                ha='right',va='center',fontsize=8.4,color=DARK)
    ax.set_xlim(60,92)
    ax.set_ylim(-0.55,1.55)
    ax.set_yticks(y); ax.set_yticklabels([r[1] for r in rows])
    ax.set_xlabel('Persistent roots per 100 reviews')
    ax.grid(axis='x',color=GRID,lw=0.7)
    ax.spines[['top','right']].set_visible(False)
    # Compact direct legend.
    ax.scatter([],[],s=42,marker='o',color=MID,label='Public-record benchmark (M0)')
    ax.scatter([],[],s=48,marker='D',color=BLUE,label='Benchmark + amendment history (M1)')
    ax.legend(loc='lower center',bbox_to_anchor=(0.5,-0.42),ncol=2,frameon=False)
    ax.text(0.985,1.05,'Paired yield difference [95% interval]',transform=ax.transAxes,ha='right',va='bottom',fontsize=7.8,color=MID)

    save_all(fig,'figure2')


def figure3():
    data=pd.read_csv(SD/'figure3.csv')
    fig,axs=plt.subplots(1,2,figsize=(7.2,3.85),sharex=True,sharey=True)
    settings=[('2023/365','2023 validation\n365-day horizon'),('Full 2024/180','Full 2024 validation\n180-day horizon')]
    for ax,(ass,title) in zip(axs,settings):
        d=data[data.assessment==ass]
        ax.plot([0,1],[0,1],ls=(0,(4,3)),lw=1.0,color=DARK,label='Identity')
        d0=d[d.model=='M0']; d1=d[d.model=='M1']
        ax.scatter(d0.predicted_persistence,d0.observed_persistence,s=31,marker='o',facecolors='white',edgecolors=DARK,linewidths=1.2,label='M0',zorder=3)
        ax.scatter(d1.predicted_persistence,d1.observed_persistence,s=37,marker='x',c=ORANGE,linewidths=1.5,label='M1',zorder=4)
        ax.set_xlim(0,1); ax.set_ylim(0,1)
        ax.set_xticks(np.arange(0,1.01,0.2)); ax.set_yticks(np.arange(0,1.01,0.2))
        ax.grid(color=GRID,lw=0.65)
        ax.set_title(title,pad=6)
        ax.set_xlabel('Mean predicted persistence')
        ax.set_ylabel('Observed persistence')
        ax.set_aspect('equal',adjustable='box')
        ax.spines[['top','right']].set_visible(False)
    panel_label(axs[0],'A',y=1.02); panel_label(axs[1],'B',y=1.02)
    handles=[axs[0].collections[0],axs[0].collections[1],axs[0].lines[0]]
    labels=['M0','M1','Identity']
    fig.legend(handles,labels,loc='lower center',bbox_to_anchor=(0.5,-0.01),ncol=3,frameon=False)
    fig.subplots_adjust(bottom=0.19,wspace=0.25)
    save_all(fig,'figure3')


def figure4():
    # Match the surrounding sans-serif family while using scholarly math notation.
    mpl.rcParams['mathtext.fontset'] = 'custom'
    mpl.rcParams['mathtext.rm'] = 'Liberation Sans'
    mpl.rcParams['mathtext.it'] = 'Liberation Sans:italic'
    data=pd.read_csv(SD/'figure4.csv')
    fig=plt.figure(figsize=(7.2,6.35))
    outer=fig.add_gridspec(2,1,height_ratios=[0.52,1.48],hspace=0.23)

    # Representation ladder.
    ax0=fig.add_subplot(outer[0]); ax0.axis('off'); ax0.set_xlim(0,1); ax0.set_ylim(0,1)
    panel_label(ax0,'A. Representation ladder',y=0.98)
    nodes=[
        (0.03,'Baseline context',r'$M_{\mathrm{base}}$'),
        (0.28,'Any approved\namendment',r'$M_{\mathrm{any}}$'),
        (0.53,'Amendment count',r'$M_{\mathrm{count}}$'),
        (0.78,'Count + timing\nhistory',r'$M_{\mathrm{history}}$'),
    ]
    w=0.19; h=0.48; y=0.25
    for i,(x,lab,mid) in enumerate(nodes):
        edge=BLUE if i==3 else DARK
        face=PALE_BLUE if i==3 else 'white'
        p=FancyBboxPatch((x,y),w,h,boxstyle='round,pad=0.015,rounding_size=0.02',
                         facecolor=face,edgecolor=edge,lw=1.2 if i==3 else 0.9)
        ax0.add_patch(p)
        ax0.text(x+w/2,y+0.29,lab,ha='center',va='center',fontsize=8.7,fontweight='bold' if i==3 else 'normal')
        ax0.text(x+w/2,y+0.10,mid,ha='center',va='center',fontsize=8.0,color=MID)
        if i<3:
            nx=nodes[i+1][0]
            ax0.annotate('',xy=(nx-0.01,y+h/2),xytext=(x+w+0.01,y+h/2),arrowprops=dict(arrowstyle='->',lw=1.0,color=MID))
    # Short arrow-step labels.
    ax0.text(0.255,0.124,'presence',ha='center',va='center',fontsize=7.6,color=MID)
    ax0.text(0.505,0.124,'volume',ha='center',va='center',fontsize=7.6,color=MID)
    ax0.text(0.755,0.124,'timing',ha='center',va='center',fontsize=7.6,color=BLUE,fontweight='bold')

    bottom=outer[1].subgridspec(1,2,wspace=0.26)
    specs=[
        ('2023_primary','2023 validation (primary)\nIBS over 0-365 days',(-0.00265,0.00020)),
        ('full_2024_corroboration','Full 2024 validation (corroboration)\nBrier score at day 180',(-0.00505,0.00020)),
    ]
    contrast_order=['M_any - M_base','M_count - M_any','M_history - M_count']
    y=np.array([2,1,0])
    row_labels=['Any amendment\nvs baseline','Amendment count\nvs any amendment','Count + timing\nvs count']
    axes=[]
    for j,(ass,title,xlim) in enumerate(specs):
        ax=fig.add_subplot(bottom[0,j]); axes.append(ax)
        d=data[data.assessment_id==ass].set_index('contrast').loc[contrast_order].reset_index()
        ax.axhspan(-0.42,0.42,color=PALE_BLUE,zorder=0)
        ax.axvline(0,color=DARK,lw=0.9)
        markers=['o','s','D']; cols=[MID,MID,BLUE]
        for yi,(_,r),m,c in zip(y,d.iterrows(),markers,cols):
            ax.errorbar(r.estimate,yi,xerr=[[r.estimate-r.percentile_2_5],[r.percentile_97_5-r.estimate]],fmt=m,
                        ms=5.3 if yi==0 else 4.8,color=c,ecolor=c,elinewidth=1.25,capsize=2.5,
                        markerfacecolor=c,markeredgecolor='white' if yi==0 else c,markeredgewidth=0.55,zorder=3)
        timing=d[d.contrast=='M_history - M_count'].iloc[0]
        ax.text(0.98,0.06,f'Timing increment: {timing.estimate:.6f}\n[{timing.percentile_2_5:.6f}, {timing.percentile_97_5:.6f}]',
                transform=ax.transAxes,ha='right',va='bottom',fontsize=7.6,color=BLUE,fontweight='bold',
                bbox=dict(boxstyle='round,pad=0.28',facecolor='white',edgecolor=BLUE,linewidth=0.6,alpha=0.96))
        ax.set_xlim(*xlim); ax.set_ylim(-0.55,2.55)
        ax.set_yticks(y)
        if j==0:
            ax.set_yticklabels(row_labels)
        else:
            ax.set_yticklabels([])
        ax.set_title(title,pad=8)
        ax.set_xlabel('Loss difference from prior rung')
        ax.grid(axis='x',color=GRID,lw=0.7)
        ax.spines[['top','right']].set_visible(False)
        ax.ticklabel_format(axis='x',style='plain',useOffset=False)
    panel_label(axes[0],'B. Adjacent paired contrasts',y=1.14)
    fig.subplots_adjust(bottom=0.12)

    save_all(fig,'figure4')


if __name__=='__main__':
    figure1(); figure2(); figure3(); figure4()
    print('Generated figure1 through figure4 in PDF, SVG, PNG and TIFF.')
