# Collection of helper functions for CFD discovery

# Returns a position list index
def get_pli(lists):
    ress = []
    for lst in lists:
        pos_lst = []
        res = []
        for i in range(0, len(lst)):
            val = lst[i]
            if val is None:
                res.append([None])
            elif val in pos_lst:
                res[pos_lst.index(val)].append(i)
            else:
                res.append([i])
                pos_lst.append(val)
        # replace unique values with -1
        for i in range(0, len(res)):
            if len(res[i]) == 1:
                res[i] = [-1]
        ress.extend(res)
    return ress


def get_attr_name_and_type(node):
    if node.type == "object" or node.type == "array":
        return {node.name: node.type}
    elif type(node.name) is dict:
        return {"type": node.type}
    else:
        return str(node.name)


def get_attr_name(node):
    if node.type == "object":
        return str(node.name)
    elif type(node.name) is dict:
        return str(list(node.name.keys())[0])
    else:
        return str(node.name)


# level starts at 1
def get_node_value(node, type, level):
    if node.type == "object":
        if type == "base":
            # we have not defined any generalisation for objects, thus just return the base case
            obj = []
            for c in node.children:
                obj.append(get_attr_name(c))
            return sorted(obj)
        elif type == "gen":
            if level > 1:
                return get_attr_name(node)
            return {"type": node.type}
        elif type == "spec":
            obj = []
            if level > 2:
                for c in node.children:
                    obj.append(get_node_value(c, type, level - 1))
            elif level > 1:
                for c in node.children:
                    obj.append(get_attr_name_and_type(c))
            else:
                for c in node.children:
                    obj.append(get_attr_name(c))
            return obj
    elif node.type == "array":
        if type == "base":
            return node.ctypes
        elif type == "gen":
            if level == 1:
                return set(node.ctypes)
            if level == 2:
                return {"type": node.type}
        elif type == "spec":
            arr = []
			
            if level > 1:
                for c in node.children:
                    cval = get_node_value(c, type, level - 1)
                    if cval not in arr:
                        arr.append(cval)
            else:
                arr = node.generic_ctypes
            return arr
    else:
        # We have no specification for primitive attributes, thus just return the base case
        if type == "base" or type == "spec":
            # base representation: name and value of attribute
            return node.name
        elif type == "gen":
            # abstraction level 1: name and type of attribute
            if level == 1:
                return get_attr_name_and_type(node)
            # abstraction level 2: Only check if node is present, this should/could be handled by path instead
            if level >= 2:
                return get_attr_name(node)
                return node is not None


def get_compressed_records(nodes, type, level=1):
    if level < 1:
        raise Exception("Level must be great than or equal to 1")
    header = []
    clmns = []
    ref_rec = dict()

    if type == "base":
        abstr = ""
    elif type == "gen":
        abstr = "_generic" + str(level) + "_"
    elif type == "spec":
        abstr = "_spec" + str(level) + "_"

    for nd in nodes:
        if len(clmns) > 0:
            maxi = max(len(x) for x in clmns)
        else:
            maxi = 0
        for n in nd:
            if type == "spec":
                if n.type != "object" and n.type != "array":
                    #  We do not have specification for primitive types
                    continue
            col = abstr + str(get_attr_name(n))
            if col not in header:
                header.append(col)
                # fill previous rows with empty value (-2)
                clmns.append([[-2]] * maxi)
                ref_rec[col] = [None]*maxi

            # TODO: How to handle "overcapped" abstractions/specifications
            val = get_node_value(n, type=type, level=level)
            clmns[header.index(col)].append(val)

            if n not in ref_rec[col]:
                ref_rec[col].append(n)

        if len(clmns) > 0:
            maxi = max(len(x) for x in clmns)
        else:
            maxi = 0

        # Add empty value (-2) if column was missing
        for i in range(0, len(clmns)):
            if len(clmns[i]) < maxi:
                clmns[i].append([-2] * (maxi - len(clmns[i])))

        for k in ref_rec:
            if len(ref_rec[k]) < maxi:
                ref_rec[k].extend([None] * (maxi - len(ref_rec[k])))

    # transform to compressed record
    cr = []
    for col in clmns:
        index = []
        cr_col = []
        for e in col:
            if e == [-2]:
                cr_col.append(e)
            else:
                if e not in index:
                    index.append(e)
                cr_col.append(index.index(e))
        cr.append(cr_col)
    return header, cr, ref_rec


def get_compressed_records_from_list(nodes, versions):
    header, clmns, ref_rec = get_compressed_records(nodes, versions[0][0], versions[0][1])
    for v in versions[1:]:
        new_header, new_clmns, new_ref_rec = get_compressed_records(nodes, v[0], v[1])
        header.extend(new_header)
        clmns.extend(new_clmns)
        ref_rec.update(new_ref_rec)
    return header, clmns, ref_rec
