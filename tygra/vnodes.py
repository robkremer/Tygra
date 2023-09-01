"""
VNodes
"""
import tkinter as tk
#from tkinter import ttk
from tygra.util import tag_bindRightMouse, tag_unbindRightMouse, pointInPoly, PO, AddrServer, \
				IDServer, overlaps, shiftRectToPoint, expandRect, allConcreteSubclasses
import sys
from tygra.mnodes import MNode
from tygra.mrelations import Isa, MRelation
from tygra.vobjects import VObject
from tygra.mobjects import ModelObserver, MObject
from abc import ABC, abstractmethod # Abstract Base Class
#from collections.abc import Iterable
from tygra.attributes import Attributes
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Iterable, Callable, Self
import tygra.app as app
from math import sqrt
from tygra.tooltip import CreateToolTip
from pickle import NONE, TRUE

class VNode(VObject):

	### CONSTRUCTOR AND HELPERS ##########################################################

	def __init__(self, tgview, x, y, x2, y2, shape="RoundedRectangle", 
			model=None, idServer:IDServer=None, _id:Optional[int]=None):
		if _id is None: # We're NOT being unserialized
			if model == None:
				if not self.tgview.isModelEditor:
					tk.messagebox.showinfo(parent=self,
							icon="info",
							title=f'{app.APP_LONG_NAME}',
							message=f'This view is not authorized to modify the model.')
				assert self.tgview.isModelEditor
				model = MNode(tgview.model, idServer=tgview.model)
		assert isinstance(model, MObject)
		super().__init__(tgview, model, idServer=idServer, _id=_id)
		if isinstance(shape, str):
			try:
				shape = self.strToShape(shape, (x, y, x2, y2))
			except:
				shape = self.strToShape("RoundedRectangle", (x, y, x2, y2))
		assert isinstance(shape, Shape)
		self._shape = shape
		self._minSize = 1
		self._aspectRatio = 0.1
		self._updatingFromAttrs = False
		self.tooltip = None

		
		self.decorators = dict()
		self.makeDecorators()

		self.register()
		
		self.dragInfo = None
		self._deleted = False

		if not tgview.readingPersistentStore:
			self._post__init__(None)

	def _post__init__(self, addrServer:AddrServer):
		self.draw()
		self.makeBindings()
		self.adjustPos()
	
	
	def register(self):
		self.tgview.nodes.append(self)

	def makeBindings(self):
		tag_bindRightMouse(self.tgview, self._shape.id, self.onRightMouse)
		self.tgview.tag_bind(self._shape.id, "<Button-1>", self.onButton_1)
		self.tgview.tag_bind(self._shape.id, "<B1-Motion>", self.onB1_Motion)
		self.tgview.tag_bind(self._shape.id, "<B1-ButtonRelease>", self.onB1_ButtonRelease)
		self.tooltip = CreateToolTip(self.tgview, self.tooltipFunc, self._shape.id, waitTime=1000)
		
	def tooltipFunc(self):
		note = self.model.attrs["notes"]
		if note is None: note = ""
		if self.tgview._scale < 0.6:
			return self.model.attrs["label"] + ((":\n  "+note) if len(note)>0 else "")
		else:
			return note
	
	def killBindings(self):
		tag_unbindRightMouse(self.tgview, self._shape.id)
		self.tgview.tag_unbind(self._shape.id, "<Button-1>")
		self.tgview.tag_unbind(self._shape.id, "<B1-Motion>")
		self.tgview.tag_unbind(self._shape.id, "<B1-ButtonRelease>")
		if self.tooltip is not None:
			self.tooltip.delete()

	def makeDecorators(self):
		self.decorators["text"] = WrappingText(self, text=self.model.attrs["label"], fill="yellow")
		try:
			if self.model.attrs["type"] or self.model.system:
				self.decorators["typeMarker"] = TypeMarker(self)
		except Exception as ex:
			self.tgview.logger.write(f"VNode.makeDecorators(): failed to make 'typeMarker': {type(ex).__name__}: {ex}.", level="warning", exception=ex)

# 	SHAPES = ["RoundedRectangle", "Rectangle", "Oval"]

	def strToShape(self, name, rect):
# 		if name in globals():
# 			cls = globals()[name]
# 			if issubclass(cls, Shape):
# 				return cls(self, rect)			
		cls = Shape.getShapeClass(name)
		if cls is not None:
			return cls(self, rect)
		raise TypeError("VNode.strToShape(): Do not know shape class '"+name+"'.")

	### DESTRUCTOR #######################################################################

	def delete(self, viewOnly=True):
		"""Removes this Node from the display, removing it from tgview's list."""
