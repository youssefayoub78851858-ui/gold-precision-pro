#!/usr/bin/env python3
"""FXCM official SDK C++ header and Java JAR *metadata* CI audit.
No SDK import, binary execution, credentials, subscriptions, or FXCM sessions.
"""
import argparse
import hashlib
import io
import json
import pathlib
import re
import struct
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

SOURCE = ("https://raw.githubusercontent.com/fxcm/ForexConnectAPI/master/"
          "ForexConnectAPI-1.6.5-Linux-x86_64.tar.gz")
EXPECTED_SHA256 = "a4c1ec512f0ede326afd0d63eb587c578b986b382cdd1e63900ce11a8c28f696"
MAX_ARCHIVE = 16 * 1024 * 1024
MAX_MEMBER = 10 * 1024 * 1024

def class_major(payload):
    if len(payload) < 8 or payload[:4] != bytes.fromhex("cafebabe"):
        raise ValueError("MALFORMED_JAVA_CLASS")
    return struct.unpack(">H", payload[6:8])[0]

def selftest():
    assert class_major(bytes.fromhex("cafebabe00000034")) == 52
    try:
        class_major(b"bad")
    except ValueError:
        pass
    else:
        raise AssertionError("bad class accepted")
    assert pathlib.PurePosixPath("../file.h").parts[0] == ".."
    print("PASS: Java class version parser and path validation (offline)")

def examine():
    result={
        "status":"BLOCKED_NOT_VERIFIED",
        "mode":"OFFICIAL_ARCHIVE_HEADER_AND_JAR_METADATA_ONLY",
        "source":SOURCE,
        "sdkCodeExecuted":False,
        "vendorConnected":False,
        "marketRequests":0,
        "orders":0,
        "payments":0,
        "eulaAndCloudRightsVerified":False,
        "fxcmReadOnlyAccountVerified":False,
        "readyForPaper":False,
        "tradeEnabled":False
    }
    try:
        request=urllib.request.Request(SOURCE,headers={"User-Agent":"GoldPrecision-SDK-Headers-Audit/1"})
        with urllib.request.urlopen(request,timeout=30) as stream:
            if stream.status!=200:
                raise ValueError("NON_200_ARCHIVE_RESPONSE")
            blob=stream.read(MAX_ARCHIVE+1)
        if len(blob)>MAX_ARCHIVE:
            raise ValueError("ARCHIVE_EXCEEDS_CAP")
        digest=hashlib.sha256(blob).hexdigest()
        result["sha256"]=digest
        if digest!=EXPECTED_SHA256:
            raise ValueError("ARCHIVE_HASH_CHANGED_FAIL_CLOSED")
        with tarfile.open(fileobj=io.BytesIO(blob),mode="r:gz") as tar:
            members=tar.getmembers()
            if len(members)>10000:
                raise ValueError("ARCHIVE_HAS_TOO_MANY_MEMBERS")
            for m in members:
                p=pathlib.PurePosixPath(m.name)
                if p.is_absolute() or ".." in p.parts or m.size>MAX_MEMBER:
                    raise ValueError("UNSAFE_ARCHIVE_MEMBER")
            headers=[m for m in members if m.isfile() and
                     m.name.lower().endswith((".h",".hpp",".hxx",".inc"))]
            jars=[m for m in members if m.isfile() and m.name.lower().endswith(".jar")]
            result["headerCount"]=len(headers)
            result["javaJarCount"]=len(jars)
            result["headerExamples"]=[m.name for m in headers[:12]]
            result["javaJarNames"]=[m.name for m in jars]
            inspected_jars=[]
            for m in jars:
                file=tar.extractfile(m)
                if file is None:
                    raise ValueError("JAR_READ_FAILED")
                raw=file.read(MAX_MEMBER+1)
                if len(raw)>MAX_MEMBER:
                    raise ValueError("JAR_MEMBER_TOO_LARGE")
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    class_names=[n for n in z.namelist() if n.endswith(".class")]
                    versions=set()
                    for filename in class_names[:300]:
                        with z.open(filename) as item:
                            versions.add(class_major(item.read(8)))
                    inspected_jars.append({
                        "path":m.name,"classCount":len(class_names),
                        "sampledClassMajorVersions":sorted(versions),
                        "firstClassNames":class_names[:5]
                    })
            result["jars"]=inspected_jars
            with tempfile.TemporaryDirectory(prefix="fxcm-cpp-header-check-") as tmp:
                root=pathlib.Path(tmp)
                for member in headers:
                    p=root.joinpath(*pathlib.PurePosixPath(member.name).parts)
                    p.parent.mkdir(parents=True,exist_ok=True)
                    stream=tar.extractfile(member)
                    if stream is None:
                        raise ValueError("HEADER_READ_FAILED")
                    with p.open("wb") as output:
                        output.write(stream.read(MAX_MEMBER+1))
                candidate_names={"ForexConnect.h","fxcore2.h","O2GSession.h"}
                candidates=[m for m in headers if pathlib.PurePosixPath(m.name).name in candidate_names]
                result["cxxCandidateHeaders"]=[m.name for m in candidates]
                if not candidates:
                    result["status"]="CPP_ENTRY_HEADER_NOT_IDENTIFIED"
                else:
                    chosen=next((m for m in candidates if m.name.endswith("/ForexConnect.h")),candidates[0])
                    result["compiledHeader"]=chosen.name
                    snippet=root/"fxcm_header_only.cpp"
                    snippet.write_text('#include "'+chosen.name+'"\nint sdk_headers_only(){return 0;}\n',
                                       encoding="utf-8")
                    paths=sorted({str(root/pathlib.PurePosixPath(m.name).parent) for m in headers})
                    compile_cmd=["g++","-std=c++17","-fsyntax-only",
                                 "-Wno-deprecated-declarations","-I",str(root)]
                    for p in paths:
                        compile_cmd.extend(["-I",p])
                    compile_cmd.append(str(snippet))
                    proc=subprocess.run(compile_cmd,capture_output=True,text=True,
                                        timeout=45,check=False)
                    result["compilerExitCode"]=proc.returncode
                    result["compilerDiagnostic"]=(proc.stderr or proc.stdout)[-1400:]
                    result["status"]=("CXX_HEADER_COMPILE_PASSED_NO_SDK_EXECUTION"
                                      if proc.returncode==0
                                      else "CXX_HEADER_COMPILE_BLOCKED")
    except Exception as ex:
        result.update(status="BLOCKED_NOT_VERIFIED",
                      errorType=type(ex).__name__,reason=str(ex)[:500])
    return result

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--selftest",action="store_true")
    ap.add_argument("--output")
    a=ap.parse_args()
    if a.selftest:
        selftest()
        return
    if not a.output:
        ap.error("output required")
    report=examine()
    output=pathlib.Path(a.output)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    brief={k:v for k,v in report.items() if k not in ("jars","headerExamples")}
    print(json.dumps(brief))
if __name__=="__main__":
    main()
