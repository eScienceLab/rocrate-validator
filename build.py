#!/usr/bin/env python3

import os
import subprocess
import sys

def convert_to_shacl(input_file, output_file):
    # Construct the command
    command = [
        "linkml", "generate", "shacl",
        "--include-annotations", "--non-closed",
        input_file
    ]
        
    # Run the command and redirect output to the output file
    with open(output_file, "w") as outfile:
        comment = (
            f"# This SHACL file was generated using the LinkML\n"
            f"# Source file: {input_file}\n"
            f"# Command: {' '.join(command)}\n\n"
        )
        outfile.write(comment)
    
    with open(output_file, "a") as outfile:
        # TODO error handling!
        subprocess.run(command, stdout=outfile)


def convert_folder_recursively(path):
    # recursively iterate through subfolders searching for yaml files
    for root, _, files, in os.walk(path):
        for file in files:

            # skip non-yaml files
            if not file.endswith(".yaml"):
                continue

            input_file = os.path.join(root, file)
            output_file = input_file.replace(".yaml", ".ttl")
            print("Converting", input_file)
            convert_to_shacl(input_file, output_file)


if __name__ == "__main__":
    convert_folder_recursively("rocrate_validator/profiles")
