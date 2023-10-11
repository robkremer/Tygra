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

from tygra.mnodes import MNode
from tygra.mobjects import MObject
import xml.etree.ElementTree as et
from ast import literal_eval
from abc import ABC, abstractmethod # Abstract Base Class
from typing import Any, Optional, Union, Tuple, List, Dict
from tygra.util import AddrServer, IDServer, treeFlatten
from tygra.attributes import Attributes, AttrOwner
import tygra.app as app

class MRelation(MObject):

	@property
	def isIsa(self):
		return False
		
	@property
	def system(self) -> bool:
		return super().system
		
	def __init__(self, tgmodel, frm:MNode, to:MNode, typ=None, idServer:IDServer=None, _id:Optional[int]=None):
		"""
		:param tgmodel: The model container object
		:type tgmodel: TGModel
		:param frm: The source node of this relation, must be the same class as *to*\ .
		:param to: The destination node of this relation, must be the same class as *from*\ .
		:param typ: A MRelation that acts as the supertype; REQUIRED, but must be none during reading from persistent store.
		:type typ: Union[Self,List[Self],None]
		:param IdServer: required.
		:param _id: DO NOT USE. Reserved for the persistent storage system. *_id* is None if 
			this constructor is called at runtime, an *int* if called when reading from persistent store.
		"""
		self.fromNode = frm
		self.toNode = to
		super().__init__(tgmodel, typ, idServer=idServer, _id=_id)
# 		self.validateReferents() # may raise exceptions
# 		self.fromNode.addRelation(self)
# 		self.toNode.addRelation(self)
		if _id is None: # we're not reading from persistent store
			self._post__init__()

	def _post__init__(self, addrServer:Optional[AddrServer]=None):
		if addrServer is not None:
			if type(self.fromNode) == str:
				self.fromNode = addrServer.idLookup(self.fromNode)
			if type(self.toNode) == str:
				self.toNode = addrServer.idLookup(self.toNode)
#		self.validateReferents() # may raise exceptions
		if self.validate() > 0:
			raise AttributeError("MRelation._post__init__({self}): Validation failed.")
		self.fromNode.addRelation(self)
		self.toNode.addRelation(self)
		assert self in self.fromNode.relations
		assert self in self.toNode.relations
		
	def validate(self) -> int:
		errCount = 0
		errCount += super().validate()
		errCount += self.validateReferents()
		return errCount			

	def validateReferents(self) -> bool:
		errCount = 0
		if not ((isinstance(self.fromNode, MNode) and isinstance(self.toNode, MNode)) or \
		        (isinstance(self.fromNode, MRelation) and isinstance(self.toNode, MRelation))): 
#			raise TypeError(f'MRelation.validateReferents(): {type(self.fromNode)}, {type(self.toNode)} | fromNode ({type(self.fromNode).__name__}) and toNode ({type(self.toNode).__name__}) must be either both MNodes or both MRelations.')
			self.tgmodel.logger.write(f'{type(self.fromNode)}, {type(self.toNode)} | fromNode ({type(self.fromNode).__name__}) and toNode ({type(self.toNode).__name__}) must be either both MNodes or both MRelations.', level="error")
			return 1
		
		for parent in self.isparent(): # to- and from- nodes must be subtypes of the parents' to- and from- nodes.
			if not self.toNode.isa(parent.toNode): 
#				raise TypeError(f'MRelation.validateReferents [{self}]: toNode {self.toNode} must be a subtype of {parent.toNode}.')
				self.tgmodel.logger.write(f'toNode {self.toNode} must be a subtype of {parent.toNode}.', level="error")
				errCount += 1
			if not self.fromNode.isa(parent.fromNode): 
