from tygra.typedgraphs import TypedGraphsContainer
import tygra.app as app
import os
import sys

if len(sys.argv) > 1:
	file = sys.argv[1]
else:
	file = f"typedgraphs.{app.APP_FILE_EXTENSION}"
	
if not os.path.isfile(file) and file.find('.') < 0:
	file += f'.{app.APP_FILE_EXTENSION}'
	
if not os.path.isfile(file):
	print(f"Cannot find file {file}")
	file = None
else:
	print(f'Attempting file {file}')

root = TypedGraphsContainer(file)
root.mainloop()