# 		if self._deleted:
# 			return
		self._deleted = True
		
		# this check is necessary because the node being deleted might be a label for an relation
		if self in self.tgview.nodes:
			self.tgview.nodes.remove(self)

		# remove all decorators
		keys = []
		for k in self.decorators: keys.append(k)
		for k in keys: 
			try: self.removeDecorator(key=k)
			except: pass

		# notify all VRelations
		for r in self.relations:
			try: r.notifyNodeDeletion(self)
			except: pass
			
		if self._shape.id is not None:
			self.killBindings()
			self._shape.delete()

		# notify the MNode this VNode is deleting
		if not viewOnly and self.tgview.isModelEditor:
			try: self.model.notifyViewDeletion(self)
			except: pass

		self._shape = None
		self.decorators = None
		self.dragInfo = None
		super().delete()

	### PERSISTENCE ######################################################################

	def xmlRepr(self) -> et.Element:
		"""
		Returns the representation of this object as an Element object.
		Implementors should call *super().xmlRepr()* **first** as this top-level method
		will construct the Element itself.
		"""
		elem = super().xmlRepr()
		elem.set('boundingBox', str(self.boundingBox()))
		return elem

	@classmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
		args = []
		kwargs = dict()
		tgview = addrServer.idLookup(elem.get('tgview'))
		args.append(tgview)
		
		x, y, x2, y2 = literal_eval(elem.get('boundingBox'))
		args += [x, y, x2, y2]
		
		model = elem.get('model')
		model = addrServer.idLookup(model) if model!=None and model!="" else None

		shape = model.attrs["shape"] #elem.get('shape')
		args.append(shape)
		
		args.append(model)
		

		idStr = elem.get('id')
		id = IDServer.getLocalID(idStr) if idStr else None
		kwargs["_id"] = id
		kwargs["idServer"] = tgview
		
		return args, kwargs
	
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
# 		if self.id != None:
# 			addrServer.idRegister(self.idServer.getIDString(self.id), self)
		super().xmlRestore(elem, addrServer)

	### ATTRIBUTES #######################################################################

	def updateFromAttrs(self, attrs:Optional[list]=None):
		def update(name):
			if name in attrs and attrsInfo[name]() != self.model.attrs[name]:
				attrsInfo[name](self.model.attrs[name])
				
		attrsInfo = {"shape":self.shape, "fillColor":self.fillColor, "borderColor":self.borderColor, \
				"textColor":self.textColor, "label":self.label, "type":self.typ, \
				"lineColor":self.lineColor, "minSize":self.minSize, "aspectRatio":self.aspectRatio}
			
		if self._updatingFromAttrs: return
		self._updatingFromAttrs = True
		if attrs is None: attrs = list(attrsInfo.keys())		
		for name in attrs:
			update(name)
		self._updatingFromAttrs = False
		

	def notifyAttrChanged(self, attrsObj:Attributes, name:str, value:Any):
		try:
			if name == 'fillColor':
				self.fillColor(value)
			if name == 'borderColor':
				self.borderColor(value)
			if name == 'shape':
				self.shape(value)
			if name == 'label':
				self.label(value)
			if name == 'textColor':
				self.textColor(value)
			if name == 'type':
				self.typ(value)
			if name == 'lineColor':
				self.lineColor(value)
			if name == 'minSize':
				self.minSize(value)
			if name == 'aspectRatio':
				self.aspectRatio(value)
		except Exception as ex:
			self.tgview.logger.write(f'VNode.notifyAttrChanged(): got except with "{name}": "{value}". Probably due to partially constructed VNode.', level="warning", exception=ex)
				
	### DECORATORS #######################################################################

	def removeDecorator(self, key=None, obj=None):
		if key!=None:
			if key in self.decorators:
				self.decorators[key].delete()
				self.decorators.pop(key, None)
				return
		if obj!=None:
			for k,v in self.decorators.items():
				if v == obj:
					v.delete()
					self.decorators.pop(k, None) #should have been popped already by the delete() above...
					return
		assert False, f'VNode.removeDecorator(self={self}, key={key}, obj={obj}): Failed to remove decorator.'

	def notifyDecoratorDeletion(self, decorator):
		for pair in self.decorators.items():
			if pair[1] == decorator:
				self.decorators.pop(pair[0], None)
				break

	### GETTERS AND SETTERS ##############################################################

	def boundingBox(self, rect:list[float]=None):
		if rect != None:
			self._shape.boundingBox(rect)
			self.redraw()
		return self._shape.boundingBox() 

	def minSize(self, s:Optional[int]=None):
		if s != None:
			bb = self.boundingBox()
			ar = self.aspectRatio()
			self.boundingBox([bb[0], bb[1], bb[0]+s, bb[1]+(s*ar)])
			self.model.attrs["minSize"] = s
			self._minSize = s
#			self.redraw()
		try:
			return self._minSize 
		except:
			self._minSize = self.model.attrs["minSize"]
			return self._minSize

	def aspectRatio(self, s:Optional[float]=None):
		if s != None:
			bb = self.boundingBox()
			self.boundingBox([bb[0], bb[1], bb[2], bb[1]+((bb[2]-bb[0])*s)])
			self.model.attrs["aspectRatio"] = s
			self._aspectRatio = s
# 			self.redraw()
		try:
			return self._aspectRatio
		except:
			self._aspectRatio = self.model.attrs["aspectRatio"]
			return self._aspectRatio

	def fillColor(self, c=None):
		if c != None:
			self._shape.redraw(fill=c)
		try: # The fill color could be non-existent for a transparent color
			return self.tgview.itemconfigure(self._shape.id, "fill")[0]
		except:
			return ""

	def borderColor(self, c=None):
		if c != None:
			self._shape.redraw(outline=c)
		try: # The fill color could be non-existent for a transparent color
			return self.tgview.itemconfigure(self._shape.id, "outline")[0]
		except:
			return ""

	def textColor(self, c=None):
		d = self.decorators["text"]
		if "text" in self.decorators:
			if d is not None:
				if c != None:
					d.redraw(fill=c)
# 				assert d.getAttr("fill") == self.model.attrs["textColor"]
		try: # The fill color could be non-existent for a transparent color
			return self.tgview.itemconfigure(d.id, "fill")[0]
		except:
			return ""
# 		return self.model.attrs["textColor"]
		
	def shape(self, c=None):
		if c is not None and c != type(self._shape).__name__:
			bb = self.boundingBox()
			newShape = None
			try:
				newShape = self.strToShape(c, bb)
			except Exception as ex:
				self.tgview.logger.write(f'WARNING: VNode.shape(): Shape "{c}" is not known.', level="warning", exception=ex)
			if newShape is not None:
				self.killBindings()
				oldShape = self._shape
				self._shape = newShape
				self._shape.draw()
				self.tgview.lift(newShape.id, oldShape.id)
				oldShape.delete()
				self.updateFromAttrs(["fillColor", "borderColor"])
				self.makeBindings()
		return type(self._shape).__name__

	def label(self, t=None):
		if "text" in self.decorators:
			d = self.decorators["text"]
			if d is not None:
				if t != None:
					d.redraw()
