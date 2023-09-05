"""
Implements an attributes dictionary from string key names to arbitrary type values. An interactive user
dialog to edit the attributes is also implemented. Each attribute enjoys "properties", including:

* system: (bool) indicating the attribute is a system attribute and shouldn't be user editable.
* editable: (bool) specifying the attribute is editable.
* final: (bool) indicating the attribute cannot be overridden by a subtype.
* kind:	(str) The type of the attribute, currently 'text', 'mtext' (multi-line
  text), 'int', 'color', 'set', 'bool', 'choices', or 'unknown'. If this argument is 
  None, the kind will be inferred by the type of the *value* argument. 'choices' is 
  inferred if the value is a list of str, where the first one in the list is the actual value.
* default:	(Any) The attribute value is not inheritable, but the child gets the
  attribute as locally instantiated with the default value.
* validator: (f()|None) None, or a function taking a single argument (the proposed 
  value) and either raising an exception or returning the value (possibly modified).
  In the case of the 'choices' *kind*, if None is passed to the validator, it should
  return a list of str of all the possible choices. 'choices' is the only kind
  that requires a validator. However, if a list is passed as the *value*, then this
  class will construct its own validator with the obvious interpretation of the value
  must be in that list (first list item is taken as the initial value, and that first
  item can be repeated in the list to indicate it doesn't fall first in the choice
  menu in the edito dialog.
  
----
"""
import xml.etree.ElementTree as et
from ast import literal_eval
from typing import Any, Optional, Iterable, Callable
from tygra.util import PO, AddrServer
from abc import ABC, abstractmethod # Abstract Base Class
import tkinter as tk
from tkinter import colorchooser
from tkinter import ttk
from tygra.app import SYS_ATTRIBUTES
from collections import namedtuple
import re


TYPES = ['text', 'mtext', 'int', 'float', 'color', 'set', 'bool', 'choices', 'unknown']

class AttrObserver(ABC):
	@abstractmethod
	def notifyAttrChanged(self, attrsObject, name:str, value:Any): pass
	
class AttrOwner(ABC):
	@abstractmethod
	def getAttrParents(self) -> list: pass

class Attributes(PO):
	"""
	Provides a set of inheritable attributes, loosely imitating a *dict*.
	Use *add()* to add a new element.  Use *__setitem__()* (aka *[]*) to change the value
	of an item (which will also trigger a *notifyAttrChanged()* call to the observers
	if the value actually changed.).
	"""

	### NESTED CLASSES ###################################################################
	
	class Item(PO):
		"""
		A class to represent a single element of an attributes list.
		"""
		def __init__(self, key, value, final=False, editable=True, kind:Optional[str]=None,
						default:Any=None, validator:Callable[[Optional[Any]],Any]=None):
			"""
			:param key:		The name of the attribute (the redundant key for the dictionary.
			:param value:	The value of the attribute.
			:param final:	This attribute value cannot be overridden by a subtype.
			:param editable: This attribute can/cannot be edited. This attribute DOES NOT inherit.
			:param kind:	The type of the attribute, currently 'text', 'mtext' (multi-line
				text), 'int', 'color', 'set', 'bool', 'choices', or 'unknown'. If this argument is 
				None, the kind will be inferred by the type of the *value* argument. 'choices' is 
				inferred if the value is a list of str, where the first one in the list is the actual value.
			:param default:	The attribute value is not inheritable, but the child gets the
				attribute as locally instantiated with the default value.
			:param validator: None, or a function taking a single argument (the proposed 
				value) and either raising an exception or returning the value (possibly modified).
				In the case of the 'choice' *kind*, if None is passed to the validator, it should
				return a list of str of all the possible choices. 'choices' is the only kind
				that requires a validator. However, if a list is passed as the *value*, then this
				class will construct its own validator with the obvious interpretation of the value
				must be in that list (first list item is taken as the initial value, and that first
				item can be repeated in the list to indicate it doesn't fall first in the choice
				menu in the edito dialog.
			
			"""
			self.key = key
			self.value = value
			self.final = final # This item can't be overridden by a child
			self.editable = editable # this item's value can't be changed
			self.default = default
			self.validator = validator
			self.system = False # this item is a system item and shouldn't normally be shown to the user
			if kind is None:
				t = type(value)
				if t == str:
					if re.search('color', key, re.IGNORECASE) or re.search('colour', key, re.IGNORECASE):
						kind = 'color'
					elif '\n' in value:
						kind = 'mtext'
					else:
						kind = 'text'
				elif t == int:
					kind = 'int'
				elif t == float:
					kind = 'float'
				elif t == bool:
					kind = 'bool'
				elif t == set:
					kind = 'set'
				elif t == list:
					kind = 'choices'
				else:
					kind = 'unknown'
			if kind not in TYPES:
				raise TypeError(f'Attributes.Item.__init__(): Unknown kind "{kind}" for attribute name "{key}".')
			if kind == 'choices':
				if validator is None:
					if not (isinstance(value, list) and len(value) > 0):
						raise TypeError(f'Attributes.Item.__init__(): Cannot infer validator for kind "choices" unless value is a list (for attribute name "{key}).".')
					self.value, self._choices = self._doChoicesList2ValAndList(value)
					validator = self._choiceValidator
			self.kind = kind
			
		def _doChoicesList2ValAndList(self, choices:list[str]) -> tuple[str,list]:
			"""
			A choices list is often specifically ordered, but the first item is the current value.
			Therefore if we find the first element repeated in the rest of the list, we take the
			first item as the current value, and the rest of the list as the choices list.  If it
			is not repeated, we take the first item as the value and the entire list as the 
			choices list.
			"""
			value = choices[0]
			if choices[0] in choices[1:]:
				choices = choices[1:]
			return value, choices.copy() 
			
		def _choiceValidator(self, val:str) -> str:
			"""
			An internal choices validator in the event the user doesn't supply a validator for a
			choices kind.
			"""
			if val is None:
				return self._choices
			if val not in self._choices:
				raise ValueError(f'value "{val}" should be one of {self._choices}.')
			return val 

		def __str__(self):
			return "(" + self.key + ": "+ str(self.value) + ", " + \
					("final" if self.final else "overridable") + ", " + \
					("editable" if self.editable else "non-editable") + ", " + \
					("kind=" + str(self.kind)) + ")"
					
		### Item: PERSISTENCE ############################################################
	
		def xmlRepr(self) -> et.Element:
			elem = et.Element(type(self).__name__)
