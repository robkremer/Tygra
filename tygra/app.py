"""
Application wide 'constants'.
"""
#################################################################################
# (c) Copyright 2023, Rob Kremer, MIT open source license.						#
#																				#
# Permission is hereby granted, free of charge, to any person obtaining a copy	#
# of this software and associated documentation files (the "Software"), to deal	#
# in the Software without restriction, including without limitation the rights	#
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell		#
# copies of the Software, and to permit persons to whom the Software is			#
# furnished to do so, subject to the following conditions:						#
#																				#
# The above copyright notice and this permission notice shall be included in all#
# copies or substantial portions of the Software.								#
# 																				#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR	#
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,		#
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE	#
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER		#
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,	#
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE	#
# SOFTWARE.																		#
#################################################################################

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

DEBUG_MENUS = True
"When true adds debug items to menus."