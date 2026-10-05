from io import BytesIO
import pandas as pd
import streamlit as st
import plotly.express as px
from src.battery import demo_files, detect_mapping, normalize_frame, validate_frame

def init():
    st.set_page_config(page_title="VoltIQ | Battery Analytics",page_icon="⚡",layout="wide")
    st.markdown('''<style>
    .stApp {background:#f5f7fa;color:#172534} section[data-testid="stSidebar"]{background:#102537}
    section[data-testid="stSidebar"] *{color:#eaf2f7!important}
    .hero{background:linear-gradient(115deg,#102b3d,#145768);padding:1.7rem 2rem;border-radius:16px;color:white;margin-bottom:1.1rem}
    .hero h1{color:white;margin:0}.hero p{color:#d6e9ef;margin:.4rem 0 0}
    div[data-testid="stMetric"]{background:white;padding:1rem;border-radius:12px;border:1px solid #e4eaf0}
    </style>''',unsafe_allow_html=True)
    for k,v in {"datasets":{},"recent":[]}.items(): st.session_state.setdefault(k,v)

def header(title,subtitle):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{subtitle}</p></div>',unsafe_allow_html=True)

def all_data():
    return pd.concat(st.session_state.datasets.values(),ignore_index=True) if st.session_state.datasets else pd.DataFrame()

def load_demos():
    for name,raw in demo_files():
        mapping=detect_mapping(raw.columns,raw)
        df=normalize_frame(raw,mapping,name)
        st.session_state.datasets[name]=df
        st.session_state.recent.insert(0,{"file":name,"rows":len(df),"status":validate_frame(df)["status"]})
    st.session_state.recent=st.session_state.recent[:6]

def render_chart(df,x,y,color="cell_id",title=None):
    if df.empty or x not in df or y not in df: st.info("Select data with the fields needed for this chart."); return
    plot=df.copy()
    if y=="power": plot["power"]=plot.voltage*plot.current
    fig=px.line(plot,x=x,y=y,color=color if color in plot else None,hover_data=[c for c in ["cell_id","test_id","cycle","step","voltage","current","capacity","temperature"] if c in plot],title=title or f"{y.title()} vs {x.title()}")
    fig.update_layout(template="plotly_white",height=430,margin=dict(l=10,r=10,t=55,b=10),legend_title_text="Cell")
    st.plotly_chart(fig,use_container_width=True,theme=None)

def store_upload(upload,manual=None):
    try:
        raw=pd.read_excel(upload)
        mapping=detect_mapping(raw.columns,raw)
        if manual: mapping.update(manual)
        normalized=normalize_frame(raw,mapping,upload.name)
        st.session_state.datasets[upload.name]=normalized
        validation=validate_frame(normalized)
        st.session_state.recent.insert(0,{"file":upload.name,"rows":len(normalized),"status":validation["status"]})
        return raw,mapping,normalized,validation,None
    except Exception as exc:
        return None,None,None,None,str(exc)

def excel_bytes(sheets):
    buff=BytesIO()
    with pd.ExcelWriter(buff,engine="openpyxl") as writer:
        for name,df in sheets.items(): df.to_excel(writer,sheet_name=name,index=False)
    return buff.getvalue()
