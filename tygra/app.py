"""
Application wide 'constants'.
"""

APP_LONG_NAME = "TypedGraphs"
APP_SHORT_NAME = "TyGra"
VERSION = "0.0"
APP_FILE_EXTENSION = "tgxml"


CONTAINER_ID = "(0)"

TOP_NODE = "T"
"The label for the top model node."

TOP_RELATION = "REL"
"The label for the top model relation."

ISA = "ISA"
"The label for the isa relation."

RESERVED_ID = 255
"The number of ID's to be considered 'system ids', not allocated to user nodes and relations."

SYS_ATTRIBUTES = ["fillColor", "borderColor", "textColor", "shape", "label", "type", "aspectRatio", "minSize"]