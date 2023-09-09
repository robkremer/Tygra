from tygra.typedgraphs import TypedGraphsContainer
import tygra.app as app
import os
import sys
from typing import Optional
from tygra.prefs import Prefs
from _tkinter import TclError
import argparse as ap
import pathlib

def startup(filename:Optional[str]=None, **kwargs):
	if filename is not None:
		try:
			TypedGraphsContainer(filename, **kwargs).mainloop() # blocks
			return
		except Exception as ex:
			print(f'Unexpected exception calling TypedGraphContainter("{filename}"): {type(ex).__name__}: ({ex}).')
	
	#Attempt to read the prefs file:
	prefs = Prefs()
	tgc = None
	try:
		prefs.read()
		openFiles = prefs.getOpenFilesData()
		for file in openFiles:
			try:
				filename = file.filename
				geometry = file.geometry
				tgc = TypedGraphsContainer(filename, **kwargs)
				tgc.geometry(geometry)
				openViews = file.openViews
				for vrec in openViews:
					for mName, mRec in tgc.directory.items():
						if vrec.id in mRec.viewRecords:
							view = tgc.openView(mRec.viewRecords[vrec.id].viewData)
							view.winfo_toplevel().geometry(vrec.geometry)
			except Exception as ex:
				print(f'Unexpected exception opening previously opened file ("{filename}"): {type(ex).__name__}: ({ex}).')
	except Exception as ex:
		print(f'Can\'t open prefs file: {prefs.prefsFileName}: {type(ex).__name__}: {ex}.')
		
	try:
		if tgc is not None:
			tgc.mainloop()
		else:	
			# didn't open any window if we got here, so open one by having it ask the user for a file				
			TypedGraphsContainer(**kwargs).mainloop() # blocks
	except Exception as ex:
		if not (type(ex) == TclError and 'loggingpanedwindow' in str(ex)):
			sys.__stderr__.write(f'Unexpected exception in TCL mainloop(): {type(ex).__name__}: ({ex}).')

parser = ap.ArgumentParser(prog=app.APP_SHORT_NAME, description="A graph editor for typed graphs")
parser.add_argument('filename', nargs='?', default=None, help='The file to load, may be empty for default or a "open file" dlalog.')
parser.add_argument('--helppath', default=None, help='A URL or file path to the root directory of this program\'s html help files. Defaults to "<packageDirectory>/html/".')

kwargs = vars(parser.parse_args())
if 'filename' in kwargs:
	filename = kwargs['filename']
	kwargs.pop('filename')
else:
	filename = None
	
startup(filename, **kwargs)
