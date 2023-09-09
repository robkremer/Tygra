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


class ModelObserver(ABC):
	@abstractmethod
	def notifyModelChanged(self, modelObj, modelOperation:str):
		"""
		:param modelOperation: "mod", "del" 
		"""
		pass
			
class MObject(PO, at.AttrOwner, at.AttrObserver): #, ModelObserver):

	@property
	def system(self) -> bool:
		return self.id < app.RESERVED_ID
		
	def __init__(self, tgmodel, typ:Union[Self,list[Self],None]=None, idServer:IDServer=None, _id:Optional[int]=None):
		super().__init__(idServer=idServer, _id=_id)
		assert self.id is not None
		self.tgmodel = tgmodel
		self.observers = WeakList()
		self.relations = WeakList()
		self._deleted = False
		self.attrs = at.Attributes(owner=self)
		self.attrs.addObserver(self)
		from tygra.mrelations import Isa
		if _id is None and not (self.tgmodel.topNode is None or self.tgmodel.topRelation is None) and not isinstance(self, Isa):
			if not isinstance(typ, list):
				typ = [typ]
			assert isinstance(typ, list)
			for t in typ:
				self.validateType(t, idServer) # may raise an exception
			for t in typ:
				Isa(self.tgmodel, frm=self, to=t, idServer=idServer)
		self.tgmodel.register(self)
		
	def validateType(self, typ:Optional[Self], idServer):
		if not (self.tgmodel.topNode is None or self.tgmodel.topRelation is None): 
			# we are not being deserialized and this isn't topNode or topRelation
			if typ == None:
				raise TypeError("MObject.__init__(): Argument 'type' is required.")
			if self.isRelation() != typ.isRelation():
				raise TypeError(f'MObject.__init__(): Argument typ {typ} is a {"relation" if typ.isRelation() else "node"}, which does not match object being created.')
		
	def delete(self):
		self._deleted = True

		#notify the observers and get rid of pointers to them
		self.notifyObservers('del')
		if len(self.observers) > 0:
			self.tgmodel.logger.write(f'MObject.delete() [{self}]: After sending a "del" to observers, they should all have done a removeObserver(). Still have {self.observers}.', level="error")
		self.observers = None
		
		# notify and get rid of relations
		rels = list(self.relations) # copy. The relations should delete themselves while we are iterating.
		for r in rels:
			try: # relation might already have been deleted
				r.notifyNodeDeletion(self)
			except Exception as ex:
				self.tgmodel.logger.write("MObject.delete(): Unexpected error in notification:", level="warning", exception=ex)
# 			assert r not in self.tgmodel._relations
		if len(self.relations) > 0:
			self.tgmodel.logger.write(f'MObject.delete() [{self}]: After sending notifyNodeDeletion to relations, they should all have deleted themselves and removed themselves from the list. Still have {self.relations}', level="error")
		self.relations = None

		#tell the container
		self.tgmodel.unregister(self)
		self.tgmodel = None
		

	### PERSISTENCE ######################################################################

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().xmlRepr()
		elem.set('tgmodel', self.tgmodel.idServer.getIDString(self.tgmodel.id))
		elem.set('class', type(self).__name__)
		self.xmlReprAttrs(elem)
		return elem

	def xmlReprAttrs(self, elem:et.Element):
		if len(self.attrs.attrs) > 0:
			elem.append(self.attrs.xmlRepr())
			
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().xmlRestore(elem, addrServer)
		attrsElem = elem.find('Attributes')
		if attrsElem:
			attrs = self.makeObject(attrsElem, addrServer, Attributes)
			for k,v in attrs.attrs.items():
				self.attrs.attrs[k] = v
		
	### ATTRIBUTES #######################################################################

	def getAttrParents(self) -> list[Attributes]:
		top = self.getTop()
		if self == top:
			return []
		ret = []
		for r in self.relations:
			if r.isIsa and self == r.fromNode:
				ret.append(r.toNode.attrs)
		if len(ret) == 0:
			ret = [top.attrs]
		return ret
	
