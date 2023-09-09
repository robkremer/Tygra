'''
Created on Sep. 5, 2023

@author: kremer
'''

import xml.etree.ElementTree as et
from tkinter.filedialog import askopenfiles
from typing import Self, Optional
import tygra.app as app
import os

class ViewData:
	def __init__(self):
		self.id:Optional[str] = None
		self.geometry:Optional[str] = None
	
class FileData:
	def __init__(self):
		self.filename:Optional[str] = None
		self.geometry:Optional[str] = None
		self.openViews:list[ViewData] = []

class Prefs:
	'''
	classdocs
	'''
			
	def __init__(self):#, owner):
		'''
		Constructor
		'''
#		self.owner = owner
#		self.openFiles:list[FileData] = []
		self.prefsFileName = f'{os.path.expanduser("~")}/.{app.APP_SHORT_NAME.lower()}prefs.xml'
		self.xmlTag = f"{app.APP_SHORT_NAME.lower()}-prefs"
		
	def load_old(self):
		from tygra.typedgraphs import TypedGraphsContainer, TGView
		self.openFiles = []
		if self.owner.filename is not None:
			fileData = FileData()
			fileData.filename = self.owner.filename
			fileData.geometry = self.owner.geometry()
			for dirViewID, dirViewRec in self.owner.getViewsFromDirectory().items():
				if isinstance(dirViewRec.viewData, TGView):
					vd = ViewData()
					vd.id = dirViewID
					vd.geometry = dirViewRec.viewData.winfo_toplevel().geometry()
					fileData.openViews.append(vd)
			self.openFiles.append(fileData)
		
	def save_old(self):
		topElem = et.Element(self.xmlTag)
		topElem.set("version", "0")
		openFiles = et.Element("openfiles")
		for f in self.openFiles:
			fileInfo = et.Element("file")
			fileInfo.set("name", os.path.abspath(f.filename))
			fileInfo.set("geometry", self.owner.geometry())
			for vd in f.openViews:
				viewInfo = et.Element("openview")
				viewInfo.set("id", vd.id)
				viewInfo.set("geometry", vd.geometry)
				fileInfo.append(viewInfo)
			openFiles.append(fileInfo)
		topElem.append(openFiles)
		tree = et.ElementTree(element=topElem)
		et.indent(tree, space='  ', level=0)
		tree.write(self.prefsFileName, xml_declaration=True, encoding="utf-8")

	def save(self):
		from tygra.typedgraphs import TypedGraphsContainer, TGView
		topElem = et.Element(self.xmlTag)
		topElem.set("version", "0")
		
		openFiles = et.Element("openfiles")
		for tgc in TypedGraphsContainer._instances:
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
		tree = et.ElementTree(element=topElem)
		et.indent(tree, space='  ', level=0)
		tree.write(self.prefsFileName, xml_declaration=True, encoding="utf-8")

	def read_old(self):
		if os.path.isfile(self.prefsFileName):
			tree = et.parse(self.prefsFileName)
			root = tree.getroot()
			if root.tag != self.xmlTag:
				raise TypeError(f'Prefs.read(): {self.prefsFileName} is not a {self.xmlTag} file.')
			for fd in root.findall("./openfiles/file"):
				fileData = FileData()
				fileData.filename = fd.get("name")
				fileData.geometry = fd.get("geometry")
				for vd in fd.findall("./openview"):
					fdata = ViewData()
					fdata.id = vd.get("id")
					fdata.geometry = vd.get("geometry")
					fileData.openViews.append(fdata)
				self.openFiles.append(fileData)
			return True
		else:
			raise FileNotFoundError(f'Prefs.read(): {self.prefsFileName} not found.')

	def read(self) -> et.Element:
		if not os.path.isfile(self.prefsFileName):
			raise FileNotFoundError(f'Prefs.read(): {self.prefsFileName} not found.')
		else:
			tree = et.parse(self.prefsFileName)
			root = tree.getroot()
			if root.tag != self.xmlTag:
				raise TypeError(f'Prefs.read(): {self.prefsFileName} is not a {self.xmlTag} file.')
			self.root = root
			return root

	def getOpenFilesData(self) -> list[FileData]:
		openFilesData:list[FileData] = []
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
		