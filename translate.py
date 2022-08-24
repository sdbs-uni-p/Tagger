# Collection of functions translating our internal representation
# to JSON Schema

import json
import re


def get_ctypes_str(s1, c1):
    s_ctypes = None
    if c1.startswith("_generic"):
        if s1.type == "object":
            s_ctypes = s1.children
        elif s1.type == "array":
            s_ctypes = s1.generic_ctypes
    elif c1.startswith("_spec1_"):
        s_ctypes = s1.specific_ctypes[0]
    elif c1.startswith("_spec2_"):
        s_ctypes = s1.specific_ctypes[1]
    elif c1.startswith("_spec3_"):
        s_ctypes = s1.specific_ctypes[2]

    if s1.type == "array":
        if c1.startswith("_spec0_"):
            s_ctypes = {"type": s1.ctypes[0]}
        if c1.startswith("_spec1_"):
            s_ctypes = {"type": s1.ctypes[0]}
        elif c1.startswith("_spec"):
            reg = re.search(r'_(.+)(\d+)_', c1)
            var = reg.group(1)
            level = int(reg.group(2))

            for c in s1.children:
                if len(c.children) > 0:
                    s_ctypes = {"type": "array", "items": get_ctypes_str(c, str("_" + var + str(level-1) + "_"))}
                    break
        elif s_ctypes is None:
            s_ctypes = {"type": s1.ctypes[0]}
        else:
            s_ctypes = {"type": str(list(s_ctypes)[0])}
    elif s1.type == "object":
        if c1.startswith("_generic2_"):
            if s1.type == "string":
                s_ctypes = {"type": s1.type}
            else:
                s_ctypes = {"type": s1.type}
        if s_ctypes is not None:
            if type(s_ctypes) is list:
                sct = {}
                for sc in s_ctypes:
                    sct[str(list(sc)[0])] = {"type": str(list(sc)[1])}

                s_ctypes = {"properties": sct}
        else:
            s_ctypes = ""
    else:
        if c1.startswith("_generic1_"):
            if s1.type == "string":
                s_ctypes = {"type": s1.type}
            else:
                s_ctypes = {"type": s1.type}
        elif c1.startswith("_generic2_"):
            if s1.type == "string":
                s_ctypes = {"type": s1.type}
            else:
                s_ctypes = {"type": s1.type}
        else:
            s_ctypes = {"const": list(s1.name.values())[0]}

    return s_ctypes


def get_ite_str(s, c, is_if = False):
    ite_str_glob = {"properties": {}}
    ite_str = ite_str_glob["properties"]
    i = 0
    required = []
    not_req = []
    for s1 in s:
        if type(s1) is str:
            nonestr = s1.replace(" is missing", "")
            if not nonestr.startswith("_generic") or True:
                nonestr = nonestr.replace("_generic1_", "", 1)
                nonestr = nonestr.replace("_generic2_", "", 1)
                if nonestr not in not_req:
                    not_req.append(nonestr)
            i += 1
            continue
        s_ctypes = get_ctypes_str(s1, c[i])
        if s1.type == "array":
            type_str = str(s1.name)
            js = {type_str: {"type": "array", "items": s_ctypes}}
            ite_str.update(js)
        elif s1.type == "object":
            type_str = str(s1.name)
            if c[i].startswith("_generic2_"):
                if False:
                    if type_str not in ite_str:
                        ite_str[type_str] = {"type": []}
                    tp = s_ctypes["type"]
                    if tp not in ite_str[type_str]["type"]:
                        ite_str[type_str]["type"].append(tp)
            elif c[i].startswith("_generic"):
                js = {type_str: {"type": "object"}}
                ite_str.update(js)
            else:
                js = {type_str: {"type": "object"}}
                js[type_str].update(s_ctypes)
                ite_str.update(js)
        else:
            type_str = list(s1.name.keys())[0]
            if c[i].startswith("_generic2_"):
                if False:
                    if type_str not in ite_str:
                        ite_str[type_str] = {"type": []}
                    tp = s_ctypes["type"]
                    if tp not in ite_str[type_str]["type"]:
                        ite_str[type_str]["type"].append(tp)
            else:
                js = {type_str: s_ctypes}
                ite_str.update(js)
        i += 1
        if type_str not in required and not type_str.startswith("_generic"):
            required.append(type_str)

    if len(required) > 0 and is_if:
        ite_str_glob["required"] = required
    if len(not_req) > 0:
        if len(ite_str_glob["properties"]) == 0:
            ite_str_glob = {"not": {"required": not_req}}
        else:
            ite_str_glob["not"] = {"required": not_req}

    return ite_str_glob


def print_ite(s1, s2, c1, c2, has_else=False):
    ite_str = {"if": get_ite_str(s1, c1, is_if=True), "then": get_ite_str(s2, c2)}

    return ite_str
