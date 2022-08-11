import copy
import re
from itertools import chain, combinations, product
from more_itertools import unique_everseen, powerset


def intersect_plis(plis):
    if len(plis) == 1:
        return plis[0]
    else:
        pli_ab = plis.pop(0)
        while len(plis) > 0:
            pli_a = pli_ab
            pli_ab = []
            pli_b = plis.pop(0)
            if pli_a == pli_b:
                pli_ab = pli_a
                continue
            for a in pli_a:
                for b in pli_b:
                    if a == b:
                        pli_ab.append(a)
                    else:
                        a_in_b = list(set.intersection(set(a), set(b)))
                        if len(a_in_b) > 0:
                            pli_ab.append(a_in_b)

        return pli_ab


def subset(pli1, pli2):
    if pli1 == pli2:
        return pli1
    subsets = []
    for l1 in pli1:
        for l2 in pli2:
            if set(l1).issubset(l2):
                subsets.append(l1)
                break
    return subsets


def get_combinations(plis, max_combs):
    max_combs[0] = max(int(max_combs[0]), 0)
    max_combs[1] = max(int(max_combs[1]), 0)

    if max_combs[0] >= 1:
        combs_l = list(powerset_maxn(unique_everseen(plis.keys()), max_combs[0]))
    else:
        combs_l = list(powerset(unique_everseen(plis.keys())))

    if max_combs[0] == max_combs[1]:
        combs_r = combs_l
    else:
        if max_combs[1] >= 1:
            combs_r = list(powerset_maxn(unique_everseen(plis.keys()), max_combs[1]))
        else:
            combs_r = list(powerset(unique_everseen(plis.keys())))

    combs = list(product(combs_l, combs_r))
    new_combs = []
    for c in combs:
        c0_in_c1 = False
        for e in c[0]:
            if e in c[1]:
                c0_in_c1 = True
                break
        if not c0_in_c1:
            new_combs.append([c[0], c[1]])
    return new_combs


def powerset_maxn(iterable, n):
    s = list(iterable)
    return chain.from_iterable(combinations(s, r) for r in range(1, n + 1))


# Only keep relations of value -> type
def val_type_filter(combs):
    filtered_combs = []
    rm_count = 0
    for c in combs:
        # TODO: Remove
        if re.match(r'^_generic\d+_', c[0][0]):
            rm_count += 1
            continue
        filtered_combs.append(c)

    return filtered_combs


def filter_combs(combs, versions):
    filtered_combs = []
    for c in combs:
        add = True
        for v in versions:
            stripped_combs = [set([x.replace(v, '', 1) for x in c[0]]),
                              set([x.replace(v, '', 1) for x in c[1]])]

            # Filter ITEs containing the generic and non-generic version of the same attribute
            if len(stripped_combs[0]) < len(c[0]) or len(stripped_combs[1]) < len(c[1]) or \
                    len(stripped_combs[0].intersection(stripped_combs[1])) > 0:
                add = False
                break
        if add:
            filtered_combs.append(c)

    return val_type_filter(filtered_combs)


def contains_same_attributes(combs, versions):
    stripped_combs = []
    for c in combs:
        for v in versions:
            stripped_combs.append(c[0].replace(v, '', 1))

    return 0 < len(stripped_combs) == len(set(stripped_combs))


def filter_cand_list(ite_cand_list, versions):
    # [subsets, combs, ref_rec]
    filtered_cand_list = [ite_cand_list[0]]
    for c in ite_cand_list:
        add = True
        for f in filtered_cand_list:
            if c == f:
                add = False
                break
            if c[0] == f[0]:
                if set(c[1][0]).issuperset(set(f[1][0])):
                    if set(c[1][1]).issubset(set(f[1][1])):
                        add = False
                        break
                    elif not set(c[1][1]).issuperset(set(f[1][1])):
                        add = False
                        new_comb = tuple(set(c[1][1]).union(set(f[1][1])))
                        if contains_same_attributes(new_comb, versions):
                            break
                        new_ref_rec = f[2] | c[2]
                        filtered_cand_list.append([c[0], [c[1][0], new_comb], new_ref_rec])
                        filtered_cand_list = filter_cand_list(filtered_cand_list, versions)
                        break
        if add:
            filtered_cand_list.append(c)

    return filtered_cand_list


def unite_cand_list_ifs(ite_cand_list, versions):
    # [subsets, combs, ref_rec]
    filtered_cand_list = [ite_cand_list[0]]
    for c in ite_cand_list:
        add = True
        for f in filtered_cand_list:
            if c == f:
                add = False
                break
            if c[0] == f[0] and set(c[1][1]) == set(f[1][1]):
                if set(c[1][0]).issuperset(set(f[1][0])):
                    add = False
                    break
                elif set(c[1][0]).issubset(set(f[1][0])):
                    filtered_cand_list.remove(f)
                    break
                else:
                    add = False
                    new_comb = tuple(set(c[1][0]).union(set(f[1][0])))
                    if contains_same_attributes(new_comb, versions):
                        break
                    new_ref_rec = f[2] | c[2]
                    filtered_cand_list.append([c[0], [new_comb, f[1][1]], new_ref_rec])
                    filtered_cand_list = unite_cand_list_ifs(filtered_cand_list, versions)
                    break
        if add:
            filtered_cand_list.append(c)

    return filtered_cand_list