# 				assert d.getAttr("text") == self.model.attrs["label"]
		return self.model.attrs["label"]

	def typ(self, b=None):
		if b is not None:
			assert isinstance(b, bool)
			if b:
				if "typeMarker" not in self.decorators:
					self.decorators["typeMarker"] = TypeMarker(self)
					self.decorators["typeMarker"].draw()
			else:
				if "typeMarker" in self.decorators and not self.model.system:
					self.decorators["typeMarker"].delete()
		return self.model.attrs["type"]
		
	def lineColor(self, c=None):
		return self.model.attrs["lineColor"]

	### DRAWING ##########################################################################

	def draw(self):#, rect=None):
		assert self._shape.id is None, f'VNode.draw() [{self}]: .draw() called twice.'
		self._shape.draw() #self.attrs["boundingBox"])#rect)
		for k, d in self.decorators.items(): # TODO: might need to concern ourselves about draw order here
			d.draw()
		self.updateFromAttrs()
		
	def redraw(self):
		self.updateFromAttrs()
		self._shape.redraw()
		for k, d in self.decorators.items():
			d.redraw()

	### GEOMETRIC INFO/CONTROL ###########################################################
	# The "primitive" is moveTo(), so all these that actually move must call moveTo() to
	# actually do the work.

	def moveTo(self, x, y, allowOverScrollRegionSE=True, adjustPos=True):
		""" 
		Move so that the NW corner is on (x,y), informing all the decorators and 
		relations
		"""
		bb = self.boundingBox()
		if bb[0] == x and bb[1] == y: # we haven't actually moved, so do nothing.
			return
		sr = self.tgview.scrollRegion
		if x<sr[0]: x = sr[0]
		if y<sr[1]: y = sr[1]
		if not allowOverScrollRegionSE:
			if x+bb[2]-bb[0]>sr[2]: x = sr[2]-(bb[2]-bb[0])
			if y+bb[3]-bb[1]>sr[3]: y = sr[3]-(bb[3]-bb[1])
		self._shape.moveTo(x, y)
		self.redraw()
		if adjustPos: self.adjustPos()
		for r in self.relations:
			r.notifyNodeMove(self)
			
	def moveBy(self, x, y, allowOverScrollRegionSE=False, adjustPos=True):
		bb = self.boundingBox()
		x1 = bb[0]+x
		y1 = bb[1]+y
		self.moveTo(x1, y1, allowOverScrollRegionSE, adjustPos=adjustPos)
		
	def moveToCenterOn(self, x, y, adjustPos=True):
		bb = self.boundingBox()
		width = abs(bb[2]-bb[0])
		height = abs(bb[3]-bb[1])
		x = x - (width/2)
		y = y - (height/2)
		self.moveTo(x, y, adjustPos=adjustPos)

	def centerPt(self):
		"""Gets the center point of this shape."""
		r = self.boundingBox()
		return ((r[0]+r[2])/2, (r[1]+r[3])/2)

	def containsPt(self, pt):
		return pointInPoly(pt, self._shape.points())
		
	def adjustPos(self, others=None):
		
		layout = self.tgview.localLayout
		if layout is not None:
			for r in self.relations:
				layout(r)
			layout(self)
		for r in self.relations:
			r.redraw()
		
	def overlaps(self, bb:list=None, others:Iterable=None, spacing:Optional[list]=None) -> list[VObject]:
		""
		if bb is None:
			bb = self.boundingBox() if spacing is None else expandRect(self.boundingBox(), spacing)
		if others is None:
			others = self.tgview.nodes + self.tgview.relations
			others.remove(self)
		else:
			if self in others:
				others = others.copy()
				others.remove(self)
		ret = []
		for n in others:
			nBB = n.boundingBox() if spacing is None else expandRect(n.boundingBox(), spacing)
			if overlaps(bb, nBB):
				ret.append(n)
		return ret

	def expand(self, filter:Optional[Callable[[Self, MRelation], bool]]=lambda vn, mr: True):
		rels = []
		for mRel in self.model.relations:
			if not self.tgview.categories.isCategory(mRel, self.tgview.hiddenCategories):
				if filter(self, mRel):
					vRel = self.tgview.findViewObjectForModelObject(mRel)
					if vRel is None:
						rels.append(mRel)
		if len(rels) > 0:
			bb = self.boundingBox()
			x = bb[2] + 50
			y = len(rels) * 25
			for r in rels:
				self.tgview.makeViewObjectForModelObject(r, atPoint=[x,y])
				y += 50

	def contract(self, filter:Optional[Callable[[Self, MRelation], bool]]=lambda vn, mr: True):
		for mRel in self.model.relations:
			if filter(self, mRel):
				vRel = self.tgview.findViewObjectForModelObject(mRel)
				if vRel is not None:
					otherNode = vRel.toNode if vRel.fromNode is self else vRel.fromNode
					if len(otherNode.relations) <= 1:
						vRel.delete()
						otherNode.delete()


	### RELATIONS ########################################################################

	def addRelation(self, relation): #, direction):
		from tygra.vrelations import VRelation
		if not isinstance(relation, VRelation):
			raise TypeError("VNode.addRelation(): first argument must be of type VRelation.")
		self.relations.append(relation) #(relation, direction))
# 		relation.model.addObserver(self) # observer the relation MODEL

	def notifyRelationDeletion(self, relation):
		""" This is the notification from removal of a relation VIEW. """ 
		for r in self.relations:
			if r == relation:
				self.relations.remove(r)
				break

	### MENUS ############################################################################
	
	def makeMenu(self) -> tk.Menu:
		m = tk.Menu(self.tgview)
