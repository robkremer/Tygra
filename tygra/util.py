"""
Required installs:
	pip3 install matplotlib
"""
from abc import ABC, abstractmethod # Abstract Base Class
from typing import final
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Type, Union, Callable, Iterable, TypeVar, Generic, Self
from string import whitespace
import sys
import tkinter as tk
from weakref import WeakValueDictionary
from inspect import isabstract
from math import ceil
import os
import subprocess

# State bits in events
def s_CMD(s)  : return (s&0x18) != 0
def s_SHIFT(s): return (s&0x1)  != 0
def s_CTL(s)  : return (s&0x4)  != 0
def s_ALT(s)  : return (s&0x88) != 0
s_OPT = s_ALT

# Graphical representations for control keys
CHAR_SHIFT = u'\u21E7'
CHAR_CTL   = u'\u2388'
CHAR_ALT   = u'\u2387'
CHAR_CMD   = u'\u2318'

##########################################################################################
########## PERSISTENCE ###################################################################
##########################################################################################

########## ID SERVER #####################################################################

class IDServer:
	def __init__(self, parent=None, _id=None):
		self.parent = parent
		if _id == None:
			if parent:
				self.id = parent.nextID()
			else:
				self.id = None
		else:
			self.id = _id
		self._nextID = 0
		
	def _getIDVector(self):
		if self.parent:
			return self.parent._getIDVector() + [self.id]
		return []
			
	def getIDTuple(self, id):
		return tuple(self._getIDVector() + [id])
		
	def getIDString(self, id):
		return self.makeIDString(self.getIDTuple(id))
		
	@staticmethod
	def getLocalID(id:tuple|str|list):
		if (isinstance(id, tuple) or isinstance(id, list)) and len(id)>0:
			return id[-1]
		if isinstance(id, str):
			return IDServer.makeIDTuple(id)[-1]
		raise TypeError(f'IDServer.getLocalID(): Bad parameter "{str(id)}" must be a tuple of length>0 or a str in the form "(id[,id]*)", eg: "(67)" or "(3,789)", etc.')
		
	@staticmethod
	def makeIDString(tupleID:tuple):
		if isinstance(tupleID, tuple) and len(tupleID)>0:
			return str(tupleID).replace(" ", "").replace(",)", ")")
		raise TypeError(f'IDServer.makeIDString(): Bad parameter "{str(tupleID)}" must be a tuple of length>0.')
		
	@staticmethod
	def makeIDTuple(stringID:str):
		if isinstance(stringID, str) and stringID.startswith("("):
			ret = literal_eval(stringID)
			if not isinstance(ret, tuple):
				ret = tuple([ret])
			return ret
		raise TypeError(f'IDServer.makeIDTuple(): Parameter "{str(stringID)}" must be in the form "(id[,id]*)", eg: "(67)" or "(3,789)", etc.')
	
	def nextID(self, _recoveredID:Optional[int]=None):
		if _recoveredID:
			if _recoveredID >= self._nextID:
				self._nextID = _recoveredID + 1
			return None
		id = self._nextID
		self._nextID += 1
		return id
		
########## ADDRESS SERVER ################################################################

class AddrServer:
	def __init__(self):
# 		self.idLookupTable:dict[tuple[str,int],Any] = dict()
		self.idLookupTable:WeakValueDictionary = WeakValueDictionary()
	
	def idLookup(self, id:tuple[str,int]) -> Any:
		return self.idLookupTable[str(id)]

	def idRegister(self, id, obj:Any):
		if id == None:
			raise KeyError("AddrServer.idRegister(): non-id registered objects should not call idRegister()")
		if isinstance(id, tuple):
			id = IDServer.makeIDStr(id)
		if id in self.idLookupTable.keys():
			keys = []
			for k in self.idLookupTable.keys():
				keys.append(k)
			raise KeyError(f'AddrServer.idRegister(): id "{id}" is already registered. Lookup Table: {keys}')
		self.idLookupTable[id] = obj
		

########## PERSISTENT OBJECT #############################################################

