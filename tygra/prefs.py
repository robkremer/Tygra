'''
Created on Sep. 5, 2023

@author: kremer
'''
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

import xml.etree.ElementTree as et
from tkinter.filedialog import askopenfiles
from typing import Optional, get_args, Union, Callable, TypeVar, Any, Generic, Type, Tuple, List, Dict
import tygra.app as app
import os
import tkinter as tk
import tkinter.ttk as ttk
from collections import namedtuple
import re
from tkinter import colorchooser
from tygra.tooltip import CreateToolTip
from pickle import FALSE
import tygra.util as util

T = TypeVar('T')

class Pref(Generic[T], object):
	def __init__(self, propertyName:str, owner:Any, kind:str, userName:Optional[str]=None, 
				help:Optional[str]=None, validatorFunc:Optional[Callable[[Any],Any]]=None,
				pythonType:Optional[Type]=None):
		"""
		:param propertyName: The string name of property in *owner*.
		:param owner: The owner of the this preference item.
		:param kind: The type used by the editor to make an edit box.  One of "text","choices:*[:*..]",...
		:param userName: The name to use in the preferences editor GUI.
		:param help: The help text to present in the tooltip in the editor GUI.
		:param validatorFunc: A function to replace :meth:`Pref.validate()`\ .
		:param pythonType: The python type corresponding to the type parameter T. (because
			python hasn't got it together on getting the top class yet...)
		"""
		self.owner = owner
		self.propertyName = propertyName
		if kind.startswith("choices:") or kind in ["text"]:
			self.kind = kind
		else:
			raise AttributeError("Pref.__init__(): Unknown kind: {kind}")
		self.userName = propertyName if userName is None else userName
		self.help = help
		self.validatorFunc = validatorFunc
		self.pythonType = pythonType
		if self.pythonType is None and (kind.startswith("choices:") or kind=="text"):
			self.pythonType = str
		val = getattr(self.owner, self.propertyName) # may throw AttributeError
		if self.pythonType is not None and not isinstance(val, self.pythonType):
			raise TypeError(f'Pref.__init__(): for property "{self.propertyName}", given property type {self.pythonType.__name__} does not match actual type of owner\'s property value, {type(val).__name__}.')

	
	def __call__(self, value:Optional[T]=None) -> T:
		"""
		Getter/setter for the value. May throw an exception if *value* is not valid. May throw
		*AttributeError* if *self.property* is not one of *self.owner*\ 's actual properties.
		
		:param value: Set the value in the object in the owner object to *value*. Only works if *value* is valid by the *self.validate()*.
		:return: The value of the object in the owner object. If *value* was set, this method should returns the **old** value.
		:throws AttributeError: if *self.property* is not one of *self.owner*\ 's actual properties.
		:throws TypeError: If *value* does not pass :meth:`Pref.validate`\ .
		"""
		oldVal = getattr(self.owner, self.propertyName) # may throw AttributeError
		if value is not None:
			validatedValue = self.validate(value)
			if validatedValue is None:
				raise TypeError(f'Prefs(value="{str(value)}":{type(value).__name__}): invalid value.')
			setattr(self.owner, self.propertyName, validatedValue)
		return oldVal
	
	def validate(self, value:T) -> Optional[T]:
		"""
		:param value: The value to check for validity.
		:return: The value (or corrected value) iff *value* is a valid value for this Pref. The default implementation
			just returns *value* if *value* is an instance of T, otherwise None.
		
		This method can do one of three things: **reject** the value by returning None, **accept** the value by returning
		the value, or **modify** the value if there is an obvious change to make it acceptable (eg: if T is *int* and the
		value is the *str* "5", it might return the *int* 5. 
		"""
		if self.validatorFunc is None:
			return value if isinstance(value, self.pythonType) else None
		else:
			return self.validatorFunc(value)
	
	def different(self, value):
		"""
		:param value: The value to test change.
		:return: True iff *value* is different (!=) than the owner's value
		"""
		return value != self()
	
	def serialize(self) -> str:
		"""
		:return: The value of this object into an xml text compatible *str*. The default implementation
			just returns *str(self())*.
			
		This method does **not** have to worry about XML escapes for xml serialization: That's taken care
		of by the :meth:`Prefs.save` , :meth:`Prefs.getPrefs` and :meth:`Prefs.getPref` methods in :class:`Prefs`\ .
		"""
		return str(self())
		
	def unserialize(self, value:str) -> Any:
		"""
		:param value: to string value to be unserialized to the value of this Pref.
		:return: The T value derived from *value*. The default implementation tries
			a cast to the type of this Pref and then calls *validate()*.
		:throws ValueError: if the string cannot be converted.
			
		This method does **not** have to worry about XML escapes for xml serialization: That's taken care
		of by the :meth:`Prefs.save` , :meth:`Prefs.getPrefs` and :meth:`Prefs.getPref` methods in :class:`Prefs`\ .
		"""
