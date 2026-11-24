"""CSI4900 Qt (PySide6) reference receiver for validated diagnostics UDP v1.

Runs actual Qt QJsonDocument parsing and QUdpSocket receive on IPv4 loopback.
This is NOT Xavier's production Qt application; no UI widgets are created.
No external network sends or source/firmware state changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import socket
import sys
from typing import List

from PySide6.QtCore import QCoreApplication,QJsonDocument
from PySide6.QtNetwork import QHostAddress,QUdpSocket

WIRE_SCHEMA="csi4900.udp.diagnostics.v1"
MAX_PACKET_BYTES=1200
MAX_PACKETS=10000
MAX_FILE_BYTES=2*1024*1024
VALID_KINDS={
    "utilization_window","task_window","isr_window","isr_call",
    "isr_summary","task_summary","warning","trace_gap","session",
    "task_summary_r1","isr_summary_r1","activation_r1",
}
VALID_SOURCES={"r1","r2"}
VALID_PROVENANCE={"synthetic","captured","replayed"}
_APP=None

def ensure_app():
    global _APP
    if _APP is None:
        _APP=QCoreApplication.instance() or QCoreApplication([])
    return _APP

def qt_json_parse(data:bytes)->dict:
    if not data or len(data)>MAX_PACKET_BYTES:
        raise ValueError("Datagram outside permitted 1..1200-byte bound")
    doc=QJsonDocument.fromJson(data)
    if doc.isNull() or not doc.isObject():
        raise ValueError("Malformed JSON object for Qt")
    obj=doc.object()
    if not isinstance(obj,dict):
        # PySide6 wrapper may expose a dict-convertible QJsonObject.
        obj=dict(obj)
    return obj

class QtReferenceSession:
    """Sequence-checked Qt JSON UDP consumer; no fabricated timing semantics."""
    def __init__(self):
        self.events=[]
        self.count=None
        self.run_id=None
        self.provenance=None
        self.source_sha256=None
    def consume(self,packet:bytes):
        obj=qt_json_parse(packet)
        if obj.get("schema")!=WIRE_SCHEMA:
            raise ValueError("Qt receiver: incompatible message schema")
        if obj.get("source") not in VALID_SOURCES or obj.get("kind") not in VALID_KINDS:
            raise ValueError("Qt receiver: unknown source or event kind")
        if obj.get("provenance") not in VALID_PROVENANCE:
            raise ValueError("Qt receiver: provenance missing")
        data=obj.get("data")
        if not isinstance(data,dict):
            raise ValueError("Qt receiver: data must be a JSON object")
        seq=obj.get("sequence")
        size=obj.get("count")
        if type(seq)!=int or type(size)!=int or size<=0 or size>MAX_PACKETS:
            raise ValueError("Qt receiver: bad sequence or count")
        if seq!=len(self.events) or seq>=size:
            raise ValueError("Qt receiver: dropped/reordered/duplicate datagram")
        digest=obj.get("diagnostics_sha256")
        if not isinstance(digest,str) or len(digest)!=64:
            raise ValueError("Qt receiver: invalid source digest")
        if self.count is None:
            self.count=size
            self.run_id=obj.get("run_id")
            self.provenance=obj["provenance"]
            self.source_sha256=digest
        if (size!=self.count or obj.get("run_id")!=self.run_id
            or obj["provenance"]!=self.provenance or digest!=self.source_sha256):
            raise ValueError("Qt receiver: inconsistent diagnostic session")
        self.events.append(obj)
    def summary(self):
        if self.count is None or len(self.events)!=self.count:
            raise ValueError("Qt receiver: missing datagrams")
        return {"status":"PASS","runtime":"PySide6 QCoreApplication/QUdpSocket/QJsonDocument",
                "schema":WIRE_SCHEMA,"packets":self.count,
                "run_id":self.run_id,"provenance":self.provenance,
                "source_sha256":self.source_sha256,
                "quality_flags":sorted(set(
                    str(e["data"]["quality"]) for e in self.events if "quality" in e["data"])),
                "qt_production_application_tested":False,
                "real_stm32_uart_tested":False}

def read_packets(path):
    path=Path(path)
    if not path.is_file() or not 1<=path.stat().st_size<=MAX_FILE_BYTES:
        raise ValueError("Missing or oversized pre-encoded packet JSONL")
    result=[]
    for linenum,line in enumerate(path.read_bytes().splitlines(),1):
        if not line.strip():continue
        if len(result)>=MAX_PACKETS:raise ValueError("Too many Qt test packets")
        result.append(line)
    if not result:raise ValueError("Empty Qt packet stream")
    return result

def qt_udp_loopback(packets):
    """Send via stdlib UDP and receive with REAL Qt QUdpSocket on localhost."""
    app=ensure_app()
    receiver=QUdpSocket()
    if not receiver.bind(QHostAddress("127.0.0.1"),0):
        raise RuntimeError("Qt QUdpSocket bind failure: "+receiver.errorString())
    port=receiver.localPort()
    if port<=0:raise RuntimeError("Qt socket returned zero local port")
    session=QtReferenceSession()
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sender:
            sender.bind(("127.0.0.1",0))
            for packet in packets:
                if sender.sendto(packet,("127.0.0.1",port))!=len(packet):
                    raise RuntimeError("Short UDP send")
        for _ in packets:
            if not receiver.hasPendingDatagrams() and not receiver.waitForReadyRead(3000):
                raise TimeoutError("Qt QUdpSocket timed out awaiting packet")
            if not receiver.hasPendingDatagrams():
                raise TimeoutError("Qt QUdpSocket has no pending datagram")
            incoming=receiver.receiveDatagram()
            if incoming.senderAddress()!=QHostAddress("127.0.0.1"):
                raise ValueError("Untrusted non-loopback UDP sender")
            session.consume(bytes(incoming.data()))
        summary=session.summary()
        summary["delivery"]="Qt QUdpSocket receives real Windows IPv4 loopback datagrams"
        return summary
    finally:
        receiver.close()

def qt_file_parse(packets):
    ensure_app()
    session=QtReferenceSession()
    for packet in packets:session.consume(packet)
    result=session.summary()
    result["delivery"]="Qt QJsonDocument parsed offline packet evidence"
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,required=True,
                   help="Step16 Qt-neutral UDP packet JSONL")
    p.add_argument("--mode",choices=("file","udp-loopback"),default="udp-loopback")
    args=p.parse_args()
    packets=read_packets(args.input)
    result=qt_udp_loopback(packets) if args.mode=="udp-loopback" else qt_file_parse(packets)
    print(json.dumps(result,sort_keys=True))
if __name__=="__main__":main()
