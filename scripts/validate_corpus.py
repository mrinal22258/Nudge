import sys
import json
import csv
from pathlib import Path
from jsonschema import validate, ValidationError

def main():
    corpus_dir = Path("corpus")
    raw_dir = corpus_dir / "raw"
    gt_dir = corpus_dir / "ground_truth"
    schema_path = Path("schema/resume_schema.json")
    manifest_path = corpus_dir / "manifest.csv"

    if not schema_path.exists():
        print(f"Error: Schema not found at {schema_path}")
        sys.exit(1)

    with open(schema_path, "r") as f:
        schema = json.load(f)

    if not manifest_path.exists():
        print(f"Error: Manifest not found at {manifest_path}")
        sys.exit(1)

    print("--- Starting Corpus Validation ---")

    # Read manifest and build file list
    manifest_files = []
    with open(manifest_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            manifest_files.append(row["filename"])

    errors = 0

    # Validate each manifest file
    for filename in manifest_files:
        base_name = Path(filename).stem
        pdf_path = raw_dir / filename
        json_path = gt_dir / f"{base_name}.json"

        # 1. Check PDF existence
        if not pdf_path.exists():
            print(f"[{base_name}] FAILED: PDF file {pdf_path} does not exist.")
            errors += 1
            continue
        if pdf_path.stat().st_size == 0:
            print(f"[{base_name}] FAILED: PDF file is empty.")
            errors += 1
            continue

        # 2. Check JSON ground truth existence
        if not json_path.exists():
            print(f"[{base_name}] FAILED: JSON ground truth {json_path} does not exist.")
            errors += 1
            continue

        # 3. Load and validate JSON Schema
        try:
            with open(json_path, "r") as f:
                gt_data = json.load(f)
            validate(instance=gt_data, schema=schema)
            print(f"[{base_name}] PASSED: PDF and JSON match & validate against schema.")
        except json.JSONDecodeError:
            print(f"[{base_name}] FAILED: JSON is not valid parseable JSON.")
            errors += 1
        except ValidationError as ve:
            print(f"[{base_name}] FAILED: JSON schema validation error: {ve.message}")
            errors += 1

    print("---------------------------------")
    if errors > 0:
        print(f"Validation FAILED with {errors} errors.")
        sys.exit(1)
    else:
        print("Validation PASSED cleanly. Corpus is ready.")
        sys.exit(0)

if __name__ == "__main__":
    main()
