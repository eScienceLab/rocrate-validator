# LinkML Schema Example for RO-Crate Validation

## Overview 

A LinkML schema is constructed using two main types of component: *classes* and *slots*. Broadly speaking, classes correspond to RDF types, while slots correspond to RDF properties. But this is not a one-to-one relationship; classes can also represent specific RDF "shapes," meaning the combination of a particular RDF type with additional constraints on the properties it uses (for example, a class could represent `Person` objects constrained to have a defined `affiliation`). Similarly, slots may be constrained This distinction is important for approaching validation in particular, as the RO-Crate root data entity (which is a `Dataset`) has different requirements to other `Dataset`s within a crate.

This section offers a quick overview of how RO-Crate/JSON-LD/RDF features can be represented in LinkML, but does not go into a lot of detail. Relevant links to the LinkML documentation are provided for further reading.

## Working Example

Applying LinkML concepts to real examples helps with understanding. Below I have selected a few requirements from the RO-Crate 1.1 specification to consider, which will showcase different features of LinkML:

* The Root Data Entity MUST have `@type` of `Dataset`
* The Root Data Entity MUST have a `name` that is a string describing the dataset.
* The Root Data Entity SHOULD have a `publisher` of type `Organization` or `Person`.
* Other data entities SHOULD have a `name` that is a string describing the entity.

## LinkML Preamble

At the top of our YAML file for our LinkML schema, we need to define some LinkML settings.

```yaml!
id: https://example.org/my_model
name: ro_crate_linkml
prefixes:
  linkml: https://w3id.org/linkml/
  schema: http://schema.org/
imports:
  - linkml:types
default_range: string
```

* `id` is an identifier for the schema (not important for a demo).
* `prefixes` work the same as in RDF. Add more as needed.
* The `imports` statement allows us to use special types defined in LinkML.
* `default_range` represents the default data type expected for properties (individual properties will override this later).

## Slots

