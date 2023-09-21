# Author: Rob Kremer <robkremer@me.com>
"""
This module builds on and is used like the 'argparse' module, but extends it to support
and optional, GUI interface to allow the user to enter arguments as a form.  It also
supports persistence for the GUI using 'pickle'.

The constructor for the class ArgumentParser is extended with the following parameters:
	callback: a callback function to execute the actual functionality of the program.
	
It extends the command line interface with the following arguments (just like
argparse.ArgumentParaser extends it with the *--help* argument):
--gui       execute the GUI automatically.
--loadfile  the name of the persistent pickle file the GUI is to load defaults from.
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

import argparse
import tkinter as tk
from tkinter import ttk
from tkinter import Tk
from tkinter import PhotoImage
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.messagebox import askyesnocancel, askokcancel
from tkinter import StringVar
import os
import pickle
import io
import sys
import traceback
import string
import inspect
from tempfile import mkstemp
from tygra.tooltip import CreateToolTip
import tygra

DEBUG = True
PARSER_ARGS = ["help", "gui", "loadfile"]


class _ArgAttr:
	"""
	A class to store the relevant attributes of an argument.
	"""
	def __init__(self, action, default):
		self.action = action
		self.default = default
		self.valueOnCommandLine = None
		self.required = False
		self.labelText = ""
		self.file = False
		self.textfile = False
		self.type = None

class ArgumentParser(argparse.ArgumentParser):
	"""
	A class overlaying argparse.ArgumentParser that adds the functionality of an auto-
	generated GUI interface allowing the user to fill out the arguments as a form before
	executing the program.  The class automatically adds the argument "--gui" to allow 
	the user to access the GUI interface (--gui is stripped from the Namespace before 
	returning from parseArgs()).
	"""
	def __init__(self,
				 prog=None,
				 usage=None,
				 description=None,
				 epilog=None,
				 parents=[],
				 formatter_class=argparse.HelpFormatter,
				 prefix_chars='-',
				 fromfile_prefix_chars=None,
				 argument_default=None,
				 conflict_handler='error',
				 add_help=True,
				 allow_abbrev=True):
		"""
		Parameters:
			The parameters are exactly the ones for argparse.ArgumentParser.__init__().
		"""
		self.argAttrs = []
		argparse.ArgumentParser.__init__(self,
					prog=prog,
					usage=usage,
					description=description,
					epilog=epilog,
					parents=parents,
					formatter_class=formatter_class,
					prefix_chars=prefix_chars,
					fromfile_prefix_chars=fromfile_prefix_chars,
					argument_default=argument_default,
					conflict_handler=conflict_handler,
					add_help=add_help,
					allow_abbrev=allow_abbrev)
		
		self.add_argument('--gui', default=False, action='store_true', help='Run a graphic interface to enter the arguments.')
		self.add_argument('--loadfile', default=os.path.splitext(self.prog)[0]+".pickle", help='Use defaults from this file. Priority: first commandLine values, this file, last defaults from .add_argument() calls. Use \'--loadfile ""\' to disable. (default='+os.path.splitext(self.prog)[0]+'.pickle)')
#		self.callback = callback

	def add_argument(self, *args, **kwargs):
		"""
		Overrides argparse.ArgumentParser.add_argument() to collect information and make
		changes for the GUI interface.  Use just like the super's version.  Note that 
		the order or the calls dictates the order of the interface elements in the GUI.
		Once the data as been collected, the new _ArgAttr object is appended to this 
		ArgumentParser's argAttr list.
		
		Parameters (in addition to argparse's parameters):
			label: A string label for column 0 of the gui form.
			file: True to make the control a file-open dialog box.
			textfile: True to make the control a file-open dialg box and add an extra 
				row with visible and editable file content.
		"""
		# Save the additional keyword arguments, and delete them from kwargs before passing kwargs to argparse.add_argument().
		label = None
		if 'label' in kwargs:
			label = kwargs['label']
			kwargs.pop('label')
		
		file = False	
		if 'file' in kwargs:
			if kwargs['file']: file = True
			kwargs.pop('file')
			
		textfile = False	
		if 'textfile' in kwargs:
			if kwargs['textfile']: textfile = True
			kwargs.pop('textfile')

		action = argparse.ArgumentParser.add_argument(self, *args, **kwargs)

		# Append the action and it's attributes to the self.argAttrs list.
		aa = _ArgAttr(action, action.default)
		#make all defaults SUPPRESS so we can tell what's on the command line and what's defaulted 
		# (except the store-type actions, which just are there or not).
		if not isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._StoreConstAction)):
			action.default = argparse.SUPPRESS 
		
		# fix up any special (GUI related) attributes in the argument's attributes
		if 'type' in kwargs:
			aa.type = kwargs['type']
		aa.labelText = action.dest if label==None else label
		aa.file = file
		aa.textfile = textfile
		
		# remove required from the super's data so we can do the gui
		aa.required = action.required
		action.required = False
		
		self.argAttrs.append(aa)
		
	def add_ruler(self):
		"""
		Add a ruler to the GUI. Interface elements (including rulers) are in the same order
		as the add_*() calls.
		"""
		self.argAttrs.append(None)
		
		
	def parse_args(self, args=None, namespace=None, callback=None, forceGUI=False):
		"""
		This is a identical to ArgumentParser.parse_args, with the addition of extra
		arguments:
			callback: a callable called when the user chooses the [execute] button in the
				GUI. If the callback is None, the GUI terminates on pressing the [execute]
				button. If the callback takes only 1 parameter it is assumed to take an 
				argparse.Namespace object; otherwise it is assumed the parameters are 
				the command arguments and will be called with the (*args, **kwargs) 
				format: the positional (*args) parameters are in the order they are 
				declared in the argparseX.ArgumentParser.add_argument calls.
			forceGUI: run the GUI interface regardless of whether the --gui argument
				is on the command line.
		"""
 		# Assumption: super's data structure should have defaults all set to SUPPRESS.
 		# We parse twice: first with defaults=SUPPRESSS so we can mark what is actually on
 		# the command line, then we restore the defaults back into super's datastructured
 		# and parse again, so it can do it's job as advertised. (We need to know what is
 		# explicitly on the command line or defaulted for the GUI interface.)
		ret = argparse.ArgumentParser.parse_args(self, args, namespace) #get the populated namespace
		#clear any previous flags in argAttrs.
		for v in self.argAttrs:
			if v==None: continue
			v.valueOnCommandLine = False
			#mark items that appear in the command line as explicitly being there.
			if v.action.dest in vars(ret).items(): v.valueOnCommandLine = True
			#store the defaults and requireds back into the super's data structure
			v.action.default = v.default
			v.action.required = v.required
		if forceGUI:
			ret = self.runGUI(ret, callback)
		else:
			#run the GUI if indicated on the command line
			guiArg = ret.__dict__["gui"] if "gui" in ret.__dict__ else None
			if guiArg != None and guiArg:
				ret = self.runGUI(ret, callback)
		#allow super to redo the parse (with defaults this time)
		commandLineList = self.namespaceToCommandLineList(ret)
		ret = argparse.ArgumentParser.parse_args(self, commandLineList, namespace)
		#clear the defaults and requireds out of super's data structure again
		for v in self.argAttrs:
			if v==None: continue
			v.action.default = argparse.SUPPRESS
			v.action.default = False
		return ret
		
	def runGUI(self, args, callback=None):
		"""
		Run (display) the GUI window.  Returns the resulting argparse.Namespace object.
		It's not normally necessary to call this as it will be called by .parse_args()
		if it's parameter forceGUI is set to True or --gui appears on the command line.
		
		Parameters:
			args: Expects an argparse.Namespace object that will serve to populate the
				fields in the form.  Before that though, the defaults from the .add_argument()
				call will fill the fields, overwritten by any values in the file specified
				by the --loadfile argument (or it's default) (and finally overwritten by
				the args parameter).
			callback: a callable called when the user chooses the [execute] button in the
				GUI. If the callback is None, the GUI terminates on pressing the [execute]
				button. If the callback takes only 1 parameterit is assumed to take an 
				argparse.Namespace object; otherwise it is assumed the parameters are 
				the command arguments and will be called with the (*args, **kwargs) 
				format: the positional (*args) parameters are in the order they are 
				declared in the argparseX.ArgumentParser.add_argument calls.
		"""
		rootWindow = _RootWindow(self.argAttrs, args, self.prog, self, callback)
		rootWindow.mainloop()
		return rootWindow.args
		#return argparse.Namespace(**rootWindow.args)
		
	def namespaceToCommandLineString(self, parsedArgs, multiline=False, includePythonPrefix=False):
		"""
		Return the result of a parse as a command line string. The return string uses
		the first long (--) argument name for optional arguments if there is one.
		Parameters:
			parsedArgs: may be either a dict or a argparse.Namespace; the result of 
				argparseX.parse_args() call.
			multiline: list each parameter on a separate line, appropriately formatted
				with \ line terminatros. (default=False)
			includePythonPrefix: prepend the Python interpreter's (this one) path to
				the return string.
		"""
		sep = " \\\n  " if multiline else " "
		ret = ((os.environ['_'] + " ") if includePythonPrefix else "") + self.prog
		positionals, keywords = self._splitNamespace(parsedArgs)
		for v in positionals:
			ret += sep + _quote_if_has_whitespace(v)
		for k in keywords:
			attr = self._getAttr(k)
			if attr==None: continue
			value = str(keywords[k])
			if isinstance(attr.action, (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._StoreConstAction)):
				value = None
			arg = self._getMainOptionString(k)
			ret += sep + arg + ((" " + _quote_if_has_whitespace(value)) if value != None else "")
		return ret
		
	def namespaceToCommandLineList(self, parsedArgs):
		"""
		Return the result of a parse as a command line list of strings. The return list uses
		the first long (--) argument name for optional arguments if there is one. The
		first element is NOT the program name, just the fist argument.

		Parameters:
			parsedArgs: may be either a dict or a argparse.Namespace; the result of 
				argparseX.parse_args() call.
		"""
		ret = []
		positionals, keywords = self._splitNamespace(parsedArgs)
		for v in positionals:
			ret.append(v)
		for k in keywords:
			arg = self._getMainOptionString(k)
			if arg != None: 
				ret.append(str(arg))
			attr = self._getAttr(k)
			if attr != None and not isinstance(attr.action, (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._StoreConstAction)):
				ret.append(str(keywords[k]))
		return ret
		
	def _toDict(self, namespace):
		if isinstance(namespace, argparse.Namespace):
			d = namespace.__dict__
		elif isinstance(namespace, dict):
			d = namespace
		else:
			raise Exception("_toDict(): <namespace> parameter must be a dict or a argparse.Namespace; got "+str(type(namespace))+".")
		return d

	def _splitNamespace(self, parsedArgs):
		"""
		Return the arguments in <parsedArgs> as a separate positional list and keyword
		dictionary, appropriate for calling in the for <func>(*args, **kwargs) form. The
		arguments handled by the parser (like --help, --gui, --loadfile) are stripped out.
		The positional arguments are in the order they were presented in the .add_argument()
		calls.
		"""
		positionals = []
		keywords = {}
		d = self._toDict(parsedArgs) # might raise an exception if parse isn't a dict or a Namespace
		for k in d:
			if k in PARSER_ARGS: continue
			if k.find("._history") != -1: continue #ignore the pseudo history list argument for file widgets
			attr = self._getAttr(k)
			arg = self._getMainOptionString(k)
			if arg == "": # a positional argument
				positionals.append(d[k])
			else: # a keyword argument
				keywords[k] = d[k] 
		return positionals, keywords
		
	def _getAttr(self, dest):
		"Return the _ArgAttr structure for name 'dest', else None"
		for a in self.argAttrs:
			if a==None: continue
			if a.action.dest == dest:
				return a
		return None
		
	def _getMainOptionString(self, dest):
		"""
		Return:
		  the first -- option if it exists, else
		  the first - option  if it exists, else 
		  ""                  if  dest is a positional argument, else
		  None                if dest is not found."""
		attr = self._getAttr(dest)
		if attr == None: return None
		single = None
		chars = self.prefix_chars
		for os in attr.action.option_strings:
			if len(os) > 1 and os[0] in chars:
				if len(os) > 2 and os[1] in chars:
					return os
				if single == None:
					single = os
		if single:
			return single
		if attr:
			return ""
		return None

def _contains_whitespace(s):
    return True in [c in s for c in string.whitespace]
    
def _quote_if_has_whitespace(s):
	return ("'"+s+"'") if _contains_whitespace(s) else s
					
WIDTH = 65
WIDTH_EDITOR = 80

class _RootWindow:
	def __init__(self, argAttrs, args, progName, parser, callback=None, title=None):
		"""
		Parameters:
			argAttrs: The list of arguments expected in the command line as per the
				argparse module.
			args: The actual list of arguments from the command line.
			progName: The name (or pathname) of the program to be called.
			parser: The argparse parser (assumedly of type argparseX.ArgumrentParser).
			callback: a callable called when the user chooses the [execute] button in the
				GUI. If the callback is None, the GUI terminates on pressing the [execute]
				button. If the callback takes only 1 parameterit is assumed to take an 
				argparse.Namespace object; otherwise it is assumed the parameters are 
				the command arguments and will be called with the (*args, **kwargs) 
				format: the positional (*args) parameters are in the order they are 
				declared in the argparseX.ArgumentParser.add_argument calls.
			title: The title for the window.
		"""
		self.progName = progName
		self.parser = parser
		self.callback = callback
		if title==None: 
			self.title = os.path.splitext(progName)[0]
		self.rootWindow = tk.Tk()
		self.rootWindow.title(self.title)
		self.rootWindow.configure(background="#F0F0F0")

		for v in argAttrs:
			if v==None:
				_Widgets.get(self.rootWindow).insertSeparator()
			else:
				name = v.action.dest
				if name in PARSER_ARGS:
					if name == "loadfile":
						vs = vars(args)
						if "loadfile" in list(vs):
							self.loadfile = vs["loadfile"]
						else:
							self.loadfile = v.default
					continue
				if isinstance(v.action, (argparse._StoreTrueAction, argparse._StoreFalseAction, argparse._StoreConstAction)):
					_CheckboxWidget(self, name, v)
				elif v.textfile:
					_TextFileWidget(self, name, v)
				elif v.file:
					_FileWidget(self, name, v)
				else:
					_TextWidget(self, name, v)
								
		self.widgets = _Widgets.get(self.rootWindow)
		self.widgets.insertSeparator()
		row = self.widgets.nextRow #Row: submit button
		f = tk.Frame(self.rootWindow)
		f.configure(background="#F0F0F0")
		btn = ttk.Button(f, text = "Execute "+self.progName+"...", command = self.execute)
		btn.grid(row = 2, column = 0)
		btn = ttk.Button(f, text = "Save params...", command = self.saveArgs)
		btn.grid(row = 2, column = 1)
		btn = ttk.Button(f, text = "Load params...", command = self.loadParamsFromFile)
		btn.grid(row = 2, column = 2)
		btn = ttk.Button(f, text = "Cancel", command = self.close)
		btn.grid(row = 2, column = 3, pady=15)
		self.loaded_Label = ttk.Label(f, text="", font='Helvetica 12')
		self.loaded_Label.grid(row=0, column=0, columnspan=4, pady=0)
		f.grid(row = row, column = 0, columnspan=2, pady=0)
		
		self.loadDefaults(argAttrs)
		if self.loadfile!="": 
			self.loadfile = self.loadFromFile(self.loadfile)
			if self.loadfile!="":
				self.updateLoadedLabel(self.loadfile)
		self.loadfromCommandLine(args)
		self.changed = False
		self.args = args
		
	def loadDefaults(self, argAttrs):
		for a in argAttrs:
			if a==None: continue
			try:
				widget = self.widgets[a.action.dest]
			except KeyError:
				continue
			widget.put(a.default if a.default != None and a.default!=argparse.SUPPRESS else None)
		
	def updateLoadedLabel(self, filename):
		self.loaded_Label['text'] = ("Loaded from: "+filename) if filename!="" else ""

	def loadFromFile(self, filename, ask=False):
		"""
		Load values from a file into the GUI interface.
		Parameters:
			filename: A file name to load from, or the default filename if 'ask' is True.
			ask:      Boolean. If true use askopenfilename() to get the filename.
		"""
		path, name = os.path.split(filename)
		if path == "" or path == None:
			path = os.getcwd()
		if ask:
			filepath = askopenfilename(initialdir=path, initialfile=name, defaultextension="pickle",
				title="SendEmail: Load params from file...", filetypes=(("wildcard","*"),))
		else:
			filepath = path + '/' + filename
		if filepath!=None and filepath!="":
			try: # get arguments from the persistent store
				with open(filepath, 'rb') as f:
					p = pickle.load(f)
					if not isinstance(p, dict):
						tk.messagebox.showerror(title=self.title, message="Unexpected type '"+str(type(p))+"' found in pickle file.")
						return filepath
				#print("loaded "+filepath)
			except Exception as err:
				#print("Can't interpret '"+filepath+"'.	 ")
				tk.messagebox.showerror(title=self.title, message="Can't interpret '"+filepath+"'.\n"+str(err))
				return filepath
			#loadParams()
			self.loadfromCommandLine(p)
		return filepath
		
	def loadfromCommandLine(self, args):
		"""
		Load the arguments in the 'args' dictionary (or Namespace) into the gui.
		"""
		if not isinstance(args, dict):
			argsDict = vars(args)
		else:
			argsDict = args
		for k,v in argsDict.items():
			if v==None: continue
			if k in PARSER_ARGS: continue
			
			# handle a history list for file widgets
			historyPos = k.find("._history")
			if historyPos != -1:
				k = k[0:historyPos]
				
			try:
				widget = self.widgets[k]
			except KeyError as ke:
				print("loadfromCommandLine(): Unexpected KeyError on key '"+k+"': "+repr(ke))
				continue
				
			if historyPos == -1: #this is not a history list
				widget.put(v)
			else: #this is a history list for file widgets
				if isinstance(widget, _FileWidget):
					widget.setHistoryList(replaceList=v)
		
	def changed(self, value=True):
		self.changed = value
		print(("" if self.changed else "not ")+"changed()")
		
	def isChanged(self):
		return self.changed
		
	def mainloop(self):
		self.rootWindow.mainloop()
		
	def saveArgs(self):
		self.args = {}
		for k,w in self.widgets.items():
			value = w.get()
			if value == None: continue #don't add empty values to the args list
			self.args[k] = value
			if isinstance(w, _FileWidget):
				self.args[k+"._history"] = w.history
		with open(self.loadfile if self.loadfile!="" else "x.pickle", 'wb') as f:
			pickle.dump(self.args, f, pickle.HIGHEST_PROTOCOL)
		return self.args
		
		
	def execute(self):
		msg = self.validateAll()
		if msg != None:
			_displayPopupMsg(self.rootWindow, self.title, "Validation failure(s):\n"+msg)
			return
		if self.callback == None: # collect the parameters in self.args and close the window
			self.close()
		else: # setup to log window and call the callback function to run the app
			args = self.saveArgs()
			log = _TextIOToWindow(self.rootWindow)
			origOut = sys.stdout
			origErr = sys.stderr
			sys.stdout = log
			sys.stderr = log
			try:
				insp = inspect.getfullargspec(self.callback) #gets the names and default values of callback()'s parameters.
				if len(insp.args)==1:
					(self.callback)(args)
				else:
					#print(str(args))
					args, kwargs = self.parser._splitNamespace(args)
					(self.callback)(*args, **kwargs)
				sys.stdout.flush()
			except BaseException as err:
				log.color("red")
				exc_type, exc_value, exc_traceback = sys.exc_info()
				traceback.print_exception(exc_type, exc_value, exc_traceback, limit=50, file=sys.stdout)
				sys.stdout.flush()
			log.color("purple")
			print("--done--")
			sys.stdout.flush()
			sys.stdout.close()
			sys.stdout = origOut
			sys.stderr = origErr

	def loadParamsFromFile(self):
		print("loadParamsFromFile()")

	def close(self):
		"""Calls saveIfNeeded() and if the user does not concel, saves the arguments in
		self.args and closes the window."""
		if self.saveIfNeeded():
			self.args = self.saveArgs()
			self.rootWindow.destroy()
			self.rootWindow = None
			
	def isModified(self):
		for k, v in self.widgets.items():
			if isinstance(v, ttk.Widget):
				print(k+": "+str(v['state']))

	def saveIfNeeded(self):
		"Returns True if saves worked or where rejected; False if operation should be cancelled."
# 		if widgets.toFileContent_Text.edit_modified():
# 			save = askyesnocancel(title=self.title, message="You have modified the contents of the CSV file. Do you want to save it?", parent=rootWindow)
# 			if save == None: # cancel
# 				return False
# 			if save: # yes
# 				actionSaveAddr()
# 		if widgets.msgFileContent_Text.edit_modified():
# 			save = askyesnocancel(title=self.title, message="You have modified the contents of the message text file. Do you want to save it?", parent=rootWindow)
# 			if save == None: # cancel
# 				return False
# 			if save: # yes
# 				actionSaveMsg()
		if self.isChanged():
			save = askyesnocancel(title=self.title, message="You have modified the arguments. Do you want to save them for next time?", parent=self.rootWindow)
			if save == None: # cancel
				return False
			if save: # yes
				self.saveArgs()
		return True
		
	def validateAll(self):
		self.clearHighlights()
		widgets = _Widgets.get(self.rootWindow)
		s = ""
		n = 1
		for k,v in widgets.items():
			try:
				v.validate()
			except Exception as err:
				s += "\nValidation error ("+str(n)+") on argument '"+k+"':\n"+(traceback.format_exc() if DEBUG else str(err))
				v.setHighlight(text="("+str(n)+")")
				n += 1
		return None if s=="" else s
		
	def clearHighlights(self):
		widgets = _Widgets.get(self.rootWindow)
		for k,v in widgets.items():
			v.clearHighlight()

class _TextIOToWindow(io.TextIOWrapper):
	def __init__(self, root, height=30, width=80):
		raw = io.StringIO()
		buffer = io.BufferedWriter(raw)
		io.TextIOWrapper.__init__(self, buffer, errors='strict', line_buffering=True)
	
		self.frame = tk.Frame(tk.Toplevel(root))
		scrollBarV = tk.Scrollbar(self.frame)
		scrollBarV.grid(row=0, column=1, sticky='nsew')
		scrollBarH = tk.Scrollbar(self.frame, orient=tk.HORIZONTAL)
		scrollBarH.grid(row=1, column=0, sticky='nsew')
		self.textArea = tk.Text(self.frame, wrap=tk.NONE, yscrollcommand=scrollBarV.set\
		  , xscrollcommand=scrollBarH.set, borderwidth=3, relief=tk.SUNKEN, height=height, width=width)
		self.textArea.grid(row=0, column=0, sticky='nsew')
		scrollBarV.config(command=self.textArea.yview)
		scrollBarH.config(command=self.textArea.xview)
		self.frame.grid_columnconfig(0, weight=1)
		self.frame.grid_rowconfigure(0, weight=1)
		self.frame.pack(side="top", fill="both", expand=True, padx=0, pady=0)
		s = ttk.Style()
		self.color(s.lookup('TFrame', 'foreground'))
		
	def write(self, s):
		self.textArea.insert(tk.END, s, self.colorTag)
		self.textArea.see(tk.END)
		
	def color(self, colorString):
		self.colorTag = colorString
		self.textArea.tag_configure(self.colorTag, foreground=colorString)

class _Widgets(dict):
	widgetss = {}
	@classmethod
	def get(cls, rootWindow):
		if rootWindow in _Widgets.widgetss:
			return _Widgets.widgetss[rootWindow]
		else:
			new = _Widgets(rootWindow)
			_Widgets.widgetss[rootWindow] = new
			return new
	def __init__(self, rootWindow):
		dict.__init__(self)
		self.rootWindow = rootWindow
		self.nextRow = 0
	def insertSeparator(self):
		ttk.Separator(self.rootWindow, orient=tk.HORIZONTAL).grid(column=0, row=self.nextRow, columnspan=2, sticky='ew', pady=5)
		self.nextRow += 1
	def __hash__(self):
		return hash(self.name)
	def __eq__(self, other):
		return self.rootWindow.title == other.rootWindow.title
	def __ne__(self, other):
		return not(self==other)
		
		
						
class _Widget:
#	widgets = {}
#	nextRow = 0
#	rootWindow = None
	def __init__(self, app, name, attrs):
		if type(self) is _Widget:
			raise TypeError("Class _Widget is abstract.")
		if not isinstance(app, _RootWindow):
			raise TypeError("_Widget.__init__(): rootWindow must be type _RootWindow, got "+str(type(app)))
		self.widgets = _Widgets.get(app.rootWindow)
		self.app = app
		self.name = name
		self.attrs = attrs
		self.row = self.widgets.nextRow
		self.widgets.nextRow += self._rows()
		self.widgets[name] = self
		self.label = self._label(self.row, 0, attrs)
		self.toolTip = CreateToolTip(self.label, attrs.action.help) if attrs.action.help != None else None
		self.highlight = None
	def get(self):
		"Returns the value in the file, a return of None means the field is blank"
		raise NotImplementedError("_Widget.get() not implemented (self.name of type "+str(type(self))+").")
	def put(self, value):
		"value=None clears the field."
		raise NotImplementedError("_Widget.put() not implemented ("+self.name+" of type "+str(type(self))+").")
	def validate(self, value=None):
		"""Raise an exception if the value in the widget is inappropriate.
		Parameters:
			value: if None (or not given) then check the value in the actual widget,
				otherwise check this value."""
		if value==None: value = self.get()
		if self.attrs.required and value==None:
			raise ValueError("_Widget.validate(): value required for '"+self.name+"'.")
		if self.attrs.type != None and not self.attrs.type(value):
			raise ValueError("_Widget.validate(): value '"+str(value)+"' should conform to type constraint "+str(self.attrs.type)+".")
	def _rows(self):
		return 1
	def _label(self, row, col, attrs):
		self.label = ttk.Label(self.widgets.rootWindow, text=attrs.labelText+":", font='Helvetica 12 '+("bold" if attrs.required else "normal"))
		self.label.grid(row=row, column=col, sticky='e')
		return self.label
	def setHighlight(self, text="*", textcolor="red"):
		if self.highlight == None:
			self.highlight = ttk.Label(self.app.rootWindow, text=text, font='Helvetica 12 bold')
			self.highlight.grid(row=self.row, column=2, sticky='w')
		else:
			self.highlight.config(text=text)
		self.highlight.configure(foreground=textcolor)
	def clearHighlight(self):
		if self.highlight != None:
			self.highlight.destroy()
			self.highlight = None
		
class _TextWidget(_Widget):
	def __init__(self, app, name, attrs):
		_Widget.__init__(self, app, name, attrs)
		self.widget = ttk.Entry(self.widgets.rootWindow, width=WIDTH)
		self.widget.bind('<KeyRelease>', app.changed)
		self.widget.grid(row=self.row, column=1, sticky="w")
	def get(self):
		ret = self.widget.get()
		return ret if ret != "" else None
	def put(self, value):
		self.widget.delete(0, tk.END)
		value = str(value) if value!=None else ""
		self.widget.insert(0, value )
		return value if value!="" else None
	def validate(self, value=None):
		_Widget.validate(self, value=value)			

class _CheckboxWidget(_Widget):
	def __init__(self, app, name, attrs): #label=None, required=False):
		_Widget.__init__(self, app, name, attrs)
		self.widget = ttk.Checkbutton(self.widgets.rootWindow)
		self.widget.bind('<ButtonRelease-1>', app.changed)
		self.widget.grid(row=self.row, column=1, sticky="w")
	def get(self):
#		self.validate()
		return self._get()
	def _get(self):
		if self.widget.instate(['alternate']):
			return None
		return self.widget.instate(['selected'])
	def put(self, boolValue):
		if boolValue==None: 
			self.widget.state(['alternate','!disabled','!selected'])
		else:
			self.validate(boolValue)
			self.widget.state(['!alternate','!disabled','selected' if boolValue else '!selected'])
		return boolValue
	def validate(self, value=None):
		_Widget.validate(self, value=value)
		if value==None: value = self._get()
		if value != None:
			if not isinstance(self.attrs.action, argparse._StoreConstAction) and not isinstance(value, bool):
				raise TypeError("CheckBoxWidget.validate(): value parameter for '"+self.name+"' must be type Bool, got "+str(type(value))+".")
		elif self.required:
			raise ValueError("CheckBoxWidget.validate(): value required for '"+self.name+"'.")

class _FileWidget(_Widget):
	def __init__(self, app, name, attrs, mode=None):
		_Widget.__init__(self, app, name, attrs)
		#self.widget = ttk.Label(self.widgets.rootWindow, text="")
		self.current = StringVar(self.widgets.rootWindow)
		self.current.set("")
		self.history = []
		#self.widget = ttk.OptionMenu(self.widgets.rootWindow, self.current, *self.history,
		#	command=self._actionOpenFile)
		self.widget = ttk.Combobox(self.widgets.rootWindow, textvariable=self.current, values=self.history,
			state="readonly", width=WIDTH, postcommand=self.resize)
		#self.widget.bind("<<ComboboxSelected>>", self._actionOpenFile)
		self.widget.bind("<KeyPress>", self._actionOpenFile)
		self.widget.grid(row=self.row, column=1, sticky='w')
		#self.widget.bind('<KeyRelease>', app.changed)
		self.mode = mode
	def get(self):
		#ret = self.widget.cget("text")
		ret = self.current.get()
		return ret if ret != "" else None
	def put(self, filename):
		# add the old value to the history list, being careful not to duplicate
		self.setHistoryList(newItem=self.get())
		#self.widget.config(text=str(filename) if filename!=None else "")
		self.current.set(str(filename) if filename!=None else "")			
		return filename
	def resize(self):
		newLen = len(self.get())
		if newLen < WIDTH: newLen = WIDTH
		self.widget.configure(width=newLen)
	def setHistoryList(self, replaceList=None, newItem=None):
		if replaceList != None:
			self.history = replaceList
		if newItem!=None and newItem!="":
			try:
				while True:
					self.history.remove(newItem)
			except ValueError:
				pass
			self.history.insert(0, newItem)
		#menu = self.widget["menu"]
		#menu.delete(0, "end")
		#for f in self.history:
		#	menu.add_command(label=f, command=lambda filename=f: self.put(filename))
		self.widget.config(values=self.history)
		
	def _label(self, row, col, attrs):
		f = tk.Frame(self.widgets.rootWindow)
		f.configure(background="#F0F0F0")
		try:
			self.clearImage = PhotoImage(file="x.png", width=8, height=8)
			clearButton = ttk.Button(f, command=self._actionClear, padding=-10)
			clearButton.config(image=self.clearImage, width=-10)#, height="10")
		except:
			clearButton = ttk.Button(f, text="x", command=self._actionClear)
		clearButton.grid(row=0, column=0, sticky='w')
		ttk.Button(f, text=attrs.labelText, command=self._actionOpenFile) \
			.grid(row=0, column=1, sticky='e')
		f.grid(row=row, column=col, sticky='e')
		self.label = f
		return self.label
	def _actionOpenFile(self, filename=None):
		defaultPathname = self.get() if filename==None else filename
		f = None
		if defaultPathname == None:
			f = askopenfilename(title=self.widgets.rootWindow.title) # show an "Open" dialog box and return the path to the selected file
		else:
			path, name = os.path.split(defaultPathname)
			if path == "" or path == None:
				path = os.getcwd()
			f = askopenfilename(title=self.widgets.rootWindow.title, initialdir=path) # show an "Open" dialog box and return the path to the selected file
		if f == None or f == "":
			return None
		self.put(f)
		return f
	def _actionClear(self):
		self.put(None)
	def validate(self, value=None):
		_Widget.validate(self, value=value)
		if value==None: value = self.get()
		if self.mode != None and "r" in self.mode and not os.path.exists(value):
			raise FileNotFoundError("_FileWidget.validate(): file '"+value+"' not found for read-mode parameter '"+self.name+"'.")

class _TextFileWidget(_FileWidget):
	def __init__(self, app, name, attrs, mode=None):
		_FileWidget.__init__(self, app, name, attrs, mode)
		self.tempFile = None
		self.save_Button = ttk.Button(self.widgets.rootWindow, text = "Save file", command=self._actionSaveFile)
		self.save_Button.grid(row=self.row+1, column=0, sticky='ne')
		(frame, text) = self._multiLineEditor(self.widgets.rootWindow)
		self.contentText = text
		text.bind('<<Modified>>', lambda event: self._onTextPaneModification(self.save_Button, self.contentText))
		frame.grid(row=self.row+1, column=1, sticky='w')
		self.save_Button.configure(state=tk.DISABLED)
	def get(self):
		return _FileWidget.get(self) if self.tempFile==None else self.tempFile
		
	def put(self, fileName):
		_FileWidget.put(self, fileName)
		self._updateFileContent()
	def _rows(self):
		return 2
	def validate(self, value=None):
		self.tempFile = None
		_Widget.validate(self, value=value)
		if value==None: value = self.get()
		if self.contentText.edit_modified():
			#decide weather to save-to-filename or to create a temporary file
			message = \
"""You have modified the text of file:

      {value}
      
Do you want to:

  [Save to file]:      Save the modified text to the file or another file
  [Save to temporary]: Save the modified text to a temporary file and use that file
  [Revert]:            Delete modified text and use the text in the file
  [Cancel]:            Cancel the current operation"""
			message = message.replace("{value}", str(value))
			answer = _displayPopupMsg(self.widgets.rootWindow, self.app.title+": Argument '"+self.name+"'", message, 
					buttons=["Save to file", "Save to temporary", "Revert", "Cancel"], 
					height=10)
			if answer == "Save to file": # save to the file return the file
				self._saveFile(self.widget, self.contentText, _FileWidget.get(self), self.save_Button, self.app.title)
			elif answer == "Save to temporary": # save to a temporary file and return that file
				(fd, self.tempFile) = mkstemp()
				print("temp file = "+self.tempFile)
				tfile = os.fdopen(fd, "w")
				data = self.contentText.get('1.0', 'end')
				tfile.write(data)
				tfile.close()
			elif answer == "Revert": # reload the text from the file and return the file
				self._updateFileContent()
			elif answer == "Cancel" or answer == None:
				raise Exception("Operation aborted by user: "+str(answer))
			else:
				raise Exception("_TextFileWidget.validate(): Unexpected return value: "+str(answer))
		else:
			_FileWidget.validate(self, value=value)
	def _actionOpenFile(self): #override _FileWidget
		filename = _FileWidget._actionOpenFile(self)
		self._readFile(filename, self.contentText)
		return filename
	def _actionSaveFile(self):
		f = self._saveFile(self.widgets.toFile_Label, self.widgets.toFileContent_Text, self.args.toFile, self.widgets.toFileSave_Button, "sendEmail: Save CVS date to file?")
		if f != None and f != "":
			self.args.toFile = f
	def _updateFileContent(self):
		fileName = _FileWidget.get(self)
		if fileName == None:
			fileName = ''
		if fileName != '':
			try:
				with open(fileName, 'r') as file:
					data = file.read()
					self.contentText.delete('1.0', 'end')
					self.contentText.insert('1.0', data)
					self.contentText.edit_modified(False)
			except Exception as err:
				tk.messagebox.showerror(title="sendEmail", message="Failed to read '"+fileName+"':\n"+str(err))
		self.tempFile = None

	def _readFile(self, fileName, contentText):
		"""read the context of 'fileName' into the Text widget 'contentText' overwriting its
		current contents, leaving the edit_modified flag False and deleting any reference
		to self.tempfile."""
		if fileName == None:
			fileName = ''
		if fileName != '':
			try:
				with open(fileName, 'r') as file:
					data = file.read()
					contentText.delete('1.0', 'end')
					contentText.insert('1.0', data)
					contentText.edit_modified(False)
					self.tempfile == None
			except Exception as err:
				tk.messagebox.showerror(title=self.title, message="Failed to read '"+fileName+"':\n"+str(err))
	def _writeFile(self, fileName, contentText, saveButton):
		if fileName != None and fileName != '':
			with open(fileName, 'w') as file:
				data = contentText.get('1.0', 'end')
				file.write(data)
				saveButton.configure(state=tk.DISABLED)
	def _saveFile(self, nameLabel, contentText, defaultPathname, saveButton, title):
		"Returns the selected path name"
		path, name = os.path.split(defaultPathname)
		if path == "" or path == None:
			path = os.getcwd()
		f = asksaveasfilename(initialdir=path, initialfile=name, title=title)
		self._writeFile(f, contentText, saveButton)
		if f != None and f != "":
			nameLabel.config(text=f)
		return f
	def _multiLineEditor(self, win, height=10, width=WIDTH_EDITOR):
		"Returns a pair (frame in win, tk Text object)"
		f = tk.Frame(win)
		scrollBarV = tk.Scrollbar(f)
		scrollBarV.grid(row=0, column=1, sticky='nsew')
		scrollBarH = tk.Scrollbar(f, orient=tk.HORIZONTAL)
		scrollBarH.grid(row=1, column=0, sticky='nsew')
		textArea = tk.Text(f, wrap=tk.NONE, yscrollcommand=scrollBarV.set\
		  , xscrollcommand=scrollBarH.set, borderwidth=3, relief=tk.SUNKEN, height=height, width=width)
		textArea.grid(row=0, column=0, sticky='nsew')
		scrollBarV.config(command=textArea.yview)
		scrollBarH.config(command=textArea.xview)
		return (f, textArea)
	def _onTextPaneModification(self, button, textWidget, event=None):
		if textWidget.edit_modified():
			button.configure(state = tk.NORMAL)
		else:
			button.configure(state = tk.DISABLED)

def _displayPopupMsg(parent, title, msg, height=40, width=100, buttons=["Close"]):
	class _Popupmsg:

		"Usage: _Popupmsg(parent, title, msg, ...).show()"
		def action(self, buttonLabel):
			self.ret = buttonLabel
			self.popup.destroy()
		def __init__(self, parent, title, msg, height=40, width=100, buttons=["Close"]):
			self.ret = None	
			self.buttons = buttons
			self.parent = parent
			self.popup = tk.Toplevel(parent)
			self.popup.wm_title(title)
			self.popup.grab_set()
			self.popup.wm_attributes("-topmost", 1)
			self.popup.configure(background="#F0F0F0")
			frame = tk.Frame(self.popup)
			frame.configure(background="#F0F0F0")
			scrollBarV = tk.Scrollbar(frame)
			scrollBarV.grid(row=0, column=1, sticky='nsew')
			scrollBarH = tk.Scrollbar(frame, orient=tk.HORIZONTAL)
			scrollBarH.grid(row=1, column=0, sticky='nsew')
			textArea = tk.Text(frame, wrap=tk.NONE, yscrollcommand=scrollBarV.set\
			  , xscrollcommand=scrollBarH.set, borderwidth=3, relief=tk.SUNKEN, height=height, width=width)
			textArea.insert(tk.END, msg)
			textArea.grid(row=0, column=0, sticky='nsew')
			scrollBarV.config(command=textArea.yview)
			scrollBarH.config(command=textArea.xview)
			frame.columnconfigure(0, weight=1)
			frame.rowconfigure(0, weight=1)
			frame.grid(row=0, column=0, sticky="nsew")
			#if there's at least one specified button, add them at the bottom
			if buttons != None and len(buttons) > 0:
				ttk.Separator(self.popup, orient=tk.HORIZONTAL).grid(column=0, row=1, columnspan=1, sticky='ew', pady=5)
				f = tk.Frame(self.popup)
				f.configure(background="#F0F0F0")
				col = 0
				for t in buttons:
					command = (lambda t=t: self.action(t))
					button = ttk.Button(f, text=t, command=command)
					button.grid(row=0, column=col, pady=10, padx=10)
					col += 1
				f.grid(row=2, column = 0, columnspan=1, pady=0, padx=0)
				
				# if there's at least one specified button, disable the system close button
				self.popup.update_idletasks()
				self.popup.overrideredirect(True)
		def show(self):
			self.popup.wait_window()
			return self.ret
	return _Popupmsg(parent, title, msg, height, width, buttons).show()
	

########## TEST STUFF #########

code = """
import argparseX as ap
import os

global parser   # only needed because we're consulting the parser in run() to format the
				# command line string.

def run(namespace):
	global parser
	ret = parser.namespaceToCommandLineString(namespace, includePythonPrefix=True)
	if len(ret) > 80: # repeat with linebreaks if it's a long line
		ret = parser.namespaceToCommandLineString(namespace, multiline=True, includePythonPrefix=True)
	print("run():")
	print(ret)
	
def run2(string_pos_arg, string_opt_arg=None, string_opt_arg_req=None, file=None, \
			textfile=None, true=None, false=None, const=None, int=None):
	print("run2():")
	print("      string_pos_arg: "+str(string_pos_arg))
	print("      string_opt_arg: "+str(string_opt_arg))
	print("  string_opt_arg_req: "+str(string_opt_arg_req))
	print("                file: "+str(file))
	print("            textfile: "+str(textfile))
	print("                true: "+str(true))
	print("               false: "+str(false))
	print("               const: "+str(const))
	print("                 int: "+str(int))
		
#OPTIONS
CALLBACK = None # a non-None callback parameter to parse_args() will cause the GUI to
				# persist so the user can make multiple runs of the program, if it's 
				# None, the GUI will only run and return arguments just like the command
				# line.  If the callback takes only 1 parameter it is assumed to take
				# a argparse.Namespace object; otherwise it is assumed the parameters 
				# are the command arguments and will be called with the 
				# (*args, **kwargs) format: the positional (*args) parameters are in the
				# order they are declared in the argparseX.ArgumentParser.add_argument
				# calls.
FORCE_GUI = True  # setting to True will cause the GUI interface during the call to 
				  # parse_args() regardless of whether --gui is on the command line.
				 
if __name__ == '__main__':
	global parser
	parser = ap.ArgumentParser()
	parser.add_argument('string_pos_arg', default="default", label="Positional String", 
		help='A string positional argument.')
	parser.add_argument('--string_opt_arg', '-s', default="Optional String", required=False, 
		label="stringArg1", help='An optional string argument.')
	parser.add_argument('--string_opt_arg_req', required=True,
		label="Required optional String", help='A required optional (--) string argument.')
	parser.add_argument('--file', label="A file", file=True,
		help="An optional (--) file argument that we don't want to allow editing on.")
	parser.add_ruler()
	parser.add_argument('--textfile', label="A text file", textfile=True,
		help="An optional (--) file argument that we want to allow in-place editing on.")
	parser.add_ruler()
	parser.add_argument('--true', action='store_true',
		help="An optional (--) boolean argument using store_true.")
	parser.add_argument('--false', action='store_false',
		help="An optional (--) boolean argument using store_false.")
	parser.add_argument('--const', action='store_const', const=42,
		help="An optional (--) const argument storing 42.")
	parser.add_argument('--int', type=int, 
		help='An optional int argument.')

	ans = ""
	while not ans.upper() in {"N", "E", "-"}:
		print()
		print("You are running a quick test of the parseX module.  You have the following callback options:")
		print()
		print("  N: Run parser.parse_args() with the callback getting the namespace parameter.")
		print("  E: Run parser.parse_args() with the callback getting explict parameters.")
		print("  -: Run parser.parse_args() with no callback.")
		print()
		ans = input("Your callback option? ")	
	if   ans.upper() == "N": 
		CALLBACK = run
	elif ans.upper() == "E": 
		CALLBACK = run2
	
	ans = ""
	print()
	while not ans.upper() in {"Y", "N"}:
		ans = input("Do you want to force run the GUI? [Y/N] ")	
	FORCE_GUI = ans.upper() == "Y" 
	
	namespace = parser.parse_args(callback=CALLBACK, forceGUI=FORCE_GUI)
	if CALLBACK == None:
		run(namespace) # parser.nameSpace version
		run(namespace.__dict__) # dict version
		args, kwargs = parser._splitNamespace(namespace)
		run2(*args, **kwargs)
	print("-- namespace ('*' denotes reserved parser arguments not passed to the app program) --")
	ns = vars(namespace)
	max = 0
	for k in ns: 
		if len(k) > max: max = len(k)
	for k in ns:
		print((k+("*" if k in ap.PARSER_ARGS else "")).rjust(max)+": "+str(ns[k]))
	print("--")
"""

if __name__ == '__main__':
	code = code.replace('\t', '    ')
	sep = "\n---------------------------\n"
	print("Executing the following example code:\n\n" + sep + code + sep)
	print("You will need to specify required command line arguments to get non-error output.\n\nOutput:" + sep)
	exec(code)
	