# 			elem.set("name", name)
			elem.set("key", str(self.key))
			kind = str(self.kind)
			value = str(self.value)
			if kind == 'choices':
				elem.set("value", str([value] + self.validator(None)))
			else:
				elem.set("value", value)
			elem.set("kind", kind)
			if self.default is not None:
				elem.set("defaut", str(self.default))
			if self.final != False: 
				elem.set("final", str(self.final))
			if self.editable != True:
				elem.set("editable", str(self.editable))
			return elem

		@classmethod
		def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
			args = []
			kwargs = dict()

			key = elem.get("key")
			args.append(key)
			
			value = elem.get('value')
			try:
				value = literal_eval(value)
			except: # failed to interpret the value as an object, so we can assume it's just a string
				pass				
			args.append(value)
			
			final = elem.get('final')
			final = literal_eval(final) if final is not None else False
			kwargs["final"] = final
			
			editable = elem.get('editable')
			editable = literal_eval(editable) if editable is not None else True
			kwargs["editable"] = editable
			
			kind = elem.get('kind')
			kwargs["kind"] = kind			

			default = elem.get('default')
			default = literal_eval(default) if default is not None else None
			kwargs["default"] = default
		
			return args, kwargs
			
		def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
			"""
			This object is partially constructed, but we need to restore this class's bits.
			Implementors should call *super().xmsRestore()* at some point.
			"""
			super().xmlRestore(elem, addrServer)
			
# 			if self.kind == 'choices':
# 				assert isinstance(self.value, list)
# 				assert len(self.value) > 0
# 				self.value, self._choices = _doChoicesList2ValAndList(self.value)
# 				self.validator = self._choiceValidator
	
	### CONSTRUCTOR ######################################################################

	def __init__(self, owner:Optional[AttrOwner]=None):
		"""
		:param owner: is the object that must supply a *notifyAttrChange(name,value)* method.
		:type  owner: AttrOwner
		"""
		super().__init__()
		self._setOwner(owner)
		self.attrs:dict[str,Any] = dict()
		self.observers:list[AttrObserver] = []
		# run through to let the *defaults* settle in
		for k in self.keys():
			self.get(k)
			
	### PERSISTENCE ######################################################################
	
	def xmlRepr(self) -> et.Element:
		elem = et.Element(type(self).__name__)
		for _,v in self.attrs.items():
			elem.append(v.xmlRepr()) #k))
		return elem
	
	@classmethod
	def getArgs(cls, elem: et.Element, addrServer:AddrServer) -> tuple[list[Any], dict[str, Any]]:
		args = []
		kwargs = dict()

		return args, kwargs
	
	def xmlRestore(self, elem: et.Element, addrServer:AddrServer):
		"""
		This object is partially constructed, but we need to restore this class's bits.
		Implementors should call *super().xmsRestore()* at some point.
		"""
		super().xmlRestore(elem, addrServer)
		items = elem.findall("./Item")
