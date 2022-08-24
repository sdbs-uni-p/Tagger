# Implementation of the approach "Schema Extraction and Structural Outlier
# Detection for JSON-based NoSQL Data Stores" by Meike Klettke, Uta Störl, 
# and Stefanie Scherzinger in BTW 2015, https://dl.gi.de/handle/20.500.12116/2420
#
# Slightly modified for the integration into Tagger

import datetime  # aktuelle Zeit beim Speichern eines Schemas
import json, bson
from collections import OrderedDict
from math import floor
from jsonpath_ng import parse

documentID = 0


# Funktion zum Bestimmen des JSON-Typs, Umwandlung von Python-Typ in JSON-Typ
def jsonType(node):
    nodeType = type(node)
    if (nodeType in [str, bson.objectid.ObjectId]):
        jsonType = "string"
    elif (nodeType is int):
        jsonType = "integer"
    elif (nodeType is float):
        jsonType = "number"
    elif (nodeType is bool):
        jsonType = "boolean"
    elif (nodeType is list):
        jsonType = "array"
    elif (nodeType is dict):
        jsonType = "object"
    elif (node is None):
        jsonType = "null"
    else:
        jsonType = ""

    return jsonType


# ERSTER TEIL
# Kernstück des Programms, schrittweises Einlesen der Struktur jedes JSON-Dokumentes und
# Ablegen der Knoten und Kanten im Spanning Graph (rekursiv für die Dokumente)
def extractSchema(node, nodeName, parentName, zaehler):
    global documentID
    zaehler = zaehler + 1

    # Typ bestimmen
    propertyType = jsonType(node)

    # Speichern der Knoten- und Kanteninformationen
    storeNode(nodeName, propertyType, documentID)

    # Speicherung der Edge (außer beim Rootknoten)
    if parentName:
        storeEdge(nodeName, parentName, documentID)

    # rekursive Aufrufe im Fall von object bzw. array
    parentName = nodeName

    # Array
    if propertyType == "array":
        arrayTypes = set()
        for i in range(len(node)):
            arrayType = jsonType(node[i])
            # extractSchema wird aufgerufen bei array und object, und wenn ein
            # primitiver Datentyp zum ersten Mal vorkommt
            if arrayType not in arrayTypes.difference({"array", "object"}):
                zaehler = extractSchema(node[i], nodeName + "__a__" + arrayType, parentName, zaehler)
                documentID += 1
            arrayTypes.add(arrayType)

    # Object: rekursiver Aufruf für jede Property des Objekts
    elif propertyType == "object":
        for prop, value in node.items():
            zaehler = extractSchema(value, nodeName + "__o__" + prop, parentName, zaehler)
            documentID += 1

    return (zaehler)


# Funktion zum Speichern eines Nodes
def storeNode(name, propertyType, documentID):
    # Test, ob Knoten schon vorhanden
    node_is_already_present = False
    for index, node in enumerate(spanning_graph_nodes):
        if node["name"] == name:
            node_is_already_present = True
            break

    if node_is_already_present:
        # Überprüfen, ob Typ übereinstimmt
        storedType = node["propertyType"]
        if storedType != propertyType:
            # schon verschiedene Typen vorhanden?
            if type(storedType) is list:
                # neuen Typ einfügen
                if propertyType not in storedType:
                    storedType.append(propertyType)
            else:
                # Array aus altem und neuen Typ bilden
                storedType = [storedType, propertyType]

                # Wert mit neuem Typ speichern
            spanning_graph_nodes[index]["propertyType"] = storedType
        # documentID zur ID-Menge "occurrence" hinzufügen
        spanning_graph_nodes[index]["occurrence"].add(documentID)

    else:
        # insert, falls noch nicht vorhanden
        spanning_graph_nodes.append({"name": name,
                                     "propertyType": propertyType,
                                     "occurrence": set([documentID])
                                     })


# Funktion zum Speichern einer Edge
def storeEdge(node, parent, documentID):
    # Test, ob Kante schon vorhanden
    edge_is_already_present = False
    for index, edge in enumerate(spanning_graph_edges):
        if edge["node"] == node and edge["parent"] == parent:
            edge_is_already_present = True
            break

    if edge_is_already_present:
        # wenn vorhanden, dann Häufigkeit erhöhen (Menge von documentIDs, in denen die Kante vorkommt)
        spanning_graph_edges[index]["occurrence"].add(documentID)
    else:
        # wenn nicht vorhanden, speichern
        spanning_graph_edges.append({"node": node,
                                     "parent": parent,
                                     "occurrence": set([documentID])
                                     })


