# Code for building parse tree

import bson

from anytree import Node


def get_json_type(node):
    node_type = type(node)

    if node_type in [str, bson.objectid.ObjectId]:
        json_type = "string"
    elif node_type is int:
        json_type = "integer"
    elif node_type is float:
        json_type = "number"
    elif node_type is bool:
        json_type = "boolean"
    elif node_type is list:
        json_type = "array"
    elif node_type is dict:
        json_type = "object"
    elif node is None:
        json_type = "null"
    else:
        json_type = ""

    return json_type


# Builds a tree that represents the JSON-File and adds some meta-data
def build_json_tree(node, parent, depths):
    node_type = get_json_type(node)
    depths.append(parent.depth + 1)
    if node_type == "object":
        for child in node:
            child_type = get_json_type(node[child])
            if child_type == "object" or child_type == "array":
                new_node = Node(child, parent=parent)
                build_json_tree(node[child], new_node, depths)
            else:
                new_node = Node({child: (build_json_tree(node[child], parent, depths))}, parent=parent)
            new_node.type = child_type
    elif node_type == "array":
        for child in node:
            child_type = get_json_type(child)
            parent_node = parent
            if child_type == "object" or child_type == "array":
                parent_node = Node(child_type, parent=parent)
                parent_node.type = child_type
            ret = build_json_tree(child, parent_node, depths)
            if ret is not None:
                new_node = Node(ret, parent=parent)
                new_node.type = child_type
    else:
        return node


# Add metadata about the path and the datatype of children to the tree
def enrich_tree(node):
    # The first two attributes are only for convenience and could also be calculated ad-hoc in one line
    node.pathstr = "/root" if node.parent is None else node.parent.separator.join([""] + [str(n.name) for n in node.parent.path])
    node.fullpathstr = "/root" if node.parent is None else node.pathstr + node.separator + str(node.name)
    node.length = 0 if node.children is None else len(node.children)

    if node.children is not None:
        node.ctypes = []
        spec1 = []
        spec2 = []
        spec3 = []
        for c in node.children:
            node.ctypes.append(c.type)
            enrich_tree(c)
            if type(c.name) is dict:
                c_name = list(c.name.keys())[0]
            else:
                c_name = c.name
            spec1.append([c_name, c.type])
            spec2.append([c_name, c.type, c.generic_ctypes])
            spec3.append([c_name, c.type, c.generic_ctypes, c.ctypes])
        node.specific_ctypes = [spec1, spec2, spec3]

        # find more generic version of child type
        # We can generalise in multiple ways. Currently we simply transform ctypes (list) to a set
        node.generic_ctypes = set(node.ctypes)
    else:
        node.ctypes = "None"
        node.generic_ctypes = "None"
        node.specific_ctypes = "None"


def get_siblings(node, depth=0):
    if depth > 0:
        res = []
        if depth == 1 and len(node.children) > 0:
            res.extend(get_siblings(node.children[0], depth - 1))
        elif len(node.children) > 0:
            for c in node.children:
                res.extend(get_siblings(c, depth - 1))
    else:
        res = [node]
        siblings = list(node.siblings)
        if len(siblings) > 0:
            res.extend(siblings)
        return [res]

    return res