# 		editable = not self.model.system and self.tgview.isModelEditor
		editable = self.tgview.isModelEditor
		if editable:
			self.addModelEditingMenuItems(m)
		self.addViewMenuItems(m)
		m.add_separator()
		self.addDeletionMenuItems(m)
		return m
		
	def addModelEditingMenuItems(self, menu:tk.Menu):
		disabled = self.model.system or not self.tgview.isModelEditor
		menu.add_command(label=f"{'show' if disabled else 'edit'} attributes", command=lambda: self.model.attrs.edit(self.tgview, \
			title=f'{type(self).__name__} {self.idString}->{self.model.idString} "{self.model.attrs["label"]}"', \
			disabled=disabled))
		menu.add_cascade(menu=self.makeMakeRelationMenu(menu), label='make relation')
		menu.add_separator()
		
	def addViewMenuItems(self, menu:tk.Menu):
		INSTANCE = "ISA (instance)"
		SUBTYPE = "ISA (subtype)"
		# collect info about the relations
		types = dict()	# {name: (modelOutgoingCount, modelIncomingCount, 
						#         viewOutgoingCount,  viewIncomingCount,  otherIsaTypeCount)}
		types[INSTANCE] = (0,0,0,0)
		types[SUBTYPE]  = (0,0,0,0)
		total = (0,0)
		for r in self.model.relations:
			# get the VNode that matches the MNode (if any)
			vRelation = None
			for rv in self.relations:
				if rv.model is r:
					vRelation = rv
					break
					
			# abort if this relation (r) is in a hidden category
			if self.tgview.categories.isCategory(r, self.tgview.hiddenCategories): continue
			
			name = r.attrs["label"]
			if name != "ISA":
				if name not in types: # add the name of the relation upon encountering a new one
					types[name] = (0,0,0,0)
				t = types[name]
			if r.toNode is self.model: # we're the toNode: increment incoming model and (maybe) view count 
				if name == "ISA":
					name = SUBTYPE if r.fromNode.attrs['type'] else INSTANCE
					t = types[name]
				t = (t[0], t[1]+1, t[2], t[3]+(0 if vRelation is None else 1))
			else: # we're the fromNode: increment outgoing model and (maybe) view count
				if name == "ISA":
					name = SUBTYPE if r.toNode.attrs['type'] else INSTANCE
					t = types[name]
				t = (t[0]+1, t[1], t[2]+(0 if vRelation is None else 1), t[3])
			types[name] = t
			total = (total[0]+1, total[1]+(0 if vRelation is None else 1))
		if types[INSTANCE] == (0,0,0,0): del types[INSTANCE]
		if types[SUBTYPE]  == (0,0,0,0): del types[SUBTYPE]

		# the expand menus
		expMenu = tk.Menu(menu)
		for k,v in types.items():
			subMenu = tk.Menu(expMenu)
			if v[0] > 0:
				if k == INSTANCE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and vn.model is mr.fromNode and not mr.toNode.attrs['type']
				elif k == SUBTYPE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and vn.model is mr.fromNode and mr.toNode.attrs['type']
				else:
					filter = lambda vn, mr, label=k: \
									mr.attrs["label"] == label and vn.model is mr.fromNode
				subMenu.add_command(label=f'outgoing ({v[0]})', \
						command=lambda f=filter: self.expand(filter=f))
			if v[1] > 0:
				if k == INSTANCE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and vn.model is mr.toNode and not mr.fromNode.attrs['type']
				elif k == SUBTYPE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and vn.model is mr.toNode and mr.fromNode.attrs['type']
				else:
					filter = lambda vn, mr, label=k: \
									mr.attrs["label"] == label and vn.model is mr.toNode
				subMenu.add_command(label=f'incoming ({v[1]})', \
						command=lambda f=filter: self.expand(filter=f))
			if v[0] > 0 and v[1] > 0:
				if k == INSTANCE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and not mr.fromNode.attrs['type']
				elif k == SUBTYPE:
					filter = lambda vn, mr: \
									mr.attrs["label"] == "ISA" and mr.fromNode.attrs['type']
				else:
					filter = lambda vn, mr, label=k: \
									mr.attrs["label"] == label
				subMenu.add_command(label=f'both ({v[0]+v[1]})', \
						command=lambda f=filter: self.expand(filter=f))
			subMenu.add_separator()
			for mr in self.model.relations:
				if k in [INSTANCE, SUBTYPE]: name = "ISA"
				else: name = k
				if mr.attrs["label"] == name:
					arrow = '->' if mr.fromNode is self.model else '<-'
					other = mr.toNode if mr.fromNode is self.model else mr.fromNode
					filter = lambda vn, mr, theMr=mr: mr is theMr
					subMenu.add_command(label=f'{k} {arrow} {other.attrs["label"]}',
								command = lambda f=filter: self.expand(filter=f))
			expMenu.add_cascade(menu=subMenu, label=f'expand {k} relations ({v[0]+v[1]})')
		menu.add_command(label=f"expand all ({total[0]})", command=self.expand)
		menu.add_cascade(menu=expMenu, label='expand')
		
		# The contract menus
		if total[1] > 0:
			conMenu = tk.Menu(menu)
			for k,v in types.items():
				subMenu = tk.Menu(conMenu)
				if v[2] > 0:
					if k == INSTANCE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and vn.model is mr.fromNode and not mr.toNode.attrs['type']
					elif k == SUBTYPE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and vn.model is mr.fromNode and mr.toNode.attrs['type']
					else:
						filter = lambda vn, mr, label=k: \
										mr.attrs["label"] == label and vn.model is mr.fromNode
					subMenu.add_command(label=f'outgoing ({v[2]})', \
							command=lambda f=filter: self.contract(filter=f))
				if v[3] > 0:
					if k == INSTANCE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and vn.model is mr.toNode and not mr.fromNode.attrs['type']
					elif k == SUBTYPE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and vn.model is mr.toNode and mr.fromNode.attrs['type']
					else:
						filter = lambda vn, mr, label=k: \
										mr.attrs["label"] == label and vn.model is mr.toNode
					subMenu.add_command(label=f'incoming ({v[3]})', \
							command=lambda f=filter: self.contract(filter=f))
				if v[2] > 0 and v[3] > 0:
					if k == INSTANCE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and not mr.fromNode.attrs['type']
					elif k == SUBTYPE:
						filter = lambda vn, mr: \
										mr.attrs["label"] == "ISA" and mr.fromNode.attrs['type']
					else:
						filter = lambda vn, mr, label=k: \
										mr.attrs["label"] == label
					subMenu.add_command(label=f'both ({v[2]+v[3]})', \
							command=lambda f=filter: self.contract(filter=f))
				conMenu.add_cascade(menu=subMenu, label=f'contract {k} relations ({v[2]+v[3]})')
			menu.add_command(label=f"contract all ({total[1]})", command=self.contract)
			menu.add_cascade(menu=conMenu, label='contract')
	
	def addDeletionMenuItems(self, menu:tk.Menu):
		menu.add_command(label="remove from view", command=self.delete)
		if not self.model.system and self.tgview.isModelEditor:
			menu.add_command(label="delete from model", command=self.model.delete)
	
	def makeMakeRelationMenu(self, menu:tk.Menu):
		m = tk.Menu(menu)
		types = []
		for t in (t for t in self.tgview.model._relations if t.attrs['type']):
				types.append(t)
		# TODO: sort menu?
		for t in types:
			m.add_command(label=t.attrs['label'], 
				command=lambda t=t: self.setMakingRelation(typ=t))
		return m

	### Event handling ###################################################################

	def onRightMouse(self, event):
		"""Creates and displays the node specific menu at the clicked location."""
		self.tgview.addEventHandled(event)
		m = self.makeMenu()
		m.post(event.x_root, event.y_root)
		return m

	def setMakingRelation(self, val=True, typ=None):
		self.tgview.makeRelationFrom(self, typ=typ)
		#self.dragInfo = None

	def onButton_1(self, event): #get initial location of object to be moved
		self.tgview.addEventHandled(event)
		winX = event.x - self.tgview.canvasx(0)
		winY = event.y - self.tgview.canvasy(0)
		self.dragInfo = (winX, winY)
		self.old_suppressLocalLayout = self.tgview.suppressLocalLayout()
		self.tgview.suppressLocalLayout(True)
		return 'break'

	def onB1_Motion(self, event):
		if self.dragInfo != None:
			winX = event.x - self.tgview.canvasx(0)
			winY = event.y - self.tgview.canvasy(0)
			newX = winX - self.dragInfo[0]
			newY = winY - self.dragInfo[1]
			self.moveBy(newX, newY)
			# reset the starting point for the next move
			self.dragInfo = (winX, winY)
			self.tgview.addEventHandled(event)
			return 'break'



	def onB1_ButtonRelease(self, event): #reset data on release
		if self.dragInfo != None:
			self.dragInfo = None
			self.tgview.suppressLocalLayout(self.old_suppressLocalLayout)
			self.onDragRelease(event)
			self.tgview.addEventHandled(event)
			return 'break'
			# TODO: add updating the boundingBox and the boundingBox attribute too.
			
	def onDragRelease(self, event):
		self.adjustPos()

	def notifyModelChanged(self, modelObj, modelOperation:str, info:Optional[any]=None):
