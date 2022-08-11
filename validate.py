from jsonschema import Draft7Validator, validate, ValidationError
import json


# Checks if JSON schema on schema_path is valid and then validates the JSON files (given as paths) in inputs
# against that schema
def validate_list(inputs, schema_path):
    with open(schema_path, "r", encoding='utf-8') as f:
        schema = json.load(f)
        
    try:
        Draft7Validator.check_schema(schema)
    except ValidationError:
        print("Schema validation failed")
        return
    else:
        print("Schema validation passed")
        
    for json_path in inputs:
        with open(json_path, "r", encoding='utf-8') as f:
            js = json.load(f)
        try:
            validate(js, schema)
        except ValidationError:
            print("JSON validation failed")
        else:
            print("JSON validation passed")