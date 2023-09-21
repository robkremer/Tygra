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
		:param typ:
		:type typ: Union[Self,List[Self],None]
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
		self.validateReferents() # may raise exceptions
		self.fromNode.addRelation(self)
		self.toNode.addRelation(self)
		assert self in self.fromNode.relations
		assert self in self.toNode.relations

	def validateReferents(self):
		if not ((isinstance(self.fromNode, MNode) and isinstance(self.toNode, MNode)) or \
		        (isinstance(self.fromNode, MRelation) and isinstance(self.toNode, MRelation))): 
		    raise TypeError(f'MRelation.__init__(): {type(self.fromNode)}, {type(self.toNode)} | fromNode ({type(self.fromNode).__name__}) and toNode ({type(self.toNode).__name__}) must be either both MNodes or both MRelations.')
		for parent in self.isparent():
			if not self.toNode.isa(parent.toNode): 
				raise TypeError(f'MRelation.validateReferents [{self}]: toNode {self.toNode} must be a subtype of {parent.toNode}.')
			if not self.fromNode.isa(parent.fromNode): 
				raise TypeError(f'MRelation.validateReferents [{self}]: fromNode {self.fromNode} must be a subtype of {parent.fromNode}.')
		return True

	### DESTRUCTOR #######################################################################
	
	def delete(self):
		super().delete()
		try: 
			self.fromNode.notifyRelationDeletion(self)
		except Exception as ex: 
			self.tgmodel.logger.write(f'MRelation.delete() [{self}]: Unexpected exception calling notifyRelationDeletion() on fromNode "{self.fromNode}"', level='error', exception=ex)
		try: 
			self.toNode  .notifyRelationDeletion(self)
		except Exception as ex: 
			self.tgmodel.logger.write(f'MRelation.delete() [{self}]: Unexpected exception calling notifyRelationDeletion() on toNode "{self.toNode}"', level='error', exception=ex)
		self.fromNode = None
		self.toNode = None

	### PERSISTENCE ######################################################################

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().xmlRepr()
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
	
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().xmlRestore(elem, addrServer)

	### ATTRIBUTES #######################################################################

	def getTop(self):
		return self.tgmodel.topRelation

	### EVENT HANDLING ###################################################################
	
	def notifyNodeDeletion(self, node):
		if node in [self.toNode, self.fromNode]:
			self.delete()
		else:
			self.tgmodel.logger.write(f'MRelation.notifyNodeDeletion() [{self}]: Got notification for node "{node}" that isn\'t a fromNode or toNode.', level="warning")
			
	### SEMANTICS ########################################################################
	
	class RelBehaviour(ABC):
		@abstractmethod
		def isRelated(self, relation, fromNode, toNode): pass
		
	class SymetricRelation(RelBehaviour):
		def isRelated(self, relation, toNode):
			if toNode: # return a bool
				return relation.fromNode is toNode
			else: # return a tree list
				return [relation.toNode, relation.fromNode]
				
	class TransitiveRelation(RelBehaviour):
		def isRelated(self, relation, toNode):
			if toNode: # return a bool
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
		super().__init__(tgmodel, frm, to, idServer=idServer, _id=_id)
		
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
			self.tgmodel.logger.write(f'Isa.__init__(): Deleting redundant relation from "{self.fromNode.attrs["label"]}" ({self.fromNode.idString}) to "{r.toNode.attrs["label"]}" ({r.toNode.idString})', level="info")
			r.delete()

	def validateReferents(self):
		super().validateReferents()
		if not self.toNode.attrs['type']:
		    raise TypeError(f'MRelation.__init__(): toNode {self.toNode} must be a type, not a individual.')
		    
		# Sanity checks
		# check for redundancy (this relation)
		frmAncestors = treeFlatten(self.fromNode.isa())[1:] # ancestors without the frm itself
		if self.toNode in frmAncestors and not self.toNode is self.fromNode: # and frmAncestors[0] != tgmodel.topNode:
			raise TypeError(f'Isa.__init__(): "{self.fromNode.attrs["label"]}" {self.fromNode.idString} is already a subtype of "{self.toNode.attrs["label"]}" {self.toNode.idString}. {frmAncestors}')
		# check for circularity
		toAncestors = treeFlatten(self.toNode.isa())[1:]# ancestors without the to itself
		if self.fromNode in toAncestors: # and toAncestors[0] != tgmodel.topNode:
			raise TypeError(f'Isa.__init__(): This relation would create a circular type hierarchy.')

	def validateType(self, typ, idServer):
		pass

	def getTop(self):
		return self.tgmodel.isa
		
	def getAttrParents(self) -> List[Attributes]:
		if self is self.tgmodel.isa: 	return []
		else:							return [self.tgmodel.isa.attrs]

	def xmlReprAttrs(self, elem:et.Element):
		"""
		Don't save the *attrs* as all the isa's share one *Attributes* (a class variable).
		"""
		pass
