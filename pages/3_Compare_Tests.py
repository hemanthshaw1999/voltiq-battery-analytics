import streamlit as st
import plotly.express as px
from src.ui import init,header,all_data
from src.battery import calculate_metrics
init(); header("Compare Tests","Compare observed capacity fade and voltage profiles across cells.")
df=all_data()
if df.empty: st.info("Load demo data on Dashboard or upload a workbook first."); st.stop()
cells=sorted(df.cell_id.dropna().unique()); selected=st.multiselect("Cells to compare",cells,default=cells)
comp=df[df.cell_id.isin(selected)]
tabs=st.tabs(["Capacity degradation","Cycle profiles","Metrics table"])
with tabs[0]:
    trend=comp.groupby(["cell_id","cycle"],as_index=False).capacity.max()
    trend["retention_pct"]=trend.groupby("cell_id").capacity.transform(lambda s: s/s.iloc[0]*100)
    fig=px.line(trend,x="cycle",y="retention_pct",color="cell_id",markers=True,labels={"cycle":"Cycle","retention_pct":"Capacity retention (%)"})
    # Display observed least-squares trend only when at least 3 distinct cycles are available.
    for cell,g in trend.groupby("cell_id"):
        if g.cycle.nunique()>=3:
            import numpy as np
            slope,intercept=np.polyfit(g.cycle,g.retention_pct,1)
            fig.add_scatter(x=g.cycle,y=slope*g.cycle+intercept,mode="lines",line={"dash":"dot"},name=f"{cell} observed trend")
    fig.update_layout(template="plotly_white",height=450); st.plotly_chart(fig,use_container_width=True)
    st.caption("Observed trend — not a lifetime prediction.")
with tabs[1]:
    maxcycle=int(comp.cycle.max()); chosen=st.multiselect("Cycles",sorted(comp.cycle.unique()),default=[1,maxcycle] if maxcycle>1 else [1])
    profile=comp[comp.cycle.isin(chosen)].copy()
    if profile.empty: st.info("Select at least one cycle.")
    else:
        fig=px.line(profile,x="capacity",y="voltage",color="cell_id",line_dash="cycle",hover_data=["cycle","step","current"]); fig.update_layout(template="plotly_white",height=460)
        st.plotly_chart(fig,use_container_width=True)
with tabs[2]:
    metrics=calculate_metrics(comp)
    st.dataframe(metrics,use_container_width=True,hide_index=True)
