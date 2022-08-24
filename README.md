# Tagger

Implementation of Tagger, a schema extraction tool initially proposed in the article *Extracting JSON Schemas with Tagged Unions*
by Stefan Klessinger, Meike Klettke, Uta Störl and Stefanie Scherzinger at DEco@VLDB '22.

Tagger utilizes conditional functional dependency discovery to extract tagged unions from JSON documents and translates them to if-then-else statements in JSON Schema. 
A number of heuristics are applied to prevent overfitting. 

Tagger is designed for compatibility with third-party schema extraction approaches, allowing Tagger to focus exclusively on the detection of tagged unions while relying on other tools to extract a more general schema. As an example, a slightly adapted implementation ([extract.py](extract.py)) of the approach *Schema Extraction and Structural Outlier Detection for JSON-based NoSQL Data Stores* by Meike Klettke, Uta Störl, and Stefanie Scherzinger (published at BTW 2015) is integrated here.

This repository is organized in two branches: The main development branch and the branch "deco", where a version of our code for the DEco Workshop at VLDB 2022 is maintned (see "Citation").

## Citation
To refer to this work, please use these BibTeX entries.

```BibTeX
@inproceedings{Klessinger:2022:JSONTaggedUnions,
  author    = {Stefan Klessinger and
               Meike Klettke and
               Uta St{\"{o}}rl and
               Stefanie Scherzinger},
  title     = {Extracting JSON Schemas with Tagged Unions},
  year      = {2022}
  booktitle = {Proc.\ DEco@VLDB 2022}
}
```

## Setup
For simplifying the setup, a [Pipfile](https://github.com/pypa/pipfile) containing all Python dependencies is provided. With [pipenv](https://pipenv.pypa.io/en/latest/) installed, run ``pipenv install`` in the directory of the Pipfile. 

## Reproduction Package

A reproduction package, provided as a fully automated Docker container, including all input data used in our experiments, is available in a [separate repository](https://github.com/sdbs-uni-p/schema-inference-repro.git).