# 	def addAttrs(self, name, value, override=True, final=False, editable=True):
# 		"""
# 		Utility method for constructors: Do the using *attrs.add(...)*, but in the case
# 		of *override=False* do not add the if *name* already exists in the parent
# 		hierarchy.
# 		"""
# 		if not override and name in self.attrs.keys():
# 			return
# 		self.attrs.add(name, value, final=final, editable=editable)
# 

	### OBSERVER PATTERN #################################################################

	def addObserver(self, observer:ModelObserver):
		if not isinstance(observer, ModelObserver):
			raise TypeError(f'MObject.addObserver(): argument of type {type(observer).__name__} is not a ModelObserver.')
		self.observers.append(observer)
		
	def removeObserver(self, observer:ModelObserver):
# 		if self._deleted: return
# 		if observer in self.observers:
# 			self.observers.remove(observer)
# 		else:
# 			self.tgmodel.logger.write(f'MObject.removeObserver() called with an unregistered observer "{observer}" of type {type(observer).__name__}.', level="warning")
		try:
			if self.observers is not None: # need this check for the case of self is deleting
				self.observers.remove(observer)
		except Exception as ex:
			self.tgmodel.logger.write(f'MObject.removeObserver() [{self}]: Unexpected exception. Probably called with an unregistered observer "{observer}" of type {type(observer).__name__}.', level="warning", exception=ex)
		
	def notifyObservers(self, op, info=None): #, observable=None):
		if self.observers is not None:
			deletions = []
			obs = list(self.observers) # copy. might be deleting going on during the process...
			for o in obs:
				try:
					o.notifyModelChanged(self, op, info=info)
				except Exception as ex:
					self.tgmodel.logger.write(f'MObject.notifyObservers() [{self}]: Exception in call to notifyModelChanged for observer "{o}"', level="warning", exception=ex)
					if hasattr(o, "_deleted") and o._deleted:
						deletions.append(o)
						self.tgmodel.logger.write(f'    - object had been marked as deleted, so removing it from observers list.', level="warning")
			for d in deletions:
				self.observers.remove(d)
			
	### Semantics ########################################################################
	
	def isa(self, nodeType:Optional[Union[Self, list[Self]]]=None) -> Union[bool, list[Self]]:
		"""
		Check if this *MObject* is an isa-decendent of *nodeType* as related through
		some chain of isa-relations. Or, if *nodeType* is *None*, then return a tree-list
		of ALL isa-supertypes of this *MObject*.
	
		:param nodeType: The *MObject* or a list of *MObjects* to serve a type representation
			or None which the following interpretation:
			* None: return a tree-list of all the isa-parents of this *MObject*. You can
			flatten this tree-list to a simple list using *treeFlatten()*\ .
			* *MObject*: return True iff *nodeType* is a isa-parent of this *MObject*.
			* *[MObject]*: return True iff EVERY element of *nodeType* is a isa-parent of this *MObject*.
		:return: a bool or a tree-list as above.
		"""
		if nodeType is None:
			if self in [self.tgmodel.topNode, self.tgmodel.topRelation]: return [self]
			ret = [self]
			for r in self.relations:
				if r.isIsa and r.fromNode is self:
					children = r.toNode.isa()
					ret += children
			return [self, ret] if len(ret)>0 else [self]
		elif isinstance(nodeType, list):
			for nt in nodeType:
				if not self.isa(nt):
					return False
			return True
		else:
			assert type(nodeType) == type(self)
			if nodeType==self: return True
			if self in [self.tgmodel.topNode, self.tgmodel.topRelation]: return False 
			for r in self.relations:
				if r.isIsa and r.fromNode is self:
					if r.toNode.isa(nodeType):
						return True
			return False
		
	def isparent(self, nodeType:Optional[Union[Self, list[Self]]]=None) -> Union[bool, list[Self]]:
		"""
		Check if this *MObject* is an immediate isa-child of *nodeType* as related through
		a single isa-relation. Or, if *nodeType* is *None*, then return a tree-list
		of ALL immediate isa-parents of this *MObject*.

		:param nodeType: The *MObject* or a list of *MObjects* to serve a type representation
			or None which the following interpretation:
			* None: return a list of all the isa-parents of this *MObject*\ .
			* *MObject*: return True iff *nodeType* is a isa-parent of this *MObject*\ .
			* *[MObject]*: return True iff EVERY element of *nodeType* is a isa-parent of this *MObject*\ .
		:return: a bool or a tree-list as above.
		"""
		if nodeType is None:
			ret = []
			for r in self.relations:
				if r.isIsa and r.fromNode is self:
					ret.append(r.toNode)
			return ret
		elif isinstance(nodeType, list):
			for nt in nodeType:
				if not self.isparent(nt):
					return False
			return True
		else:
			assert type(nodeType) == type(self)
			for r in self.relations:
				if r.isIsa and r.fromNode is self:
					if r.toNode is nodeType:
						return True
			return False
		
	def isRelatedTo(self, relType, toNode:Self=None, _omit:set=set()) -> set[Self]:
		"""
		Check if this *MObject* is related to *nodeType* as related through
		some chain of relations that are subtypes of *reltype*. Or, if *nodeType* is *None*, 
		then return the set of ALL *MObject*s so related to *MObject*. 
	
		.. note::
		   This is not a simple "return the *toNode*s end of the *MObject*'s conforming relations",
		   as it also takes account of the relation's transitive, symmetric, and reflective
		   properties.
	
		:param relType: The *MRelation* or a list of *MObjects* to serve a type representation.
			The search will ONLY follow relations that are a isa-subtype of *relType*, which
			may be a simple MObject, or a list of MObjects.
		:param toNode: A node or relation as the 2nd element in a relation. If specified,
			makes this a (boolean or list) query. May be an *MObject* or None
			or None which the following interpretation:
			* *None*: return a *set* of all the *MObjects* related through some *MRelation*
			that is a subtype of *relType*. 
			* *MObject*: return True iff *toNode* is related to this *MObject* through
			some chain of relations that are subtypes of *relType*\ .
		:param _omit: Should never be used. Used ONLY by relational properties to prevent
			infinite recursion in following relation chains.
		:return: Depends on the *ToNode* argument, as above.
		"""
		from tygra.mrelations import MRelation
		assert isinstance(relType, MRelation), f'MObject.isRelatedTo() [MObject]: Argument relType must be a MRelation or list of MRelations, but got argument of type {type(relType).__name__}.'
		if toNode: # return a bool
			for r in self.relations:
				if r.isa(relType):
					if r.fromNode is self and r.toNode is toNode: return True
					for behaviour in r.properties:
						if behaviour.isRelated(relType, self, r, toNode, _omit=_omit.union([toNode])):
							return True
			return False
		else: # return a tree list
			result = []
			for r in self.relations:
				if r.isa(relType):
					if r.fromNode is self: 
						result.append(r.toNode)
					for behaviour in r.properties:
						related = behaviour.isRelated(relType, self, r, _omit=_omit)#.union(result))
						if len(related): result += related
			return set(result) 
	
	@abstractmethod	
	def getTop(self) -> Self:
		"""
		Subclasses must implement this method to return the Top object for their class.
		Used in *self.getAttrParents* to return this object's *Attributes* object if 
		there is no other parent.
		"""
		pass
	
	@abstractmethod
	def isRelation(self) -> bool:
		pass
		
	### Event Handling ###################################################################
	
	def notifyAttrChanged(self, attrsObject, name:str, value:Any):
		"""
		These notification come from either this object's *attrs* object or from a isa-parent. 
		This method is responsible to notify it's observers (the view objects representing it),
		and all of the isa-child MObjects connected to it via isa-relations.
		"""
		assert value is not None
		self.notifyObservers('mod attr', info=(name, value))#, observable=attrsObject) # view objects
		for r in self.relations:
			if r.isIsa and r.toNode is self:
				r.fromNode.notifyAttrChanged(attrsObject, name, value)

	def notifyModelChanged(self, modelObj, modelOperation:str, info:Optional[any]=None):
		self.tgmodel.logger.write(f'MObject.notifyModelChanged() [{self.idString}]: operation "{modelOperation}".', level='debug') 
		unhandled = False
