"""Independent timer comparison harness for Macintosh's CSI4900 M8.

Compare *interval durations* rather than unsynchronized absolute timestamps.
Input pairs must be manually captured at the SAME semantic marker using
independent, calibrated STM32 timer instrumentation. This code does not
create the required hardware measurements.
"""
import argparse
import csv
import json
from pathlib import Path
from statistics import mean

REQUIRED=("run_id","marker","trace_us","reference_us","reference_overhead_us")
def compare(source):
    with Path(source).open(newline="",encoding="utf-8-sig") as f:
        reader=csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError("Missing marker/timebase/overhead columns")
        entries=list(reader)
    if not entries:raise ValueError("No samples")
    records=[]
    last={}
    for number,row in enumerate(entries,2):
        run=row["run_id"]
        marker=row["marker"]
        if not run or not marker:raise ValueError(f"Row {number}: blank marker or run")
        try:
            trace=int(row["trace_us"])
            reference=int(row["reference_us"])
            overhead=int(row["reference_overhead_us"])
        except ValueError as exc:
            raise ValueError(f"Row {number}: nonnumeric timing") from exc
        if min(trace,reference,overhead)<0 or reference<overhead:
            raise ValueError(f"Row {number}: negative or impossible timing")
        adjusted=reference-overhead
        if run in last:
            before=last[run]
            tdiff=trace-before[0]
            rdiff=adjusted-before[1]
            if tdiff<=0 or rdiff<=0:
                raise ValueError(f"Row {number}: non-monotonic timer in run {run}")
            error=tdiff-rdiff
            records.append(dict(run_id=run,from_marker=before[2],
                to_marker=marker,trace_interval_us=tdiff,
                reference_interval_us=rdiff,signed_error_us=error,
                absolute_error_us=abs(error)))
        last[run]=(trace,adjusted,marker)
    if not records:
        raise ValueError("Need two matched markers per run")
    errors=sorted(r["absolute_error_us"] for r in records)
    n=len(errors)
    result=dict(paired_intervals=n,
        mean_absolute_error_us=round(mean(errors),6),
        max_absolute_error_us=errors[-1],
        p95_absolute_error_us=errors[max(0,(95*n+99)//100-1)],
        max_reference_interval_us=max(r["reference_interval_us"] for r in records))
    return records,result

def export(source,out_dir,provenance):
    if provenance not in ("synthetic","hardware"):
        raise ValueError("Specify explicit provenance")
    rows,summary=compare(source)
    out=Path(out_dir)
    out.mkdir(parents=True,exist_ok=True)
    fields=("run_id","from_marker","to_marker","trace_interval_us",
            "reference_interval_us","signed_error_us","absolute_error_us")
    with (out/"timer_reference_errors.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader();writer.writerows(rows)
    summary.update(provenance=provenance,source_file=str(source),
        method="paired_adjacent_intervals; reference_overhead_subtracted; no absolute clock synchronization")
    (out/"timer_reference_summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return summary

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("paired_csv",type=Path)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--provenance",choices=("synthetic","hardware"),
                        required=True)
    args=parser.parse_args()
    print(json.dumps(export(args.paired_csv,args.output,args.provenance),sort_keys=True))
if __name__=="__main__":main()
