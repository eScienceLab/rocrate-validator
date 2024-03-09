# Define allowed RDF extensions and serialization formats as map
import typing


# Define allowed RDF extensions and serialization formats as map
RDF_SERIALIZATION_FILE_FORMAT_MAP = {
    "xml": "xml",
    "pretty-xml": "pretty-xml",
    "trig": "trig",
    "n3": "n3",
    "turtle": "ttl",
    "nt": "nt",
    "json-ld": "json-ld"
}

# Define allowed RDF serialization formats
RDF_SERIALIZATION_FORMATS_TYPES = typing.Literal[
    "xml", "pretty-xml", "trig", "n3", "turtle", "nt", "json-ld"
]
RDF_SERIALIZATION_FORMATS = typing.get_args(RDF_SERIALIZATION_FORMATS_TYPES)

# Define allowed inference options
VALID_INFERENCE_OPTIONS_TYPES = typing.Literal["owl", "rdfs", "both", None]
VALID_INFERENCE_OPTIONS = typing.get_args(VALID_INFERENCE_OPTIONS_TYPES)
