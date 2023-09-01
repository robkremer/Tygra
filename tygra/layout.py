"""
Layout hieristics
"""
from abc import ABC, abstractmethod # Abstract Base Class
from typing import Optional, Self, Union
from tygra.vobjects import VObject
from tygra.vnodes import VNode
from tygra.vrelations import VRelation
import tygra.util as util
from random import randrange
# from tygra.typedgraphs import TGView
import tygra.app as app
from tygra.mnodes import MNode
from tygra.mobjects import MObject
from tygra.mrelations import MRelation
from math import ceil, floor
from functools import reduce

class LayoutHieristic(ABC):

	def __init__(self, view, spacing=[1,1,1,1], relSpacing=None, **kwargs):
		"""
		:param view: The view this layout applies to.
		:param spacing: The expansion on the bounding box for node and (maybe) relation
				shapes when evaluating overlaps. Can be negative.
		:param relSpacing: The spacing specifically for relation label shapes. If set to
				*None*, *relSpacing* will be the same as *spacing*.
				
		"""
		self.view = view
		self.spacing = spacing
		self.relSpacing = spacing if relSpacing is None else relSpacing
		
	@abstractmethod
	def __call__(self, focus:VObject=None):
		pass
		
	@classmethod
	@abstractmethod
	def isLocal(self) -> bool: pass

	@classmethod
	@abstractmethod
	def isGlobal(self) -> bool: pass

	def expand(self, node:VNode, byRect:list=None) -> list:
		"""
		:param node: A VNode or VRelation who's bounding box will be expanding.
		:param byRect: a 4-list describing the delta to expand.
		:return: The rectangle describing the expanded bounding box.
		
		Expands the edges of a *node* (could be an actual VNode or or VRelation).
		"""
		if byRect is None:
			byRect = self.relSpacing if isinstance(node, VRelation) else self.spacing
		rect = node.boundingBox()
		return  [rect[0]-byRect[0],
				 rect[1]-byRect[1],
				 rect[2]+byRect[2],
				 rect[3]+byRect[3]]
				 
	def findFree(self, node) -> tuple[int, int]:
		expandBy = self.relSpacing if isinstance(node, VRelation) else self.spacing
		rect = self.expand(node, byRect=expandBy)
		rect = [int(i) for i in rect] # convert to integer
		size = (rect[2]-rect[0], rect[3]-rect[1])
		others = node.overlaps()
		if len(others) == 0: return
		otherNode = others[0]
		otherRect = otherNode.boundingBox()
		otherRect = [int(i) for i in otherRect] # convert to integer
		otherSize = (otherRect[2]-otherRect[0], otherRect[3]-otherRect[1])
		for d in range(1, 100):
			searchSize = (d*otherSize[0], d*otherSize[1])
			tried = False # this will go true if we even try to find a place within the scroll region
			for y in range(-searchSize[1]+otherRect[1], searchSize[1]+otherRect[1]+1, otherSize[1]):
			
				# muck with the x-increment so we only look at the ring around the target node
				if y==-searchSize[1]+otherRect[1] or y==searchSize[1]+otherRect[1]:
					incr = otherSize[0]
				else:
					incr = 2*d*otherSize[0]
					
				for x in range(-searchSize[0]+otherRect[0], searchSize[0]+otherRect[0]+1, incr):
					ret = [x, y, x+size[0], y+size[1]]
					# if the attempted box is within the scroll region
					if ret[0]>=0 and ret[1]>=0: #and \
							#ret[2]<=self.view.scrollRegion[2] and \
							#ret[3]<=self.view.scrollRegion[3]:
						tried = True
						overlaps = False
						for vn in self.view.nodes+self.view.relations:
							if vn is not node and vn is not otherNode:
								if util.overlaps(ret, vn.boundingBox()):
									overlaps = True
									break
						if not overlaps:
							return x, y