# 		if modelObj != self.model: # it must be that a isa-ancestor of the model changed,
# 			self.tgview.logger.write(f'VNode.notifyModelChanged({modelObj}[NOT self.model], "{modelOperation}", info={info}) [{self}]', level="debug")
# 			self.updateFromAttrs([info[0]])
		unhandled = False
		if modelOperation == 'del': 
			if modelObj is self.model:
				self.delete()
			elif modelObj in self.relations:
				for r in self.relations:
					if r.model is modelObj:
						self.relations.remove(r)
						if isinstance(modelObj, Isa):
							self.redraw()
						break
		elif modelOperation == 'mod attr':
			assert info[1] is not None
			if modelObj == self.model:
				self.notifyAttrChanged(self.model.attrs, info[0], info[1])
			self.redraw()

		elif modelOperation == 'add rel':
			# the model is telling us about a added relation, but we rely on the VRelation's model to handle any added relations.
			pass
# 			if not hasattr(self, "addrel123"):
# 				unhandled = True
# 				self.addrel123 = True
		elif modelOperation == 'del rel':
			done = False
			if modelObj is not self.model: # the model is telling us about a deleted relation, but we rely on the VRelation's model to handle any deleted relations.
				for r in self.relations:
					if r.model is modelObj:
						r.model.removeObserver(self)
						r.delete()
						done = True
						break
				if not done:
					self.tgview.logger.write(f'VNode.notifyModelChanged() [{self}]: Got a "del rel" operation for "{modelObj}" that isn\'t one of my relations {self.relations}.', level='warning')
# 			if not hasattr(self, "delrel123"):
# 				unhandled = True
# 				self.delrel123 = True
		else:
			raise NotImplementedError(f'VNode.notifyModelChanged(): operation "{modelOperation}" not implemented.') 
		if unhandled:
			self.tgview.logger.write(f'VNode.notifyModelChanged(): operation "{modelOperation}" not implemented.', level='warning') 

	### Debugging support ################################################################
	
	def __str__(self):
		try:
			label = self.label()
		except:
			label = '<no label>'
		model = '<no model>' if self.model is None else self.model.idString
		return f'({type(self).__name__} [{self.idString}, "{label}"], model={model}{" *DELETED*" if self._deleted else ""})'

	def __repr__(self):
		return self.__str__()

		
	
import tygra.layout

##########################################################################################
################################### S H A P E S ##########################################
##########################################################################################

