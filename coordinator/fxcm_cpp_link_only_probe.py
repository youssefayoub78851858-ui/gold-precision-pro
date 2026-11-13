#!/usr/bin/env python3
"""Offline C++ SDK symbol link check, deliberately NO compiled binary execution.

Uses signed-off public archive SHA, writes only libraries and selected headers
into a temporary directory in CI. No FXCM account or network to market servers.
"""
import argparse
import hashlib
import io
import json
import pathlib
import re
import subprocess
import tarfile
import tempfile
import urllib.request

URL=("https://raw.githubusercontent.com/fxcm/ForexConnectAPI/master/"
     "ForexConnectAPI-1.6.5-Linux-x86_64.tar.gz")
SHA="a4c1ec512f0ede326afd0d63eb587c578b986b382cdd1e63900ce11a8c28f696"
MAX_ARCHIVE=16*1024*1024
MAX_MEMBER=24*1024*1024

def test_self():
    assert pathlib.PurePosixPath("good/libA.so.1").name=="libA.so.1"
    assert ".." in pathlib.PurePosixPath("../escape").parts
    assert re.fullmatch(r"lib[A-Za-z0-9_+.-]+\.so(?:\.[0-9.]+)?","libForexConnect.so.1.6.5")
    print("PASS: safe paths and library name validation")