#		ret = self.validate(T(value))
		if self.pythonType is None:
			return self.validate(value)
		else:
			ret = self.validate(self.pythonType(value))
		
		if ret is None:
			raise ValueError(f'Pref.unserialize("{value}"): Invalid value.')
		self(ret)
		return ret
	
class ViewData:
	def __init__(self):
		self.id:Optional[str] = None
		self.geometry:Optional[str] = None
	
class FileData:
	def __init__(self):
		self.filename:Optional[str] = None
		self.geometry:Optional[str] = None
		self.openViews:List[ViewData] = []

class Prefs:
	'''
	classdocs
	'''
			
	def __init__(self):#, owner):
		'''
		Constructor
		'''
#		self.owner = owner
#		self.openFiles:List[FileData] = []
		self.prefsFileName = f'{os.path.expanduser("~")}/.{app.APP_SHORT_NAME.lower()}prefs.xml'
		self.xmlTag = f"{app.APP_SHORT_NAME.lower()}-prefs"
		self.prefs:List[Pref] = []
		
	def save(self):
		from tygra.typedgraphs import TygraContainer, TGView
		topElem = et.Element(self.xmlTag)
		topElem.set("version", "0")
		
		# open files
		openFiles = et.Element("openfiles")
		for tgc in TygraContainer._instances:
			if tgc.filename is None: continue
			fileInfo = et.Element("file")
			fileInfo.set("name", os.path.abspath(tgc.filename))
			fileInfo.set("geometry", tgc.geometry())
			for dirViewID, dirViewRec in tgc.getViewsFromDirectory().items():
				if isinstance(dirViewRec.viewData, TGView):
					viewInfo = et.Element("openview")
					viewInfo.set("id", dirViewID)
					viewInfo.set("geometry", dirViewRec.viewData.winfo_toplevel().geometry())
					fileInfo.append(viewInfo)
			openFiles.append(fileInfo)
		topElem.append(openFiles)
		
		# prefs
		for pref in self.prefs:
			elem = et.Element(pref.propertyName)
			elem.text = util.xmlEscape(pref.serialize())
			topElem.append(elem)
		
		tree = et.ElementTree(element=topElem)
		et.indent(tree, space='  ', level=0)
		tree.write(self.prefsFileName, xml_declaration=True, encoding="utf-8")
		

	def read(self) -> et.Element:
		if not os.path.isfile(self.prefsFileName):
			raise FileNotFoundError(f'Prefs.read(): {self.prefsFileName} not found.')
		else:
			tree = et.parse(self.prefsFileName)
			root = tree.getroot()
			if root.tag != self.xmlTag:
				raise TypeError(f'Prefs.read(): {self.prefsFileName} is not a {self.xmlTag} file.')
			self.root = root
			for k, v in self.getPrefs().items():
				for p in self.prefs:
					if p.propertyName == k:
						try:
							p(v) # set the property in the owner object
						except:
							pass
			return root
		
	def getPrefs(self) -> Dict[str, Any]:
		"""
		Read all the prefs stored in the XML element and return as a dictionary.
		"""
		ret:Dict[str, Any] = dict()
		elems = self.root.findall('./*')
		for elem in elems:
			if elem.tag == "openfiles": continue
			found = False
			for p in self.prefs:
				if p.propertyName == elem.tag:
					ret[elem.tag] = util.xmlUnescape(p.unserialize(elem.text))
					found = True
					break
			if not found:
				ret[elem.tag] = util.xmlUnescape(elem.text)
		return ret
	
	def getPref(self, prop:Union[str,Pref]) -> Any:
		assert isinstance(prop, str) or isinstance(prop, Pref)
		elem = self.root.find('./'+(prop if isinstance(prop, str) else prop.propertyName))
		if elem is None: return None
		if isinstance(prop, Pref):
			return util.xmlUnescape(prop.unserialize(elem.text))
		else:
			for p in self.prefs:
				if prop == elem.tag:
					return util.xmlUnescape(p.unserialize(elem.text))
			return util.xmlUnescape(elem.text)

	def getOpenFilesData(self) -> List[FileData]:
		openFilesData:List[FileData] = []
		for fd in self.root.findall("./openfiles/file"):
			fileData = FileData()
			fileData.filename = fd.get("name")
			fileData.geometry = fd.get("geometry")
			for vd in fd.findall("./openview"):
				fdata = ViewData()
				fdata.id = vd.get("id")
				fdata.geometry = vd.get("geometry")
				fileData.openViews.append(fdata)
			openFilesData.append(fileData)
		return openFilesData
	
	def __getitem__(self, key) -> Any:
		for p in self.prefs:
			if p.propertyName == key:
				return p()
		raise AttributeError(f'Prefs["{key}"] <access>: Unknown key.')
	
	def __setitem__(self, key, value):
		for p in self.prefs:
			if p.propertyName == key:
				return p(value)
		raise AttributeError(f'Prefs["{key}"] <assignment>: Unknown key.')
	
	def bind(self, propertyName:str, owner:Any, kind:str, userName:Optional[str]=None, 
				help:Optional[str]=None, validatorFunc:Optional[Callable[[Any],Any]]=None,
				pythonType:Optional[Type]=None):
		"""
		:param propertyName: The string name of property in *owner*.
		:param owner: The owner of the this preference item.
		:param kind: The type used by the editor to make an edit box.  One of "text","choices:*[:*...]",...
		:param userName: The name to use in the preferences editor GUI.
		:param help: The help text to present in the tooltip in the editor GUI.
		:param validatorFunc: A function to replace :meth:`Pref.validate()`\ .
		:param pythonType: The python type corresponding to the type parameter T. (because
			python hasn't got it together on getting the top class yet...)
		"""
		typ = Any
		if kind.startswith("choices:") or kind=="text":
			typ = str
		self.prefs.append(Pref[typ](propertyName, owner, kind, userName=userName,
							help=help, validatorFunc=validatorFunc, 
							pythonType=pythonType))

	def edit(self, parentWindow, title=None):
		"""
		Put up a GUI dialog to edit the *Attributes*
		
		:param parentWindow: A parent for dialog.
		:param title: A title to put on the dialog window.
		"""
		editor = PrefsEditor(parentWindow, self, self.prefs, title=title)
		editor.show()