class Shape:
	@classmethod
	def isPublic(cls): return False

	@classmethod
	def getShapeClass(cls, name:str):
		try:
			klass = globals()[name]
		except:
			return None
		if issubclass(klass, Shape):
			return klass
		return None
	
	@classmethod
	def shapeValidator(cls, name:Optional[str]):
		if name is None:
			classes = allConcreteSubclasses(Shape)
			return [c.__name__ for c in classes if c.isPublic()]
		c = Shape.getShapeClass(name)
		if c is None:
			raise ValueError(f'Shape.shapeValidator(): name "{name}" is not the name of a subclass of Shape.')
		return c.__name__

	def innerBox(self, rect=None):
		pass

	@staticmethod
	def transform(old, new, pointsVector): # -> newPointsVector
		"""return the transform of the points vector to fit the new bounding box"""
		assert len(old) == 4
		assert len(new) == 4
		assert len(pointsVector)%2 == 0

		oox = old[0] # old offset
		nox = new[0] # new offset
		owx = abs(old[2] - old[0]) # old width
		nwx = abs(new[2] - new[0]) # new width
		stretchx = nwx/owx
		ooy = old[1] # old offset
		noy = new[1] # new offset
		owy = abs(old[3] - old[1]) # old width
		nwy = abs(new[3] - new[1]) # new width
		stretchy = nwy/owy
		newPoints = []
		for i in range(0, len(pointsVector), 2):
			x = (pointsVector[i]   - oox) * stretchx + nox
			y = (pointsVector[i+1] - ooy) * stretchy + noy
			newPoints.append(x)
			newPoints.append(y)
		return newPoints

	def __init__(self, vnode:VNode, rect:list[float], **kwargs):
		"""
		points: A list of numbers where the even (starting with zero) indices are x's and
			the odd indices are y's. Must have an even number of elements.
		"""
		assert len(rect) == 4
		self.vnode = vnode # container
		self.id = None # id of the tgview draw item
		self.kwargs = kwargs
		self.boundingBox(rect)
		
	def delete(self):
		# remove the shape
		self.vnode.tgview.delete(self.id)
		self.kwargs = None
		self.vnode = None
		
	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [0.0, 0.0, 
				1.0, 0.0, 
				1.0, 1.0, 
				0.0, 1.0] # bounding box rectangle
	
	def points(self, rect:Optional[list[float]]=None) -> list[float]:
		"""
		:param rect: a rectangle taken as the bounding box for this Shape's points
					in VIEW coordinates. 
		:return: Returns the vertex points fitted to *rect* if it's given, otherwise 
					*self.boundingBox(), in VEIW coordinates (not WINDOW coordinates).
					
		If subclasses have properly overridden the *template()* method, there should
		be no need to override this method.
		"""
		if rect is None:
			rect = self.boundingBox()
		return self.transform([0,0,1,1], rect, self.template()) # points in WINDOW coordinates
	
#	def _moveBy(self, x, y):
#		for i in range(0, len(self.points), 2):
#			self.points[i]   = self.points[i]   + x
#			self.points[i+1] = self.points[i+1] + y
			
	def moveTo(self, x, y):
		"""
		:param x: in view coordinates
		:param y: in view coordinates
		"""
#		bb = self.boundingBox()
#		dx = x - bb[0]
#		dy = y - bb[1]
#		self._moveBy(dx, dy)
#		self.vnode.tgview.moveto(self.vnode.tag, x, y)
		x, y = self.vnode.tgview.viewToWindow(x,y)
		self.vnode.tgview.moveto(self.vnode.tag, x, y)
		

	def boundingBox(self, new=None): # -> list(float):
		"""
		Get or set the bounding box of this shape in view cooradinates.
		In the case of setting, update this shape on the tgview.
		"""
		if new!=None: # new bb
			self.declaredBB = new
			points = self.points(new) #self.transform([0,0,1,1], new, self.points())
			if self.id is not None and self.id >= 0: # no point in updated the tgview if we haven't drawn this shape yet...
				self.vnode.tgview.coords(self.id, self.vnode.tgview.viewToWindow(points))
#				self.vnode.redraw()

		if self.id is None:
			ret = self.declaredBB
#			points = self.points()
#			# calculate the bounding box from the points vector
#			minx = miny =  100000
#			maxx = maxy = -100000
#			for i in range(0, len(points)-1, 2):
#				x = points[i]
#				y = points[i+1]
#				if x<minx: minx = x
#				if y<miny: miny = y
#				if x>maxx: maxx = x
#				if y>maxy: maxy = y	
#			ret = [minx, miny, maxx, maxy]
		else:
			ret = self.vnode.tgview.windowToView(self.vnode.tgview.bbox(self.id))
#		assert ret[0] < 10000
		return ret

	def redraw(self, **kwargs):
		self.kwargs.update(kwargs)
		if self.id is not None:
			self.vnode.tgview.itemconfigure(self.id, **kwargs)

		
	def draw(self, rect=None) -> int:
		assert self.id is None, f'Shape.draw() [{self.vnode}]: .draw() called twice.'
		if rect != None:
			self.boundingBox(rect)
		self.id = self.vnode.tgview.create_polygon(self.points(), **self.kwargs)
		self.vnode.tgview.itemconfigure(self.id, tags=self.vnode.tag)
		
		return self.id
		
class Rectangle(Shape):
	@classmethod
	def isPublic(cls): return True


