"""
VRelations
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
import tkinter as tk
from tkinter import ttk
from tygra.vnodes import VNode
from tygra.util import tag_bindRightMouse, flattenPairs, midpoint, PO, AddrServer, IDServer
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Union, Tuple, List, Dict
from tygra.attributes import Attributes
from tygra.mrelations import MRelation
from tygra.vobjects import VObject
from tygra.mobjects import MObject
import tygra.app as app

class VRelation(VNode):

	granularity = 1 # the accuracy to which we should calculate endpoints
	
	### CONSTRUCTOR AND HELPERS ##########################################################

	def __init__(self, tgview, frm:Optional[Union[VNode,str]]=None, to:Optional[Union[VNode,str]]=None, \
			model=None, typ:MRelation=None, idServer:IDServer=None, \
			_id:Optional[int]=None, _bb:Optional[list]=None, \
			_floating:Optional[bool]=None):
		"""
		This class has to take special measures to avoid an address fault because Relations
		may reference other relations, so there is no way to ensure that toNode and fromNode
		idString-to-addresses have already be registered.  To get around that, if there had
		been an address fault in *self.getArgs()*, it will have put the str isString in place
		of the pointer.  The pointer(s) will be properly instantiated (etc) on a second 
		pass when the owner container calls the *self._post__init__()* method.
		"""

		modelClass = MRelation
		if typ:
			if not isinstance(typ, MRelation):
				raise TypeError(f'VRelation._init_(): "typ" argument a subtyp of MRelation object; got object of class {typ(typ).__name__}.')
			modelClass = type(typ)

		self.toID = None
		self.fromID = None
		self.fromDotID = None
		self.toDotID = None
		
		self.model = model
		
		# argument check: we must have a legit *fromNode* and *toNode* OR a legit *model*.
		assert frm is None if to is None else True
		assert model is not None if frm is None else True
		
		self.fromNode = None
		self.toNode = None
		self._floatingAnchor = True if _floating is None else _floating
		self.tgview = tgview
		self._redrawExecuting = False
		
		### Case: we're being created in the interface by the user
		if _id is None:
			if frm is not None: # we got an explicit from- and to-node
				assert to is not None
				self.fromNode = frm
				self.toNode = to
				# We need to create a model if we don't have one
				if self.model is None: # we're NOT being unserialized
					if not self.tgview.isModelEditor:
						tk.messagebox.showinfo(parent=self,
								icon="info",
								title=f'{app.APP_LONG_NAME}',
								message=f'This view is not authorized to modify the model.')
					assert self.tgview.isModelEditor
					assert isinstance(self.fromNode, VObject) and isinstance(self.toNode, VObject), \
							f'VRelation.__init__(): fromNode is type {type(self.fromNode).__name__}, toNode is type {type(self.toNode).__name__}'
					self.model = modelClass(tgview.model, frm=self.fromNode.model, to=self.toNode.model, idServer=tgview.model)
					assert self.fromNode.model is self.model.fromNode and self.toNode.model is self.model.toNode, \
							f'{self.fromNode.model} is {self.model.fromNode} and {self.toNode.model} is {self.model.toNode}.'
			else: # self.fromNode and self.toNode need to be instantiated from the model
				assert self.model is not None # We have a model
				for vo in tgview.nodes+tgview.relations:
					if vo.model is self.model.fromNode:
						self.fromNode = vo
					if vo.model is self.model.toNode:
						self.toNode = vo
					if self.toNode is not None and self.fromNode is not None:
						break
				# At this point, we have the terminal nodes ONLY if they are in the view. We might
				# need to instantiate them:
				fromNode = None
				toNode = None
				if self.fromNode is None:
					fromNode = self.tgview.makeViewObjectForModelObject(self.model.fromNode)
				if self.toNode is None:
					toNode = self.tgview.makeViewObjectForModelObject(self.model.toNode)
				if fromNode is not None:
					self.fromNode = fromNode
					if toNode is None: # that means self.toNode exists, so move fromNode close
						bb = self.toNode.boundingBox()
						fromNode.moveTo(bb[2]+150, bb[1])
				if toNode is not None:
					self.toNode = toNode
					if fromNode is None: # that means self.fromNode exists, so move toNode close
						bb = self.fromNode.boundingBox()
						toNode.moveTo(bb[2]+150, bb[1])
			assert isinstance(self.fromNode, VObject), f'VRelation.__init__() [{self}]: Could not find or instantiate fromNode from model {self.model.fromNode}.'
			assert isinstance(self.toNode, VObject), f'VRelation.__init__() [{self}]: Could not find or instantiate toNode from model {self.model.toNode}.'
			assert issubclass(type(self.fromNode), type(self.toNode)), f'VRelation.__init__() [{self}]: fromNode ({type(self.fromNode).__name__}) must be equal or a subclass of toNode ({type(self.fromNode).__name__}).'
		
		### Case: we're being unserialized
		else:
			assert frm is not None, f'VRelation.__init__() [{type(self).__name__}]: {self.toNode} is not None and {self.fromNode} is not None' 
			assert to is not None
			assert self.model is not None
			self.fromNode = frm
			self.toNode = to
			# We are asserting we the terminal nodes, but NOT THE ADDRESSES of the terminal nodes
			# (the pointers may be id strings which still need to be looked up.)
			assert self.fromNode is not None, \
						f'VRelation.__init__() [{type(self).__name__}]: {self.fromNode} is not None'
			assert self.toNode is not None, \
						f'VRelation.__init__() [{type(self).__name__}]: {self.toNode} is not None'
			# we could be trying to create a visual for a model that got deleted during restoring for persistence store...
			if self.model.fromNode is None and self.model.toNode is None: # the model is deleted
				raise AttributeError("VRelation.__init__(): Cannot create VRelation for a deleted model.")
				
		assert isinstance(self.model, MObject)
		
		self.init = {"typ": typ, "_bb": _bb} # pass these parameters to self			
		super().__init__(self.tgview, 0, 0, 30, 30, shape="Oval", 
					model=self.model, idServer=idServer, _id=_id)
					
	def _post__init__(self, addrServer:AddrServer):
		"""
		If one or more of the terminal nodes' models had been deleted in the model, then
		we will fail to get the address of the terminal nodes, in which case, we will throw
		a KeyError exception.
		"""
		if isinstance(self.fromNode, str):
			self.fromNode = addrServer.idLookup(self.fromNode)
			self.fromNode.addRelation(self)
		if isinstance(self.toNode, str):
			self.toNode = addrServer.idLookup(self.toNode)
			self.toNode.addRelation(self)
			
		# we have proper terminal nodes
		assert isinstance(self.fromNode, VObject) and isinstance(self.toNode, VObject)
		# each terminal node points to the same thing as our model does.
		assert self.fromNode.model is self.model.fromNode and self.toNode.model is self.model.toNode, \
					f'{self.fromNode.model} is {self.model.fromNode} and {self.toNode.model} is {self.model.toNode}.'
		
# 		if isinstance(self.fromNode, VObject): # otherwise, we'll do it after we resolve fromNode
		self.fromNode.addRelation(self)
# 		if isinstance(self.toNode, VObject): # ditto
		self.toNode.addRelation(self)

		typ = self.init["typ"]
		_bb = self.init["_bb"]
		self.__dict__.pop('init', None)		

		if _bb is None:
			if self.fromNode is self.toNode:
				c = self.fromNode.centerPt()
				ctr = (c[0] + self.tgview.model.topNode.attrs["minSize"]/1.5, c[1])
			else:
				ctr = midpoint(self.fromNode.centerPt(), self.toNode.centerPt())
			try:
				sizex = self.model.attrs["minSize"] / 2
				sizey = sizex * self.model.attrs["aspectRatio"] / 2
			except:
				sizex = 15
				sizey = 15
			bb = [ctr[0]-sizex, ctr[1]-sizey, \
				  ctr[0]+sizex, ctr[1]+sizey]
		else:
			bb = _bb
			ctr = ((bb[0]+bb[2])/2, (bb[1]+bb[3])/2)
		self.anchorPt = ctr
		self.boundingBox(bb)
		super()._post__init__(addrServer)
		
	def register(self):
		self.tgview.relations.append(self)

	def makeDecorators(self):
		from tygra.vnodes import Text, TypeMarker
		self.decorators["text"] = Text(self, text=self.model.attrs["label"], fill="yellow")
		if self.model.attrs["type"] or self.model.system:
			self.decorators["typeMarker"] = TypeMarker(self)

# 	def makeAttrs(self):
# 		self.addAttrs("fillColor", "", override=False)
# 		self.addAttrs("borderColor", "gray", override=False)
# 		self.addAttrs("textColor", "black", override=False)
# 		self.addAttrs("shape", "oval", override=False)
# 		self.addAttrs("label", "kind", override=False)
# # 		self.addAttrs("floating", True, override=False)
# 
	### DESTRUCTOR ########################################################################

	def _delete(self):
		""" Low-level delete that doesn't take care of notifications."""
		self.tgview.delete(self.fromID)
		self.tgview.delete(self.toID)
		self.tgview.delete(self.fromDotID)
		self.tgview.delete(self.toDotID)
		if self in self.tgview.relations:
			self.tgview.relations.remove(self)
		super().delete()

	def delete(self):
		"""
		Removes this Relation:
			remove it from the display
			removing it from tgview's list
			notify the relevant nodes
		"""
		try: # The node could be deleting too.
			self.toNode  .notifyRelationDeletion(self)
		except:
			pass
		try: # The node could be deleting too.
			self.fromNode.notifyRelationDeletion(self)
		except:
			pass
		self._delete()
		
	### PERSISTENCE ######################################################################

	def serializeXML(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().serializeXML()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().serializeXML()
		elem.set('fromNode', str(self.fromNode.idString))
		elem.set('toNode', str(self.toNode.idString))
		elem.set('floating', str(self._floatingAnchor))
		return elem

	@classmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> Tuple[List[Any], Dict[str, Any]]:
		args = []
		kwargs = dict()

		tgview = addrServer.idLookup(elem.get('tgview'))
		args.append(tgview)
		
		idStr = elem.get('id')
		id = IDServer.getLocalID(idStr) if idStr else None

		fromNode = elem.get('fromNode')
		try:
			fromNode = addrServer.idLookup(fromNode) if fromNode!=None and fromNode!="" else None
		except KeyError:
			print(f'WARNING: VRelation.getArgs(): addr fault on {idStr} for fromNode, using string "{fromNode}" in place of address.')
		args.append(fromNode)
		
		toNode = elem.get('toNode')
		try:
			toNode = addrServer.idLookup(toNode) if toNode!=None and toNode!="" else None
		except KeyError:
			print(f'WARNING: VRelation.getArgs(): addr fault on {idStr} for toNode, using string "{toNode}" in place of address.')
		args.append(toNode)

		model = elem.get('model')
		exStr = None
		try:
			model = addrServer.idLookup(model) if model!=None and model!="" else None
		except KeyError as ex:
			exStr = f'Failed to instantiate model {model} ({type(ex).__name__}: {ex})'
		if exStr is not None:
			raise AttributeError(exStr)
		args.append(model)

		kwargs["_id"] = id
		kwargs["idServer"] = tgview
		
		kwargs["_bb"] = literal_eval(elem.get('boundingBox'))
		kwargs["_floating"] = literal_eval(elem.get('floating'))
		
		return args, kwargs
	
	def unserializeXML(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().unserializeXML(elem, addrServer)

	### ATTRIBUTES #######################################################################

	def notifyAttrChanged(self, attrsObj:Attributes, name:str, value:Any):
		super().notifyAttrChanged(attrsObj, name, value)

	### DECORATORS #######################################################################

	### GETTERS AND SETTERS ##############################################################
	
	def floating(self, value:Optional[bool]=None):
		if self.model.attrs['type']: return False # type relations never float
		if value != None:
			oldVal = self._floatingAnchor
			self._floatingAnchor = value
			if oldVal != self._floatingAnchor:
				self.reposition()
		return self._floatingAnchor

	### DRAWING ##########################################################################

	def redraw(self):
		self._redrawExecuting = True
		try:
			super().redraw()
			self.setPoints()
			color = self.model.attrs["lineColor"]
			if color is None: color = "black"
			width = self.model.attrs["lineWidth"]
			if width is None: width = 1
			fill = self.model.attrs["fillColor"]
			if fill is None: fill = "white"
			if self.fromID is not None:
				self.tgview.coords(self.fromID, 
						self.tgview.viewToWindow(flattenPairs([self.ptFrom,       self.ptFromMySide])))
				self.tgview.itemconfigure(self.fromID, fill=color, width=width)
			if self.toID is not None:
				self.tgview.coords(self.toID,   
						self.tgview.viewToWindow(flattenPairs([self.ptToMySide, self.ptTo])))
				self.tgview.itemconfigure(self.toID  , fill=color, width=width)
			if self.fromDotID is not None:
				self.tgview.coords(self.fromDotID, 
						self.tgview.viewToWindow(
							self.ptFromMySide[0]-3, self.ptFromMySide[1]-3, self.ptFromMySide[0]+3, self.ptFromMySide[1]+3))
				self.tgview.itemconfigure(self.fromDotID, outline=color, fill="white")
			if self.toDotID is not None:
				self.tgview.coords(self.toDotID,
						self.tgview.viewToWindow(
							self.ptToMySide  [0]-3, self.ptToMySide  [1]-3, self.ptToMySide  [0]+3, self.ptToMySide  [1]+3))
				self.tgview.itemconfigure(self.toDotID, outline=color, fill="white")
		except Exception as ex:
			self.tgview.logger.write(f"Exception ({ex}), probably due to partial construction.", level="warning", exception=ex)
# 			raise ex
		self._redrawExecuting = False

	def draw(self):
		super().draw()
		color = self.model.attrs["lineColor"]
		if color is None: color = "black"
		width = self.model.attrs["lineWidth"]
		if width is None: width = 1
		fill = self.model.attrs["fillColor"]
		if fill is None: fill = "white"
		self.setPoints()
		self.fromID = self.tgview.create_line(
				self.tgview.viewToWindow(flattenPairs([self.ptFrom, self.ptFromMySide])),
				fill=color, width=width)
		self.toID   = self.tgview.create_line(
				self.tgview.viewToWindow(flattenPairs([self.ptToMySide, self.ptTo])), 
				arrow=tk.LAST, fill=color, width=width)
		self.fromDotID = self.tgview.create_oval(
				self.tgview.viewToWindow(self.ptFromMySide[0]-3, 
				self.ptFromMySide[1]-3, self.ptFromMySide[0]+3, self.ptFromMySide[1]+3),
				outline=color, fill="white")
		self.toDotID   = self.tgview.create_oval(
				self.tgview.viewToWindow(self.ptToMySide  [0]-3, 
				self.ptToMySide  [1]-3, self.ptToMySide  [0]+3, self.ptToMySide  [1]+3),
				outline=color, fill="white")

	### GEOMETRIC INFO/CONTROL ###########################################################

	def reposition(self):
		if self.floating():
			if self.fromNode is self.toNode:
				c = self.fromNode.centerPt()
				ctr = (c[0] + self.tgview.model.topNode.attrs["minSize"]/1.5, c[1])
			else:
				ctr = midpoint(self.fromNode.centerPt(), self.toNode.centerPt())
			self.moveToCenterOn(ctr[0], ctr[1])
#		self.setPoints()
		self.redraw()

	def setPoints(self):
		self.ptFrom,     self.ptFromMySide = self.findEndPoints(self.fromNode, self)
		self.ptToMySide, self.ptTo         = self.findEndPoints(self, self.toNode)

	def findEndPoints(self, frm:VNode, to:VNode):
		return (self.findIntersection(to.centerPt(), frm), self.findIntersection(frm.centerPt(), to))

	def findIntersection(self, p1, node):
		"""p2 is the center of node"""
		p2 = node.centerPt()
		while not self.closePts(p1,p2):
			pc = midpoint(p1, p2)
			if node.containsPt(pc):
				p2 = pc
			else:
				p1 = pc
		return p1
		
	def closePts(self, p1, p2):
		""" Return True iff the two points are close to one another. """
		return abs(p1[0]-p2[0]) < VRelation.granularity and abs(p1[1]-p2[1]) < VRelation.granularity

	### NODES ############################################################################

	def notifyNodeMove(self, node): #, direction):
		self.reposition()
		
	def notifyNodeDeletion(self, node):
		if node is self.fromNode:
			notify = self.toNode
		elif node is self.toNode:
			notify = self.fromNode
		else:
			return # this shouldn't happen
		notify.notifyRelationDeletion(self)
		self._delete()

	### MENUS ############################################################################

	def addViewMenuItems(self, menu:tk.Menu):
		if not self.model.attrs['type']:
			self._menuFloating = tk.BooleanVar()
			self._menuFloating.set(self.floating())
			menu.add_checkbutton(label="floating", onvalue=1, offvalue=0, variable=self._menuFloating, command=self._toggleFloatingAnchor)
		super().addViewMenuItems(menu)
	
	def _toggleFloatingAnchor(self, event=None):
		self.floating(self._menuFloating.get())
# 		if self.floating():
# 			self.redraw()
			

	### Event handling ###################################################################

	def onDragRelease(self, event):
		super().onDragRelease(event)
		self.floating(False)

	### Debugging support ################################################################
	
	def __str__(self):
		try:
			label = self.label()
		except:
			label = '<no label>'
		model =    '<no model>'    if self.model    is None else self.model.idString
		toNode =   '<no toNode>'   if self.toNode   is None else self.toNode.idString
		fromNode = '<no fromNode>' if self.fromNode is None else self.fromNode.idString
		return f'({type(self).__name__} [{self.idString}, "{label}"], model={model}, from {fromNode} to {toNode}{" *DELETED*" if self._deleted else ""})'

	def __repr__(self):
		return self.__str__()

class VIsa(VRelation):
	def __init__(self, tgview, frm:Optional[VNode]=None, to:Optional[VNode]=None, \
			model=None, typ:MRelation=None, idServer:IDServer=None, \
			_id:Optional[int]=None, _bb:Optional[list]=None, \
			_floating:Optional[bool]=None):
		super().__init__(tgview, frm, to, model, typ, idServer, _id, _bb, _floating)
	
	def _post__init__(self, addrServer:AddrServer):
		super()._post__init__(addrServer)
		self.fromNode.updateFromAttrs()
	
	def addModelEditingMenuItems(self, menu:tk.Menu):
		pass # we don't want to allow user editing of attributes or relations on isa's.
	
# 	def makeMenu(self) -> tk.Menu:
# 		m = tk.Menu(self.tgview)
# 		self._menuFloating = tk.BooleanVar()
# 		self._menuFloating.set(self.floating())
# 		m.add_checkbutton(label="floating", onvalue=1, offvalue=0, variable=self._menuFloating, command=self._toggleFloatingAnchor)
# 		m.add_separator()
# 		m.add_command(label="remove from view", command=self.delete)
# 		if self.tgview.isModelEditor and not self.model.system:
# 			m.add_command(label="delete from model", command=self.model.delete)
# 		return m
# 		
