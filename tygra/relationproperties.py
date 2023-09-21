from abc import ABC, abstractmethod # Abstract Base Class
from typing import Union, Optional, Any, Tuple, List, Dict
from tygra.mobjects import MObject
from tygra.mnodes import MNode
from tygra.mrelations import MRelation
	 			
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

class RelationProperty():

	def __init__(self):
		assert type(self) != RelationProperty
		if type(self)._instance is None:
			type(self)._instance = self
		else:
			raise TypeError("Should never create an instance of a RelationProperty.")
			
	@property
	def priority(self): return self._priority
	
	@classmethod
	def getInstance(cls):
		if cls._instance is None:
			cls._instance = cls()
		return cls._instance			
		
	@abstractmethod
	def isRelated(self, relType:MRelation, fromNode:MObject, relation:MRelation, 
					toNode:Optional[MObject]=None, _omit:set=set()) \
											-> Union[bool,set[MObject]]:
		pass
		
class ReflexiveProperty(RelationProperty):

	_priority = 2
	_instance = None

	def isRelated(self, relType:MRelation, fromNode:MObject, relation:MRelation, 
					toNode:Optional[MObject]=None, _omit:set=set()) \
											-> Union[bool,set[MObject]]:
		assert relation.isa(relType), f'{type(self).__name__}.isRelated(): Expected a relation argument (type {type(relation).__name__}) to be a subtype of the relType, {type(relType).__name__}.'
		if toNode: # return a bool
			return relation.fromNode is fromNode
		else: # return a tree list
			return [relation.fromNode] if relation.fromNode is fromNode else []
	
class SymmetricProperty(RelationProperty):

	_priority = 3
	_instance = None

	def isRelated(self, relType:MRelation, fromNode:MObject, relation:MRelation, 
					toNode:Optional[MObject]=None, _omit:set=set()) \
											-> Union[bool,set[MObject]]:
		assert relation.isa(relType), f'{type(self).__name__}.isRelated(): Expected a relation argument (type {type(relation).__name__}) to be a subtype of the relType, {type(relType).__name__}.'
		if toNode: # return a bool
			if fromNode is relation.fromNode and toNode is relation.toNode  : return True
			if fromNode is relation.toNode   and toNode is relation.fromNode: return True
			return False
		else: # return a tree list
			if fromNode is relation.toNode: return [relation.fromNode]
			return []
			
class TransitiveProperty(RelationProperty):

	_priority = 4
	_instance = None

	def isRelated(self, relType:MRelation, fromNode:MObject, relation:MRelation, 
					toNode:Optional[MObject]=None, _omit:set=set()) \
											-> Union[bool,set[MObject]]:
		assert relation.isa(relType), f'{type(self).__name__}.isRelated(): Expected a relation argument (type {type(relation).__name__}) to be a subtype of the relType, {type(relType).__name__}.'
		if toNode: # return a bool
			assert relation.isa(relType), f'{type(self).__name__}.isRelated(): Expected a relation argument (type {type(relation).__name__}) to be a subtype of the relType, {type(relType).__name__}.'
			if fromNode in _omit: return False
			return relation.toNode.isRelatedTo(relType, toNode, _omit=_omit.union([fromNode]))
		else: # return a tree list
			if fromNode in _omit: return []
			return relation.toNode.isRelatedTo(relType, _omit=_omit.union([fromNode]))

		
		