class RightParallelogram(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [self.cutIn  , 0,
				1           , 0,
				1-self.cutIn, 1,
				0           , 1]
	

class LeftParallelogram(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [0           , 0,
				1-self.cutIn, 0,
				1           , 1,
				self.cutIn  , 1]

class FileFolder(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		d = 0.3 # fraction the tab covers
		s = 0.02 # slope offset of the tab edge
		return [0,		self.cutIn,
				1-d,	self.cutIn,
				1-d+s,	0,
				1-s,	0,
				1,		self.cutIn,
				1,		1,
				0,		1]

class TopPentagon(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [0,	0+self.cutIn,
				0.5,0,
				1,  0+self.cutIn,
				1,	1,
				0,	1]

class RightPentagon(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [0			,		0,
				1-self.cutIn,		0,
				1			,		0.5,
				1-self.cutIn,		1,
				0			,		1]

class LeftPentagon(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [self.cutIn, 0,
				1         , 0,
				1         , 1,
				self.cutIn, 1,
				0         ,	0.5]

class Hexagon(Shape):
	def __init__(self, vnode, rect:list[float], cutIn=0.05, **kwargs):
		self.cutIn = cutIn
		super().__init__(vnode, rect, **kwargs)

	@classmethod
	def isPublic(cls): return True

	def template(self): 
		"""
		Templates always return a list of vertex points bound by a [0,0,1,1] rectangle.
		Subclasses should override this to yield their own shape vertices.
		"""
		return [self.cutIn  , 0,
				1-self.cutIn, 0,
				1           , 0.5,
				1-self.cutIn, 1,
				self.cutIn  , 1,
				0           , 0.5]

class RoundedShape(Shape):
	def __init__(self, vnode, rect:list[float], sharpness=1.5, **kwargs):
		"""
		Based on https://stackoverflow.com/questions/44099594/how-to-make-a-tkinter-tgview-rectangle-with-rounded-corners.
		"""
		self.sharpness = sharpness
		if "smooth" not in kwargs:
			kwargs["smooth"] = tk.TRUE

		super().__init__(vnode, rect, **kwargs)

	def points(self, rect:Optional[list[float]]=None) -> list[float]: 
		sharpness = self.sharpness
		polyPoints = self.template()
		
		# The sharpness here is just how close the sub-points
		# are going to be to the vertex. The more the sharpness,
		# the more the sub-points will be closer to the vertex.
		# (This is not normalized)
		if sharpness < 1.5:
			sharpness = 1.5

		x = [] #vector of all the x coordinates
		y = [] #vector of all the y coordinates
		for i in range(0, len(polyPoints), 2):
			x.append(polyPoints[i])
			y.append(polyPoints[i+1])

		ratioMultiplier = sharpness - 1
		ratioDividend = sharpness

		# Array to store the points
		points = []

		# Iterate over the x points
		for i in range(len(x)):
			# Set vertex
			points.append(x[i])
			points.append(y[i])

			# If it's not the last point
			if i != (len(x) - 1):
				# Insert submultiples points. The more the sharpness, the more these points will be
				# closer to the vertex.
				points.append((ratioMultiplier*x[i] + x[i + 1])/ratioDividend)
				points.append((ratioMultiplier*y[i] + y[i + 1])/ratioDividend)
				points.append((ratioMultiplier*x[i + 1] + x[i])/ratioDividend)
				points.append((ratioMultiplier*y[i + 1] + y[i])/ratioDividend)
			else:
				# Insert submultiples points.
				points.append((ratioMultiplier*x[i] + x[0])/ratioDividend)
				points.append((ratioMultiplier*y[i] + y[0])/ratioDividend)
				points.append((ratioMultiplier*x[0] + x[i])/ratioDividend)
				points.append((ratioMultiplier*y[0] + y[i])/ratioDividend)
				# Close the polygon
				points.append(x[0])
				points.append(y[0])

		if rect is None:
			rect = self.boundingBox()
		return self.transform([0,0,1,1], rect, points) # points in WINDOW coordinates

class RoundedRectangle(RoundedShape):
	def __init__(self, vnode, rect:list[float], sharpness=2, **kwargs):
		super().__init__(vnode, rect, sharpness, **kwargs)
		
	@classmethod
	def isPublic(cls): return True

class Oval(Shape):
	def __init__(self, vnode, rect:list[float], **kwargs):
		super().__init__(vnode, rect, **kwargs)		

	@classmethod
	def isPublic(cls): return True

#	def boundingBox(self, new=None): # -> list(float):
#		"""
#		Get or set the bounding box of this shape.
#		In the case of setting, update this shape on the tgview.
#		"""
#		if new!=None:
#			self.points = self.transform(self.boundingBox(), new, self.points)
#			if self.id  and self.id >= 0: # no point in updated the tgview if we haven't drawn this shape yet...
#				self.vnode.tgview.coords(self.id, self.boundingBox())
#			# TODO: optimize by just returning new instead of doing the calculation below
#
#		# calculate the bounding box from the points vector
#		for i in range(0, len(self.points)-1, 2):
#			x = self.points[i]
#			y = self.points[i+1]
#			if x<minx: minx = x
#			if y<miny: miny = y
#			if x>maxx: maxx = x
#			if y>maxy: maxy = y
#		return [minx, miny, maxx, maxy]

	def draw(self, rect=None) -> int:
		assert self.id is None, f'Oval.draw() [{self.vnode}]: .draw() called twice.'
		bb = None
		if rect != None:
			bb = self.boundingBox(rect)
		else:
			bb = self.boundingBox()
		self.id = self.vnode.tgview.create_oval(self.vnode.tgview.viewToWindow(bb), **self.kwargs)
		self.vnode.tgview.itemconfigure(self.id, tags=self.vnode.tag)
		return self.id
	

##########################################################################################
################################ D E C O R A T O R S #####################################
##########################################################################################

class Decorator(ABC):
	def __init__(self, owner:VObject):
		super().__init__()
		self.owner = owner
		self.kind = type(self).__name__
		self.id = 0 # The id of the tgview item

	@abstractmethod
	def delete(self):
		pass

	@abstractmethod
	def draw(self):
		pass

	@abstractmethod
	def redraw(self, **kwargs):
		pass

class Text(Decorator):
	def __init__(self, owner:VObject, **kwargs):
		super().__init__(owner)
		self.kwargs = kwargs
		if "justify" not in self.kwargs: self.kwargs["justify"] = "center"
		if "anchor"  not in self.kwargs: self.kwargs["anchor"]  = "center"
		if "font"    not in self.kwargs: self.kwargs["font"]    = (self.owner.tgview._fontFace, int(self.owner.tgview._fontSize*self.owner.tgview._scale))
		if "fill"    not in self.kwargs: self.kwargs["fill"]    = "black"
		self.id = None

	def draw(self):
		assert self.id is None, f'Text.draw() [{self.owner}]: .draw() called twice.'
		self.kwargs['text'] = str(self.owner.model.attrs['label'])
		self.kwargs["state"] = "disabled"
		self.kwargs["tags"] = [self.owner.tag, 'text']
		x, y = self.owner.centerPt()
		x += 3
		x, y = self.owner.tgview.viewToWindow(x,y)
		self.id = self.owner.tgview.create_text(x, y, **self.kwargs)
		
	def redraw(self, **kwargs):
		self.kwargs.update(kwargs)
		self.kwargs['text'] = str(self.owner.model.attrs['label']).strip()
		self.kwargs["font"] = (self.owner.tgview._fontFace, int(self.owner.tgview._fontSize * self.owner.tgview._scale))
		if self.id is not None:
			x, y = self.owner.centerPt()
			x += 3
			x, y = self.owner.tgview.viewToWindow(x,y)
			self.owner.tgview.coords(self.id, x, y)
			self.owner.tgview.itemconfigure(self.id, **self.kwargs)

	def getAttr(self, name):
		if name in self.kwargs:
			return self.kwargs[name]
		else:
			return None
		
	def delete(self):
		self.owner.tgview.delete(self.id)
		self.owner.notifyDecoratorDeletion(self)
		self.kwargs = None
	
class WrappingText(Text):

	def __init__(self, owner:VObject, **kwargs):
		super().__init__(owner, **kwargs)
		self.text = NONE
		self.minSize = -1
		self.aspectRatio = 0

	def draw(self):
		super().draw()
		self._redraw()

	def _redraw(self):
		self.kwargs["font"] = (self.owner.tgview._fontFace, int(self.owner.tgview._fontSize * self.owner.tgview._scale))
		dirty = False
		text = str(self.owner.model.attrs['label']).strip()
		self.kwargs['text'] = text
		if text != self.text: 
			dirty = True
			self.text = text
		minSize = self.owner.model.attrs["minSize"]
		if minSize != self.minSize: 
			dirty = True
			self.minSize = minSize
		aspectRatio = self.owner.model.attrs["aspectRatio"]
		if aspectRatio != self.aspectRatio: 
			dirty = True
			self.aspectRatio = aspectRatio

		# We may need to change the size of the Shape
		if dirty:
			area = len(text)*160
			width = sqrt(area/aspectRatio) # area = width * width*aspectRatio
			if width > minSize: # we need to make the Shape bigger
				self.kwargs["width"] = width
				self.owner.tgview.itemconfigure(self.id, **self.kwargs)
				height = area/width
				bb = self.owner.boundingBox()
				self.owner.boundingBox([bb[0], bb[1], bb[0]+width, bb[1]+height])

		self.owner.tgview.itemconfigure(self.id, **self.kwargs)
					
	def redraw(self, **kwargs):
		self.kwargs.update(kwargs)
		self.kwargs['text'] = str(self.owner.model.attrs['label']).strip()
		self._redraw()		
		x, y = self.owner.centerPt()
		x += 3 	 	
		x, y = self.owner.tgview.viewToWindow(x,y)
		self.owner.tgview.coords(self.id, x, y)

class TypeMarker(Decorator):
	def __init__(self, owner:VObject, **kwargs):
		super().__init__(owner)
		self.kwargs = kwargs
		self.kwargs2 = {"fill": "grey", "outline": ""}
		self.id = None
		self.id2 = None
		self.offset = (-3,-3)
		self.size = (6,6) # actually, this is half of the size

	def setArgs(self):
		if self.owner.model.attrs["type"]:
			self.kwargs["text"] = "T"
		elif self.owner.model.system:
			self.kwargs["text"] = "S"
		else:
			self.kwargs["text"] = ""
			
		self.kwargs2["fill"] = "black" if self.owner.model.system else "grey"
		
	def draw(self):
		assert self.id is None, f'Text.draw() [{self.owner}]: .draw() called twice.'
		self.kwargs["state"] = "normal"
		self.kwargs["tags"] = [self.owner.tag, 'text']
		if "justify" not in self.kwargs: self.kwargs["justify"] = "center"
		if "anchor"  not in self.kwargs: self.kwargs["anchor"]  = "center"
		if "font"    not in self.kwargs: self.kwargs["font"]    = ("TkSmallCaptionFont", int(self.owner.tgview._fontSize * self.owner.tgview._scale))
		if "fill"    not in self.kwargs: self.kwargs["fill"]    = "white"
		self.setArgs()
		x, y, _, _ = self.owner.boundingBox()
		self.id2 = self.owner.tgview.create_oval(
								self.owner.tgview.viewToWindow(
								[x+self.offset[0]-self.size[0], 
								 y+self.offset[1]-self.size[1], 
								 x+self.offset[0]+self.size[0], 
								 y+self.offset[1]+self.size[1]]),
								 **self.kwargs2)
		self.id  = self.owner.tgview.create_text(x+self.offset[0], y+self.offset[1], **self.kwargs)
		
	def redraw(self, **kwargs):
		self.kwargs.update(kwargs)
		if self.id is not None:
			self.setArgs()
			x, y, _, _ = self.owner.boundingBox()
			self.owner.tgview.coords(self.id2, 
								self.owner.tgview.viewToWindow(
								[x+self.offset[0]-self.size[0], 
								 y+self.offset[1]-self.size[1], 
								 x+self.offset[0]+self.size[0], 
								 y+self.offset[1]+self.size[1]]))
			self.owner.tgview.coords(self.id, self.owner.tgview.viewToWindow([x+self.offset[0], y+self.offset[1]]))
			self.kwargs["font"] = ("TkSmallCaptionFont", int(self.owner.tgview._fontSize * self.owner.tgview._scale))
			self.owner.tgview.itemconfigure(self.id, **self.kwargs)
			self.owner.tgview.itemconfigure(self.id2, **self.kwargs2)

	def getAttr(self, name):
		if name in self.kwargs:
			return self.kwargs[name]
		else:
			return None
		
	def delete(self):
		self.owner.tgview.delete(self.id)
		self.owner.tgview.delete(self.id2)
		self.owner.notifyDecoratorDeletion(self)
		self.kwargs = None
		self.kwargs2 = None
