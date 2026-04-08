"""Comprehensive bug search across the codebase."""

import re
import os

BASE = r"C:\Users\JO\OneDrive\Desktop\jo"
OUROBOROS = os.path.join(BASE, "ouroboros")
SUPERVISOR = os.path.join(BASE, "supervisor")

# 1. Syntax check
print("=== 1. SYNTAX CHECK ===")
syntax_errors = []
for root_dir in [OUROBOROS, SUPERVISOR]:
    for root, dirs, files in os.walk(root_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                try:
                    with open(path, "r", encoding="utf-8") as fh:
                        compile(fh.read(), path, "exec")
                except SyntaxError as e:
                    rel = os.path.relpath(path, BASE)
                    syntax_errors.append(f"{rel}:{e.lineno}: {e.msg}")

if syntax_errors:
    for e in syntax_errors:
        print(f"  FAIL: {e}")
else:
    print("  ALL OK")

# 2. Missing module imports
print("\n=== 2. MISSING MODULE IMPORTS ===")
valid_modules = set()
for f in os.listdir(OUROBOROS):
    if f.endswith(".py"):
        valid_modules.add(f[:-3])
    elif os.path.isdir(os.path.join(OUROBOROS, f)) and os.path.exists(os.path.join(OUROBOROS, f, "__init__.py")):
        valid_modules.add(f)

tools_dir = os.path.join(OUROBOROS, "tools")
for f in os.listdir(tools_dir):
    if f.endswith(".py"):
        valid_modules.add("tools." + f[:-3])

skills_dir = os.path.join(OUROBOROS, "skills")
for f in os.listdir(skills_dir):
    if f.endswith(".py"):
        valid_modules.add("skills." + f[:-3])

supervisor_modules = set()
for f in os.listdir(SUPERVISOR):
    if f.endswith(".py"):
        supervisor_modules.add(f[:-3])

missing_found = False
for root_dir in [OUROBOROS, SUPERVISOR]:
    for root, dirs, files in os.walk(root_dir):
        for fn in files:
            if fn.endswith(".py"):
                fp = os.path.join(root, fn)
                with open(fp, "r", encoding="utf-8") as fh:
                    for line_no, line in enumerate(fh, 1):
                        m = re.match(r"\s*from\s+(ouroboros\.\S+)\s+import", line)
                        if m:
                            mod = m.group(1)
                            parts = mod.split(".")
                            if len(parts) >= 2:
                                immediate = ".".join(parts[1:])
                                if immediate not in valid_modules and parts[1] not in valid_modules:
                                    rel = os.path.relpath(fp, BASE)
                                    print(f"  {rel}:{line_no}: {mod}")
                                    missing_found = True
                        m2 = re.match(r"\s*from\s+(supervisor\.\S+)\s+import", line)
                        if m2:
                            mod = m2.group(1)
                            parts = mod.split(".")
                            if len(parts) >= 2:
                                immediate = ".".join(parts[1:])
                                if immediate not in supervisor_modules:
                                    rel = os.path.relpath(fp, BASE)
                                    print(f"  {rel}:{line_no}: {mod}")
                                    missing_found = True
if not missing_found:
    print("  NONE FOUND")

# 3. Import of non-existent names
print("\n=== 3. MISSING IMPORTED NAMES ===")
module_defs = {}
for root, dirs, files in os.walk(OUROBOROS):
    for fn in files:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            defs = set()
            with open(fp, "r", encoding="utf-8") as fh:
                for line in fh:
                    m = re.match(r"^(?:def|class)\s+(\w+)", line)
                    if m:
                        defs.add(m.group(1))
                    m2 = re.match(r"^([A-Z][A-Z0-9_]+)\s*=", line)
                    if m2:
                        defs.add(m2.group(1))
            rel = os.path.relpath(fp, OUROBOROS).replace(os.sep, ".").replace(".py", "")
            module_defs[rel] = defs

name_issues = []
for root, dirs, files in os.walk(OUROBOROS):
    for fn in files:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8") as fh:
                content = fh.read()
                lines = content.split("\n")

            i = 0
            while i < len(lines):
                line = lines[i]
                m = re.match(r"\s*from\s+(ouroboros\.\S+)\s+import\s+(.+)", line)
                if m:
                    mod = m.group(1)
                    names_str = m.group(2).strip()
                    while names_str.count("(") > names_str.count(")") and i + 1 < len(lines):
                        i += 1
                        names_str += " " + lines[i].strip()
                    names_str = names_str.replace("(", "").replace(")", "")
                    if "#" in names_str:
                        names_str = names_str[: names_str.index("#")].strip()
                    names = [n.strip() for n in names_str.split(",") if n.strip()]

                    mod_parts = mod.split(".")
                    if len(mod_parts) >= 2:
                        mod_key = ".".join(mod_parts[1:])
                        if mod_key in module_defs:
                            defs = module_defs[mod_key]
                            for name in names:
                                if name.startswith("_") and not name.startswith("__"):
                                    continue
                                actual_name = name.split(" as ")[0].strip() if " as " in name else name
                                if actual_name and actual_name not in defs:
                                    caller_rel = os.path.relpath(fp, OUROBOROS)
                                    name_issues.append((caller_rel, i + 1, mod, actual_name))
                i += 1

if name_issues:
    for caller, line_no, mod, name in sorted(name_issues):
        print(f"  {caller}:{line_no}: from {mod} import {name}")
else:
    print("  NONE FOUND")

# 4. Dead functions (public, never called)
print("\n=== 4. POTENTIALLY DEAD FUNCTIONS ===")
all_funcs = {}
for root, dirs, files in os.walk(OUROBOROS):
    for fn in files:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8") as fh:
                for line_no, line in enumerate(fh, 1):
                    m = re.match(r"^def\s+(\w+)\(", line)
                    if m:
                        func_name = m.group(1)
                        if func_name.startswith("_"):
                            continue
                        rel = os.path.relpath(fp, OUROBOROS)
                        if func_name not in all_funcs:
                            all_funcs[func_name] = []
                        all_funcs[func_name].append((rel, line_no))

all_text = {}
for root, dirs, files in os.walk(OUROBOROS):
    for fn in files:
        if fn.endswith(".py"):
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8") as fh:
                all_text[os.path.relpath(fp, OUROBOROS)] = fh.read()

dead = []
for func_name, defs in sorted(all_funcs.items()):
    if len(defs) > 1:
        continue
    rel, line_no = defs[0]
    total_count = 0
    for file_path, content in all_text.items():
        total_count += len(re.findall(r"\b" + re.escape(func_name) + r"\b", content))
    if total_count <= 1:
        dead.append((rel, line_no, func_name))

if dead:
    for rel, line_no, func_name in sorted(dead):
        print(f"  {rel}:{line_no}: def {func_name}")
else:
    print("  NONE FOUND")

print("\n=== DONE ===")