# If we have not only an inclusion but a functional dependency, we have the a -> b and b -> a.
# In this case, we only keep the first one that occurs
def filter_equal_pli(ite_cand_list):
    # [subsets, combs, ref_rec]
    filtered_cand_list = [ite_cand_list[0]]
    for c in ite_cand_list:
        add = True
        for f in filtered_cand_list:
            if c[0] == f[0] and c[1] != f[1]:
                if c[1] == list(reversed(f[1])):
                    #print(f"Rev: Removed {c[1]} for {f[1]}")
                    add = False
                    break
                elif c[1][1] == f[1][1]:
                    add = False
                    for attr in c[1][0]:
                        if attr not in f[1][0]:
                            add = True
                            break
                    if not add:
                        print(f"{c[1]} <=> {f[1]}")
                        break
        if add:
            filtered_cand_list.append(c)
    return filtered_cand_list


def filter_combs_pli(combs, plis):
    if len(combs) == 0: return combs
    filtered_combs = [combs[0]]
    mult_ifs = []
    for c in combs:
        if len(c[0]) > 1:
            mult_ifs.append(c)
        else:
            if_attr = c[0][0]

            if any(plis[if_attr] == plis[fc[0][0]] and c[1] == fc[1] for fc in filtered_combs):
                pass
                #print(f"Removed {if_attr}")
                #print(c[0])
            else:
                filtered_combs.append(c)
    filtered_combs.extend(mult_ifs)
    return filtered_combs


# Only keeps most specific version with same PLI of a column
def filter_plis(plis, versions):
    filtered_plis = {}
    for p in plis:
        add = True
        for i in range(len(versions) - 1):
            current_version = versions[i]
            if p.startswith(current_version):
                next_version = p.replace(versions[i], versions[i + 1], 1)
                if next_version in filtered_plis:
                    if plis[p] == plis[next_version]:
                        add = False
                    else:
                        add_version = p
                    break
                if next_version in plis and plis[p] == plis[next_version]:
                    add_version = next_version
                else:
                    add_version = p
                    break

        if add:
            filtered_plis[p] = plis[add_version]

    return filtered_plis


# remove more specific version if generic version covers more rows
def pre_filter_cand_list(candidate_list, versions):
    new_candidate_list = candidate_list.copy()
    for entry in candidate_list:
        c = entry[1]
        if len(c[1]) > 1 or len(c[0]) > 1: continue
        cand_then = c[1][0]
        loc_vers = versions
        for v in versions:
            if len(v) > 0 and cand_then.startswith(v):
                cand_then = cand_then.replace(v, "", 1)
                loc_vers = versions[:versions.index(v)]
                break
        for v in loc_vers:
            if entry not in new_candidate_list: continue
            vc = v + cand_then
            for ca in new_candidate_list:
                a = c
                b = ca[1]
                # abort if the
                if a == b:
                    continue
                elif a[0] == b[0] and vc in b[1]:
                    entry_plis = entry[0]
                    ncl_plis = ca[0]
                    # Continue if plis are disjoint
                    if not any(l in ncl_plis for l in entry_plis):
                        continue
                    ncl_rm = []
                    for e in entry_plis:
                        for n in ncl_plis:
                            if e == n:
                                ncl_rm.append(e)

                    if len(ncl_rm) > 0:
                        index = new_candidate_list.index(ca)
                        for rm in ncl_rm:
                            new_candidate_list[index][0].remove(rm)

                        index = new_candidate_list.index(entry)
                        for e in entry_plis:
                            if e not in ncl_rm:
                                new_candidate_list[index][0].remove(e)
                    else:
                        new_candidate_list.remove(entry)
                    break

    return new_candidate_list


def filter_calc_ite(config, combs, stripped_combs, ref_rec, combs_list, plis):
    # Do not allow generic attributes on the left (if-condition)
    # As we only have generic types for objects/arrays (for now), this is redundant if we only allow
    # primitive types on the left
    for c in combs[0]:
        if str(c).startswith('_generic'):
            return True

    # only allow primitive types on left side
    if config["only_primitive_if"]:
        for c in combs[0]:
            i = 0
            while ref_rec[c][i] is None and i < len(ref_rec[c]): i += 1
            if ref_rec[c][i].type in ["array", "object"]:
                return True

    # Check if a subset of the attribute combinations (or its non-generic version) already covers all rows
    for cl in combs_list:
        for sc in stripped_combs:
            found = set(cl[0]).issubset(set(combs[0])) and set(cl[1]).issubset(set(combs[1])) or \
                    set(cl[0]).issubset(set(sc[0])) and set(cl[1]).issubset(set(sc[1]))
            if found:
                # Checking if smaller combination also covers whole set should not be necessary if we make sure that
                # (len(combs[0]) + len(combs[1])) is monotonically increasing
                # TODO: We currently don't make that sure
                return True

    return False


def is_val(dct):
    is_v = True
    for k in dct:
        if type(dct[k]) in [dict, list]:
            is_v = is_v and is_val(dct[k])
        else:
            return k == "const"

    return is_v


def is_type(dct):
    is_t = True
    for k in dct:
        if type(dct[k]) in [dict, list]:
            is_t = is_t and is_type(dct[k])
        else:
            return k == "type"

    return is_t


def filter_ite_dict(ite_dict):
    filterd_ite_dict = copy.deepcopy(ite_dict)

    filter_count = 0
    for path in ite_dict:
        i = 0
        for ite in ite_dict[path]:
            if not is_val(ite["if"]["properties"]) or not is_type(ite["then"]["properties"]):
                #print(f"dct rm: {ite}")
                filter_count += 1
                del filterd_ite_dict[path][i]
            else:
                #print(f"dct keep: {ite}")
                i += 1

    pop_list = []
    for k in filterd_ite_dict:
        if len(filterd_ite_dict[k]) == 0:
            pop_list.append(k)
    for k in pop_list:
        filterd_ite_dict.pop(k)

    return filterd_ite_dict