# ZWEITER TEIL
# Erstellung des Schemas aus den Informationen des Spanning Graph
def printSchema(parent, occurrence):
    # Aufbau des Schemas als OrderedDictionary (Python-dictionary, das Reihenfolge beibehält)
    schema = OrderedDict()

    # Knoten im Spanning Graph finden
    for parentNode in spanning_graph_nodes:
        if parentNode["name"] == parent:
            break

    # Anzahl der Document IDs in occurrence
    node_occurrence = len(parentNode["occurrence"])

    propertyType = parentNode["propertyType"]
    # Typ ins Schema schreiben
    schema["type"] = propertyType

    # Typ oder einer der Typen des Nodes ist Objekt (propertyType kann String ("object") oder Array ([..., "object", ...]) sein)
    if "object" in propertyType:
        # alle ausgehenden Kanten des Objektes finden
        outgoing_edges = []
        for edge in spanning_graph_edges:
            if edge["parent"] == parent:
                outgoing_edges.append(edge)

        if len(outgoing_edges) > 0:
            # Properties erstellen
            properties = {}
            # required-Array erstellen
            requiredProperties = []
            # jede ausgehende Kante ist eine Property
            for edge in outgoing_edges:
                node = edge["node"]
                # Namenskonvention "__o__" beseitigen
                pos = node.rfind("__o__")
                if pos != -1:
                    nodeName = node[pos + 5:]
                # Property ist required, wenn sie so oft vorkommt, wie die Parent-Property
                if len(edge["occurrence"]) == node_occurrence:
                    requiredProperties.append(nodeName)
                # rekursiver Aufruf für jede Property
                properties[nodeName] = printSchema(node, node_occurrence)
            # Properties nach Key sortieren und ins Schema schreiben
            schema["properties"] = OrderedDict(sorted(properties.items(), key=lambda item: str.lower(item[0])))
            # requiredProperties schreiben, wenn es welche gibt (sortiert)
            if requiredProperties:
                schema["required"] = sorted(requiredProperties, key=str.lower)

    # Typ oder einer der Typen des Nodes ist Array
    if "array" in propertyType:
        # alle ausgehenden Kanten des Arrays finden
        outgoing_edges = []
        for edge in spanning_graph_edges:
            if edge["parent"] == parent:
                outgoing_edges.append(edge)
        if len(outgoing_edges) == 1:
            # Array hat nur einen Typ
            # TODO: node_occurences wurde hier durch len(outgoing_edges[0]["occurence"]) ersetzt.
            #    Es bleibt zu überprüfen ob das auch so korrekt ist
            schema["items"] = printSchema(outgoing_edges[0]["node"], len(outgoing_edges[0]["occurrence"]))
        elif len(outgoing_edges) > 1:
            # Array hat verschiedene Typen
            schema["items"] = {"anyOf": []}
            for edge in outgoing_edges:
                schema["items"]["anyOf"].append(printSchema(edge["node"], node_occurrence))

    # Description für Knoten hinzufügen
    if parent != collectionName:
        # prozentuales Vorkommen berechnen
        occ_percentage = str(floor(node_occurrence * 100 / occurrence)) + "%"
        global possibleOutliers
        if int(occ_percentage[:-1]) >= 95: possibleOutliers += occurrence - node_occurrence
        if int(occ_percentage[:-1]) <= 5: possibleOutliers += node_occurrence
        schema["description"] = "Occurrence: " + str(node_occurrence) + "/" + str(occurrence) + ", " + occ_percentage

    # Schema zurückgeben
    return schema


spanning_graph_nodes = []
spanning_graph_edges = []
possibleOutliers = 0
zaehler = 0