class PO(ABC):
	"""
	Subclasses should all implement the following signatures:

		def xmlRepr(self) -> et.Element:
			- Serialize to an xml Element the object.
		
		@classmethod
		def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]
			- Returns an (\*args, \*\*kwargs) tuple used in constructing on object of the class
			  who's name is *elem*'s tag's name, based on the *elem*.)
			  
		@classmethod
		def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
			- Returns an (\*args, \*\*kwargs) tuple for the constructor of the class found in the element's name.
			  Called before the object to be unserialized is constructed and the values are 
			  used in it's construction.
	
		def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
			- Called just after an object is constructed, and is used to clean up anything
			  from the constructor specific to unserialization.
	"""
	
	def __init__(self, idServer:IDServer=None, _id:Optional[int]=None):
		"""
		Initialize the persistent object by registering the IDServer and getting this
		objects's self.id.
		
		:param idServer: If present, indicates whether or not this object has an id, that is whether pointers 
				to the object has a lookup address in files (this you can't store pointers to this
				object, just whole copies of it).
		:param _id: ** This parameter should NEVER be used except for persistent storage.**
		"""
		self.idServer = idServer
		if not isinstance(self, IDServer): # if this object is also an IDServer, it should have already got an id
			if _id == None: # this object is being created for the first time, as opposed to read from a file
				if idServer: # this is a registered object
					self.id = idServer.nextID()
				else:
					self.id = None
			else: # this object is being restored from persistent store (a file)
				if idServer: # this is a registered object
					self.id = _id
					idServer.nextID(_recoveredID=_id)
				else:
					raise TypeError(f"PO.__init__(): it's inconsistent for an unregistered object for have an id. In this case, {_id}")
		
	@property
	def idString(self) -> Optional[str]:
		if self.id != None and self.idServer:
			return self.idServer.getIDString(self.id)
		else:
			return None

	@classmethod
	@staticmethod
	def getClass(className:str) -> type:
		cls = None
		for modName, mod in sys.modules.items():
			c = None
			try:
				c = getattr(mod, className)
			except:
				continue
			cls = c
			break
		return cls

	@classmethod
	@staticmethod
	def makeObject(elem:et.Element, addrServer:AddrServer, typ:Optional[Type[Self]]=None) -> Self:
		className = elem.tag
		klass = PO.getClass(className)
		if klass == None:
			# the class could possibly be a nested class, so lets try using the typ given...
			if typ != None:
				klass = typ
			else:
				raise TypeError(f"PO.makeObject(): can't find type {className}.")
		if typ!=None and not issubclass(klass, typ):
			raise TypeError(f"PO.makeObject(): class {className} in element is not a subtype of constraining argument typ '{typ.__name__}'")
		args, kwargs = klass.getArgs(elem, addrServer)
		ret = klass(*args, **kwargs) # could throw an exception
		try:
			if addrServer != None and ret.id != None:
				addrServer.idRegister(ret.idServer.getIDString(ret.id), ret)
		except AttributeError: # We have to assume if this object isn't keeping an id then it's not expecting to have a pointer to it.
			pass
		ret.xmlRestore(elem, addrServer)

		if typ!=None and not isinstance(ret, typ):
			raise TypeError(f"PO.makeObject(): class {type(ret).__name__} of contructed object is not a subtype of constraining argument typ '{typ.__name__}'")
		return ret

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = et.Element(type(self).__name__)
		if self.id != None:
			idStr = self.idString
			elem.set('id', idStr)
			
		return elem

	@classmethod
	@abstractmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
		"""
		Returns an (\*args, \*\*kwargs) tuple for the constructor of the class found in the element's name.
		"""
		pass
	
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		idStr = elem.get("id")
		self.id = IDServer.getLocalID(idStr) if idStr else None
		
	def isAddressable(self) -> bool:
		return self.id != None
		
##########################################################################################
########## CATEGORIES ####################################################################
##########################################################################################

T = TypeVar('T')

class Categories(Generic[T]):
	
	def __init__(self):
		self.categories:dict[str, Callable[[T]], bool] = dict()
		
	def addCategory(self, name:str, test:Callable[[T], bool]):
		self.categories[name] = test
		
	def deleteCategory(self, name:str):
		if name in self.categories:
			del self.categories[name]
			
	def isCategory(self, obj:T, categories:Union[Iterable[str], str]):
		if isinstance(categories, str): categories = [categories]
		for c in categories:
			if c in self.categories:
				if self.categories[c](obj):
					return True
			else:
				raise AttributeError(f'Categories.isCategory(): Unknown category "{c}"')
		return False
		
	def keys(self):
		return self.categories.keys()

##########################################################################################
########## GRAPHIC UtiLItiES #############################################################
##########################################################################################

def pointInRect(pt, rect):
	""""pt: (x,y); rect: (x,y,x1,y1)"""
	return pointInPoly(pt, [(rect[0], rect[1]),
							(rect[2], rect[1]),
							(rect[2], rect[3]),
							(rect[0], rect[3])])
							
def shiftRectToPoint(rect:list, point:list):
	return [point[0], point[1], point[0]+rect[2]-rect[0], point[1]+rect[3]-rect[1]]
										
