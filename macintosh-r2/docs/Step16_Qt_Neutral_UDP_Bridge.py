"""CSI4900 Qt-neutral bounded UDP diagnostic datagrams, OFFLINE adapter.

Consumes only Step10 validated diagnostics.jsonl; does not derive RELEASE,
COMPLETE, ISR, idle or CPU metrics from raw v1 UART switch events. Each
datagram is independently parseable as a QJsonDocument JSON object.

Default --output-mode=file emits newline-delimited datagrams, no network.
Optional UDP mode defaults to IPv4 loopback; sending to other hosts requires
an explicit --allow-nonloopback flag.
"""
from argparse import ArgumentParser
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import socket
from typing import Iterable

SOURCE_SCHEMA="csi4900.diagnostics.v1"
WIRE_SCHEMA="csi4900.udp.diagnostics.v1"
MAX_DATAGRAM=1200
MAX_FILE=2*1024*1024
MAX_RECORDS=10000
RUN_ID=re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
PROVENANCES={"synthetic","captured","replayed"}
SOURCES={"r1","r2"}
KNOWN_KINDS={
    "utilization_window","task_window","isr_window","isr_call",
    "isr_summary","task_summary","warning","trace_gap",
    "session","task_summary_r1","isr_summary_r1","activation_r1",
}
def canonical(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode("utf-8")

def verify_record(rec, common):
    if not isinstance(rec,dict):
        raise ValueError("Expected JSON object")
    if rec.get("schema")!=SOURCE_SCHEMA:
        raise ValueError("Unknown diagnostics source schema")
    if rec.get("provenance") not in PROVENANCES:
        raise ValueError("Missing explicit provenance")
    if rec.get("source") not in SOURCES:
        raise ValueError("Unknown R1/R2 source")
    if rec.get("kind") not in KNOWN_KINDS or not isinstance(rec.get("data"),dict):
        raise ValueError("Unknown kind or invalid diagnostics data")
    run_id=rec.get("run_id")
    if not isinstance(run_id,str) or not RUN_ID.fullmatch(run_id):
        raise ValueError("Invalid run ID")
    ident=(run_id,rec["provenance"])
    if common is not None and ident!=common:
        raise ValueError("Cannot mix multiple runs or provenance values")
    return ident

def prepare(path, max_datagram=MAX_DATAGRAM):
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=MAX_FILE:
        raise ValueError("Input JSONL missing or too large")
    if not 200<=max_datagram<=1200:
        raise ValueError("Datagram bound must be between 200 and 1200 bytes")
    raw=path.read_bytes()
    source_hash=hashlib.sha256(raw).hexdigest()
    records=[]
    common=None
    for i,line in enumerate(raw.splitlines(),1):
        if not line.strip():
            continue
        if len(line)>8192:
            raise ValueError("Overlong diagnostics record")
        try:
            parsed=json.loads(line.decode("utf-8"))
        except (ValueError,UnicodeDecodeError) as exc:
            raise ValueError(f"Malformed diagnostics row {i}") from exc
        common=verify_record(parsed,common)
        records.append(parsed)
        if len(records)>MAX_RECORDS:
            raise ValueError("Too many diagnostic records")
    if not records:
        raise ValueError("Empty diagnostics stream")
    out=[]
    for seq,rec in enumerate(records):
        env={
            "schema":WIRE_SCHEMA,
            "sequence":seq,
            "count":len(records),
            "run_id":rec["run_id"],
            "provenance":rec["provenance"],
            "source":rec["source"],
            "kind":rec["kind"],
            "data":rec["data"],
            "diagnostics_sha256":source_hash,
        }
        payload=canonical(env)
        if len(payload)>max_datagram:
            raise ValueError(f"Record {seq} exceeds UDP size bound ({len(payload)} > {max_datagram})")
        out.append(payload)
    return out

def inspect_packets(packets):
    if not packets:
        raise ValueError("No packets")
    total=len(packets)
    run=None
    digest=None
    for index,payload in enumerate(packets):
        item=json.loads(payload)
        if item.get("schema")!=WIRE_SCHEMA or item.get("sequence")!=index or item.get("count")!=total:
            raise ValueError("Packet sequence/count or schema invalid")
        source=(item["run_id"],item["provenance"])
        if run is None:run=source
        if run!=source:raise ValueError("Mixing runs in packet stream")
        if digest is None:digest=item["diagnostics_sha256"]
        if digest!=item["diagnostics_sha256"]:raise ValueError("Conflicting source digest")
    return {"records":total,"run_id":run[0],"provenance":run[1],
            "source_sha256":digest,"schema":WIRE_SCHEMA}

def emit_to_file(packets,output):
    out=Path(output)
    if out.exists():
        raise FileExistsError("Refusing to overwrite existing datagram evidence")
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("xb") as stream:
        for row in packets:stream.write(row+b"\n")

def emit_udp(packets,address,port,allow_nonloopback=False):
    try:dest=ipaddress.ip_address(address)
    except ValueError as exc:raise ValueError("Use literal IPv4/IPv6 address, not DNS hostnames") from exc
    if not 1<=port<=65535:raise ValueError("UDP port out of range")
    if not dest.is_loopback and not allow_nonloopback:
        raise ValueError("Nonloopback UDP target requires explicit --allow-nonloopback")
    af=socket.AF_INET6 if dest.version==6 else socket.AF_INET
    with socket.socket(af,socket.SOCK_DGRAM) as sock:
        for packet in packets:
            if sock.sendto(packet,(str(dest),port))!=len(packet):
                raise OSError("Short UDP send")

def main():
    parser=ArgumentParser()
    parser.add_argument("--input",required=True,type=Path,help="Step10 diagnostics.jsonl")
    parser.add_argument("--output-mode",choices=("file","udp"),default="file")
    parser.add_argument("--output",type=Path,help="Required in file mode")
    parser.add_argument("--host",default="127.0.0.1",help="Literal IP; loopback default")
    parser.add_argument("--port",type=int,default=49000)
    parser.add_argument("--allow-nonloopback",action="store_true")
    parser.add_argument("--max-datagram",type=int,default=MAX_DATAGRAM)
    args=parser.parse_args()
    packets=prepare(args.input,args.max_datagram)
    summary=inspect_packets(packets)
    if args.output_mode=="file":
        if not args.output:parser.error("File output requires --output")
        emit_to_file(packets,args.output)
    else:
        if args.output:parser.error("--output only allowed in file mode")
        emit_udp(packets,args.host,args.port,args.allow_nonloopback)
    summary.update({"mode":args.output_mode,"packet_bytes_max":max(map(len,packets)),
                    "network_test":"UDP loopback only; NO live Qt or QNX target was tested"})
    print(json.dumps(summary,sort_keys=True))
if __name__=="__main__":
    main()