if __name__ == "__main__":

	class MObject(ABC):
		def __init__(self, name, isa=[]):
			"""
			:param isa:
			:type isa: Optional[Union[Self, List[Self]]]
			"""
			self.name = name
			self.relations = []
			if isa is None: isa = []
			elif isinstance(isa, MObject): isa = [isa] 
			for parent in isa:
				r = MRelation("isa", self, parent)
				r._isa = True
			self._isa = False
		
		def __str__(self): return self.name
		def __repr__(self): return self.name

		def isa(self, nodeType=None) -> Union[bool, list]:
			"""
			Check if this *MObject* is an isa-decendent of *nodeType* as related through
			some chain of isa-relations. Or, if *nodeType* is *None*, then return a tree-list
			of ALL isa-supertypes of this *MObject*.
		
			:param nodeType: The *MObject* or a list of *MObjects* to serve a type representation
				or None which the following interpretation:
					* None: return a tree-list of all the isa-parents of this *MObject*. You can
						flatten this tree-list to a simple list using *treeFlatten()*.
					* *MObject*: return True iff *nodeType* is a isa-parent of this *MObject*.
					* *[MObject]*: return True iff EVERY element of *nodeType* is a isa-parent of this *MObject*.
			:type nodeType: Optional[Union[Self, List[Self]]]
			:return: a bool or a tree-list as above. Type: Union[bool, List[Self]]
			"""
			if nodeType is None:
				ret = []
				for r in self.relations:
					if r._isa and r.fromNode is self:
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
				for r in self.relations:
					if r._isa and r.fromNode is self:
						if r.toNode.isa(nodeType):
							return True
				return False
			
		def isparent(self, nodeType=None) -> Union[bool, list]:
			"""
			Check if this *MObject* is an immediate isa-child of *nodeType* as related through
			a single isa-relation. Or, if *nodeType* is *None*, then return a tree-list
			of ALL immediate isa-parents of this *MObject*.

			:param nodeType: The *MObject* or a list of *MObjects* to serve a type representation
				or None which the following interpretation:
					* None: return a list of all the isa-parents of this *MObject*.
					* *MObject*: return True iff *nodeType* is a isa-parent of this *MObject*.
					* *[MObject]*: return True iff EVERY element of *nodeType* is a isa-parent of this *MObject*.
			:type nodeType: Optional[Union[Self, List[Self]]]
			:return: a bool or a tree-list as above. Type: Union[bool, List[Self]]
			"""
			if nodeType is None:
				ret = []
				for r in self.relations:
					if r._isa and r.fromNode is self:
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
					if r._isa and r.fromNode is self:
						if r.toNode is nodeType:
							return True
				return False
			
		def isRelatedTo(self, relType, toNode=None, _omit:set=set()) -> set:
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
						 some chain of relations that are subtypes of *relType.
			:type toNode: Self
			:param _omit: Should never be used. Used ONLY by relational properties to prevent
				infinite recursion in following relation chains.
			:return: Depends on the *ToNode* argument, as above. Type: set[Self]
			"""
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
		

	class MNode(MObject):
		pass

	class MRelation(MObject):
		def __init__(self, name, fromNode, toNode, isa=[], properties=[]):
			super().__init__(name, isa=isa)
			self.fromNode = fromNode
			self.toNode = toNode
			fromNode.relations.append(self)
			toNode.relations.append(self)
			self.validateReferents()
			self.declaredProperties = properties.copy() #list(set(properties)) if len(properties) else [] # make a copy, eliminating any duplicates
			self.resetProperties()
		
		def resetProperties(self):
			self.properties = self.declaredProperties
			for parent in self.isparent():
				self.properties += parent.properties
			self.properties = list(set(self.properties))  if len(self.properties) else []# eliminate any duplicates
			self.properties.sort(key=lambda prop: prop.priority)
		
		def validateReferents(self):
			if not ((isinstance(self.fromNode, MNode) and isinstance(self.toNode, MNode)) or \
					(isinstance(self.fromNode, MRelation) and isinstance(self.toNode, MRelation))): 
				for parent in self.isparent():
					if not self.toNode.isa(parent.toNode): 
						raise TypeError(f'MRelation.validateReferents [{self}]: toNode {self.toNode} must be a subtype of {parent.toNode}.')
					if not self.fromNode.isa(parent.fromNode): 
						raise TypeError(f'MRelation.validateReferents [{self}]: fromNode {self.fromNode} must be a subtype of {parent.fromNode}.')
			return True



	testsFailed = 0
	testsPassed = 0
	def test(test:str, expected:Any=None, throws:Exception=None):
		global testsPassed
		global testsFailed
		try:
			r = eval(test)
		except Exception as ex:
			if type(ex) == throws:
				testsPassed += 1
				print(f'    passed: {test} --> {type(ex).__name__}: {ex}')
			else:
				testsFailed += 1
				print(f'*** FAILED: {test} --> {type(ex).__name__}: {ex}')
		else:
			if callable(expected):
				success = expected(r)
			else:
				success = r == expected
			if success:
				testsPassed += 1
				print(f'    passed: {test} --> {r}')
			else:
				testsFailed += 1
				print(f'*** FAILED: {test} --> {r}')

	#        N
	#       / \
	#     N1   N2
	#       \ /  \
	#       N21   N22
	#
	#        R----+
	#       / \    \
	#     RR   RS   RT
	#       \ /  \ /  \\  \\\
	#       RRS  RST   RRT RRST
	#
	#   num <: N
	
	N   = MNode("N")
	N1  = MNode("N1" , isa=[N])
	N2  = MNode("N2" , isa=[N])
	N21 = MNode("N21", isa=[N1, N2])
	N22 = MNode("N22", isa=[N2])
	print("--- isa tests on nodes")
	test("N.isa(N1)", False)
	test("N1.isa(N)", True)
	test("N.isa(N)", True)
	test("N1.isa(N1)", True)
	test("N21.isa(N1)", True)
	test("N21.isa(N2)", True)
	test("N21.isa(N)", True)
	test("N21.isa(N22)", False)
	test("N21.isa([N1,N2])", True)
	test("N21.isa([N,N2])", True)
	test("N21.isa([N1,N22])", False)
	test("N21.isa([])", True)
	
	R   = MRelation("R",    N, N)
	RR  = MRelation("RR",   N, N, isa=[R]      , properties=[ReflexiveProperty.getInstance()])
	RS  = MRelation("RS",   N, N, isa=[R]      , properties=[SymmetricProperty.getInstance()])
	RT  = MRelation("RT",   N, N, isa=[R]      , properties=[TransitiveProperty.getInstance()])
	RRS = MRelation("RRS",  N, N, isa=[RR, RS])
	RST = MRelation("RST",  N, N, isa=[RS, RT])
	RRT = MRelation("RRT",  N, N, isa=[RR, RT])
	RRST= MRelation("RRST", N, N, isa=[RR, RS, RT])
	print("--- isa tests on relations")
	test("R.isa(R)", True)
	test("RR.isa(R)", True)
	test("RRST.isa([RR,RS,RT])", True)
	test("RRST.isa([RR,RT])", True)
	test("RRST.isa([R])", True)
	test("RRST.isa(RST)", False)
	test("RRST.isa()", [RRST, [RR, [R], RS, [R], RT, [R]]])	
	
	print("---Relational Properities------")
	
	person = MNode("person", isa=N)
	alice = MNode("alice", isa=person)
	bob = MNode("bob", isa=person)
	carol = MNode("carol", isa=person)
	knows = MRelation("knows", person, person, isa=R)
	MRelation("knows1", alice, carol, isa=knows)
	test("alice.isRelatedTo(knows)", {carol})
	test("carol.isRelatedTo(knows)", set())
	test("bob.isRelatedTo(knows)", set())
	test("carol.isRelatedTo(knows, alice)", False)
	test("alice.isRelatedTo(knows, carol)", True)
	test("MRelation('knowsX', carol, N2, isa=knows)", throws=TypeError)
	
	friend = MRelation("friend", person, person, isa=RS)
	MRelation("friend1", alice, bob, isa=[friend, RS])
	test("alice.isRelatedTo(friend, bob)", True)
	test("alice.isRelatedTo(friend)", {bob})
	test("bob.isRelatedTo(friend, alice)", True)
	test("bob.isRelatedTo(friend)", {alice})
	test("alice.isRelatedTo(friend, carol)", False)
	test("bob.isRelatedTo(friend, carol)", False)

	num    = MNode("int",   isa=[N])
	zero   = MNode("zero",  isa=[num])
	one    = MNode("one",   isa=[num])
	two    = MNode("two",   isa=[num])
	three  = MNode("three", isa=[num])
	gt     = MRelation("gt", num, num, isa=[RT])
	ge     = MRelation("ge", num, num, isa=[RRT])
	eq     = MRelation("eq", num, num, isa=[RRST])
	MRelation("gt3", three, two,  isa=[gt])
	MRelation("gt2", two,   one,  isa=[gt])
	MRelation("gt1", one,   zero, isa=[gt])
	MRelation("ge3", three, two,  isa=[ge])
	MRelation("ge2", two,   one,  isa=[ge])
	MRelation("ge1", one,   zero, isa=[ge])
	
	test("one.isRelatedTo(gt)", {zero})
	one.isRelatedTo(gt, zero)
	test("one.isRelatedTo(gt, zero)", True)
	test("zero.isRelatedTo(gt, one)", False)
	test("two.isRelatedTo(gt, zero)", True)
	test("three.isRelatedTo(gt, zero)", True)
	test("zero.isRelatedTo(gt, two)", False)
	test("two.isRelatedTo(gt)", {one, zero})
	test("three.isRelatedTo(gt)", {one, zero, two})
	
	test("one.isRelatedTo(ge)", {one, zero})
	test("one.isRelatedTo(ge, one)", True)
	test("three.isRelatedTo(ge, three)", True)
	test("one.isRelatedTo(ge, zero)", True)
	test("zero.isRelatedTo(ge, one)", False)
	test("two.isRelatedTo(ge, zero)", True)
	test("three.isRelatedTo(ge, zero)", True)
	test("zero.isRelatedTo(ge, two)", False)
	test("two.isRelatedTo(ge)", {two, one, zero})

	print('-----------')
	print(f'    {testsPassed}/{testsPassed+testsFailed} tests passed.')
	if testsFailed:
		print(f'*** {testsFailed}/{testsPassed+testsFailed} tests failed. ***')
