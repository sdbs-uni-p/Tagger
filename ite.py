# Main logic of the algorithm

import json
import os
import sys
import time
from anytree import findall
import fd
import translate
import utils
import validate
from extract import extract_from_files
from pathlib import Path
from tree import *

ite_dict = {}
config = dict()
ite_cand_list = {}
versions = []
schema_out = 'schema.json'
ite_schema_out = 'schema-ite.json'
config = ""


# Initialises the search for if-then-else relations at a certain depth, starting from a node (usually the root)
def find_dependencies(node, depth=0):
    nodes = get_siblings(node, depth)

    # separate elements by pathstr
    nodes_dict = {}
    for n in nodes:
        path = n[0].pathstr
        if path not in nodes_dict:
            nodes_dict[path] = [n]
        else:
            nodes_dict[path].append(n)

    for n in nodes_dict.values():
        find_ite(n, depth)


def find_ite(nodes, depth):
    if depth not in ite_cand_list:
        ite_cand_list[depth] = []
    max_combs = config["max_combs"]
    min_sample = config["min_sample"]

    # Do not compute ite between array elements
    if True or not config["compare_array_elems"]:
        tmp_nodes = nodes.copy()
        nodes = []
        for i in range(0, len(tmp_nodes)):
            nodes.append([])
            for n in tmp_nodes[i]:
                if n.parent.type != "array":
                    nodes[i].append(n)

    versions_list = []
    for k in range(config["max_gen"], 0, -1):
        versions.append(f"_generic{k}_")
        versions_list.append(["gen", k])
    versions.append("")
    versions_list.append(["base", 1])
    for k in range(1, config["max_spec"] + 1):
        versions.append(f"_spec{k}_")
        versions_list.append(["spec", k])

    header, clmns, ref_rec = fd.get_compressed_records_from_list(nodes, versions_list)

    if len(clmns) == 0:
        return

    plis = {}
    for i in range(0, len(clmns)):
        pli = fd.get_pli([clmns[i]])

        if config["individual_noise_threshold"] > 0 and not config["disable_heuristics"]:
            total_len = sum([len(p) for p in pli])
            individual_threshold = int(config["individual_noise_threshold"]*total_len)
            plis_below_threshold = []
            for p in pli:
                if len(p) <= individual_threshold:
                    plis_below_threshold.append(p)

            if config["total_noise_threshold"] <= 0:
                pli = [p for p in pli if p not in plis_below_threshold]
            elif sum([len(p) for p in plis_below_threshold]) <= int(config["total_noise_threshold"]*total_len):
                pli = [p for p in pli if p not in plis_below_threshold]

        # Exclude constant columns as these should not be modeled with if-then-else
        # Also exclude all plis where every column is unique
        if (config["ignore_constant_attributes"] and not config["disable_heuristics"] and len(pli) == 1): # or all(p == [-1] for p in pli):
            continue
        elif config["ignore_constant_attributes"] and len(pli) == 2 and not config["disable_heuristics"]:
            if ref_rec[header[i]][pli[0][0]] is None or ref_rec[header[i]][pli[1][0]] is None:
                continue
            else:
                plis[header[i]] = pli
        else:
            plis[header[i]] = pli

    if config["filter_plis"] and not config["disable_heuristics"]:
        plis = utils.filter_plis(plis, versions)
		
    combs = utils.get_combinations(plis, max_combs)
    combs.sort(key=len)

    # list that contains ites that cover all rows
    combs_list = []
    candidate_list = []
    combs = utils.filter_combs(combs, versions)
    if config["filter_plis"] and not config["disable_heuristics"]:
        combs = utils.filter_combs_pli(combs, plis)
    for c in combs:
        ite = calc_ite(c, plis, ref_rec, combs_list, candidate_list, min_sample)
        if ite is not None:
            ite_cand_list[depth].append(ite)

    # remove more specific version if generic version covers more rows

    if len(ite_cand_list[depth]) > 0 and not config["keep_specific_versions"]:
        ite_cand_list[depth] = utils.pre_filter_cand_list(ite_cand_list[depth], versions)