class CellLayout(LayoutHieristic):
	class Cell:
		def __init__(self, 	node	:VNode, 
							parent	:Optional[Self]	=None, 
							row		:int			=0, 
							col		:int			=-1,
							leftSib	:Optional[Self]	=None,
							rightSib:Optional[Self]	=None):
			self.col = col
			self.row = row
			self.node = node
			self.parent = parent
			self.leftSib = leftSib
			self.rightSib = rightSib
			self.children:Optional[list[Self]] = None
			self.width = 0
			self.rightMargin = -1
		
		def validate(self):
			assert self.col >= 0
			assert self.row >= 0
			assert self.rightMargin >= 0
			if self.leftSib is not None:
				assert self.leftSib.col < self.col
				assert self.width <= self.rightMargin-self.leftSib.rightMargin
			if self.rightSib is not None:
				assert self.rightSib.col > self.col
			if self.children is None:
				assert self.width == 1
			else:
				assert len(self.children) > 0
				w = 0
				for c in self.children:
					w += c.width
				assert w == self.width	
						
class IsaHierarchy(CellLayout):

	def __init__(self, view, 
				cellWidth:Optional[int]=None, 
				cellHeight:Optional[int]=None,
				marginWidth=20, marginHeight=15, **kwargs):
		super().__init__(view, **kwargs)
		if cellWidth is None:
			sizex = self.view.model.topNode.attrs["minSize"]
			self.cellWidth = int(1.5*sizex)
		else:
			self.cellWidth = cellWidth
			
		if cellHeight is None:
			sizex = self.view.model.topNode.attrs["minSize"]
			sizey = int(sizex * self.view.model.topNode.attrs["aspectRatio"]) 
			self.cellHeight = int(4*sizey)
		else:
			self.cellHeight = cellHeight

		self.marginWidth = marginWidth
		self.marginHeight = marginHeight

	@classmethod
	def isLocal(self) -> bool: return False

	@classmethod
	def isGlobal(self) -> bool: return True
			
	def makeLayoutForNodes(self, nodes, topNode):

		layers:list[list[MNode]] = []

		def findLayer(mNode, topNode) -> int:
			"Return the shortest isa-distance from the *mNode* to *topNode*."
			assert isinstance(mNode, MObject)
			if mNode is topNode: return 0
			min = 1000
			for mp in mNode.isparent():
					depth = findLayer(mp, topNode)
					if depth < min:
						min = depth
			return min+1
		
		def appendAt(vNode, index):
			"Add the node to end of the *index* row, creating the row if necessary."
			while len(layers) <= index:
				layers.append([])
			layers[index].append(vNode)
		
		def getVisual(mNode):
			"Return the view's visual object in model object. None if there isn't one."
			if isinstance(mNode, MNode):
				for n in self.view.nodes:
					if n.model == mNode:
						return n
			elif isinstance(mNode, MRelation):
				for n in self.view.relations:
					if n.model == mNode:
						return n
			return None
		
		def makeTree(n:VNode, done=[]) -> list[Union[VNode,list]]:
			"""
			Make a list tree (eg: [n1 [n1.1, n1.2], n2, [n2.1]]) representing the 
			isa hierarchy of the nodes in the view.
			"""
			if n in done: return []
			tree = []
			tree.append(n)
			done.append(n)
			children = []
			for r in n.model.relations:
				if r.isIsa and r.toNode == n.model:
					child = getVisual(r.fromNode)
					if child is not None and child in nodes:
						children += makeTree(child, done)
						done.append(child)
			if len(children) > 0:
				tree.append(children)
			return tree
			
		def moveAll(cells:list[CellLayout.Cell], col:int):
			right = col
			for c in cells: right += c.width
			right -= 1
			for c in reversed(cells):
				c.col = right - c.width//2
				c.rightMargin = c.col + c.width//2
				if c.children is not None: moveAll(c.children, right-c.width//2)
# 				c.validate()
				right -= c.width

		def centerChildren(cell:CellLayout.Cell):
			"""Move all childen (if any) so that they are centered below the *cell*. If 
			there's an even number of children, the extra child is to the right.'"""
			if cell.children is None: return
			assert cell.width > 0
			expectedLeftChildCol = cell.col - (cell.width-1)//2
			childCol = cell.children[0].col
			if expectedLeftChildCol == childCol: return
			moveBy = expectedLeftChildCol - childCol
# 			hasOnlyTerminalChildren = reduce(lambda a,b: a and (b.children is None), cell.children, True)
			for c in reversed(cell.children):
				c.col += moveBy
				c.leftMargin = c.col + c.width//2
			moveAll(cell.children, expectedLeftChildCol)
			for c in reversed(cell.children):
				centerChildren(c)

		def makeLayout(	tree	:list[Union[VNode,list]], 
						rowInfo	:dict[int,list[CellLayout.Cell]]	=dict(),
						parent	:CellLayout.Cell					=None, 
						level	:int								=0, 
						left	:CellLayout.Cell					=None) \
							-> list[CellLayout.Cell]:
			"""
			Make a list of Cell objects, recursively as a isa-hierarchy tree and a rowInfo
			structure containing all the same cells. Eg:
			
			v rowInfo   v isaTrees
			0:         [cell0,             cell1,       cell2]
			           /    \             /    \          |
			1:    [cell0.0, cell0.1, cell1.0, cell1.1, cell2.0]
			
			2:     ...
			
			"""
			assert isinstance(tree, list)
			assert isinstance(tree[0], VNode)
			assert parent==None or isinstance(parent, CellLayout.Cell)
			assert left==None or isinstance(left, CellLayout.Cell)
			i = 0
			isaTrees = []
			while i < len(tree): #work across the nodes in the row in the tree
				node = tree[i]
				assert isinstance(node, VNode)
				cell = CellLayout.Cell(node, parent, row=level, leftSib=left)
				if level in rowInfo: # we must have a right sibling owned by another parent
					rowInfo[level][-1].rightSib = cell
					cell.leftSib = rowInfo[level][-1]
					rowInfo[level].append(cell)
				else:
					rowInfo[level] = [cell]
				isaTrees.append(cell)
			
				# instantiate the children and calculate the width
				children = None
				if i+1 < len(tree) and isinstance(tree[i+1], list):
					children = tree[i+1]
					i += 1
				if children is None:
					cell.width = 1
				else:
					cell.children, _ = makeLayout(children, rowInfo=rowInfo, parent=cell, level=level+1)
					cell.width = 0
					for c in cell.children:
						cell.width += c.width
					
				# finally, we can calculate this cell's position 
				leftCol = (cell.leftSib.rightMargin+1) if cell.leftSib is not None else 0
				cell.col = leftCol + ceil(cell.width/2) - 1
				cell.rightMargin = leftCol + cell.width - 1
				cell.validate()
				
				# housekeeping for the loop
				i += 1
				left = cell
				
			# At this point, we have the cells placed and spaced out with room for the 
			# children, but the terminal children are all flushed left.
			if len(rowInfo) > 0:
				for root in reversed(rowInfo[0]):
					if root.children is not None:
						centerChildren(root)
			
			return isaTrees, rowInfo


		# collect all nodes into distance-from-T layers
		for n in nodes:
			layer = findLayer(n.model, topNode)
			appendAt(n, layer)
		
		# compress the layers by removing any empty layers
		emptyIndexes = []
		for i in range(0, len(layers)):
			if layers[i] == []:
				emptyIndexes.insert(0, i)
		for i in emptyIndexes:
			del layers[i]
		
		# make an isa-child tree that includes all the layers
		tree = []
		done = []
		for n in util.treeFlatten(layers):
			if n not in done:
				tree += makeTree(n, done)
			
		# do the actual layout
		return makeLayout(tree)
		
	def optimize(self, cells):
		pass
		
	def position2(self, rowInfo:dict[int, list], xoffset, yoffset, cellWidth, cellHeight, vertical=True):
		maxX = 0
		maxY = 0
		for rowNum, row in rowInfo.items():
			for cell in row:
				x = (cell.col if vertical else cell.row) * cellWidth + xoffset
				y = (cell.row if vertical else cell.col) * cellHeight + yoffset
				cell.node.moveTo(x, y)
				x = x + cellWidth
				y = y + cellHeight
				if x>maxX: maxX = x
				if y>maxY: maxY = y
				
		return maxX, maxY

	def get2ndOffset(self, prevMinX, prevMinY, prevMaxX, prevMaxY) -> tuple[int, int]:
		return prevMaxX, prevMinY 
		
	def validate(self, layout, rowInfo): # for debugging only
		count1 = 0
		for rowNum, row in rowInfo.items():
			cellNum = 0
			lastCell = len(row) -1
			for cell in row:
				count1 += 1
				if cellNum == 0:
					assert cell.leftSib is None, f'cell with label "{cell.node.model.attrs["label"]}"'
				else:
					if cellNum == lastCell:
						assert cell.rightSib is None, f'cell with label "{cell.node.model.attrs["label"]}"'
					else:
						assert cell.rightSib.leftSib is cell, f'cell with label "{cell.node.model.attrs["label"]}"'
				cellNum += 1
			
		def countLayout(cells) -> int:
			if cells is None: return 0
			count = 0
			for cell in cells:
				count += 1 + countLayout(cell.children)
			return count
				
		count2 = countLayout(layout)
		assert count1 == count2

	def __call__(self):
		self.view.logger.write(f'starting layout {type(self).__name__}', level='info')
		cellWidth = 120
		cellHeight = 160
				
		oldSuppress = self.view.suppressLocalLayout()
		self.view.suppressLocalLayout(True)
		
		# float all the relations
		for r in self.view.relations:
			r._floatingAnchor = True
		
		# place the nodes
		self.view.logger.write('laying out nodes.', level='info')
		layout, rowInfo = self.makeLayoutForNodes(self.view.nodes, self.view.model.topNode)
		self.validate(layout, rowInfo) # debugging
		self.optimize(layout)
		maxX, maxY = self.position2(rowInfo, self.marginWidth, self.marginHeight, self.cellWidth, self.cellHeight)
		
		# place the relations that are types
		reltypes = []
		for r in self.view.relations:
			if r.model.attrs["type"]:
				reltypes.append(r)
		if len(reltypes) > 0:
			self.view.logger.write('laying out relations', level="info")
			layout, rowInfo = self.makeLayoutForNodes(reltypes, self.view.model.topRelation)
			self.optimize(layout)
			pt = self.get2ndOffset(self.marginWidth, self.marginHeight, maxX, maxY)
			self.position2(rowInfo, pt[0], pt[1], self.cellWidth, self.cellHeight)
			
		localLayout = FindFree(self.view, spacing=[-3,-3,-3,-3])
		for r in self.view.relations:
			localLayout(r)
		
		self.view.suppressLocalLayout(oldSuppress)
		self.view.setScrollRegion()


class IsaHierarchyCompressed(IsaHierarchy):

	def moveBy(self, cell, n:int) -> int:
		# never move such that your parent's rightmost (leftmost) sibling's doing the same move 
		# would put it left (right) of the parent (with a fudge factor of 1)
		if cell.parent is not None:
			if n < 0:
				space = cell.parent.children[-1].col - cell.parent.col + 1
				if -n > space: n = -space
			elif n > 0:
				space = cell.parent.col - cell.parent.children[0].col + 1
				if n > space: n = space
		
		# never move such that you are left (right) of your children (with a fudge
		# factor of 1)
		if cell.children is not None:
			if n < 0:
				space = cell.col - cell.children[0].col
				if -n > space: n = -space
			elif n > 0:
				space = cell.children[-1].col - cell.col
				if n > space: n = space
				
		# never move over your siblings
		if n < 0:
			space = cell.col - ((cell.leftSib.col + 1) if cell.leftSib is not None else 0)
			if -n > space: # ask the left sibling to moeve
# 				if cell.leftSib is not None:
# 					assert space >= 0, f'cell.col={cell.col}, cell.leftSib.col={cell.leftSib.col}, n={n}, space={space}, cell.node="{cell.node.model.attrs["label"]}"'
# 					ask = -n - space
# 					assert ask > 0
# 					assert ask <= -n
# 					got = self.moveBy(cell.leftSib, -ask)
# 					assert got <= 0
# 					space = cell.col - ((cell.leftSib.col + 1) if cell.leftSib is not None else 0) # -got
# 					assert space >= 0
				n = -space
				assert n <= 0
		elif n > 0:
			space = (cell.rightSib.col - 1 - cell.col) if cell.rightSib is not None else n 
			if n > space:
# 				if cell.rightSib is not None:
# 					ask = n - space
# 					got = self.moveBy(cell.rightSib, ask)
# 					space = ((cell.rightSib.col - 1) if cell.rightSib is not None else n) - cell.col
				n = space
			
		if n != 0:
			self.moved = True
			cell.col += n
			try:
				cell.validate()
			except Exception as ex:
				self.view.logger.write(f'cell.col={cell.col}, cell.leftSib.col={cell.leftSib.col}, n={n}, space={space}, cell.node="{cell.node.model.attrs["label"]}"', level="error", exception=ex)
		return n

	def compact(self, cells):
		self.moved = False
		for cell in cells:
			self.moveBy(cell, (cell.leftSib.col if cell.leftSib is not None else 0) - cell.col)
			if cell.children is not None:
				self.compact(cell.children)
		return self.moved
		
	def centerParents(self, cells):
	
		def centerParent(cell):
			if cell.children is None:
				return
			if cell.children is None: return
			self.centerParents(cell.children)
			center = cell.children[0].col + cell.children[-1].col // 2
			if center != cell.col:
				self.moveBy(cell, center - cell.col)
			
		self.moved = False
		for cell in cells:
			centerParent(cell)
		return self.moved
						
	def optimize(self, cells):
		self.view.logger.write("starting optimizaiton", level="info")
		count = 0
		while self.compact(cells): # while we moved something
			count += 1
			self.view.container.update_idletasks()
			self.view.container.update()
		self.view.logger.write(f"compacted in {count} passes.", level='info')
		count = 0
		while self.centerParents(cells):
			count += 1
			self.view.container.update_idletasks()
			self.view.container.update()
		self.view.logger.write(f"centered in {count} passes.", level='info')
		
	
class IsaHierarchyHorizontal(IsaHierarchy):

	def __init__(self, view, 
				cellWidth:Optional[int]=None, 
				cellHeight:Optional[int]=None,
				marginWidth=20, marginHeight=10, **kwargs):
		if cellWidth is None:
			sizex = view.model.topNode.attrs["minSize"]
			cellWidth = int(3*sizex)
			
		if cellHeight is None:
			sizex = view.model.topNode.attrs["minSize"]
			sizey = int(sizex * view.model.topNode.attrs["aspectRatio"]) 
			cellHeight = int(1.5*sizey)

		super().__init__(view, cellWidth=cellWidth, cellHeight=cellHeight,
				marginWidth=marginWidth, marginHeight=marginHeight, **kwargs)

	def position2(self, cell, xoffset, yoffset, cellWidth, cellHeight):
		return super().position2(cell, xoffset, yoffset, cellWidth, cellHeight, vertical=False)

	def get2ndOffset(self, prevMinX, prevMinY, prevMaxX, prevMaxY) -> tuple[int, int]:
		return prevMinX, prevMaxY
		
class IsaHierarchyHorizontalCompressed(IsaHierarchyCompressed, IsaHierarchyHorizontal):
	pass

class FindFree(LayoutHieristic):
	"""
	Can be used both as a local (single-node) placement, and as a global layout.
	Simple layout that checks a node for overlaps if if it overlaps, searches circularly
	around its position for free space to move it.
	"""
		
	def __call__(self, focus:VObject=None):		
		if focus is None:
			for n in self.view.nodes+self.view.relations:
				self(n)
			self.view.setScrollRegion()
			
		elif isinstance(focus, VNode):
			overlapsWith = focus.overlaps(spacing=self.relSpacing if isinstance(focus, VRelation) else self.spacing)
			nOthers = len(overlapsWith)
			if nOthers == 0: # This object doesn't overlap anything: leave it alone.
				return
			pos = self.findFree(focus)
			if pos is not None:
				focus.moveTo(pos[0], pos[1], adjustPos=False)

	@classmethod
	def isLocal(self) -> bool: return True

	@classmethod
	def isGlobal(self) -> bool: return True

class Nudge(LayoutHieristic):
	"""
	Can be used both as a local (single-node) placement, and as a global layout.
	Resolves overlap conflicts by trying to move (bump) both nodes in a pair away from
	one another.  Keeps count of nodes it bumps and then won't move that node if it exceeds
	*maxBumps*.  So this does **not** guarantee no overlaps.
	"""
	
	def __init__(self, view, maxBumps=5, **kwargs):
		super().__init__(view, **kwargs)
		self.maxBumps = maxBumps
	
	def __call__(self, focus:VObject=None, _desperationFactor=0, _moved:dict[str,int]=None):
		moved:dict[str,int] = _moved if _moved is not None else dict() # inf recursion prevention
				
		if focus is None:
			for n in self.view.nodes+self.view.relations:
				self(n, _moved=moved)
			self.view.setScrollRegion()

				
		elif isinstance(focus, VNode):
			# count the number of times this node has moved, return True iff it exceeds the threshold
			def registerMove(node): 
				id = node.idString
				if id not in moved:
					moved[id] = 1
				else:
					moved[id] += 1
				if moved[id] > self.maxBumps:
					return True
				return False
				
			def related(n1, n2) -> bool:
				"Return True iff one of n1 and n2 are VRelations a pointer to the other"
				if isinstance(n1, VRelation):
					if n1.toNode is n2 or n1.fromNode is n2: 
						return True
				if isinstance(n2, VRelation):
					if n2.toNode is n1 or n2.fromNode is n1: 
						return True
				return False
			
			overlapsWith = focus.overlaps(spacing=self.relSpacing if isinstance(focus, VRelation) else self.spacing)
			
			# should we bother?
			length = len(overlapsWith)
			if length == 0: # This object doesn't overlap anything: leave it alone.
				return
				
			# There may be more than one overlap: pick one
			if length > 1:
				n = overlapsWith[randrange(length)]
			else:
				n = overlapsWith[0]
			assert focus != n
			if registerMove(n): return # Don't pick on any one too much (prevent inf recursion)			
			nCtr = n.centerPt()
			nBB = self.expand(n)

			# Move the two nodes away from one another
			focusCtr = focus.centerPt()
			focusBB = self.expand(focus)
			if related(n, focus):
				spacing = [7,7,7,7] # node x, y, relation x, y
			else:
				spacing = [self.spacing[0], self.spacing[1], self.relSpacing[0], self.relSpacing[1]]
			factor = 16
			offset = [(focusCtr[0]-nCtr[0])/factor, (focusCtr[1]-nCtr[1])/factor]
			size = [(focusBB[2]-focusBB[0]+nBB[2]-nBB[0])/factor, (focusBB[3]-focusBB[1]+nBB[3]-nBB[1])/factor]
			if abs(offset[0]) == abs(offset[1]):
				randx = 1 if randrange(2)==0 else -1
				randy = 1 if randrange(2)==0 else -1
				moveby = [randx*(size[0]-abs(offset[0])+spacing[0]+_desperationFactor), randy*(size[1]-abs(offset[1])+spacing[3]+_desperationFactor)]				
			elif abs(offset[0]) > abs(offset[1]):
				moveby = [size[0]-abs(offset[0])+spacing[0]+_desperationFactor, 0]
			else:
				moveby = [0, size[1]-abs(offset[1])+spacing[3]+_desperationFactor]
			focus.moveBy((-1 if offset[0]<0 else  1)*moveby[0], (-1 if offset[1]<0 else  1)*moveby[1], adjustPos=False)
			n.    moveBy(( 1 if offset[0]<0 else -1)*moveby[0], ( 1 if offset[1]<0 else -1)*moveby[1], adjustPos=False)
			if randrange(2) == 0: # flip order to avoid getting stuck on an scroll region edge
				self(focus, _desperationFactor=_desperationFactor+10, _moved=moved)
				self(n, _desperationFactor=_desperationFactor+10, _moved=moved)
			else:
				self(n, _desperationFactor=_desperationFactor+10, _moved=moved)
				self(focus, _desperationFactor=_desperationFactor+10, _moved=moved)
				
		else:
			raise TypeError(f"Nudge.__call__(): Unexpected type for argument focus: {type(focus)}.")
			
	@classmethod
	def isLocal(self) -> bool: return True

	@classmethod
	def isGlobal(self) -> bool: return True
	
class ObjectRowGALayout(LayoutHieristic):
	def __init__(self, view, rowTypes:list[MNode],
				cellWidth:Optional[int]=None, 
				cellHeight:Optional[int]=None,
				marginWidth=20, marginHeight=15, **kwargs):
		super().__init__(view, **kwargs)
		if cellWidth is None:
			sizex = self.view.model.topNode.attrs["minSize"]
			self.cellWidth = int(1.5*sizex)
		else:
			self.cellWidth = cellWidth
			
		if cellHeight is None:
			sizex = self.view.model.topNode.attrs["minSize"]
			sizey = int(sizex * self.view.model.topNode.attrs["aspectRatio"]) 
			self.cellHeight = int(4*sizey)
		else:
			self.cellHeight = cellHeight

		self.marginWidth = marginWidth
		self.marginHeight = marginHeight

		order = []
		rowTypes2 = rowTypes.copy()
		while len(rowTypes2) > 0:
			for r in rowTypes2:
				notIsa = True
				for r2 in rowTypes2:
					if r is not r2 and r.isa(r2):
						notIsa = False
						break
				if notIsa:
					order.append(rowTypes.index(r))
					rowTypes2.remove(r)
					break
					
		assert len(order) == len(rowTypes)
		assert len(rowTypes2) == 0
		self.rowTypes = rowTypes
		self.order = order
		
	def position(self, rows, xoffset, yoffset, cellWidth, cellHeight, vertical=True):
		longest = 0
		for r in rows:
			if len(r) > longest: longest = len(r)

		maxX = 0
		maxY = 0
		rowNum = 0
		for row in rows:
			colNum = 0
			for node in row:
				x = (colNum if vertical else rowNum) * cellWidth + xoffset
				y = (rowNum if vertical else colNum) * cellHeight + yoffset
				node.moveTo(x, y)
				x = x + cellWidth
				y = y + cellHeight
				if x>maxX: maxX = x
				if y>maxY: maxY = y
				colNum += 1
			rowNum += 1
				
		return maxX, maxY
			
	def __call__(self):
		nodes = self.view.nodes.copy()
		rows = []
		for i in self.rowTypes: rows.append([]) # initialize the rows with empty lists to the proper length
		for i in self.order:
			doneNodes = []
			typ = self.rowTypes[i]
			for node in nodes:
				if node.model.isa(typ):
					rows[i].append(node)
					doneNodes.append(node)
			for n in doneNodes: nodes.remove(n)
		rows.append(nodes) # put any leftovers in a last row

		# do the actual moves in the window
		oldSuppress = self.view.suppressLocalLayout()
		self.view.suppressLocalLayout(True)		
		self.position(rows, self.marginWidth, self.marginHeight, self.cellWidth, self.cellHeight)
		localLayout = FindFree(self.view, spacing=[-3,-3,-3,-3])
		for r in self.view.relations:
			localLayout(r)
		self.view.suppressLocalLayout(oldSuppress)
		self.view.setScrollRegion()
		

	@classmethod
	def isLocal(self) -> bool: return False

	@classmethod
	def isGlobal(self) -> bool: return True
	
	
			