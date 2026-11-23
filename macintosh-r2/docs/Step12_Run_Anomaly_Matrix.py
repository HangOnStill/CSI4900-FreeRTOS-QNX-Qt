"""Synthetic anomaly acceptance matrix; real hardware cases remain NOT_TESTED."""
import csv
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/"build"/"trace_analyzer_host.exe"
CFG=ROOT/"fixtures"/"config.csv"
OUT=ROOT/"evidence"/"r2_anomaly_matrix"
CASES=[
 ("deadline_miss","normal.csv",0,"WARN,DEADLINE_MISS,1,7000,7000,5000"),
 ("blocking_bound","blocking.csv",0,"WARN,BLOCK_TOO_LONG,1,1800,1500,1000"),
 ("release_jitter","jitter.csv",0,"WARN,RELEASE_JITTER,1,10400,400,200"),
 ("isr_budget","overbudget_isr.csv",0,"WARN,ISR_OVER_BUDGET,2,150,150,100"),
 ("overlap","overlap.csv",0,"WARN,OVERLAPPING_RELEASE"),
 ("corrupt_gap","gap.csv",1,"WARN,TRACE_GAP,-1,300"),
 ("incomplete_activation","incomplete.csv",0,"WARN,INCOMPLETE_ACTIVATION"),
 ("reversed_time","reverse_time.csv",1,"WARN,TIME_REVERSED"),
 ("nested_isr_duration","nested_isr.csv",0,"ISR_DURATION,ISR,1,200,200,600"),
]
MANUAL=[
 ("priority_inversion","Requires mutex owner/waiter priority & inheritance event IDs"),
 ("overload_demand","Requires configured WCET/period demand and measured source workload"),
 ("stm32_timer_reference","Requires independent timer capture on NUCLEO"),
 ("ring_buffer_overflow","Requires observed dropped-event counter sent over protocol"),
 ("full_qt_live","Requires Xavier Qt receiver and live NUCLEO stream"),
]
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    entries=[]
    failed=0
    for name,fixture,expected,token in CASES:
        result=subprocess.run([str(EXE),str(CFG),str(ROOT/"fixtures"/fixture)],
                              capture_output=True,text=True,timeout=10)
        ok=result.returncode==expected and token in result.stdout
        if not ok:failed+=1
        (OUT/(name+".txt")).write_text("SYNTHETIC=YES\nCOMMAND_FIXTURE="+fixture+
             "\nEXIT_CODE="+str(result.returncode)+"\n"+result.stdout+
             "\nSTDERR:\n"+result.stderr,encoding="utf-8")
        entries.append(dict(test=name,input=fixture,source="synthetic",
             expected=token,observed="PASS" if ok else "FAIL",
             integration_status="HOST_ONLY",notes="Offline fixture: not physical hardware"))
    for name,reason in MANUAL:
        entries.append(dict(test=name,input="",source="none",expected=reason,
             observed="NOT_TESTED",integration_status="REQUIRES_XAVIER_OR_HARDWARE",
             notes="No valid acceptance evidence yet"))
    with (OUT/"anomaly_matrix.csv").open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=list(entries[0]))
        writer.writeheader();writer.writerows(entries)
    print(f"HOST_SYNTHETIC_CASES={len(CASES)} PASS={len(CASES)-failed} FAIL={failed}")
    print(f"REMAINING_PHYSICAL_JOINT_GATES={len(MANUAL)}")
    print(f"MATRIX={OUT/'anomaly_matrix.csv'}")
    return 1 if failed else 0
if __name__=="__main__":
    raise SystemExit(main())
