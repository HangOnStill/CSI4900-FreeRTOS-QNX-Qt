"""CSI4900 Macintosh R2 -> Qt-neutral diagnostics export.

Consumes already validated decoded-event analysis output. Does not decode STM32
UART or invent releases, idles, synchronization ownership, or lost events.

Creates stable JSONL for QJsonDocument and reviewable CSVs for Qt tables/export.
No network activity; bridge only operates on explicitly named input files.
"""
from argparse import ArgumentParser
import hashlib
import csv
import json
from pathlib import Path
import re

SCHEMA="csi4900.diagnostics.v1"
KINDS={
    "M2_WINDOW":"utilization_window",
    "M2_WINDOW_TASK":"task_window",
    "M2_WINDOW_ISR":"isr_window",
    "M2_ISR_CALL":"isr_call",
    "M2_ISR_SUMMARY":"isr_summary",
    "M2_TASK_SUMMARY":"task_summary",
    "M2_WARN":"warning",
    "M2_GAP":"trace_gap",
    "M2_SESSION":"session",
    "WARN":"warning",
    "TASK_SUMMARY":"task_summary_r1",
    "ISR_SUMMARY":"isr_summary_r1",
    "ACTIVATION":"activation_r1",
}
NUMERIC=re.compile(r"^-?\d+$")
FLOAT=re.compile(r"^-?(?:\d+\.\d+|\d+\.\d*|\.\d+)$")

def convert(value):
    if NUMERIC.fullmatch(value):
        return int(value)
    if FLOAT.fullmatch(value):
        return float(value)
    return value

def read_records(path):
    for n,line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(),1):
        if not line.strip():
            continue
        pieces=line.split(",")
        record_type=pieces[0]
        if record_type not in KINDS:
            continue
        if record_type=="WARN":
            if len(pieces)!=6:
                raise ValueError(f"{path}:{n}: invalid R1 WARN length")
            p={"code":pieces[1],"id":convert(pieces[2]),"ts_us":convert(pieces[3]),
               "measured_us":convert(pieces[4]),"limit_us":convert(pieces[5])}
        elif record_type=="ACTIVATION":
            if len(pieces)!=6:
                raise ValueError(f"{path}:{n}: invalid activation layout")
            p={"object_type":pieces[1],"id":convert(pieces[2]),
               "ts_us":convert(pieces[3]),"response_us":convert(pieces[4]),
               "cpu_us":convert(pieces[5])}
        else:
            p={}
            for item in pieces[1:]:
                if "=" not in item:
                    raise ValueError(f"{path}:{n}: unexpected positional field")
                key,value=item.split("=",1)
                if not key or key in p:
                    raise ValueError(f"{path}:{n}: duplicate/blank field {key}")
                p[key]=convert(value)
        yield record_type,p

def validated_windows(records):
    prev_end=None
    windows=[]
    for kind,row in records:
        if kind!="M2_WINDOW":continue
        required=("start_us","end_us","elapsed_us","task_us","isr_us",
                  "idle_us","unknown_us","busy_lower_pct","quality")
        if not all(k in row for k in required):
            raise ValueError("Incomplete R2 utilization record")
        start,end=row["start_us"],row["end_us"]
        if not isinstance(start,int) or not isinstance(end,int) or start>=end:
            raise ValueError("Invalid window endpoints")
        if prev_end is not None and start!=prev_end:
            raise ValueError("Noncontiguous sliding windows")
        if end-start!=row["elapsed_us"]:
            raise ValueError("Window length mismatch")
        if sum(row[k] for k in ("task_us","isr_us","idle_us","unknown_us"))!=row["elapsed_us"]:
            raise ValueError("Exclusive CPU accounting invalid")
        if row["quality"]=="COMPLETE" and row["unknown_us"]!=0:
            raise ValueError("Incorrect COMPLETE quality declaration")
        if not 0<=row["busy_lower_pct"]<=100.001:
            raise ValueError("Invalid CPU percentage")
        prev_end=end
        windows.append(row)
    if not windows:
        raise ValueError("No R2 utilization windows found")
    return windows

