import tygra.attributes as at
from abc import ABC, abstractmethod # Abstract Base Class
from typing import final, Any, Optional, Type, Self, Union
import xml.etree.ElementTree as et
from ast import literal_eval
from string import whitespace
import sys
from tygra.util import PO, AddrServer, IDServer
from tygra.attributes import Attributes
from tygra.weaklist import WeakList
import tygra.app as app
from tygra.mobjects import ModelObserver, MObject

class VObject(PO, at.AttrObserver, ModelObserver): #, at.AttrOwner

	def __init__(self, tgview, model, idServer:IDServer=None, _id:Optional[int]=None):
		super().__init__(idServer=idServer, _id=_id)
		assert self.id is not None
		self.tgview = tgview
		self.tag = "ID"+str(self.id)
		self.relations = WeakList()
		assert model != None
		self.model = model
		self._deleted = False
		model.addObserver(self)
		
	def delete(self):
		self._deleted = True
		self.model.removeObserver(self)
		self.model = None
		self.tgview = None
		self.relations = None
		

	### PERSISTENCE ######################################################################

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().xmlRepr()
		elem.set('tgview', self.tgview.idServer.getIDString(self.tgview.id))
		elem.set('model', self.model.idString)
		return elem

	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().xmlRestore(elem, addrServer)