# 		if modelOperation == 'del': 
# 			pass
		if modelOperation == 'mod attr':
			if isinstance(info, list) and len(info) == 2:
				# modelObj should be one we isa-inherit from
				for r in self.relations:
					if r.isIsa() and r.toNode is modelObj:
						self.attrs.ping(info[0])
						self.notifyObservers(modelOperation, info)
						break
			else:
				self.tgmodel.logger.write(f'MObject.notifyModelChanged(): operation "{modelOperation}" expected a 2-list as info parameter, got info={info} of type {type(info).__name__}', level="error")
		if modelOperation in ['mod attr', 'add rel', 'del rel', 'del']:
# 			self.notifyObservers(modelOperation, info, observable=modelObj)
			pass
		else:
			raise NotImplementedError(f'MObject.notifyModelChanged(): operation "{modelOperation}" not implemented.') 
		if unhandled:
			self.tgmodel.logger.write(f'MObject.notifyModelChanged(): operation "{modelOperation}" not implemented.', level="warning") 
	
	def notifyViewDeletion(self, viewObj):
		# TODO: fill out implementation of notifyViewDeletion() (authorizing?)
		self.delete()

	def addRelation(self, relation):
		self.relations.append(relation)
		self.notifyObservers('add rel', relation)
		if relation.isIsa and relation.fromNode is self: # we need to assure that all the attributes are reset correctly
			for k in self.attrs.keys():
				self.attrs.get(k)
				
	def notifyRelationDeletion(self, relation):
		"""
		Called by MRelations for thier toNodes and fromNodes when they are deleting .
		"""
		if relation in self.relations:
			self.relations.remove(relation)
		else:
			self.tgmodel.logger.write('MObject.notifyRelationDeletion() called with an unregistered relation "{relation}".', level="warning")
			
		self.notifyObservers('del rel', relation)
		
		# if (one of) our supertype(s) is disappearing and it's the last one, add in an ISA to the topNode (or topRelation).
		if relation.isIsa and relation.fromNode is self: 
			relation.toNode.removeObserver(self)
			# if there is no other supertype, then make the supertype topNode or topRelation
			if len([r for r in self.relations if r.isIsa and r.fromNode is self]) == 0 and not self._deleted:
				from tygra.mrelations import Isa
				Isa(self.tgmodel, self, self.tgmodel.topRelation if self.isRelation() else self.tgmodel.topNode, idServer=self.tgmodel)
		if relation.isIsa and relation.fromNode.isRelation():
			# TODO: it's possible that there was ANOTHER isa connected that won't be connected anymore...
			relation.fromNode.toNode.removeObserver(relation.fromNode) 
		
	### Debugging support ################################################################
	
	def __str__(self):
		return f'({type(self).__name__} [{self.idString}, "{self.attrs["label"]}"]{" *DELETED*" if self._deleted else ""})'

	def __repr__(self):
		return f'({type(self).__name__} [{self.idString}, "{self.attrs["label"]}"])'

if __name__ == "__main__":
	p1 = IDServer()
	p = IDServer(p1)
	c1 = IDServer(p)
	c2 = IDServer(p)
	print(c1.getIDString(1), c2.getIDString(2), "s/b (0,0,1) (0,1,2)")
	print(IDServer.makeIDTuple(c1.getIDString(1)), IDServer.makeIDTuple(c2.getIDString(2)), "s/b (0,0,1) (0,1,2)")	
	print(c1.getLocalID(c1.getIDString(1)), "s/b 1")
	print(c1.getLocalID(c2.getIDString(2)), "s/b 2")
	