#		print(f'Attributes.xmlRestore(): restoring {len(items)} items.')
		for subelem in items:
# 			name = subelem.get("name")
			item = PO.makeObject(subelem, addrServer, Attributes.Item)
			self.attrs[item.key] = item
#			print(f'Attributes.xmlRestore(): restored {name}.')

	### OBSERVERS ########################################################################

	def addObserver(self, observer:AttrObserver):
		"""
		Add an observer.
		"""
		self.observers.append(observer)
		
	def removeObserver(self, observer:AttrObserver):
		"""
		Remove an observer. Only prints a warning if the observer isn't on the observers list.
		"""
		if observer in self.observers:
			self.observers.remove(observer)
		else:
			print('Attributes.removeObserver() called with an unregistered observer.')
			
	def notifyObservers(self, key, value):
		"""
		Notify all the observers on the observers list.
		"""
		for ob in self.observers:
			try:
				ob.notifyAttrChanged(self, key, value)
			except Exception as ex:
				print(f'WARNING: Attributes.notifyObservers(): While notifying {ob}: {type(ex).__name__}, {ex}.')
		
	def ping(self, key):
		"""
		Calling this method signals to the Attributes object that some parent (getParents())
		has changed this key's value'.  This method reacts by calling notifyObservers()
		if this Attribute does NOT have a local value, on presumption that this value
		will have changed.
		"""
		if key in self.attrs: return
		self.notifyObservers(key, self.get(key))
	
#	def update(self):
#		keys = self.keys()
#		for k in keys:
#			r = self.get(k)
#			self.notifyObservers(k, r)

	### PRIMITIVE OPERATIONS #############################################################

	def _setOwner(self, owner:AttrOwner):
		if owner is not None and not isinstance(owner, AttrOwner):
			raise TypeError(f'Attributes.setOwner(): owner must be an instance of AttrOwner (parameter\'s type is {type(owner).__name__}).')
		self.owner = owner
		
	def getParents(self):
		"""Override this to implement a dynamic parent hierarchy."""
		try:
			return self.owner.getAttrParents() if self.owner is not None else []
		except:
			return []

	def add(self, name:str, value, 	final:Optional[bool]=False, 
									editable:Optional[bool]=True, 
									kind:Optional[str]=None, 
									suppressNotify=False,
									system=False,
									validator=None,
									default=None):
		"""Add a new attribute. Note that new attributes are added 
		
		:param name: the name of the attribute
		:type  name: str
		:param value: the value of the attribute
		:type  value: Any
		:param final: the attribute can't be overridden by a child
		:type  final: bool
		:param editable: the attribute is editable
		:type  editable: bool
		:param kind: type of the attribute
		:type kind: str
		:param suppressNotify: Don't notify the observers that there have been changes.
		:type suppressNotify: bool
		:param system: the attribute is a system attribute so don't show it to the user.
		:type system: bool
		:param validator: A validator function for the attribute value
		:type validator: Callable
		:param default: The attribute value is not inheritable, but the child gets the
			attribute as locally instantiated with the default value.
		:type default: Any
		:return: None
		:rtype: None
		"""
		pRec = self._get(name, includeLocals=False)
		if pRec:
			if pRec.final:
				raise AttributeError(f'Attributes.add(): cannot override attribute "{name}".')
		self.attrs[name] = Attributes.Item(name, value)
		self.config(name, final=final, editable=editable, kind=kind, default=default, \
				system=system, validator=validator, suppressNotify=suppressNotify)
