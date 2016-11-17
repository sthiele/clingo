#!/usr/bin/python

import re
import os
import os.path
import sys
import subprocess as sp
import difflib as dl
import argparse

parser = argparse.ArgumentParser(description="""
Can be used to run and normalize tests.
Additional options can be passed to clingo by adding them at the end of the command line preceded by '--'.
""")
parser.add_argument('-c', '--clingo', default=None, help="path to clingo executable")

subparsers = parser.add_subparsers(dest="action", help="sub-command --help")
subparsers.required = True
parser_run = subparsers.add_parser('run', help='run all tests')
parser_normalize = subparsers.add_parser('normalize', help='normalize the output of clingo')
parser_normalize.add_argument("file")

argv = sys.argv[1:]
extra_argv = []
if "--" in argv:
    extra_argv = argv[argv.index("--")+1:]
    argv       = argv[:argv.index("--")]

parse_ret = parser.parse_args(argv)

if parse_ret.action is None:
    print (parser.usage)
    exit(0)

clingo = parse_ret.clingo

def find_clingo():
    clingos = [
        "build/debug/bin/clingo",
        "build/release/bin/clingo",
        "build/bin/clingo",
        "build/cmake/bin/clingo",
        "build/bin/Debug/clingo.exe",
        "build/bin/Release/clingo.exe",
        ]
    for x in clingos:
        x = os.path.normpath("{}/../../../{}".format(wd, x))
        if os.path.exists(x):
            return x
    return None

wd = os.path.normpath(os.path.dirname(__file__))
if clingo is None:
    clingo = find_clingo()

if clingo is None:
    print ("no usable clingo version found")
    exit(1)

def reorder(out):
    return out
    res = []
    current = []
    for line in out.splitlines():
        if line.startswith("Step: ") or line.startswith("SAT") or line.startswith("UNSAT") or line.startswith("UNKNOWN") or line.startswith("OPTIMUM FOUND"):
            res.extend(sorted(current))
            res.append(line)
            current = []
        else:
            current.append(" ".join(sorted(line.split(" "))))
    return "\n".join(res)

def normalize(out):
    state=0
    current=[]
    step=0
    result="ERROR"
    norm=[]
    for line in out.split('\n'):
        if state == 1:
            if step > 0:
                norm.append("Step: {}".format(step))
                models = []
                for model in current:
                    models.append(" ".join(sorted(model)))
                for model in sorted(models):
                    norm.append(model)
            step += 1
            state = 0
            current = []
        if state == 2:
            current.append(line.strip().split(" "))
            state=0
        elif line.startswith("Solving..."):
            state = 1
        elif line.startswith("Answer: "):
            state = 2
        elif line.startswith("SATISFIABLE"):
            result="SAT"
            state=1
        elif line.startswith("UNSATISFIABLE"):
            result="UNSAT"
            state=1
        elif line.startswith("UNKNOWN"):
            result="UNKNOWN"
            state=1
        elif line.startswith("OPTIMUM FOUND"):
            result="OPTIMUM FOUND"
            state=1
    norm.append(result)
    norm.append("")
    return "\n".join(norm)

if parse_ret.action == "normalize":
    args = [clingo, "0", parse_ret.file, "-Wnone"]
    b = os.path.splitext(parse_ret.file)[0]
    if os.path.exists(b + ".cmd"):
        for x in open(b + ".cmd"):
            args.extend(x.strip().split())
    args.extend(extra_argv)
    out, err = sp.Popen(args, stderr=sp.PIPE, stdout=sp.PIPE, universal_newlines=True).communicate()
    sys.stdout.write(normalize(out))
    exit(0)
if parse_ret.action == "run":
    total  = 0
    failed = 0

    out, err = sp.Popen([clingo, "--version"], stderr=sp.PIPE, stdout=sp.PIPE, universal_newlines=True).communicate()
    with_python  = out.find("with Python") > 0
    with_lua     = out.find("with Lua") > 0
    with_threads = out.find("WITH_THREADS=1") > 0
    for root, dirs, files in os.walk(wd):
        for f in sorted(files):
            if f.endswith(".lp"):
                b = os.path.join(root, f[:-3])
                inst = open(b + ".lp").read()
                if (not with_python and re.search(r"#script[ ]*\(python\)", inst)) or \
                   (not with_lua and (re.search(r"#script[ ]*\(lua\)", inst) or re.search(r"#include[ ]*<incmode>[ ]*.", inst))) or \
                   (not with_threads and re.search("solve_async", inst)):
                    continue

                total+= 1
                sys.stdout.flush()

                args = [clingo, "0", b + ".lp", "-Wnone"]
                if os.path.exists(b + ".cmd"):
                    for x in open(b + ".cmd"):
                        args.extend(x.strip().split())
                args.extend(extra_argv)
                out, err = sp.Popen(args, stderr=sp.PIPE, stdout=sp.PIPE, universal_newlines=True).communicate()
                norm = normalize(out)
                sol  = reorder(open(b + ".sol").read())
                if norm != sol:
                    failed+= 1
                    print
                    print ("-" * 79)
                    print (" ".join(args))
                    print ("." * 79)
                    print
                    print ("FAILED:")
                    d = dl.Differ()
                    for line in list(d.compare(sol.splitlines(), norm.splitlines())):
                        if not line.startswith(" "):
                            print (line)
                    print
                sys.stdout.flush()

    print ("=" * 79)
    if failed > 0:
        print ("Some tests failed ({} of {} test cases)".format(failed, total))
        print
        exit(1)
    else:
        print ("All tests passed ({} test cases)".format(total))
        print
        exit(0)