def extract_from_file(filepath, name = "undefined"):
    global zaehler, spanning_graph_nodes, spanning_graph_edges, beginCollection, endCollection, possibleOutliers, \
        arrayTime, collectionName

    # Reset variables
    spanning_graph_nodes = []
    spanning_graph_edges = []
    possibleOutliers = 0
    zaehler = 0

    # Beginn-Zeit ermitteln
    begin = datetime.datetime.now()
    print("Begin extract " + str(begin))
    arrayTime = datetime.timedelta()

    beginCollection = datetime.datetime.now()
    collectionName = name

    # Beginn-Zeit nehmen
    beginLocal = datetime.datetime.now()

    with open(filepath, "r") as f:
        jsD = json.load(f)
    jsonpath_expr = parse("$")
    test = [match.value for match in jsonpath_expr.find(jsD)]
    print(test)
    i = 0
    for jsonDocument in test:
        # Schemaextraktion
        # Nodes und Edges speichern, Aufruf der rekursiven Funktion
        zaehler = extractSchema(jsonDocument, collectionName, "", i, zaehler)
        i += 1

    print("########################################")
    print(zaehler)
    print(spanning_graph_nodes)
    print(spanning_graph_edges)
    currentCollection_count = 1
    # Aus dem Spanning Graph: Schema auslesen und in JSON umwandeln (wenn Dokumente vorhanden)
    # OrderedDict behält Reihenfolge bei (bessere Lesbarkeit des Schemas)
    schema = OrderedDict()
    # Meta-Daten: Schema-Version, Titel und Beschreibung inkl. Erstellungszeit
    schema["title"] = collectionName
    schema[
        "description"] = "JSON Schema for collection " + collectionName + " of database " + "noDB" + ", created on " + str(
        datetime.datetime.now()) + "."
    schema[
        "$schema"] = "http://json-schema.org/draft-04/schema#"  # Schema entspricht Version 4 des JSON Schema-Draft
    # Aufruf der Funktion printSchema, Hinzufügen der Eigenschaften
    schema.update(printSchema(collectionName, currentCollection_count))
    # Ausgabe der Schemas
    print()
    print("######################################################################")
    print("######################################################################")
    print("######################################################################")
    print()
    print(json.dumps(schema, indent=4))
    # Ende-Zeit nehmen
    endLocal = datetime.datetime.now()
    diff = endLocal - beginLocal
    schema["time1"] = str(diff)

    endCollection = datetime.datetime.now()
    # print("Collection " + collectionName + ": " + str(endCollection-beginCollection))
    if possibleOutliers > 0:
        print(
            "Collection " + collectionName + ": " + str(possibleOutliers) + "/" + str(currentCollection_count))
    possibleOutliers = 0

    print("Collection " + collectionName + ": " + str(diff))

    end = datetime.datetime.now()
    print("Ende extract " + str(end))
    print("Dauer: " + str(end - begin))
    return(schema)


def extract_from_files(filepaths, name = "undefined"):
    global documentID, zaehler, spanning_graph_nodes, spanning_graph_edges, beginCollection, endCollection, \
        possibleOutliers, arrayTime, collectionName

    # Reset variables
    spanning_graph_nodes = []
    spanning_graph_edges = []
    possibleOutliers = 0
    zaehler = 0

    # Beginn-Zeit ermitteln
    begin = datetime.datetime.now()
    print("Begin extract " + str(begin))
    arrayTime = datetime.timedelta()

    beginCollection = datetime.datetime.now()
    collectionName = name

    # Beginn-Zeit nehmen
    beginLocal = datetime.datetime.now()
    i = 1
    for filepath in filepaths:
        with open(filepath, "r", encoding="utf-8") as f:
            jsD = json.load(f)
        jsonpath_expr = parse("$")
        test = [match.value for match in jsonpath_expr.find(jsD)]
        for jsonDocument in test:
            # Schemaextraktion
            # Nodes und Edges speichern, Aufruf der rekursiven Funktion
            zaehler = extractSchema(jsonDocument, collectionName, "", zaehler)
            documentID += 1
            print(documentID)

    print("########################################")
    print(zaehler)
    currentCollection_count = 1
    # Aus dem Spanning Graph: Schema auslesen und in JSON umwandeln (wenn Dokumente vorhanden)
    # OrderedDict behält Reihenfolge bei (bessere Lesbarkeit des Schemas)
    schema = OrderedDict()
    # Meta-Daten: Schema-Version, Titel und Beschreibung inkl. Erstellungszeit
    schema["title"] = collectionName
    schema[
        "description"] = "JSON Schema for collection " + collectionName + " of database " + "noDB" + ", created on " + str(
        datetime.datetime.now()) + "."
    schema[
        "$schema"] = "http://json-schema.org/draft-04/schema#"  # Schema entspricht Version 4 des JSON Schema-Draft
    # Aufruf der Funktion printSchema, Hinzufügen der Eigenschaften
    schema.update(printSchema(collectionName, currentCollection_count))
    # Ausgabe der Schemas
    print()
    print("######################################################################")
    print("######################################################################")
    print("######################################################################")
    print()
    print(json.dumps(schema, indent=4))
    # Ende-Zeit nehmen
    endLocal = datetime.datetime.now()
    diff = endLocal - beginLocal
    schema["time1"] = str(diff)

    endCollection = datetime.datetime.now()
    # print("Collection " + collectionName + ": " + str(endCollection-beginCollection))
    if possibleOutliers > 0:
        print(
            "Collection " + collectionName + ": " + str(possibleOutliers) + "/" + str(currentCollection_count))
    possibleOutliers = 0

    print("Collection " + collectionName + ": " + str(diff))

    end = datetime.datetime.now()
    print("Ende extract " + str(end))
    print("Dauer: " + str(end - begin))
    return schema
