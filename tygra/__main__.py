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
import os
import sys
import traceback

try:
	from tygra.typedgraphs import TygraContainer
except:
	sys.path.insert(0, ".")
	print(sys.path)
	print(f'__file__ = {__file__}')
	
from tygra.typedgraphs import TygraContainer
import tygra.app as app
from typing import Optional
from tygra.prefs import Prefs
from _tkinter import TclError
import argparse as ap
import pathlib

def startup(filename:Optional[str]=None, **kwargs):
	if filename is not None:
		try:
			TygraContainer(filename, **kwargs).mainloop() # blocks
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
				tgc = TygraContainer(filename, **kwargs)
				tgc.geometry(geometry)
				openViews = file.openViews
				for vrec in openViews:
					for mName, mRec in tgc.directory.items():
						if vrec.id in mRec.viewRecords:
							view = tgc.openView(mRec.viewRecords[vrec.id].viewData)
							view.winfo_toplevel().geometry(vrec.geometry)
			except Exception as ex:
				sys.stderr.write(traceback.format_exc()+"\n")
				sys.stderr.write(f'Unexpected exception opening previously opened file ("{filename}"): {type(ex).__name__}: ({ex}).\n')
	except Exception as ex:
		print(f'Can\'t open prefs file: {prefs.prefsFileName}: {type(ex).__name__}: {ex}.')
		
	try:
		if tgc is not None:
			tgc.mainloop()
		else:	
			# didn't open any window if we got here, so open one by having it ask the user for a file				
			TygraContainer(**kwargs).mainloop() # blocks
	except Exception as ex:
		if not (type(ex) == TclError and 'loggingpanedwindow' in str(ex)):
			#sys.__stderr__.write(f'Unexpected exception in TCL mainloop(): {type(ex).__name__}: ({ex}).')
			raise ex

def main():
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
	
if __name__ == "__main__":
	main()