def overlaps(rect1, rect2):
	def overlapDim(a1, a2, b1, b2):
		return not(a2 < b1 or b2 < a1)
	return overlapDim(rect1[0], rect1[2], rect2[0], rect2[2]) and \
	   	   overlapDim(rect1[1], rect1[3], rect2[1], rect2[3])

def pointInPoly(pt, poly):
	import numpy as np
	import matplotlib.path as mplPath
	arr = []
	for i in range(0, len(poly), 2):
		arr.append([poly[i], poly[i+1]])
	bbPath = mplPath.Path(np.array(arr))
	return bbPath.contains_point(pt)

def midpoint(pt1, pt2):
	return ((pt1[0]+pt2[0])/2, (pt1[1]+pt2[1])/2)
	
def expandRect(rect:list, spacing:list):
	return  [rect[0]-spacing[0],
			 rect[1]-spacing[1],
			 rect[2]+spacing[2],
			 rect[3]+spacing[3]]
	
def normalizeRect(rect:list[float]) -> list[float]:
	return [rect[0] if rect[0]<rect[2] else rect[2],
			rect[1] if rect[1]<rect[3] else rect[3],
			rect[2] if rect[0]<rect[2] else rect[0],
			rect[3] if rect[1]<rect[3] else rect[1]]
		
##########################################################################################
########## USER INTERFACE ################################################################
##########################################################################################

def bindRightMouse(window, func):
	if window.winfo_toplevel().tk.call("tk", "windowingsystem") == 'aqua':
		window.bind("<2>", func)
		window.bind("<Control-1>", func)
	else:
		window.bind("<3>", func)

def tag_bindRightMouse(window, id, func):
	if window.tk.call("tk", "windowingsystem") == 'aqua':
		window.tag_bind(id, "<2>", func)
		window.tag_bind(id, "<Control-1>", func)
	else:
		window.tag_bind(id, "<3>", func)

def tag_unbindRightMouse(window, id):
	if window.tk.call("tk", "windowingsystem") == 'aqua':
		window.tag_unbind(id, "<2>")
		window.tag_unbind(id, "<Control-1>")
	else:
		window.tag_unbind(id, "<3>")

def eventEqual(e1, e2):
	return isinstance(e1, tk.Event) and isinstance(e2, tk.Event) and \
			e1.x_root == e2.x_root and \
			e1.y_root == e2.y_root and \
			e1.type   == e2.type
			
##########################################################################################
########## SOUNDS ########################################################################
##########################################################################################

def play(soundFile:Optional[str]):
	"""
	Plays a sound file. So far, this is only implemented for mac.
	
	:param soundFile: May have the following values:
		* None: plays "/System/Library/Sounds/Sosumi.aiff" (an error beep).
		* Just a file name: (not containing any slashes ("/")) looks in /System/Library/Sounds/
			for the file.
		* A path: (containing slashes ("/")) just tries to play that file.
	"""
	if soundFile is None or len(soundFile)==0:
		soundFile = '/System/Library/Sounds/Sosumi.aiff'
	elif soundFile.find('/') < 0:
		soundFile = '/System/Library/Sounds/'+soundFile
	subprocess.Popen(["afplay", soundFile])


##########################################################################################
########## LIST MANIPULATION #############################################################
##########################################################################################

def flattenPairs(pairs):
	"""
	From a vector of pairs, return a simple vector. [(1,2),(3,4)] -> [1,2,3,4]
	"""
	ret = []
	for p in pairs:
		ret.append(p[0])
		ret.append(p[1])
	return ret
	
def treeFlatten(tree:list, _omit:list=[]):
	"""
	Flatten a tree formed by nested lists into a single flat list eliminating duplicates.
	
	eg: [1 [2 [6], 3 [4 [6], 5 [6]]]] --> [1, 2, 6, 3, 4, 5]
	"""
	ret = []
	for item in tree:
		if isinstance(item, list):
			ret += treeFlatten(item, _omit=ret)
		elif item not in _omit and item not in ret:
			ret.append(item)
	return ret
	
def treeSplit(tree:list, _omit:list=[]):
	"""
	Split a tree list into roots and the children
	
	eg: [1 [2 [6], 3 [4 [6], 5 [6]]]] --> [1], [2 [6], 3 [4 [6], 5 [6]]] and
	
	[2 [6], 3 [4 [6], 5 [6]] --> [2, 3], [6, 4, 5], [6, 6] (note that [6, 4, 5] are the 
		immediate parents "1 in the example above)
	"""
	roots = []
	branches = []
	for item in tree:
		if isinstance(item, list):
			branches += item
		elif item not in _omit:
			roots.append(item)
	return roots, branches
	
from inspect import currentframe, getframeinfo, getmodulename
from pathlib import Path
from pprint import pprint