def calc_ite(combs, plis, ref_rec, combs_list, cand_list, min_sample):
    stripped_combs = []
    for case in versions:
        stripped_combs.append([set([x.replace(case, '', 1) for x in combs[0]]),
                               set([x.replace(case, '', 1) for x in combs[1]])])

    if utils.filter_calc_ite(config, combs, stripped_combs, ref_rec, combs_list, plis):
        return

    plis1 = []
    plis2 = []

    # Remove unique values
    # Could also use min_sample filter here
    for c in combs[0]:
        plis1.append(list(filter(lambda elem: elem != [-1], plis[c])))
    for c in combs[1]:
        plis2.append(list(filter(lambda elem: elem != [-1], plis[c])))

    plis1 = utils.intersect_plis(plis1)
    plis2 = utils.intersect_plis(plis2)

    subsets = utils.subset(plis1, plis2)

    # Calculate value for relative min_sample
    # Enforce that min_sample = max(2, min_sample)
    if 1 > min_sample > 0:
        attrs = (*combs[0], *combs[1])
        lengths = []
        for a in attrs:
            lengths.append(sum(len(x) for x in plis[a]))
        min_sample = round(min_sample * max(lengths))

    # only consider if-then-else relations if we have the minimum amount of samples
    # if min_sample <= 0 allow any size of samples
    if min_sample > 0:
        subsets = list(filter(lambda elem: len(elem) >= min_sample, subsets))
    if len(subsets) == 0:
        return

    # Do not add generalisation if base version covers the same rows
    for cand in cand_list:
        attrs = cand[0]
        for sc in stripped_combs:
            if set(attrs[0]) == set(sc[0]) and set(attrs[1]) == set(sc[1]) and cand[1] == subsets:
                return

    # Do not add attribute combinations on left side if smaller version covers the same rows
    for cand in cand_list:
        attrs = cand[0]
        for sc in stripped_combs:
            if set(attrs[0]).issubset(set(sc[0])) and set(attrs[1]).issuperset(set(sc[1])) and cand[1] == subsets:
                return

    cand_list.append([combs, subsets])

    maxl = max(sum([len(x) for x in plis1]), sum([len(x) for x in plis2]))
    if sum([len(x) for x in subsets]) == maxl:
        combs_list.append(combs)

    return [subsets, combs, ref_rec]


def prep_print(subsets, combs, ref_rec):
    # Results from the intersection show dependencies and hint at if-then-else constraints
    had_else = False
    new_subset = True
    ite_str_json = ""
    for i in range(0, len(subsets)):
        samples = []
        none_on_left = False
        found_none = False
        for co in combs:
            sample = []
            samples.append(sample)
            for c in co:
                if ref_rec[c][subsets[i][0]] is None:
                    if c in combs[0]:
                        none_on_left = True
                        samples = samples[:-1]
                        break
                    # NOTE: we ignore structural relations for now
                    found_none = True
                    sample.append(f"{c} is missing")
                else:
                    sample.append(ref_rec[c][subsets[i][0]])
        if none_on_left or found_none: continue
        s1 = samples[0]
        s2 = samples[1]

        c1 = []
        c2 = []
        for k in range(len(s1)):
            c1.append(combs[0][k])

        for k in range(len(s2)):
            c2.append(combs[1][k])

        if i < len(subsets)-1:
            if had_else:
                ite_str_json["else"] = translate.print_ite(s1, s2, c1, c2)
                ite_str_json = ite_str_json["else"]
            else:
                ite_str_json = translate.print_ite(s1, s2, c1, c2)
                parent_dict = ite_str_json
            had_else = True
        else:
            if had_else:
                ite_str_json["else"] = translate.print_ite(s1, s2, c1, c2)
                ite_str_json = parent_dict
            else:
                ite_str_json = translate.print_ite(s1, s2, c1, c2)
            had_else = False

        if_paths = set()
        for s in s1:
            if type(s) is str:
                for val in ref_rec[c1[0]]:
                    if val is not None:
                        if_paths.add(val.pathstr)
                        # continue ?
            else:
                if_paths.add(s.pathstr)

        if_pathstr = ""
        for ip in sorted(if_paths):
            if_pathstr += ip + ", "
        if_pathstr = if_pathstr[:-2]

        # can we move this one layer higher?
        # both of these operations should not be necessary if we did everything correctly
        if if_pathstr in ite_dict:
            if len(subsets) > 1 and not new_subset:
                ite_dict[if_pathstr][-1].update(ite_str_json)
            else:
                new_subset = False
                ite_dict[if_pathstr].append(ite_str_json)
        else:
            ite_dict[if_pathstr] = [ite_str_json]
            new_subset = False
    if len(ite_str_json) > 0:
        pass


