"""Canonical battery data ingestion, validation, demo generation and metrics."""
from __future__ import annotations

from io import BytesIO
import re
import numpy as np
import pandas as pd

CANONICAL = ["timestamp", "test_id", "cell_id", "cycle", "step", "voltage", "current", "capacity", "energy", "temperature"]
ALIASES = {
    "timestamp": ["time", "datetime", "date/time", "date_time", "timestamp"],
    "cycle": ["cycle", "cycle number", "cycle_number", "cycleindex", "cycle index"],
    "step": ["step", "step number", "step_index"],
    "voltage": ["voltage", "voltage(v)", "voltage_v", "v"],
    "current": ["current", "current(a)", "current_a", "i"],
    "capacity": ["capacity", "capacity(ah)", "capacity_ah", "discharge capacity", "discharge capacity(ah)"],
    "energy": ["energy", "energy(wh)", "energy_wh"],
    "temperature": ["temperature", "temp", "temp(c)", "temperature_c", "temperature(c)"],
    "cell_id": ["cell_id", "cell id", "cell", "sample"],
    "test_id": ["test_id", "test id", "test", "experiment"],
}
REQUIRED = ["timestamp", "cycle", "voltage", "current", "capacity"]

def _key(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())

def detect_mapping(columns):
    result = {}
    for col in columns:
        key = _key(col)
        for field, aliases in ALIASES.items():
            if key in aliases or key.replace(" ", "") in [a.replace(" ", "") for a in aliases]:
                if field not in result:
                    result[field] = col
    return result

def normalize_frame(frame: pd.DataFrame, mapping: dict, filename="upload") -> pd.DataFrame:
    missing = [f for f in REQUIRED if not mapping.get(f) or mapping[f] not in frame.columns]
    if missing:
        raise ValueError(f"Required field(s) could not be mapped: {', '.join(missing)}. Available columns: {', '.join(map(str, frame.columns))}")
    out = pd.DataFrame(index=frame.index)
    for field in CANONICAL:
        source = mapping.get(field)
        out[field] = frame[source] if source in frame.columns else np.nan
    out["timestamp"] = pd.to_datetime(out.timestamp, errors="coerce")
    for field in ["cycle", "step", "voltage", "current", "capacity", "energy", "temperature"]:
        out[field] = pd.to_numeric(out[field], errors="coerce")
    stem = re.sub(r"\.[^.]+$", "", filename)
    out["test_id"] = out.test_id.fillna(stem).astype(str)
    out["cell_id"] = out.cell_id.fillna(stem).astype(str)
    return out[CANONICAL]

def validate_frame(df: pd.DataFrame):
    issues = []
    errors = []
    if df.empty: errors.append("No data rows found")
    absent = [c for c in REQUIRED if c not in df]
    if absent: errors.append("Missing required fields: " + ", ".join(absent))
    if "timestamp" in df and df.timestamp.isna().any(): issues.append(f"{int(df.timestamp.isna().sum())} invalid or missing timestamps")
    if "timestamp" in df and df.timestamp.duplicated().any(): issues.append(f"{int(df.timestamp.duplicated().sum())} duplicate timestamps")
    for c in ["cycle", "voltage", "current", "capacity"]:
        if c in df and df[c].isna().any(): issues.append(f"{int(df[c].isna().sum())} missing/invalid {c} values")
    for c in ["energy", "temperature", "step"]:
        if c in df and df[c].isna().any(): issues.append(f"{int(df[c].isna().sum())} missing/invalid {c} values")
    if "cycle" in df and (df.cycle.dropna() < 0).any(): errors.append("Negative cycle numbers found")
    if "voltage" in df and ((df.voltage < 0) | (df.voltage > 6)).any(): issues.append("Voltage outside expected 0–6 V range")
    if "temperature" in df and ((df.temperature < -40) | (df.temperature > 100)).any(): issues.append("Suspicious temperature outside −40–100 °C")
    if "cycle" in df and not df.cycle.dropna().empty:
        observed = set(df.cycle.dropna().astype(int)); expected = set(range(min(observed), max(observed)+1))
        gaps = expected - observed
        if gaps: issues.append(f"Missing cycle numbers: {', '.join(map(str, sorted(gaps)[:10]))}")
    if "timestamp" in df and df.timestamp.notna().sum() > 1 and not df.timestamp.dropna().is_monotonic_increasing: issues.append("Timestamps are not in ascending order")
    status = "ERROR" if errors else ("WARNING" if issues else "PASS")
    return {"status": status, "errors": errors, "warnings": issues, "rows": len(df)}

