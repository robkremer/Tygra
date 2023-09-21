""" tk_ToolTip_class101.py
gives a Tkinter widget a tooltip as the mouse is above the widget
tested with Python27 and Python34  by  vegaseat	 09sep2014
www.daniweb.com/programming/software-development/code/484591/a-tooltip-class-for-tkinter

Modified to include a delay time by Victor Zaccardo, 25mar16
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
from typing import Union, Callable, Optional

class CreateToolTip(object):
	"""
	create a tooltip for a given widget
	"""
	def __init__(self, widget, text:Union[str,Callable[[],str]]='', canvasID:Optional[int]=None, 
				waitTime:int=500, wrapLength:int=180, 
				shouldDisplay:Optional[Callable]=None):
		"""
		:param widget:		The widget at attach this tooltip to
		:param text:		Either a string to display or a no-argument function returning a *str*
		:param canvasID:	A required item ID if *widget* is a tk.Canvas, otherwise ignored.
		:param waitTime:	The time to wait in msec. [default=500]
		:param wrapLength:	The width to wrap at in pixels. [default=180]
		:param shouldDisplay: A function taking this object as an argument returning a bool
							indicating that this text tool is to be displayed. If not 
							specified or None, the tooltip will display only if the text
							(text or a function) is not a zero-length string.
		:type shouldDisplay: Optional[Callable[[Self],bool]]
		:throws TypeError:
		:throws ValueError:
		"""
		self.waittime = waitTime	 #miliseconds
		self.wraplength = wrapLength   #pixels
		if isinstance(text, Callable):
			self.text = text
		elif isinstance(text, str):
			self.text = lambda text=text: text
		else:
			raise TypeError(f'CreateToolTip: Expected parameter "text" to be a function, f()->str, or a str; but got {type(text).__name__}.')
		self.shouldDisplay = shouldDisplay if shouldDisplay is not None else (lambda x: self.text() is not None and len(self.text()) > 0)
		self.widget = widget
		self.canvasID = canvasID
		self.isCanvas = isinstance(widget, tk.Canvas)
		if self.isCanvas:
			if self.canvasID is None: raise ValueError('CreateToolTip: When parameter "widget" is a tk.Canvas, parameter "canvasID" must be specified.')
			self.widget.tag_bind(self.canvasID, "<Enter>", self.enter)
			self.widget.tag_bind(self.canvasID, "<Leave>", self.leave)
			self.widget.tag_bind(self.canvasID, "<ButtonPress>", self.leave)
		else:
			self.widget.bind("<Enter>", self.enter)
			self.widget.bind("<Leave>", self.leave)
			self.widget.bind("<ButtonPress>", self.leave)
		self.id = None
		self.tw = None
		
	def delete(self):
		self.unschedule()
		self.hidetip()
		if self.isCanvas:
			assert self.canvasID is not None
			self.widget.tag_unbind(self.canvasID, "<Enter>")
			self.widget.tag_unbind(self.canvasID, "<Leave>")
			self.widget.tag_unbind(self.canvasID, "<ButtonPress>")
		else:
			self.widget.unbind("<Enter>")
			self.widget.unbind("<Leave>")
			self.widget.unbind("<ButtonPress>")
		self.widget = None
		self.text = None
		self.shouldDisplay = None

	def enter(self, event=None):
		if self.shouldDisplay(self):
			self.schedule()

	def leave(self, event=None):
		self.unschedule()
		self.hidetip()

	def schedule(self):
		self.unschedule()
		self.id = self.widget.after(self.waittime, self.showtip)

	def unschedule(self):
		id = self.id
		self.id = None
		if id:
			self.widget.after_cancel(id)

	def showtip(self, event=None):
		x = y = 0
		if self.isCanvas:
			x, y, cx, cy = self.widget.bbox(self.canvasID)
		else:
			x, y, cx, cy = self.widget.bbox("insert")
		x += self.widget.winfo_rootx() + 25
		y += self.widget.winfo_rooty() + 20
		# creates a toplevel window
		self.tw = tk.Toplevel(self.widget)
		# Leaves only the label and removes the app window
		self.tw.wm_overrideredirect(True)
		self.tw.wm_geometry("+%d+%d" % (x, y))
		label = tk.Label(self.tw, text=self.text(), justify='left',
					   background="#ffffff", relief='solid', borderwidth=1,
					   wraplength = self.wraplength)
		label.pack(ipadx=1)

	def hidetip(self):
		tw = self.tw
		self.tw= None
		if tw:
			tw.destroy()

# testing ...
if __name__ == '__main__':
	root = tk.Tk()
	btn1 = tk.Button(root, text="button 1")
	btn1.pack(padx=10, pady=5)
	button1_ttp = CreateToolTip(btn1, \
   'Neque porro quisquam est qui dolorem ipsum quia dolor sit amet, '
   'consectetur, adipisci velit. Neque porro quisquam est qui dolorem ipsum '
   'quia dolor sit amet, consectetur, adipisci velit. Neque porro quisquam '
   'est qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit.')

	btn2 = tk.Button(root, text="button 2")
	btn2.pack(padx=10, pady=5)
	button2_ttp = CreateToolTip(btn2, lambda: \
	"First thing's first, I'm the realest. Drop this and let the whole world "
	"feel it. And I'm still in the Murda Bizness. I could hold you down, like "
	"I'm givin' lessons in	physics. You should want a bad Vic like this.")

	btn3 = tk.Button(root, text="button 3")
	btn3.pack(padx=10, pady=5)
	button3_ttp = CreateToolTip(btn3, lambda: "")
	
	root.mainloop()