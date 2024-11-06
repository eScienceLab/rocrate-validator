#!/usr/bin/env python3

import os
import subprocess
import sys
from linkml.generators.shaclgen import ShaclGenerator
import linkml._version as linkml_version


def convert_to_shacl(input_file: str, output_file: str):
    # Generate shacl
    shacl_shapes = ShaclGenerator(input_file).serialize()

    comment = (
        f"# This SHACL file was auto-generated with LinkML {linkml_version.__version__}.\n"
        f"#Changes will be overwritten on install.\n"
        f"# Source file: {input_file}\n"
        "\n"
    )

    # Run the command and redirect output to the output file
    with open(output_file, "w") as outfile:
        outfile.write(comment)
        outfile.write(shacl_shapes)


def convert_folder_recursively(path: str, force: bool = False):
    # recursively iterate through subfolders searching for yaml files
    for root, _, files, in os.walk(path):
        for file in files:

            # skip non-yaml files
            if not file.endswith(".yaml"):
                continue

            input_file = os.path.join(root, file)
            output_file = input_file.replace(".yaml", ".ttl")
            if force or not os.path.exists(output_file) or os.path.getmtime(input_file) > os.path.getmtime(output_file):
                print("Converting", input_file)
                convert_to_shacl(input_file, output_file)


if __name__ == "__main__":
    convert_folder_recursively("rocrate_validator/profiles", force="--force" in sys.argv)
