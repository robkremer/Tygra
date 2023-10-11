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

import tygra.attributes as at
from abc import ABC, abstractmethod # Abstract Base Class
from typing import final, Any, Optional, Type, Union
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

	def serializeXML(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().serializeXML()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().serializeXML()
		elem.set('tgview', self.tgview.idServer.getIDString(self.tgview.id))
		elem.set('model', self.model.idString)
		return elem

	def unserializeXML(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().unserializeXML(elem, addrServer)
