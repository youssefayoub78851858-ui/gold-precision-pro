#!/usr/bin/env python3
"""Read-only static ELF ABI inspection of the official FXCM Linux SDK.
No SDK library loading, installation, import, credentials, vendor API or trades.
Run only in isolated CI after obtaining the official public archive.
"""
import argparse
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import tarfile
import tempfile
import urllib.request

URL = ("https://raw.githubusercontent.com/fxcm/ForexConnectAPI/master/"
       "ForexConnectAPI-1.6.5-Linux-x86_64.tar.gz")
EXPECTED_SHA256 = "a4c1ec512f0ede326afd0d63eb587c578b986b382cdd1e63900ce11a8c28f696"
MAX_DOWNLOAD = 16 * 1024 * 1024
MAX_MEMBER = 64 * 1024 * 1024

def parse_readelf(source):
    needed = re.findall(r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]", source)
    machine = re.search(r"Machine:\s*([^\n]+)", source)
    cls = re.search(r"Class:\s*([^\n]+)", source)
    versions = sorted(set(re.findall(r"\bGLIBC_(\d+\.\d+(?:\.\d+)?)", source)))
    return {"machine": machine.group(1).strip() if machine else None,
            "elfClass": cls.group(1).strip() if cls else None,
            "needed": sorted(set(needed)), "glibcVersions": versions}

def glibc_tuple(s):
    return tuple(int(x) for x in s.split("."))

def selftest():
    report = parse_readelf("Class: ELF64\nMachine: Advanced Micro Devices X86-64\n"
                           "0x00000001 (NEEDED) Shared library: [libssl.so.1.0.0]\n"
                           "Version: GLIBC_2.17\nVersion: GLIBC_2.28\n")
    assert report["needed"] == ["libssl.so.1.0.0"]
    assert report["glibcVersions"] == ["2.17", "2.28"]
    assert report["elfClass"] == "ELF64"
    assert glibc_tuple("2.28") > glibc_tuple("2.17")
    print("PASS static readelf parsing, no SDK or vendor network")

def installed_sonames():
    result = subprocess.run(["ldconfig", "-p"], capture_output=True, text=True,
                            check=False, timeout=5)
    return set(re.findall(r"^\s*(\S+)\s+\(", result.stdout, flags=re.M))

def inspect():
    result = {"status":"BLOCKED_NOT_VERIFIED",
              "source":"OFFICIAL_FXCM_GITHUB_ARCHIVE",
              "sourceURL":URL,
              "baseImage":"node:24-bookworm-slim (matches coordinator base family)",
              "inspection":"STATIC_READELF_ONLY",
              "sdkLoaded":False, "sdkExecuted":False, "vendorLogin":False,
              "fxcmQuoteRequests":0, "tradeOrders":0, "payments":0,
              "providerRightsVerified":False,"readOnlyAccountVerified":False,
              "realMarketDataVerified":False,"runtimeLinkLoadVerified":False}
    try:
        request = urllib.request.Request(URL, headers={"User-Agent":"GoldPrecision-StaticELF-Audit/1"})
        with urllib.request.urlopen(request, timeout=28) as response:
            if response.status != 200:
                raise ValueError("ARCHIVE_NOT_HTTP_200")
            blob = response.read(MAX_DOWNLOAD + 1)
        if len(blob)>MAX_DOWNLOAD:
            raise ValueError("ARCHIVE_TOO_LARGE")
        digest=hashlib.sha256(blob).hexdigest()
        result["archiveSha256"]=digest
        if digest!=EXPECTED_SHA256:
            raise ValueError("ARCHIVE_SHA256_CHANGED_FAIL_CLOSED")
        with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as tar:
            members=tar.getmembers()
            if len(members)>10000:
                raise ValueError("TOO_MANY_ARCHIVE_ENTRIES")
            for m in members:
                p=pathlib.PurePosixPath(m.name)
                if p.is_absolute() or ".." in p.parts:
                    raise ValueError("UNSAFE_ARCHIVE_ENTRY")
                if m.size>MAX_MEMBER:
                    raise ValueError("ARCHIVE_MEMBER_TOO_LARGE")
            candidates=[m for m in members if m.isfile() and
                        re.search(r"\.so(?:\.[A-Za-z0-9._-]+)?$", m.name)]
            internal={pathlib.PurePosixPath(m.name).name for m in members if
                      (m.isfile() or m.issym() or m.islnk()) and
                      re.search(r"\.so(?:\.[A-Za-z0-9._-]+)?$", m.name)}
            result["linksNotExtracted"]=sum(m.issym() or m.islnk() for m in members)
            installed=installed_sonames()
            inspected=[];missing=set();glibc_requirements=set()
            with tempfile.TemporaryDirectory(prefix="fxcm-static-abi-") as tmp:
                for i,m in enumerate(candidates):
                    f=tar.extractfile(m)
                    if f is None:
                        raise ValueError("CANNOT_READ_ARCHIVE_MEMBER")
                    b=f.read(MAX_MEMBER+1)
                    if len(b)>MAX_MEMBER:
                        raise ValueError("OVERSIZE_ELF")
                    if not b.startswith(b"\x7fELF"):
                        continue
                    filename=os.path.join(tmp,str(i)+".so")
                    with open(filename,"wb") as dst:
                        dst.write(b)
                    proc=subprocess.run(
                        ["readelf","-h","-d","--version-info",filename],
                        capture_output=True,text=True,timeout=8,check=False)
                    if proc.returncode:
                        raise ValueError("READELF_FAILED_FOR_MEMBER")
                    info=parse_readelf(proc.stdout)
                    if info["elfClass"]!="ELF64":
                        raise ValueError("NON_64_BIT_ELF_IN_LINUX_X64_ARCHIVE")
                    unknown=[n for n in info["needed"] if n not in internal
                             and n not in installed and n!="linux-vdso.so.1"]
                    missing.update(unknown)
                    glibc_requirements.update(info["glibcVersions"])
                    inspected.append({"archivePath":m.name,"elfClass":info["elfClass"],
                                      "machine":info["machine"],
                                      "needed":info["needed"],"missingOnBase":unknown})
        libc=subprocess.run(["getconf","GNU_LIBC_VERSION"],
                            capture_output=True,text=True,check=False,timeout=5).stdout.strip()
        max_req=max(glibc_requirements,key=glibc_tuple) if glibc_requirements else None
        libc_match=re.search(r"glibc (\d+(?:\.\d+)+)",libc)
        libc_version=libc_match.group(1) if libc_match else None
        glibc_ok=libc_version is not None and (not max_req or
                 glibc_tuple(libc_version)>=glibc_tuple(max_req))
        result.update(status=("ABI_STATIC_REVIEW_BLOCKED" if missing or not glibc_ok
                              else "STATIC_DEPS_PLAUSIBLE_NOT_EXECUTED"),
                      binaryCount=len(inspected), archiveSharedObjectCount=len(candidates),
                      neededSonamesMissingOnBase=sorted(missing),
                      baseGlibc=libc_version,maxRequiredGlibc=max_req,
                      baseGlibcSufficient=glibc_ok,
                      libraries=inspected, allDependenciesVerified=False)
    except Exception as exc:
        result.update(status="BLOCKED_NOT_VERIFIED",
                      errorCode=type(exc).__name__,reason=str(exc)[:400])
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output")
    args=p.parse_args()
    if args.self_test:
        selftest();return
    if not args.output:
        p.error("--output is required")
    result=inspect()
    target=pathlib.Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n")
    brief={k:v for k,v in result.items() if k not in ("libraries",)}
    print(json.dumps(brief))
if __name__=="__main__":
    main()