def process_cand_list():
    global ite_cand_list
    ble = ite_cand_list
    for depth in ite_cand_list:
        if len(ite_cand_list[depth]) == 0:
            continue
        if False and config["filter_candidate_list"] and not config["disable_heuristics"]:
            ite_cand_list[depth] = utils.filter_equal_pli(ite_cand_list[depth])
            ite_cand_list[depth] = utils.unite_cand_list_ifs(ite_cand_list[depth], versions)
            ite_cand_list[depth] = utils.filter_cand_list(ite_cand_list[depth], versions)
            # repeat the same step for the reversed list
            ite_cand_list[depth] = utils.filter_cand_list(list(reversed(ite_cand_list[depth])), versions)

        for cand in ite_cand_list[depth]:
            prep_print(cand[0], cand[1], cand[2])


def update_schema(schema, tree):
    global ite_dict
    ite_dict = utils.filter_ite_dict(ite_dict)

    schema_dumps = json.dumps(schema, indent=2)
    schema = json.loads(schema_dumps)
    with open(schema_out, 'w+') as f:
        f.write(schema_dumps)
    schema["$schema"] = schema["$schema"].replace("draft-04", "draft-07")
    current_schema_global = None
    
    total_schema = {"properties": {}}

    for k in ite_dict:
        current_schema = total_schema["properties"]
        paths = []
        paths.extend(k.split("/")[2:])
        full_path = "/root"
        i = 0
        for p in paths:
            i += 1
            full_path += "/" + p
            ntype = findall(tree, lambda node: node.fullpathstr == full_path)[0].type
            
            if p != "object":
                if p not in current_schema:
                    current_schema[p] = {}
                current_schema = current_schema[p]

            if i < len(paths):
                if ntype == "array":
                    if "items" not in current_schema:
                        current_schema["items"] = {}
                    current_schema = current_schema["items"]
                elif ntype == "object":
                    if "properties" not in current_schema:
                        current_schema["properties"] = {}
                    current_schema = current_schema["properties"]

        json_str = {}
        if len(ite_dict[k]) > 1:
            json_allof = []
            json_str = {"allOf": json_allof}
            for ites in ite_dict[k]:
                json_allof.append(ites)

        else:
            json_str.update(ite_dict[k][0])

        test = json_str

        current_schema.update(test)
    if current_schema_global is None:
        current_schema_global = total_schema.copy()
    else:
        current_schema_global = current_schema_global | total_schema
    schema2 = {"allOf": [schema, current_schema_global]}
    res = json.dumps(schema2, indent=2)

    with open(ite_schema_out, 'w+') as f:
        f.write(res)
    base_loc = sum(1 for line in open(schema_out))
    ite_loc = sum(1 for line in open(ite_schema_out))
    res_str = f"Lines in Schema without if-then-else:\t {base_loc}\n" \
              f"Lines in Schema with if-then-else:\t {ite_loc} ({ite_loc - base_loc} additional lines)"

    return res_str, base_loc, ite_loc


