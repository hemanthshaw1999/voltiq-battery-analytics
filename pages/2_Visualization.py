import streamlit as st
import pandas as pd
from src.ui import init,header,all_data,render_chart
init(); header("Visualization","Explore voltage, current, capacity, energy, temperature and power.")
df=all_data()
if df.empty: st.info("Load demo data on Dashboard or upload a workbook first."); st.stop()
cells=sorted(df.cell_id.dropna().unique()); selected=st.multiselect("Cells / tests",cells,default=cells)
view=df[df.cell_id.isin(selected)].copy()
cycle_values=view.cycle.dropna().drop_duplicates().tolist()
numeric_cycles=pd.to_numeric(view.cycle,errors="coerce")
if cycle_values and pd.api.types.is_numeric_dtype(view.cycle) and numeric_cycles.notna().sum()==view.cycle.notna().sum():
    low,high=numeric_cycles.min(),numeric_cycles.max()
    if float(low).is_integer() and float(high).is_integer(): low,high=int(low),int(high)
    cr=st.slider("Cycle range",low,high,(low,high))
    view=view[numeric_cycles.between(*cr)]
elif cycle_values:
    chosen_cycles=st.multiselect("Cycle(s)",cycle_values,default=[cycle_values[-1]])
    view=view[view.cycle.isin(chosen_cycles)]
else:
    st.warning("No valid cycle identifiers were found.")
    st.stop()
a,b,c=st.columns(3)
x=a.selectbox("X axis",["timestamp","cycle","capacity"],format_func=str.title,index=1)
y=b.selectbox("Y axis",["voltage","current","capacity","energy","temperature","power"],format_func=str.title)
kind=c.selectbox("Chart type",["Line","Scatter","Bar"])
if y=="power": view["power"]=view.voltage*view.current
import plotly.express as px
fig=px.line(view,x=x,y=y,color="cell_id",hover_data=["test_id","cycle","step","voltage","current","capacity","temperature"],render_mode="webgl") if kind=="Line" else (px.scatter(view,x=x,y=y,color="cell_id",hover_data=["test_id","cycle","step"]) if kind=="Scatter" else px.bar(view,x=x,y=y,color="cell_id"))
fig.update_layout(template="plotly_white",height=470,legend_title="Cell")
st.plotly_chart(fig,use_container_width=True)
st.caption("Use the chart toolbar to zoom, pan and download a chart image.")
st.subheader("Engineering Views")
options={"Voltage vs Time":("timestamp","voltage"),"Voltage vs Capacity":("capacity","voltage"),"Current vs Time":("timestamp","current"),"Temperature vs Time":("timestamp","temperature"),"Capacity vs Cycle":("cycle","capacity"),"Energy vs Cycle":("cycle","energy"),"Power vs Time":("timestamp","power")}
choice=st.selectbox("Quick view",list(options))
if choice=="Capacity vs Cycle":
    quick=view.groupby(["cell_id","cycle"],as_index=False).capacity.max()
elif choice=="Energy vs Cycle": quick=view.groupby(["cell_id","cycle"],as_index=False).energy.max()
else: quick=view
render_chart(quick,*options[choice],title=choice)
st.subheader("Efficiency vs Cycle")
eff=[]
for cell,g in view.groupby("cell_id"):
    charge=g[g.current>0].groupby("cycle").capacity.max()
    discharge=g[g.current<0].groupby("cycle").capacity.max()
    shared=charge.index.intersection(discharge.index)
    for cycle in shared:
        if charge.loc[cycle]>0: eff.append({"cell_id":cell,"cycle":cycle,"efficiency_pct":discharge.loc[cycle]/charge.loc[cycle]*100})
if eff:
    st.plotly_chart(px.line(__import__('pandas').DataFrame(eff),x="cycle",y="efficiency_pct",color="cell_id",labels={"efficiency_pct":"Estimated coulombic efficiency (%)"}).update_layout(template="plotly_white",height=360),use_container_width=True)
    st.caption("Estimated from charge/discharge capacity endpoints per cycle; source capacity conventions affect this value.")
else: st.info("Not available from current dataset: charge and discharge records could not be paired by cycle.")