# 		self.notifyObservers(name, value) # config() wouldn't have done it because the it didn't see the attribute change.

	def remove(self, name:str):
		"""
		Remove the attibute with key *name*.
		"""
		if name in self.attrs:
			self.attrs.pop(name)

	def config(self, key, value=None, 	final=None, 
										editable=None, 
										kind=None,
										default=None,
										system=None,
										validator=None,
										suppressNotify=False,
										_record=None):
		"""
		Most of arguments are as per the constructor, but there are some control arguments:
		:param suppressNotify: Don't notify the observers that there have been changes.
		:param _record: [Item] Use the value of this parameter as a template to update all
		the other parameters.
		"""
		if _record and (value or final or editable or kind):
			raise AttributeError('Attributes.config(): argument "_record" is inconsistent with arguments all other arguments.')
		if key not in self.attrs:
			raise KeyError(f'Attributes.config(): key "{key}" not found.')
		if _record:
			if not isinstance(_record, Attributes.Item):
				raise TypeError(f'Attributes.config(): expected a Attributes.Item in 2nd argument, got type {type(_record).__name__}.')
			value = _record.value
			final = _record.final
			editable = _record.editable
			kind = _record.kind
			system = _record.system
			validator = _record.validator
		pRec = self._get(key, includeLocals=False)
		if pRec:
			if pRec.final:
				raise AttributeError(f'Attributes.config(): cannot override attribute "{key}". Parent attribute is final.')
		oldRec = self.attrs[key] # The local old record
		if (not oldRec.editable) and value is not None and value != oldRec.value:
			raise AttributeError(f'Attributes.config(): cannot change attribute "{key}" value from "{oldRec.value}" ({type(oldRec.value).__name__}) to "{value}" ({type(value).__name__}). Attribute is not editable.')
		oldValue = oldRec.value
		if validator is not None: oldRec.validator = validator
		if value is not None:
			if oldRec.validator is not None:
				oldRec.value = oldRec.validator(value) # might raise and exception
			else:
				oldRec.value = value
		if final is not None: oldRec.final = final
		if editable is not None: oldRec.editable = editable
		if kind is not None: oldRec.kind = kind
		if default is not None: oldRec.default = default
		if system is not None: oldRec.system = system
		if value is not None and oldValue != value and not suppressNotify:
			self.notifyObservers(key, value)
			
	def _get(self, key, includeLocals=True, includeInherited=True):
		"""
		An internal getter that returns the entire *Item* record for *key*.
		"""
		cumulativeValue = []
		cumulativeRecord = None
		if includeLocals:
			if key in self.attrs.keys():
				at = self.attrs[key]
				if at.kind == 'set':
					if cumulativeRecord is None: cumulativeRecord = at
				if cumulativeRecord is not None:
					if isinstance(at.value, Iterable):
						cumulativeValue += list(at.value)
					else:
						cumulativeValue.append(at.value)
				else:
					return at
		if includeInherited:
			for p in self.getParents():
				v = p._get(key)
				if v is not None:
					if v.kind == 'set':
						if cumulativeRecord is None: cumulativeRecord = v
					if v.default is not None and key not in self.attrs:
						self.attrs[key] = Attributes.Item(key, v.default, final=v.final, editable=True, \
								kind=v.kind, default=v.default)
						return self._get(key, includeLocals=includeLocals, includeInherited=includeInherited)
					if cumulativeRecord is not None:
						if isinstance(v.value, Iterable):
							cumulativeValue += list(v.value)
						else:
							cumulativeValue.append(v.value)
					else:
						return v
		if cumulativeRecord is not None:
			if cumulativeRecord.kind == 'set':
				try:
					cumulativeRecord.value = set(cumulativeValue)
				except Exception as ex:
					raise type(ex)(f'{ex}: {cumulativeValue}')
			else:
				raise TypeError('Attributes._get(): Unexpected cumulative kind.')
		else:
			return None
		
	### OPERATIONS #######################################################################
		
	def get(self, key, includeLocals=True, includeInherited=True):
		"""
		Public getter.  Returns the value for the key.
		
		:param key: The key to find the value for.
		:param includeLocals: Suppress looking at local keys by setting this *False*. Useful
			if you want to check if this is an inherited value.
		:param includeInterited: Suppress looking for inherited key values by setting this to *False*.
			Useful if you want to check for only local values.
		"""
		ret = self._get(key, includeLocals=includeLocals, includeInherited=includeInherited)
		return ret.value if ret else None

	def isEditable(self, key):
		"""Returns *true* iff the *key* is editable."""
		item = self._get(key)
		return item.editable if item is not None else None

	def isFinal(self, key):
		"""Returns *true* iff the *key* is final."""
		item = self._get(key)
		return item.final if item is not None else None
		
	def getKind(self, key):
		"""Returns the *kind* of the key as a str."""
		item = self._get(key)
		return item.kind if item is not None else None		

	def isSystem(self, key):
		"""Returns *true* iff the *key* is system."""
		item = self._get(key)
		return item.system if item is not None else None		

	def getDefault(self, key):
		"""Returns the default value for this key."""
		item = self._get(key)
		return item.default if item is not None else None		

	### DICTIONARY-LIKE OPERATIONS #######################################################
		
	def keys(self, includeLocals=True, includeInherited=True):
		"""
		Standard *keys()* function for an iterator, with additional filter.
		
		:param includeLocals: Suppress looking at local keys by setting this *False*. Useful
			if you want to check if this is an inherited value.
		:param includeInterited: Suppress looking for inherited key values by setting this to *False*.
			Useful if you want to check for only local values.
		"""
		keys = []
		if includeLocals:
			for k in self.attrs.keys():
				keys.append(k)
		if includeInherited:
			for p in self.getParents():
				for k in p.keys():
					if (k not in keys):
						keys.append(k)
		return keys

	def items(self, includeLocals=True, includeInherited=True):
		"""
		Standard *items()* function for an iterator with additional filters. Returns a list
		of key/value pairs.
		
		:param includeLocals: Suppress looking at local keys by setting this *False*. Useful
			if you want to check if this is an inherited value.
		:param includeInterited: Suppress looking for inherited key values by setting this to *False*.
			Useful if you want to check for only local values.
		"""
		it = dict()
		if includeLocals:
			for k,v in self.attrs.items():
				it[k] = v.value
		if includeInherited:
			for p in self.getParents():
				for k,v in p.items():
					if (k not in it):
						it[k] = v
						print(f'too many: {k}: {v}.')
		return it.items()

	def _items(self, includeLocals=True, includeInherited=True):
		"""
		Internal version of *items()* that returns key/Item record pairs.
		"""
		it = dict()
		if includeLocals:
			for k,v in self.attrs.items():
				it[k] = v
		if includeInherited:
			for p in self.getParents():
				for k,v in p._items():
					if (k not in it):
						it[k] = v
		return it.items()

	def __getitem__(self, key):
		"""Overrides the [] operator."""
		return self.get(key)

	def __setitem__(self, key, value):
		"""
		Overrides the [] operator for assignment.
		IMPORTANT: Note that if you set a value in an inherited item, a new record will
		be created in THIS Attributes structure.
		"""
		if key in self.attrs:
			self.config(key, value=value)
		else:
			self.add(key, value) #raise KeyError()
			
	### PRINTING SUPPORT #################################################################
		
	def __str__(self, verbose=False):
		prefix = "{"
		ret = ""
		for key in self.keys():
			ret += prefix + key + ": " + str(self[key])
			prefix = ", "
		ret += '}'
		if verbose:
			ret += ", parents: " + str(self.getParents())
		return ret

	def __repr__(self, verbose=False):
		prefix = "{"
		ret = ""
		for key, item in self.attrs.items():
			ret += prefix + key + ": " + str(item)
			prefix = ", "
		ret += '}'
		if verbose:
			ret += ", parents: " + str(self.getParents())
		return ret
		
	### GUI ##############################################################################

	def edit(self, parentWindow, title=None, disabled=False):
		"""
		Put up a GUI dialog to edit the *Attributes*
		
		:param parentWindow: A parent for dialog.
		:param title: A title to put on the dialog window.
		:param disabled: Setting this to *False* will still show the dialog, but all fields will the locked (uneditable).
		"""
		print(f"Attributes.edit(): {self.__str__(True)}")
		editor = AttrEditor(parentWindow, self, title=title)
		editor.show(disabled=disabled)
		editor.destroy()
		
		
		