def audit():
    output={"status":"BLOCKED_NOT_VERIFIED","provider":"FXCM",
        "kind":"CPP_LINK_ONLY_NO_EXECUTION","sdkLoaded":False,"sdkExecuted":False,
        "vendorLogin":False,"fxcmQuoteRequests":0,"ordersSent":0,"payments":0,
        "licenseVerified":False,"readOnlyCredentialsVerified":False,
        "liveDataVerified":False,"paperEnabled":False,"cloudRuntimeVerified":False}
    try:
        request=urllib.request.Request(URL,headers={"User-Agent":"GoldPrecision-CppLinkOnly/1"})
        with urllib.request.urlopen(request,timeout=25) as response:
            if response.status!=200:raise ValueError("HTTP_NOT_200")
            data=response.read(MAX_ARCHIVE+1)
        if len(data)>MAX_ARCHIVE:raise ValueError("ARCHIVE_TOO_LARGE")
        digest=hashlib.sha256(data).hexdigest();output["sha256"]=digest
        if digest!=SHA:raise ValueError("UNPINNED_ARCHIVE_SHA256")
        with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as archive:
            entries=archive.getmembers()
            if len(entries)>10000:raise ValueError("TOO_MANY_ARCHIVE_ITEMS")
            for m in entries:
                p=pathlib.PurePosixPath(m.name)
                if p.is_absolute() or ".." in p.parts or m.size>MAX_MEMBER:
                    raise ValueError("UNSAFE_ARCHIVE_ITEM")
            with tempfile.TemporaryDirectory(prefix="fxcm-link-only-") as folder:
                root=pathlib.Path(folder)
                includes=[]
                libdir=root/"lib";libdir.mkdir()
                link_count=0
                file_count=0
                prefix=pathlib.PurePosixPath("ForexConnectAPI-1.6.5-Linux-x86_64")
                for member in entries:
                    p=pathlib.PurePosixPath(member.name)
                    if not member.isfile() or not p.suffix.lower() in (".h",".hpp",".hxx"):
                        continue
                    if prefix not in p.parents:continue
                    dest=root.joinpath(*p.parts)
                    dest.parent.mkdir(parents=True,exist_ok=True)
                    reader=archive.extractfile(member)
                    if reader is None:raise ValueError("MISSING_HEADER")
                    dest.write_bytes(reader.read(MAX_MEMBER+1))
                    includes.append(str(dest.parent))
                if len(includes)<20:raise ValueError("INSUFFICIENT_HEADER_FILES")
                top=prefix/"lib"
                libs=[m for m in entries if pathlib.PurePosixPath(m.name).parent==top and
                      re.fullmatch(r"lib[A-Za-z0-9_+.-]+\.so(?:\.[0-9.]+)?",
                                   pathlib.PurePosixPath(m.name).name)]
                for m in libs:
                    p=pathlib.PurePosixPath(m.name)
                    dest=libdir/p.name
                    if m.isfile():
                        reader=archive.extractfile(m)
                        if reader is None:raise ValueError("MISSING_LIBRARY_BYTES")
                        data=reader.read(MAX_MEMBER+1)
                        if len(data)>MAX_MEMBER or not data.startswith(b"\x7fELF"):
                            raise ValueError("LIBRARY_NOT_VALID_ELF")
                        dest.write_bytes(data);file_count+=1
                    elif m.issym():
                        target=pathlib.PurePosixPath(m.linkname)
                        if target.is_absolute() or ".." in target.parts or target.name!=m.linkname:
                            raise ValueError("UNSAFE_LIBRARY_SYMLINK")
                        if not re.fullmatch(r"lib[A-Za-z0-9_+.-]+\.so(?:\.[0-9.]+)?",target.name):
                            raise ValueError("BAD_LIBRARY_SYMLINK_TARGET")
                        dest.symlink_to(target.name);link_count+=1
                if not (libdir/"libForexConnect.so.1.6.5").is_file():
                    raise ValueError("PRIMARY_LIBRARY_MISSING")
                # This function is compiled and linked but is NEVER run.
                src=root/"link_only.cpp"
                src.write_text('#include <string>\n#include "ForexConnect.h"\n'
                               'IO2GSession* fxcm_sdk_factory_link_only() {\n'
                               '    return CO2GTransport::createSession();\n'
                               '}\n',encoding="utf-8")
                incflags=[]
                for directory in sorted(set(includes)):
                    incflags.extend(["-I",directory])
                obj=root/"link_only.o"
                compile_cmd=["g++","-std=c++17","-fPIC","-c",str(src),"-o",str(obj),
                             "-Wno-deprecated-declarations"]+incflags
                c=subprocess.run(compile_cmd,capture_output=True,text=True,timeout=60)
                output.update(headerFiles=len(includes),elfFileCount=file_count,
                              symlinksRecreated=link_count,cxxCompileExitCode=c.returncode,
                              cxxCompileDiagnostic=c.stderr[-1600:])
                if c.returncode:
                    output["status"]="CPP_SOURCE_COMPILE_FAILED"
                else:
                    product=root/"libfxcm_link_only_check.so"
                    cmd=["g++","-shared","-Wl,--no-undefined","-Wl,--no-as-needed",
                         str(obj),"-o",str(product),"-L",str(libdir),
                         "-Wl,-rpath-link,"+str(libdir),
                         "-l:libForexConnect.so.1.6.5","-Wl,--as-needed"]
                    link=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
                    output.update(cxxLinkExitCode=link.returncode,
                                  cxxLinkDiagnostic=link.stderr[-2000:])
                    if link.returncode:
                        output["status"]="CPP_LINK_FAILED"
                    else:
                        check=subprocess.run(["readelf","-d",str(product)],
                            capture_output=True,text=True,timeout=10,check=False)
                        output["linkedElfCreated"]=product.exists()
                        output["linkedElfNeeded"] = re.findall(
                            r"\(NEEDED\)\s+Shared library: \[([^\]]+)\]",check.stdout)
                        output["status"]="CPP_SYMBOL_LINK_PASSED_NOT_EXECUTED"
    except Exception as ex:
        output.update(status="BLOCKED_NOT_VERIFIED",
                      exceptionType=type(ex).__name__,
                      error=str(ex)[:500])
    return output

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--output")
    args=p.parse_args()
    if args.self_test:
        test_self()
        return
    if not args.output:p.error("--output required")
    report=audit()
    target=pathlib.Path(args.output)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report))
if __name__=="__main__":
    main()
