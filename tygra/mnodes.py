from tygra.attributes import Attributes
from tygra.mobjects import MObject
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Self, Union
from tygra.util import AddrServer, IDServer
import tygra.app as app
from tygra.weaklist import WeakList

	
class MNode(MObject):
	def __init__(self, tgmodel, typ:Union[Self,list[Self],None]=None, idServer:IDServer=None, _id:Optional[int]=None):
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
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
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