##########################################################################################
########## COLORS ########################################################################
##########################################################################################

def colorInterpolation(color1:str, color2:str, count:int) -> list[str]:
	"""
	Given two string colors in the form "#xxxxxx" and a count, return a vector of *count*
	length containing interpolated string colors (inclusive) between the two.
	"""
	def fix(c):
		if c < 0: return 0
		if c > 0xff: return 0xff
		return c
		
	assert len(color1) == 7
	assert len(color2) == 7
	assert color1[0] == "#"
	assert color2[0] == "#"
	R = int(color1[1:3], 16)
	G = int(color1[3:5], 16)
	B = int(color1[5:7], 16)
	R2 = int(color2[1:3], 16)
	G2 = int(color2[3:5], 16)
	B2 = int(color2[5:7], 16)
	c = count-1
	dR = ceil((R-R2)/c)
	dG = ceil((G-G2)/c)
	dB = ceil((B-B2)/c)
	ret = []
	for i in range(count):
		ret.append("#%0.2x%0.2x%0.2x" % (fix(R), fix(G), fix(B)))
		R, G, B = R-dR, G-dG, B-dB
	return ret


##########################################################################################
########## INTROSPECTION #################################################################
##########################################################################################

def allSubclasses(cls) -> set:
	"""Returns the set of all descendants of *cls*"""
	return set(cls.__subclasses__()).union([s for c in cls.__subclasses__() for s in allSubclasses(c)])

def allConcreteSubclasses(cls) -> set:
	"""Returns the set of all non-abstract descendants of *cls*"""
	subclasses = allSubclasses(cls)
	return set([c for c in subclasses if not isabstract(c)])
	

def getCaller():
	# surround with a try block with "finally: del current_frame"
	cuurent_frame = currentframe()
	caller_frame = cuurent_frame.f_back.f_back
	if caller_frame!=None:
#		filename, lineno, function, code_context, index = getframeinfo(caller_frame)
		info = getframeinfo(caller_frame)
# 		pprint(dir(caller_frame))
# 		pprint(caller_frame.__class__)
# 		print("************************************************")
		for n in dir(caller_frame):
			if n.startswith("f_"):
				pprint(n+": "+str(getattr(caller_frame, n)))
	
	if caller_frame == None:
		return None

	args = caller_frame.f_code.co_varnames
#	print(repr(caller_frame), caller_frame.co_argcount)
	first_arg_name = args[0] if len(args)>0 else None
	caller_instance = None
# 	if caller_frame.__self__:
# 		# f_locals is the local namespace seen by the frame
# 		caller_instance = caller_frame.f_locals[caller_frame.__self__]

# 	assert caller_instance is caller_frame.f_back.f_locals['b'] is b
# 	assert type(caller_instance).__name__ == 'B'
# 	assert function == caller_frame.f_code.co_name == 'class_B_fun'
# 	assert filename == caller_frame.f_code.co_filename == __file__
# 	assert getmodulename(filename) == Path(__file__).stem
	return #caller_frame.co_qualname#__name__#__self__#caller_instance
	


if __name__ == "__main__":
	testsPassed = 0
	testsFailed = 0
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
				
	test("colorInterpolation('#000000', '#ffffff', 3)", ['#000000', '#888888' '#ffffff'])
	test("colorInterpolation('#ffffff', '#000000', 3)", ['#ffffff', '#888888' '#000000'])

# 	test("overlaps([0,0,1,1], [2,2,3,3])", False)
# 	test("overlaps([2,2,3,3], [0,0,1,1])", False)
# 	test("overlaps([0,0,1,1], [0,0,1,1])", True)
# 	test("overlaps([0,0,2.5,2.5], [2,2,3,3])", True)
# 	test("overlaps([2,2,3,3], [0,0,2.5,2.5])", True)
# 	test("overlaps([0,0,1,2.5], [2,2,3,3])", False)
# 	test("overlaps([2,2,3,3], [0,0,1,2.5])", False)
# 	test("overlaps([0,0,1,1], [1,1,2,2])", True)
# 	test("overlaps([0,0,1,1], [1.01,1,2,2])", False)
# 	test("overlaps([0,0,4,4], [1,1,2,2])", True)
# 	test("overlaps([1,1,2,2], [0,0,4,4])", True)

# 	class C:
# 		def f(self): return getCaller()
# 	def f(): return getCaller()
# 	#print(pointInRect((0.5,0.5), ((0,0,2,2))))
# 	#print(flattenPairs([(1,2),(3,4)]))
# 	#print(midpoint((1,1),(2,2)))
# 	print(repr(getCaller()))
# 	print(repr(f()))
# 	c = C()
# 	print(repr(c.f()))
	
