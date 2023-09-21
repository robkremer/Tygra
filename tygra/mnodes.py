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

from tygra.attributes import Attributes
from tygra.mobjects import MObject
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Union, Tuple, List, Dict
from tygra.util import AddrServer, IDServer
import tygra.app as app
from tygra.weaklist import WeakList

	
class MNode(MObject):
	def __init__(self, tgmodel, typ=None, idServer:IDServer=None, _id:Optional[int]=None):
		"""
		Constructs an MNode.
		
		:param typ: The type of this MNode (\ *ISA* relations will automatically be created to this node). May
			be either a single of instance of a type MNode or a list of isntance of type MNodes.
		:type typ: Union[Self,List[Self],None]
		"""
		super().__init__(tgmodel, typ, idServer=idServer, _id=_id)
# 		assert self.id != 259

	def delete(self):
		super().delete()

	### PERSISTENCE ######################################################################

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().xmlRepr()
		return elem

	@classmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> Tuple[List[Any], Dict[str, Any]]:
		args = []
		kwargs = dict()
		tgmodel = addrServer.idLookup(elem.get('tgmodel'))
		args.append(tgmodel)

		idStr = elem.get('id')
		id = IDServer.getLocalID(idStr) if idStr else None
		kwargs["_id"] = id
		kwargs["idServer"] = tgmodel
		
		return args, kwargs
	
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().xmlRestore(elem, addrServer)

	### MISC #############################################################################

	def isRelation(self) -> bool:
		return False
		
	def getTop(self):
		return self.tgmodel.topNode

	### EVENT HANDLING ###################################################################

# def test():
# 	n = MNode()
# 	n.addRelation(None)

# if __name__ == "__main__":
# 	test()

# from tygra.mrelations import MRelation