#				raise TypeError(f'MRelation.validateReferents [{self}]: fromNode {self.fromNode} must be a subtype of {parent.fromNode}.')
				self.tgmodel.logger.write(f'fromNode {self.fromNode} must be a subtype of {parent.fromNode}.', level="error")
				errCount += 1
		return errCount

	### DESTRUCTOR #######################################################################
	
	def delete(self):
		try: 
			self.fromNode.notifyRelationDeletion(self)
		except Exception as ex: 
			self.tgmodel.logger.write(f'Unexpected exception calling notifyRelationDeletion() on fromNode "{self.fromNode}"', level='error', exception=ex)
		try: 
			self.toNode  .notifyRelationDeletion(self)
		except Exception as ex: 
			self.tgmodel.logger.write(f'Unexpected exception calling notifyRelationDeletion() on toNode "{self.toNode}"', level='error', exception=ex)
		self.fromNode = None
		self.toNode = None
		super().delete()

	### PERSISTENCE ######################################################################

	def serializeXML(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().serializeXML()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().serializeXML()
		assert isinstance(self.fromNode, MObject), f'Unexpected type for fromNode: {type(self.fromNode).__name__}, "{self.fromNode}".'
		elem.set('fromNode', str(self.fromNode.idString))
		elem.set('toNode', str(self.toNode.idString))
# 		elem.set('isa', str(self._isa))
		return elem

	@classmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> Tuple[List[Any], Dict[str, Any]]:
		args = []
		kwargs = dict()
		tgmodel = addrServer.idLookup(elem.get('tgmodel'))
		args.append(tgmodel)

		fromNode = elem.get('fromNode')
		try: # Node might not have been loaded yet.
			fromNode = addrServer.idLookup(fromNode) if fromNode!=None and fromNode!="" else None
		except: # The node hasn't been loaded, so we leave it as the ID string for the constructor to look it up later
			pass
		args.append(fromNode)

		toNode = elem.get('toNode')
		try: # Node might not have been loaded yet.
			toNode = addrServer.idLookup(toNode) if toNode!=None and toNode!="" else None
		except: # The node hasn't been loaded, so we leave it as the ID string for the constructor to look it up later
			pass
		args.append(toNode)

		idStr = elem.get('id')
		id = IDServer.getLocalID(idStr) if idStr else None
		kwargs["_id"] = id
		kwargs["idServer"] = tgmodel
		
		return args, kwargs
	
	def unserializeXML(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().unserializeXML(elem, addrServer)

	### ATTRIBUTES #######################################################################

	def getTop(self):
		return self.tgmodel.topRelation

	### EVENT HANDLING ###################################################################
	
	def notifyNodeDeletion(self, node):
		if node in [self.toNode, self.fromNode]:
			self.delete()
		else:
			self.tgmodel.logger.write(f'Got notification for node "{node}" that isn\'t a fromNode or toNode.', level="warning")
			
	### SEMANTICS ########################################################################
	
	class RelBehaviour(ABC):
		@abstractmethod
		def isRelated(self, relation, fromNode, toNode): pass
		
	class SymetricRelation(RelBehaviour):
		def isRelated(self, relation, toNode):
			if toNode is not None: # return a bool
				return relation.fromNode is toNode
			else: # return a tree list
				return [relation.toNode, relation.fromNode]
				
	class TransitiveRelation(RelBehaviour):
		def isRelated(self, relation, toNode):
			if toNode is not None: # return a bool
				for rel in toNode.relations:
					if relation.isaSibling(rel):
						if rel.isRelatedTo(toNode): return True
				return False
			else: # return a tree list
				for rel in toNode.relations:
					result = []
					if relation.isaSibling(rel):
						result.append(rel.isRelatedTo())
				
		
	def isRelatedTo(self, toNode:MObject=None): # -> tree
		"""
		:param fromNode: A node or relation as the first element of a relation. Default is
			this relation's *self.fromNode*.
		:param toNode: A node or relation as the 2nd element in a relation. If specified,
			makes this a (boolean or list) query.
		:return: Depends on the two arguments:
			*     toNode:** returns a bool indicating whether this relation
												relates it's *self.fromNode* to the *toNode*.
			* not toNode:** returns a tree list of all the MObjects
												that are related to the *self.FromNode* 
												this relation's siblings or 
												decendents.  
		"""
		if toNode: # return a bool
			if self.toNode is toNode: return True
			result = False
			for behaviour in self.relBehaviours:
				result = behaviour.isRelated(self, toNode)
				if result: break
			return result
		else: # return a tree list
			result = []
			for behaviour in self.relBehaviours:
				for n in result.copy():
					for rel in toNode.relation:
						if self.isaSibling(rel):
							result += behaviour.isRelated(self)
			return result
		
	def isRelation(self) -> bool:
		return True
		
	### Debugging support ################################################################
	
	def __str__(self):
		try:
			label = self.attrs["label"]
		except:
			label = '<no label>'
		try:
			toNode =   '<no toNode>'   if self.toNode   is None else self.toNode.idString
			fromNode = '<no fromNode>' if self.fromNode is None else self.fromNode.idString
			return f'({type(self).__name__} [{self.idString}, "{label}", fromNode={fromNode}, toNode={toNode}])'
		except:
			return f'({type(self).__name__} [{self.idString}, "{label}"]{" *DELETED*" if self._deleted else ""})'
			

	def __repr__(self):
		return self.__str__()



class Isa(MRelation):
	"""
	All objects of this class (except the top isa, *self.tgmodel.isa*) share the same
	*Attributes* object which is stored as a class variable (*Isa.attrs*). The *getAttrParents()*
	method thus returns the *Attributes* object from *self.tgmodel.isa*, or [] if the
	object actually IS *self.tgmodel.isa*.
	This avoids endless recursion in an isa relation being isa to isa.
	"""

	class IsaAttributes(Attributes):
		def __init__(self, owner:Optional[AttrOwner]=None, top=None):
			self.top = top
			super().__init__(owner)
		def getParents(self):
			return [self.top]
				
	attrs:Optional[IsaAttributes] = None
		
	@property
	def isIsa(self):
		return True
		
	commonAttrs = None #:Optional[Self.IsaAttributes]
		
	@property
	def system(self) -> bool:
		return super().system or self.fromNode.system
		
	def __init__(self, tgmodel, frm:MNode, to:MNode, idServer:IDServer=None, _id:Optional[int]=None):
		super().__init__(tgmodel, frm, to, typ=None, idServer=idServer, _id=_id)
		
		if hasattr(self.tgmodel, "isa"): # if the model container has isa, we have the mother ISA existing and this instance isn't it.
			if Isa.commonAttrs is None:
				Isa.commonAttrs = Isa.IsaAttributes(owner=self, top=self.tgmodel.isa.attrs)
			self.attrs.owner = None
			self.attrs = Isa.commonAttrs
			
	def _post__init__(self, addrServer:Optional[AddrServer]=None):
		super()._post__init__(addrServer)
		toAncestors = treeFlatten(self.toNode.isa())[1:]# ancestors without the to itself
		deletions = []
		for t in toAncestors:
			for r in self.fromNode.relations:
				if r.isIsa and r.toNode is t:
					deletions.append(r)
		for r in deletions:
			self.tgmodel.logger.write(f'Deleting redundant relation from "{self.fromNode.attrs["label"]}" ({self.fromNode.idString}) to "{r.toNode.attrs["label"]}" ({r.toNode.idString})', level="info")
			r.delete()

	def validateReferents(self) -> int:
		errCount = 0
		errCount += super().validateReferents()

		# Sanity checks
		# check for redundancy (this relation)
		frmAncestors = treeFlatten(self.fromNode.isa())[1:] # ancestors without the frm itself
		if self.toNode in frmAncestors and not self.toNode is self.fromNode: # and frmAncestors[0] != tgmodel.topNode:
#			raise TypeError(f'Isa.validateReferents(): "{self.fromNode.attrs["label"]}" {self.fromNode.idString} is already a subtype of "{self.toNode.attrs["label"]}" {self.toNode.idString}. {frmAncestors}')
			self.tgmodel.logger.write(f'{self.fromNode} is already a subtype of {self.toNode}. {frmAncestors}', level="error")
			errCount += 1
		# check for circularity
		toAncestors = treeFlatten(self.toNode.isa())[1:]# ancestors without the to itself
		if self.fromNode in toAncestors: # and toAncestors[0] != tgmodel.topNode:
#			raise TypeError(f'Isa.validateReferents(): This relation would create a circular type hierarchy.')
			self.tgmodel.logger.write(f'This relation would create a circular type hierarchy.', level="error")
			errCount += 1
		return errCount

	def validateType(self, typ, idServer):
		pass

	def getTop(self):
		return self.tgmodel.isa
		
	def getAttrParents(self) -> List[Attributes]:
		if self is self.tgmodel.isa: 	return []
		else:							return [self.tgmodel.isa.attrs]

	def serializeXMLAttrs(self, elem:et.Element):
		"""
		Don't save the *attrs* as all the isa's share one *Attributes* (a class variable).
		"""
		pass
