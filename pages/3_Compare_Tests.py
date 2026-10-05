import streamlit as st
import plotly.express as px
import pandas as pd
from src.ui import init,header,all_data
from src.battery import calculate_metrics
init(); header("Compare Tests","Compare observed capacity fade and voltage profiles across cells.")
df=all_data()
if df.empty: st.info("Load demo data on Dashboard or upload a workbook first."); st.stop()
cells=sorted(df.cell_id.dropna().unique()); selected=st.multiselect("Cells to compare",cells,default=cells)
comp=df[df.cell_id.isin(selected)]
tabs=st.tabs(["Capacity degradation","Cycle profiles","Metrics table"])
with tabs[0]:
    trend=comp.groupby(["cell_id","cycle"],as_index=False,sort=False).capacity.max()
    trend["retention_pct"]=trend.groupby("cell_id",sort=False).capacity.transform(lambda s: s/s.iloc[0]*100)
    fig=px.line(trend,x="cycle",y="retention_pct",color="cell_id",markers=True,labels={"cycle":"Cycle","retention_pct":"Capacity retention (%)"})
    # Display observed least-squares trend only when at least 3 distinct cycles are available.
    for cell,g in trend.groupby("cell_id"):
        numeric_cycles=pd.to_numeric(g.cycle,errors="coerce")
        if g.cycle.nunique()>=3 and numeric_cycles.notna().all():
            import numpy as np
            slope,intercept=np.polyfit(numeric_cycles,g.retention_pct,1)
            fig.add_scatter(x=numeric_cycles,y=slope*numeric_cycles+intercept,mode="lines",line={"dash":"dot"},name=f"{cell} observed trend")
    fig.update_layout(template="plotly_white",height=450); st.plotly_chart(fig,use_container_width=True)
    st.caption("Observed trend — not a lifetime prediction.")
with tabs[1]:
    cycle_options=comp.cycle.dropna().drop_duplicates().tolist()
    default_cycles=list(dict.fromkeys([cycle_options[0],cycle_options[-1]])) if cycle_options else []
    chosen=st.multiselect("Cycles",cycle_options,default=default_cycles)
    profile=comp[comp.cycle.isin(chosen)].copy()
    if profile.empty: st.info("Select at least one cycle.")
    else:
        fig=px.line(profile,x="capacity",y="voltage",color="cell_id",line_dash="cycle",hover_data=["cycle","step","current"]); fig.update_layout(template="plotly_white",height=460)
        st.plotly_chart(fig,use_container_width=True)
with tabs[2]:
    metrics=calculate_metrics(comp)
    st.dataframe(metrics,use_container_width=True,hide_index=True)
