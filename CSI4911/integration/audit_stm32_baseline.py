"""Audit recovered, historical STM32 Core sources; does not compile or flash."""
import hashlib,json,re
from pathlib import Path
REPO=Path(__file__).resolve().parents[2]
MCU=REPO/"CSI4911"
CORE=MCU/"Core"
OLD=Path(r"D:\Courses\CSI 4900 F00 Honours project Mohamed Ibrahim\Xavier Codes\Core")
NAMES=("SensorTask","ControlTask","LoggerTask","CommunicationTask")
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def fnv1a(name):
    h=2166136261
    for v in name.encode("ascii"):h=((h^v)*16777619)&0xffffffff
    return h
def main():
    srcs=sorted(p for p in CORE.rglob("*") if p.is_file())
    assert len(srcs)==17,len(srcs)
    files=[]
    for p in srcs:
        rel=p.relative_to(CORE).as_posix()
        origin=OLD/rel
        assert origin.exists() and digest(origin)==digest(p),rel
        files.append({"path":"Core/"+rel,"bytes":p.stat().st_size,"sha256":digest(p)})
    app=(CORE/"Src/app_freertos.c").read_text()
    trace=(CORE/"Src/trace_buffer.c").read_text()
    proto=(CORE/"Src/trace_transport.c").read_text()
    config=(CORE/"Inc/FreeRTOSConfig.h").read_text()
    events=(CORE/"Inc/trace_buffer.h").read_text()
    collector=(REPO/"macintosh-r2/src/uart_collector_v1.c").read_text()
    ioc=(MCU/"CSI4911.ioc").read_text()
    checks={
      "task_names_match_collector":all(f'.name = "{s}"' in app and f'fnv1a("{s}")' in collector for s in NAMES),
      "v1_event_type_ids":all(s in events for s in ("TRACE_EVENT_TASK_SWITCH_IN = 1U","TRACE_EVENT_TASK_SWITCH_OUT = 2U")),
      "switch_hooks_enabled":all(s in config for s in ("traceTASK_SWITCHED_IN()  Trace_OnTaskSwitchedIn()","traceTASK_SWITCHED_OUT() Trace_OnTaskSwitchedOut()")),
      "DWT_counter_enabled_and_read":"DWT->CYCCNT" in trace and "DWT_CTRL_CYCCNTENA_Msk" in trace,
      "FNV1a_task_hash":"2166136261U" in trace and "16777619U" in trace,
      "ring_overflow_counter":"traceOverflowCount++" in trace,
      "uart_PG7_PG8_AF8":all(s in proto for s in ("GPIO_PIN_7 | GPIO_PIN_8","GPIOG","GPIO_AF8_LPUART1")),
      "uart_LPUART1_115200":"LPUART1->TDR" in proto and "115200U" in proto,
      "wire_header_and_crc":all(s in proto for s in ("0xA5U","0x5AU","0x1021U")),
      "ioc_source_task_name_conflict_detected":all(s in ioc for s in ("task_green","task_blue","task_red")) and "task_green" not in app,
      "v1_lacks_explicit_RELEASE_COMPLETE":all(s not in events for s in ("TRACE_EVENT_RELEASE","TRACE_EVENT_COMPLETE")),
    }
    for name,ok in checks.items():
        if not ok:raise RuntimeError("FAILED static source check: "+name)
    out={
      "source_provenance":"Older archived 'Xavier Codes' 2026-11-15, NOT Xavier's latest November 23 firmware",
      "sha256_preserved_core_files":files,
      "static_source_checks":checks,
      "task_fnv1a_hashes":{n:fnv1a(n) for n in NAMES},
      "CPU_hsi_nominal":"16 MHz configured in archived main.c; measured frequency NOT VERIFIED",
      "UART_source":"LPUART1 GPIOG PG7/PG8 AF8, 115200 baud; board connector mapping NOT VERIFIED",
      "stm32_build":"NOT RUN - GNU Tools for STM32 toolchain unavailable",
      "live_hardware_capture":"NOT RUN - Pi and STM32 power off",
      "ioc_source_mismatch":"DETECTED; generator could replace user task source",
      "v1_release_complete_isr_semantics":"NOT PRESENT",
    }
    dest=MCU/"integration/STM32_BASELINE_SOURCE_MANIFEST.json"
    dest.write_text(json.dumps(out,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(f"SOURCE_SHA256_IDENTICAL_TO_ARCHIVED_ORIGINAL={len(files)}/{len(files)}")
    print(f"STATIC_CONTRACT_ASSERTIONS={len(checks)}/{len(checks)} PASS")
    print("IOC_TASK_NAME_CONFLICT=DETECTED")
    print("ARM_BUILD=NOT_RUN")
    print("EVIDENCE="+str(dest))
if __name__=="__main__":main()