def generate_demo(cell_id="CELL-A001", cycles=100, capacity_ah=5.0, fade=0.00042, seed=4):
    rng = np.random.default_rng(seed)
    rows=[]; timestamp=pd.Timestamp("2025-01-01")
    for cycle in range(1, cycles+1):
        cap=capacity_ah*(1-fade*(cycle-1))
        # Charge and discharge each have a modest number of smooth engineering samples.
        for step, direction in [(1,1),(2,-1)]:
            fractions=np.linspace(0,1,24)
            for f in fractions:
                timestamp += pd.Timedelta(seconds=150 + int(rng.integers(0,20)))
                if direction > 0:
                    voltage=3.0+1.2*f+0.12*np.tanh((f-.88)*12)
                    current=1.0
                else:
                    voltage=4.2-1.15*f-0.16*np.tanh((f-.8)*10)
                    current=-1.0
                temp=25+5*f+0.2*np.sin(cycle/8)+rng.normal(0,.12)
                rows.append((timestamp, f"TEST-{cell_id}", cell_id, cycle, step, voltage+rng.normal(0,.004), current, cap*f, cap*f*3.65, temp))
    return pd.DataFrame(rows,columns=CANONICAL)

def demo_files():
    specs=[("CELL-A001",5.0,.00042,4),("CELL-B001",4.9,.00063,8),("CELL-C001",5.1,.00029,12)]
    result=[]
    for cell,cap,fade,seed in specs:
        df=generate_demo(cell,100,cap,fade,seed)
        # Ship demo data in a cycler-like alias format to exercise auto mapping.
        result.append((f"{cell.lower()}.xlsx",pd.DataFrame({"Time":df.timestamp,"Test ID":df.test_id,"Cell ID":df.cell_id,"Cycle Number":df.cycle,"Step":df.step,"Voltage(V)":df.voltage,"Current(A)":df.current,"Capacity(Ah)":df.capacity,"Energy(Wh)":df.energy,"Temp(C)":df.temperature})))
    return result

def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    records=[]
    for (test,cell), group in df.groupby(["test_id","cell_id"],dropna=False):
        g=group.sort_values("timestamp")
        cyc=g.groupby("cycle",dropna=True).capacity.max().dropna()
        first=float(cyc.iloc[0]) if len(cyc) else np.nan
        latest=float(cyc.iloc[-1]) if len(cyc) else np.nan
        retention=latest/first*100 if first and np.isfinite(first) else np.nan
        # Coulombic efficiency is available only when charge/discharge capacity endpoints are separable by step.
        charge=g[g.current>0].groupby("cycle").capacity.max()
        discharge=g[g.current<0].groupby("cycle").capacity.max()
        common=charge.index.intersection(discharge.index)
        ce=(discharge.loc[common]/charge.loc[common].replace(0,np.nan)).mean()*100 if len(common) else np.nan
        records.append({"test_id":test,"cell_id":cell,"cycles":int(g.cycle.nunique()),"data_points":len(g),"average_voltage":g.voltage.mean(),"max_voltage":g.voltage.max(),"min_voltage":g.voltage.min(),"average_current":g.current.mean(),"max_current":g.current.abs().max(),"max_temperature":g.temperature.max(),"average_temperature":g.temperature.mean(),"initial_capacity_ah":first,"latest_capacity_ah":latest,"capacity_retention_pct":retention,"capacity_fade_pct":100-retention if pd.notna(retention) else np.nan,"coulombic_efficiency_pct":ce})
    return pd.DataFrame(records)

def energy_from_power(df):
    g=df.sort_values("timestamp").copy()
    if g.timestamp.isna().any() or g.timestamp.nunique()<2: return np.nan
    seconds=(g.timestamp.astype("int64")/1e9).to_numpy()
    return float(np.trapezoid((g.voltage*g.current).to_numpy(),seconds)/3600)