ChangeDescr = namedtuple("ChangeDescr", "oldValue tkVar delete")
		
class AttrEditor(tk.Toplevel):

	def __init__(self, parent, attrs:Attributes, title="Attribute Editor"):
		super().__init__(parent)
		self.parent = parent
		self.title(title if title else "Attribute Editor")
		self.attrs = attrs
		self.changes = dict() # name:Item
		self.vars = dict() # name:ChangeDescr
		


	def checkInt(self, newval):
		return re.match('^[0-9]*$', newval) is not None and len(newval) <= 20

	def checkFloat(self, newval):
		try:
			float(newval)
			return True
		except:
			return False

	def colorChooser(self, tkVar, button):
		color = colorchooser.askcolor(initialcolor=tkVar.get())
		color = color[1]
		if color is not None:
			tkVar.set(color)
			button.config(highlightbackground=color)
		
	def show(self, disabled=False):
# 		from tkinter import colorchooser
# 		colorchooser.askcolor(initialcolor='#ff0000')


		def makeEditor(key, item, column, row, disabled=False):
			editor = None
#			print(f'Item: {key}="{item.value}" ({item.kind}/{type(item.value).__name__})')
			if item.kind == 'text':
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=item.value), False)
				editor = ttk.Entry(self, textvariable=self.vars[key].tkVar)
			elif item.kind == 'mtext':
				editor = tk.Text(self, height=2)
				editor.insert('1.0', item.value)
				self.vars[key] = ChangeDescr(item.value, editor, False)
			elif item.kind == 'int':
				checkWrapper = (self.winfo_toplevel().register(self.checkInt), '%P')
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=str(item.value)), False)
				editor = ttk.Entry(self, textvariable=self.vars[key].tkVar, validate='key', validatecommand=checkWrapper)
			elif item.kind == 'float':
				checkWrapper = (self.winfo_toplevel().register(self.checkFloat), '%P')
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=str(item.value)), False)
				editor = ttk.Entry(self, textvariable=self.vars[key].tkVar, validate='key', validatecommand=checkWrapper)
			elif item.kind == 'bool':
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=str(item.value)), False)
				editor = ttk.Checkbutton(self, text='', variable=self.vars[key].tkVar, onvalue='True', offvalue='False')
			elif item.kind == 'color':
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=item.value), False)
				editor = tk.Button(self, text=item.value, highlightbackground=item.value)#, highlightthickness=4)
				editor.config(command=lambda v=self.vars[key].tkVar, e=editor: self.colorChooser(v, e))
			elif item.kind == 'choices':
				self.vars[key] = ChangeDescr(item.value, tk.StringVar(value=item.value), False)
				editor = ttk.Combobox(self, textvariable=self.vars[key].tkVar)
				editor['values'] = item.validator(None)
				editor.state(["readonly"])
			elif item.kind == 'unknown':
				editor = ttk.Label(self, text=str(item.value), foreground="brown")
			else:
				return None

			editor.grid(column=column, row=row, sticky='EW', padx=0, pady=0)
			if disabled:
				self.conf(editor, state= "disabled")#, foreground="blue")
			return editor

		def makeButton(key, item, column, row, text, command=None):
			if item.kind == 'unknown':
				return
			button = ttk.Button(self, text=text, width=8, padding=0)
			button.grid(column=column, row=row, sticky=tk.E, padx=0, pady=0)
			if command: 
				button.config(command=lambda b=button: command(b))
			return button

		def makeLabel(key, item, column, row):
			font = ('Helvetica', 14, 'bold italic') if k in SYS_ATTRIBUTES else ('Helvetica', 14, 'normal')
			label = ttk.Label(self, text=k+':', font=font)
			label.grid(column=column, row=row, sticky=tk.E, padx=0, pady=0)
			return label

		def makeKind(key, item, column, row):
			font = ('Helvetica', 8, 'bold') if item.kind=="unknown" else ('Helvetica', 8, 'normal')
			label = ttk.Label(self, text=item.kind, font=font)
			label.grid(column=column, row=row, sticky="sw", padx=0, pady=0)
			return label
			
		self.geometry("400x500")
		#self.title('Attributes')
		self.resizable(1, 1)

		# configure the grid
		cLabel = 0
		cEdit = 1
		cDel = 2
		cKind = 3
		span = 4
		self.columnconfigure(cLabel, weight=0)
		self.columnconfigure(cEdit,  weight=2)
		self.columnconfigure(cDel,   weight=0)
		self.columnconfigure(cKind,  weight=0)

		inherited = dict(self.attrs._items(includeLocals=False))
		localVals    = dict(self.attrs._items(includeInherited=False))
		
		i = 0
		ttk.Label(self, text="Local", font=('Helvetica', 18, 'bold')) \
			.grid(column=cEdit, row=i, sticky=tk.W, padx=0, pady=0)
		i += 1
		for k,v in localVals.items():
			if v.system: continue # hide system attributes
			makeLabel(k, v, cLabel, i)
			ed = makeEditor(k, v, cEdit, i, disabled=disabled or not v.editable)
			if v.default is None and not disabled:
				if k in inherited:
					makeButton(k, v, cDel, i, "del&inherit", command=lambda b, k1=k, v1=v, ed1=ed: self.deleteAndInhAttr(k1, v1, ed1, b))
				else:
					makeButton(k, v, cDel, i, "delete", command=lambda b, k1=k, v1=v, ed1=ed: self.deleteAttr(k1, v1, ed1, b))
			makeKind(k, v, cKind, i)
			i += 1
			
		ttk.Separator(self, orient='horizontal') \
			.grid(column=cLabel, row=i, columnspan=span, sticky=tk.W+tk.E, padx=0, pady=10)
		i+= 1
		ttk.Label(self, text="Inherited", font=('Helvetica', 18, 'bold')) \
			.grid(column=cEdit, row=i, sticky=tk.W, padx=0, pady=0)
		i += 1
		for k,v in inherited.items():
			if v.system: continue # hide system attributes
			if k not in localVals:
				makeLabel(k, v, cLabel, i)
				ed = makeEditor(k, v, cEdit, i, disabled=True)
				if not v.final and not disabled:
					makeButton(k, v, cDel, i, "override", command=lambda b, k1=k, v1=v, ed1=ed: self.override(k1, v1, ed1, b))
				makeKind(k, v, cKind, i)
				i += 1
			
		ttk.Separator(self, orient='horizontal') \
			.grid(column=cLabel, row=i, columnspan=span, sticky=tk.W+tk.E, padx=0, pady=10)
		i+= 1
		ttk.Button(self, text="Cancel", command=self.dismiss) \
			.grid(column=0, columnspan=span, row=i, sticky=tk.W, padx=20, pady=2)
		ttk.Button(self, text="Save Changes", command=self.save) \
			.grid(column=0, columnspan=span, row=i, sticky=tk.E, padx=20, pady=2)

		self.protocol("WM_DELETE_WINDOW", self.dismiss) # intercept close button
		self.transient(self.parent) # dialog window is related to main
		self.wait_visibility() # can't grab until window appears, so we wait
		self.grab_set()        # ensure all input goes to our window
		self.wait_window()     # block until window is destroyed
		
	def conf(self, tkObj, **kwargs):
		for k,v in kwargs.items():
			if isinstance(tkObj, tk.Button) and k=="state" and v == "!disabled":	
				v = "normal"
			d = dict()
			d[k] = v
			try: 
				tkObj.config(**d)
			except: 
				if k not in ["foreground", "background"]:
					print(f'WARNING: AttrEditor.show.conf(): Couldn\'t set attr "{k}" to "{v}" on tk type {type(tkObj).__name__}')

	def override(self, key, item, editor, button):
		text = button.config()['text'][-1]
		print(f"override: text = {text}")
		if text == 'override':
			button.config(text='revert')
			self.conf(editor, state="!disabled", foreground="black")
			self.vars[key].tkVar.set(item.value)
		else:
			button.config(text='override')
			self.conf(editor, state="disabled", foreground="blue")
			self.vars[key].tkVar.set(self.vars[key].oldValue) # revert
		
	def deleteAttr(self, key, item, editor, button):
		text = button.config()['text'][-1]
		print(f"deleteAttr: text = '{text}'")
		if text == 'delete':
			button.config(text='undelete')
			editor.config(state="disabled")
			self.vars[key] = ChangeDescr(self.vars[key].oldValue, self.vars[key].tkVar, True)
		else:
			button.config(text='delete')
			editor.config(state="!disabled")
			self.vars[key] = ChangeDescr(self.vars[key].oldValue, self.vars[key].tkVar, False)

	def deleteAndInhAttr(self, key, item, editor, button):
		text = button.config()['text'][-1]
		print(f"deleteAndInhAttr: text = {text}")
		if text == 'del&inherit':
			button.config(text='undelete')
			self.conf(editor, state="disabled", foreground="blue")
			self.vars[key] = ChangeDescr(self.vars[key].oldValue, self.vars[key].tkVar, True)
			pValue = self.attrs.get(key, includeLocals=False)
			self.vars[key].tkVar.set(pValue)
		else:
			button.config(text='del&inherit')
			self.conf(editor, state="!disabled", foreground="black")
			self.vars[key] = ChangeDescr(self.vars[key].oldValue, self.vars[key].tkVar, False)
			value = self.attrs.get(key, includeInherited=False)
			self.vars[key].tkVar.set(value)
		
	def dismiss(self):
		self.grab_release()
		self.destroy()
		
	def save(self):
		for k,v in self.vars.items():
			if v.delete: # flagged for deletion
				self.attrs.remove(k)
				continue
				
			# get the kind and the new value
			kind = self.attrs._get(k).kind
			if kind == 'mtext':
				newValue = v.tkVar.get('1.0', 'end').rstrip() # the Text widget is tk, and doesn't use a a ttk.Variable.
			else:
				newValue = v.tkVar.get() 
				
			if kind == 'int':
				try:
					newValue = int(newValue)
				except:
					print(f'WARNING: AttrEditor.save(): attribute {k} of kind int has value {newValue}, which failed the int test.  Not saving.')
					continue
			if kind == 'float':
				try:
					newValue = float(newValue)
				except:
					print(f'WARNING: AttrEditor.save(): attribute {k} of kind float has value {newValue}, which failed the float test.  Not saving.')
					continue
			elif kind == 'bool':
				try:
					newValue = newValue.lower() in ['true', 't', 'yes', 'y']
				except:
					print(f'WARNING: AttrEditor.save(): attribute {k} of kind bool has value {newValue}, which failed the bool test.  Not saving.')
					continue
					
			if v.oldValue != newValue:
				print(f"AttrEditor.save(): {k} changed from '{v.oldValue}' ({type(v.oldValue).__name__}) to '{newValue}' ({type(newValue).__name__}). Observers={self.attrs.observers}.")
				try:
					self.attrs.config(k, newValue)
				except KeyError:
					self.attrs[k] = Attributes.Item(k, newValue)
					# need to copy all the details from the inherited record to the new value...
					inhRec = self.attrs._get(k, includeLocals=False)
					inhRec.value = newValue
					inhRec.editable = True # the editable attribute does not inherit
					self.attrs.config(k, _record=inhRec)
					
				self.attrs.notifyObservers(k, newValue)
		self.grab_release()
		self.destroy()




