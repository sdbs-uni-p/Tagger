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
        print("Validation of produced schema against JSON Schema Draft 7 failed")
        # We can not validate input against an invalid schema, thus we consider both failed
        return False, False
    else:
        print("Validation of produced schema against JSON Schema Draft 7 passed")
        
    for json_path in inputs:
        with open(json_path, "r", encoding='utf-8') as f:
            js = json.load(f)
        try:
            validate(js, schema)
        except ValidationError:
            print("Validation of input JSON document against produced JSON Schema failed")
            return True, False
        else:
            print("Validation of input JSON document against produced JSON Schema passed")
            return True, True