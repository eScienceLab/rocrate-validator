# Development notes for LinkML Workflow RO-Crate profile

## Setup
1. Create a folder for the profile under `rocrate_validator/profiles`
1. Copy across `profile.ttl` from another profile & update that metadata for the new profile.
    1. In particular, change the token for the profile to a new and unique name, e.g.
    `prof:hasToken "workflow-ro-crate-linkml"`. This is the name which can be used to 
    select the profile using `--profile-identifier` argument
    1. The ID of the profile must also be unique (the first line after the `@prefix` statements), to prevent conflation between this profile and any other profile in the package.
1. Create a `profile-name.yaml` file - this is where you will write the LinkML.
1. Create a test folder for the profile under `tests/integration/profiles`
1. Copy the style of other profiles' tests to build up a test suite for the profile.
   Add any required RO-Crate test data under `tests/crates/` and create corresponding 
   classes in `tests/ro_crates.py` which can be used to fetch the data during the tests

## Converting LinkML to SHACL

```
linkml generate shacl --include-annotations --non-closed workflow-ro-crate.yaml > workflow-ro-crate.ttl
```

`--include-annotations` passes through anything included under `annotations` property in LinkML.
`--non-closed` tells LinkML to generate open SHACL shapes (i.e. entities will be permitted to have properties that aren't explicitly listed)

## Running the validator

Use `--profile-identifier` to select the desired profile.

The crates in `tests/data/crates` can be used as examples for running the validator. For example:

```
rocrate-validator validate -v --profile-identifier workflow-ro-crate-linkml tests/data/crates/invalid/1_wroc_crate/no_mainentity/
```

## Running the tests

Run `pytest` as usual after setup - the new tests should be picked up automatically.

## Error message "The requirement check cannot be None"

Occurred intermittently when running the validator on test cases - the first run would be fine, but later runs would then have this error. It's something to do with how the SHACL checks are instantiated in Python. Maybe a caching issue? 

Resolved by ensuring generated SHACL uses non-closed shapes (which should be the case in most profiles?) Not sure why this works.

``` 
[2024-10-10 15:22:13,315] WARNING in models: Unexpected error during check <rocrate_validator.requirements.shacl.checks.SHACLCheck object at 0x7f4e2195aea0> - PropertyShape -        
 mainEntity of Main Workflow entity existence: Check if the Main Workflow is specified through a `mainEntity` property in the root data entity (2807297706545425892) - PropertyShape - mainEntity of     
 Main Workflow entity existence: Check if the Main Workflow is specified through a `mainEntity` property in the root data entity (2807297706545425892).  Exception: The requirement check cannot be      
 None                                                                                                                                                                                                 
 [2024-10-10 15:22:13,316] WARNING in models: Consider reporting this as a bug.                                                                                                     
 [2024-10-10 15:22:13,629] WARNING in models: Unexpected error during check <rocrate_validator.requirements.shacl.checks.SHACLCheck object at 0x7f4e2195acf0> - PropertyShape -        
 mainEntity of RootDataEntity: Check if the Main Workflow is specified through a `mainEntity` property in the root data entity (2807297706545425892) - PropertyShape - mainEntity of RootDataEntity:     
 Check if the Main Workflow is specified through a `mainEntity` property in the root data entity (2807297706545425892).  Exception: The requirement check cannot be None                              
 [2024-10-10 15:22:13,629] WARNING in models: Consider reporting this as a bug.    
 ```