def write_csv(path,columns,rows):
    with path.open("w",newline="",encoding="utf-8") as file:
        writer=csv.DictWriter(file,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        for row in rows:writer.writerow(row)

def export(r2,r1,out,run_id,provenance,source_trace=None):
    out=Path(out)
    if not re.fullmatch(r"[a-zA-Z0-9_.-]{1,80}",run_id):
        raise ValueError("run-id must be a short portable identifier")
    if provenance not in ("synthetic","captured","replayed"):
        raise ValueError("provenance must identify the evidence source")
    if r1 and not source_trace:
        raise ValueError("Pairing R1/R2 requires --source-trace from the same input to both")
    source_sha=(hashlib.sha256(Path(source_trace).read_bytes()).hexdigest()
                if source_trace else None)
    r2_rec=list(read_records(r2))
    windows=validated_windows(r2_rec)
    r1_rec=list(read_records(r1)) if r1 else []
    if len([1 for k,_ in r2_rec if k=="M2_SESSION"])!=1:
        raise ValueError("Exactly one R2 session is required")
    session=next(row for kind,row in r2_rec if kind=="M2_SESSION")
    if session["elapsed_us"]!=sum(w["elapsed_us"] for w in windows):
        raise ValueError("R2 windows do not cover the declared session")
    for key in ("task_us","isr_us","idle_us","unknown_us"):
        if session[key]!=sum(w[key] for w in windows):
            raise ValueError(f"Session/window total mismatch for {key}")
    out.mkdir(parents=True,exist_ok=True)
    content=[]
    for source,records in (("r2",r2_rec),("r1",r1_rec)):
        for tag,row in records:
            content.append({"schema":SCHEMA,"run_id":run_id,
                "provenance":provenance,"source":source,
                "kind":KINDS[tag],"data":row})
    jsonl=out/"diagnostics.jsonl"
    with jsonl.open("w",encoding="utf-8",newline="\n") as stream:
        for item in content:
            stream.write(json.dumps(item,sort_keys=True,separators=(",",":"),ensure_ascii=False)+"\n")
    cols=("start_us","end_us","elapsed_us","task_us","isr_us","idle_us",
          "unknown_us","busy_lower_pct","quality")
    write_csv(out/"utilization_windows.csv",cols,windows)
    warning_rows=[]
    for source,records in (("r2",r2_rec),("r1",r1_rec)):
        for kind,row in records:
            if kind in ("M2_WARN","WARN"):
                warning_rows.append({"run_id":run_id,"source":source,
                    "code":row.get("code",""),"id":row.get("id",""),
                    "ts_us":row.get("ts_us",""),
                    "measured_us":row.get("measured_us",""),
                    "limit_us":row.get("limit_us","")})
    write_csv(out/"warnings.csv",
              ("run_id","source","code","id","ts_us","measured_us","limit_us"),
              warning_rows)
    stat_rows=[]
    for source,records in (("r2",r2_rec),("r1",r1_rec)):
        for kind,row in records:
            if kind.endswith("_SUMMARY") and kind not in ("M2_SESSION",):
                for field,value in row.items():
                    if field=="id":continue
                    stat_rows.append({"run_id":run_id,"source":source,
                        "record":kind,"id":row.get("id",""),
                        "metric":field,"value":value})
    write_csv(out/"statistics.csv",
        ("run_id","source","record","id","metric","value"),stat_rows)
    (out/"manifest.json").write_text(json.dumps({
        "schema":SCHEMA,"run_id":run_id,"provenance":provenance,
        "input_r2":str(r2),"input_r1":str(r1) if r1 else None,
        "source_trace":str(source_trace) if source_trace else None,
        "source_sha256":source_sha,
        "records":len(content),"windows":len(windows),
        "warnings":len(warning_rows),
        "data_status":"Not a live Qt connection; no firmware provenance is implied."
    },indent=2)+"\n",encoding="utf-8")
    return {"records":len(content),"windows":len(windows),"warnings":len(warning_rows)}

def main():
    p=ArgumentParser()
    p.add_argument("--r2",type=Path,required=True)
    p.add_argument("--r1",type=Path)
    p.add_argument("--source-trace",type=Path,
                   help="Mandatory when pairing R1 and R2 outputs; must be their shared input")
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--run-id",default="r2_synthetic")
    p.add_argument("--provenance",choices=("synthetic","captured","replayed"),
                   default="synthetic")
    args=p.parse_args()
    print(json.dumps(export(args.r2,args.r1,args.output,args.run_id,args.provenance,
                            args.source_trace),
                     sort_keys=True))
if __name__=="__main__":main()
