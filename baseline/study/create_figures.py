"""Figures computed only from stored, reproducible study CSV results."""
import csv
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]; res=ROOT/'results'; out=ROOT/'figures';out.mkdir(exist_ok=True)
r=list(csv.DictReader((res/'mode_summary.csv').open()))
a=[x for x in r if x['mode']!='correct']
labels=['Gross energy\ndenominator','Omitted Scope 2','Understated net\noutput']
fig,ax=plt.subplots(figsize=(7.4,3.7))
bars=ax.bar(labels,[float(x['selection_change_pct']) for x in a],width=.62)
for b in bars:
    ax.annotate(f'{b.get_height():.1f}%',(b.get_x()+b.get_width()/2,b.get_height()),xytext=(0,5),textcoords='offset points',ha='center',va='bottom',fontsize=10)
ax.set_ylabel('Changed project-selection sets (%)')
ax.set_ylim(0,109)
ax.spines[['top','right']].set_visible(False)
ax.grid(axis='y',alpha=.22)
fig.tight_layout()
fig.savefig(out/'figure1_selection_change.pdf',bbox_inches='tight')
fig.savefig(out/'figure1_selection_change.png',dpi=200,bbox_inches='tight')
plt.close(fig)

fig,ax=plt.subplots(figsize=(7.4,3.7))
bars=ax.bar(labels,[float(x['mean_valid_npv_regret_musd']) for x in a],width=.62)
for b in bars:
    ax.annotate(f'{b.get_height():.2f}',(b.get_x()+b.get_width()/2,b.get_height()),xytext=(0,5),textcoords='offset points',ha='center',fontsize=10)
ax.set_ylabel('Mean policy-qualified NPV shortfall (USD millions)')
ax.set_ylim(0,16)
ax.spines[['top','right']].set_visible(False)
ax.grid(axis='y',alpha=.22)
fig.tight_layout()
fig.savefig(out/'figure2_value_shortfall.pdf',bbox_inches='tight')
fig.savefig(out/'figure2_value_shortfall.png',dpi=200,bbox_inches='tight')
plt.close(fig)