LinkML documentation: [Slots](https://linkml.io/linkml/schemas/slots.html#slots)

Slots correspond closely to RDF properties/JSON-LD keywords. They are defined in the `slots:` section of the LinkML schema.

In our requirements, we need to describe the `name` and `publisher` properties (`@type` is special, and we will come to that later).

Here is how the `name` property can be represented in LinkML:

```yaml
slots:
  name:
    slot_uri: schema:name
    range: string
    title: Name
    description: The name of the entity
```

There are a few key fields for all slots:

* `slot_uri` links to the property definition, in this case https://schema.org/name (the `schema:` prefix is defined in the `prefixes` section of the LinkML scheme)
* `range` defines the type that values of this property should have
* `title` is a name for the slot, it is not used for validation but it is passed through to the SHACL
* `description` is a description for the slot, behaves the same as `title`

The `publisher` slot can be defined similarly, but the `range` must be changed to `Organization` or `Person`:

```yaml!
classes:
  Organization:
    class_uri: schema:Organization
  Person:
    class_uri: schema:Person

slots:
  ...
  publisher:
    slot_uri: schema:publisher
    title: Publisher
    description: The publisher of the object
    any_of:
      - range: Organization
      - range: Person
    annotations:
      sh:message: The publisher SHOULD be an Organization or a Person
      sh:severity: sh:Warning
```

The `any_of` feature is essentially an OR statement - either of the listed options are permitted. LinkML also has features like `all_of`, `exactly_one_of`, and `none_of`, which work in the same way, but these are [not currently supported when converting to SHACL](https://github.com/linkml/linkml/issues/2400).

A quirk of LinkML is that you cannot directly include a CURIE (such as `schema:Person`) as a value for `range`. Instead, a LinkML class must be defined that corresponds to that CURIE using `class_uri`. [Eli to check with Michael: how to use [imports](https://linkml.io/linkml/schemas/imports.html#imports) to get the full [schema.org LinkML schema](https://github.com/linkml/linkml-schemaorg)]

## Classes

LinkML documentation: [Classes](https://linkml.io/linkml/schemas/models.html#classes)

Classes correspond to both RDF classes (which are used as values for `@type` in JSON-LD) and SHACL shapes. Classes are defined in the `classes:` section of the LinkML schema.

Properties on classes are defined as slots. In most cases those slots should be declared in the `slots:` section and then referenced by the class, as in the example below. However, it is also possible to declare slot definitions directly within a class using the [attributes](https://linkml.io/linkml/schemas/models.html#the-attributes-slot) feature, which may be a more suitable choice if the slot is very specific to the class and unlikely to be used by other classes.

Classes can use [inheritance](https://linkml.io/linkml/schemas/inheritance.html), including [mixins](https://linkml.io/linkml/schemas/inheritance.html#mixin-classes-and-slots), to re-use slots and structures from other classes.

In our requirements, we need to describe general data entities and the Root Data Entity (RDE). The RDE can be treated as a subclass of a general data entity for datasets. (We'll skip defining a file data entity for simplicity.)

```yaml!
classes:
  ...
  DatasetDataEntity:
    title: Dataset Data Entity
    description: Dataset Data Entity properties
    class_uri: schema:Dataset
    slots:
      - name
  RootDataEntity:
    title: Root Data Entity
    description: Root Data Entity properties
    is_a: DatasetDataEntity
    slots:
      - publisher
```

The `RootDataEntity` class inherits the `class_uri` and `slots` from `DatasetDataEntity`, so these don't need to be redefined. (It would also inherit the other properties `title` and `description` if we didn't override them.)

An issue that springs up when doing validation is that we actually want each of these classes to do a slightly different thing. The `DatasetDataEntity` class is intended to define that _every_ dataset entity has a `name`, but the `RootDataEntity` class is intended to define that _one_ specific dataset entity has additional properties like `publisher`. 

How can we specify the intended target for the `RootDataEntity` class? Unfortunately, this is not straightforward - see the [tangent below](#Tangent-Defining-the-target-of-RootDataEntity) if you're interested, but the short answer is that (for now) we need to change the `class_uri` to use a custom class `ro-crate:RootDataEntity` which is defined by `roc-validator`.

### Slot usage within a class

LinkML documentation: [Slot Usage](https://linkml.io/linkml/schemas/slots.html#slot-usage)

Take another look at two of the requirements we defined earlier:
* The Root Data Entity MUST have a `name` that is a string describing the dataset.
* Other data entities SHOULD have a `name` that is a string describing the entity.

The strength of the `name` requirement is different for the different types of entity! Fortunately, LinkML allows us to tweak the definition of slots to customise them for use in specific classes.

First, let's ensure our `name` slot has a default severity defined. Since the general requirement is that a name SHOULD be present, we set `sh:severity:` to the value `sh:Warning` in the annotations.

```yaml!
slots:
  name:
    slot_uri: schema:name
    range: string
    title: Name
    description: The name of the entity
    annotations:
      sh:message: The entity SHOULD have a descriptive name
      sh:severity: sh:Warning
```

Now we need to upgrade the severity in our `RootDataEntity` class. We do this using the `slot_usage` feature (remembering that the `name` slot has been inherited from `DatasetDataEntity`):

```yaml!
classes:
  RootDataEntity:
    title: Root Data Entity
    description: Root Data Entity properties
    is_a: DatasetDataEntity
    slots:
      - publisher
    slot_usage:
      name:
        annotations:
          sh:message: The Root Data Entity MUST have a name which describes the dataset
          sh:severity: sh:Violation
```

From the LinkML slot usage docs:
>Note that LinkML schemas are [monotonic](https://en.wikipedia.org/wiki/Monotonicity_of_entailment). This means it’s not possible to override existing constraints, new constraints are always additive and “layered on”.

This means we have not actually overridden the annotations, only added extra ones. But when this schema is converted to SHACL, only the annotations from the more specific class are kept.

The `slot_usage` feature is powerful enough to tweak just about any property of the original slot - but due to the monotonicity of LinkML, it should only be used to tighten constraints, not to loosen them.

### Tangent: Defining the target of `RootDataEntity`

Unfortunately, this is not a problem I have solved yet in LinkML. LinkML supports both [rules](https://linkml.io/linkml/schemas/advanced.html#rules) with conditional statements, and [defining slots](https://linkml.io/linkml/schemas/advanced.html#defining-slots) which state that membership of a class can be inferred based on those slots. However, neither of these quite applies in the case of the RDE. The RDE is defined by being the object of the `about` property on the RO-Crate Metadata Descriptor, which itself is defined by being the node with `@id` of `ro-crate-metadata.json`. Extra fiddling is therefore required to reverse this property within the schema (perhaps using [subjectOf](https://schema.org/subjectOf)), and I don't know yet if it's possible (partly because selecting a single node by `@id` is not easy in LinkML either).

A SHACL-based workaround is present in the [roc-validator](https://github.com/crs4/rocrate-validator) library. The library defines a special class [`ro-crate:RootDataEntity`](https://github.com/crs4/rocrate-validator/blob/develop/rocrate_validator/profiles/ro-crate/ontology.ttl#L35) which can be referenced by all profiles (using the prefix `ro-crate: https://github.com/crs4/rocrate-validator/profiles/ro-crate/`). At runtime in the validator, the RDE is identified from the metadata descriptor, and the data graph of the crate is expanded to set the `@type` of the RDE to include `ro-crate:RootDataEntity` ([source](https://github.com/crs4/rocrate-validator/blob/develop/rocrate_validator/profiles/ro-crate/must/1_file-descriptor_metadata.ttl#L24)). 

The uses both the `sh:SPARQLTarget` and `sh:rule` features of SHACL, which are not supported in LinkML - though perhaps these could be fully included through slot `annotations`. That said, the `ro-crate:RootDataEntity` class _can_ be used as a `class_uri` in a LinkML schema, so if you are converting a schema to SHACL and feeding that into `roc-validator`, you can make use of their workaround (which is what I have done in [my Workflow RO-Crate implementation](https://github.com/eScienceLab/rocrate-validator/blob/04bfae450ee266b4111d74cdad773b0ef4384a46/rocrate_validator/profiles/workflow-ro-crate-linkml/workflow-ro-crate.yaml#L55)). For a full definition of the RO-Crate spec in pure LinkML, however, this issue will need to be properly navigated.

## Final Schema & Conversion to SHACL

Here's the full schema built from the examples above:

```yaml!
id: https://example.org/my_model
name: ro_crate_linkml
prefixes:
  linkml: https://w3id.org/linkml/
  schema: http://schema.org/
  ro-crate: https://github.com/crs4/rocrate-validator/profiles/ro-crate/
imports:
  - linkml:types
default_range: string

classes:
  Organization:
    class_uri: schema:Organization
  Person:
    class_uri: schema:Person
  DatasetDataEntity:
    title: Dataset Data Entity
    description: Dataset Data Entity properties
    class_uri: schema:Dataset
    slots:
      - name
  RootDataEntity:
    title: Root Data Entity
    description: Root Data Entity properties
    is_a: DatasetDataEntity
    class_uri: ro-crate:RootDataEntity
    slots:
      - publisher
    slot_usage:
      name:
        annotations:
          sh:message: The Root Data Entity MUST have a name which describes the dataset
          sh:severity: sh:Violation

slots:
  name:
    slot_uri: schema:name
    range: string
    title: Name
    description: The name of the entity
    annotations:
      sh:message: The entity SHOULD have a descriptive name
      sh:severity: sh:Warning
  publisher:
    slot_uri: schema:publisher
    title: Publisher
    description: The publisher of the object
    any_of:
      - range: Organization
      - range: Person
    annotations:
      sh:message: The publisher SHOULD be an Organization or a Person
      sh:severity: sh:Warning

```

We use the following LinkML CLI command to convert this schema to SHACL (assuming it was saved as `ro-crate.yml`):

```
linkml generate shacl --include-annotations --non-closed ro-crate.yml
```

Options:
* `--include-annotations` ensures slot `annotations` are passed through to the SHACL
* `--non-closed` is essential when generating SHACL. LinkML is "closed" by default (meaning objects may not have properties other than their defined slots), but SHACL shapes are normally intended to be open, and in RO-Crate in particular any entity may have additional properties that should be ignored.

```ttl
@prefix ns1: <sh:> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix ro-crate: <https://github.com/crs4/rocrate-validator/profiles/ro-crate/> .
@prefix schema1: <http://schema.org/> .
@prefix sh: <http://www.w3.org/ns/shacl#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

schema1:Dataset a sh:NodeShape ;
    sh:closed false ;
    sh:description "Dataset Data Entity properties" ;
    sh:ignoredProperties ( rdf:type schema1:publisher ) ;
    sh:name "Dataset Data Entity" ;
    sh:property [ sh:datatype xsd:string ;
            sh:description "The name of the entity" ;
            sh:maxCount 1 ;
            sh:name "Name" ;
            sh:nodeKind sh:Literal ;
            sh:order 0 ;
            sh:path schema1:name ;
            ns1:message "The entity SHOULD have a descriptive name"^^xsd:string ;
            ns1:severity ns1:Warning ] ;
    sh:targetClass schema1:Dataset .

ro-crate:RootDataEntity a sh:NodeShape ;
    sh:closed false ;
    sh:description "Root Data Entity properties" ;
    sh:ignoredProperties ( rdf:type ) ;
    sh:name "Root Data Entity" ;
    sh:property [ sh:datatype xsd:string ;
            sh:description "The name of the entity" ;
            sh:maxCount 1 ;
            sh:name "Name" ;
            sh:nodeKind sh:Literal ;
            sh:order 1 ;
            sh:path schema1:name ;
            ns1:message "The Root Data Entity MUST have a name which describes the dataset"^^xsd:string ;
            ns1:severity ns1:Violation ],
        [ sh:description "The publisher of the object" ;
            sh:maxCount 1 ;
            sh:name "Publisher" ;
            sh:or ( [ sh:class schema1:Organization ] [ sh:class schema1:Person ] ) ;
            sh:order 0 ;
            sh:path schema1:publisher ] ;
    sh:targetClass ro-crate:RootDataEntity .

schema1:Organization a sh:NodeShape ;
    sh:closed false ;
    sh:ignoredProperties ( rdf:type ) ;
    sh:targetClass schema1:Organization .

schema1:Person a sh:NodeShape ;
    sh:closed false ;
    sh:ignoredProperties ( rdf:type ) ;
    sh:targetClass schema1:Person .
```

To incorporate this into `roc-validator`, follow these [steps to create a profile](https://rocrate-validator.readthedocs.io/en/latest/11_writing_a_profile/) (changing step 4 to use the `profile_name.yaml` file instead). Note that I haven't tested this working example myself, so I can't guarantee it will work as intended!

You can also browse my [in-development implementation of the Workflow RO-Crate profile](https://github.com/eScienceLab/rocrate-validator/tree/04bfae450ee266b4111d74cdad773b0ef4384a46/rocrate_validator/profiles/workflow-ro-crate-linkml) as a reference. 

Note that as of January 2025, the LinkML SHACL converter has a number of significant bugs that block some checks from being possible. See the bugs on the LinkML GitHub: https://github.com/linkml/linkml/issues?q=is%3Aissue+is%3Aopen+label%3Agenerator-shacl