#		editor.destroy()
		


#ChangeDescr = namedtuple("ChangeDescr", "oldValue tkVar delete")

class PrefsEditor(tk.Toplevel):

	def __init__(self, parent, owner, prefs:List[Pref], title="Attribute Editor"):
		super().__init__(parent)
		self.parent = parent
		self.title(title if title else "Prefs Editor")
		self.owner = owner
		self.prefs = prefs
		self.deleting = False
		
	def checkEntry(self, editedValue, pref, tkVar) -> bool:
		if self.deleting: return True
		newVal = pref.validate(editedValue)
		if newVal is None:
			util.play()
			return False
		tkVar.set(newVal)
		return True

	def colorChooser(self, tkVar, button):
		color = colorchooser.askcolor(initialcolor=tkVar.get())
		color = color[1]
		if color is not None:
			tkVar.set(color)
			button.config(highlightbackground=color)
		
	def show(self, disabled=False):
		self.geometry("400x500")
		#self.title('Attributes')
		self.resizable(1, 1)

		# configure the grid
		cLabel = 0
		cEdit = 1
		cKind = 2
		span = 3
		self.columnconfigure(cLabel, weight=0)
		self.columnconfigure(cEdit,  weight=2)
		self.columnconfigure(cKind,  weight=0)
		
		i = 0
		for pref in self.prefs:
			label = ttk.Label(self, text=pref.userName+':', font=('Helvetica', 14, 'normal'))
			label.grid(column=cLabel, row=i, sticky=tk.E, padx=0, pady=0)
			if pref.help is not None and len(pref.help)>0:
				CreateToolTip(label, pref.help)
			editor = None
			if pref.kind == 'text':
				var = tk.StringVar(value=pref())
				checkWrapper = (self.winfo_toplevel().register(lambda v, pref=pref, var=var: self.checkEntry(v,pref,var)), '%P')
				editor = ttk.Entry(self, textvariable=var, validate="focusout", validatecommand=checkWrapper)
				setattr(pref, "tkVar", var) # now pref has a new property holding the variable
			elif pref.kind.startswith("choices:"):
				var = tk.StringVar(value=pref())
				checkWrapper = (self.winfo_toplevel().register(lambda v, pref=pref, var=var: self.checkEntry(v,pref,var)), '%P')
				editor = ttk.Combobox(self, textvariable=var, validate="focusout", validatecommand=checkWrapper)
				editor['values'] = pref.kind.split(':')[1:]
				editor.state(["readonly"])
				setattr(pref, "tkVar", var) # now pref has a new property holding the variable
			else:
				print(f'PrefsEditor.show(): Unknow kind "{pref.kind}".')
			if editor is not None:
				editor.grid(column=cEdit, row=i, sticky='EW', padx=0, pady=0)
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
		
		
	def dismiss(self):
		self.deleting = True
		self.grab_release()
		self.destroy()
		
	def save(self):
		badVals = 0
		for pref in self.prefs:
			newVal = pref.tkVar.get() #TODO: do something different for non-Entry types
			if pref() != newVal:
				valid = pref.validate(newVal)
				if valid is None:
					badVals += 1
					print(f'PrefsEditor.save(): Invalid value "{pref.tkVar.get()}" for "{pref.propertyName}" ("{pref.userName}").')
				else:
					pref(valid)
		self.dismiss()
		