def process_file(filenames):
    root = Node("root")
    root.type = "root"
    max_depth = 0
    for filename in filenames:
        with open(filename, "r", encoding='utf-8') as f:
            js = json.load(f)

            if js is None:
                exit(1)

            depths = []
            build_json_tree(js, root, depths)
            max_depth = max(max(depths), max_depth)

    enrich_tree(root)

    for i in range(1, max_depth + 1):
        find_dependencies(root, i)

    process_cand_list()
    return root


def run_experiments(config_path):
    global config, schema_out, ite_schema_out, ite_dict, ite_cand_list, versions
    if os.path.exists(config_path):
        with open(config_path, "r", encoding='utf-8') as conf_file:
            exp_config = json.load(conf_file)
    else:
        exit(1)
    table = []
    for exp_key in exp_config:
        exp = exp_config[exp_key]
        if "name" in exp:
            exp_name = exp["name"]
        else:
            exp_name = "experiment_" + str(i + 1)
        configs = exp["config"]
        for i in range(len(configs)):
            start_time = time.time()
            # reset global variables
            ite_dict = {}
            ite_cand_list = {}
            versions = []

            config = configs[i]
            if "name" in config:
                config_name = config["name"]
            else:
                config_name = "config_" + str(i + 1)
            print(f"Processing \"{exp['name']}\" with configuration \"{config_name}\"...")
            out_dir = exp["out_dir"] + "/" + config_name
            schema_out = out_dir + "/" + exp["schema_out"]
            ite_schema_out = out_dir + "/" + exp["ite_schema_out"]
            results_out = out_dir + "/" + exp["results_out"]
            input_files = exp["input"]

            Path(out_dir).mkdir(parents=True, exist_ok=True)

            tree = process_file(input_files)
            # supress prints from extract_from_files
            save_stdout = sys.stdout
            sys.stdout = open(os.devnull, 'w')
            schema_klettke = extract_from_files(input_files)
            sys.stdout = save_stdout

            res_str, size_base, size_total = update_schema(schema_klettke, tree)
            schema_valid, input_valid = validate.validate_list(input_files, ite_schema_out)
            
            if schema_valid:
                schema_state = "passed"
            else:
                schema_state = "failed"
                
            if input_valid:
                input_state = "passed"
            else:
                input_state = "failed"

            elapsed_time = time.time() - start_time

            # Count ITE-Constraints
            ite_count = 0
            for lst in ite_dict.values():
                for elem in lst:
                    ite_count += 1
                    elem = elem
                    while "else" in elem:
                        ite_count += 1
                        elem = elem["else"]

            res_str += f"\n\nRuntime: {elapsed_time}s\nCFDs found: {ite_count}\n\n" \
                       f"Validation of produced schema against JSON Schema Draft 7 {schema_state}" \
                       f"\nValidation of input JSON document against produced JSON Schema {input_state}\n\n" #\
                       # f"###### Config ######\n{json.dumps(config, indent=4)}"

            row_name = "row_" + str(i)
            
            # Concatenation with allOf adds 4 additional lines
            size_ite = size_total - size_base - 4
            ratio = round(size_ite/size_total, 3)
            results = {"Dataset": exp["name"], "Size Schema": size_base, "Config": config_name,
                       "Size ITE": size_ite, "Ratio ITE": ratio, "#Constraints": ite_count, "Runtime": elapsed_time}
            table.append(results)

            with open(results_out, 'w') as res_file:
                res_file.write(res_str)

    return table


def run(config_file, input_files):
    global config
    if os.path.exists(config_file):
        with open(config_file, "r", encoding='utf-8') as f:
            config = json.load(f)

    parse_tree = process_file(input_files)
    # supress prints from extract_from_file
    save_stdout = sys.stdout
    sys.stdout = open(os.devnull, 'w')
    # Extract third-party with approach by Klette et al.
    schema_klettke = extract_from_files(input_files)
    sys.stdout = save_stdout

    update_schema(schema_klettke, parse_tree)

    validate.validate_list(input_files, ite_schema_out)