if __name__ == "__main__":
	class C(AttrOwner, AttrObserver):
		def __init__(self):
			self.attrs = Attributes(self)
			self.parents = []
		def addParent(self, a):
			self.parents.append(a)
		def getAttrParents(self):
			return self.parents
		def notifyAttrChanged(self, obj, name, value):
			print(f'Got notification: {name} changed to {value}.')
			
	c = C()
	c2 = C()
	c2.attrs.addObserver(c2)
	
	c.attrs.add("height", 3)
	c.attrs.add("width", 5)
	c.attrs.add('label', "a label")
	print(c.attrs, "s/b {height: 3, width: 5}")
	print(c.attrs['height'], "s/b 3")
	c2.addParent(c.attrs)

	c2.attrs.add("height", 1)
	c.attrs.add("color", "red")
	print(c2.attrs, 's/b {height: 1, another: hi, width: 5}')
	print(c2.attrs.keys(), "s/b ['height', 'another', 'width']")
	print(c2.attrs["height"], c2.attrs["width"], c2.attrs["diag"], "s/b 1 5 None")
	c2.attrs["height"] = 101
	c2.attrs.removeObserver(c2)	
	c2.attrs.removeObserver(c2)	
	c2.attrs["height"] = 100
	c2.attrs["width"] = 500
	print(c2.attrs, "s/b {height: 100, another: hi, width: 500}")
	print(c.attrs, "s/b {height: 3, width: 5}")
	c2.attrs["x"] = 10
	c2.attrs.add("width", 5000)
	print(repr(c2.attrs), "s/b\n{height: (100, overridable, editable), another: (hi, overridable, editable), width: (5000, overridable, editable), x: (10, overridable, editable)}")
	print(repr(c.attrs), "s/b\n{height: (3, overridable, editable), width: (5, overridable, editable)}")
	root = tk.Tk()
	c2.attrs.addObserver(c2)
	c2.attrs["list"] = (1,2,3)
	while True:
		print(f'c.attrs: {c.attrs}')
		print(f'c2.attrs: {c2.attrs}')
		c2.attrs.edit(root)
	root.mainloop()
