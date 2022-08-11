from graph_tool.all import Graph, Vertex
from typing import List,Iterator,Union
import numpy as np
import math

def double_loop_iterator(stuff:iter):
    if type(stuff)!=list:
        stuff = list(stuff)
    for i,el1 in enumerate(stuff):
        for el2 in stuff[i+1:]:
            yield(el1,el2)

def findsquares(squares):
    winsquarenums = set()
    perrow = int(math.sqrt(squares))
    for s in range(squares-perrow-1):
        if s % perrow != perrow-1:
            winsquarenums.add(frozenset({s,s+1,s+perrow,s+perrow+1}))
    return winsquarenums

def remove_useless_wsn(winsquarenums):
    discardos = set()
    for ws1 in winsquarenums:
        for ws2 in winsquarenums:
            if ws1!=ws2 and ws1.issubset(ws2):
                discardos.add(ws2)
    for d in discardos:
        winsquarenums.discard(d)
def findfivers(squares):
    winsquarenums = set()
    perrow = int(math.sqrt(squares))
    for s in range(squares):
        if perrow - (s % perrow) >= 5:
            winsquarenums.add(frozenset({s,s+1,s+2,s+3,s+4}))
            if perrow - (s // perrow) >= 5:
                winsquarenums.add(frozenset({s,s+perrow+1,s+2*(perrow+1),s+3*(perrow+1),s+4*(perrow+1)}))
        if perrow - (s // perrow) >= 5:
            winsquarenums.add(frozenset({s,s+perrow,s+2*perrow,s+3*perrow,s+4*perrow}))
            if (s % perrow) >= 4:
                winsquarenums.add(frozenset({s,s+perrow-1,s+2*(perrow-1),s+3*(perrow-1),s+4*(perrow-1)}))
    return winsquarenums

def fully_connect_lists(g:Graph,l1:List[Vertex],l2:List[Vertex]):
    for v1 in l1:
        for v2 in l2:
            if v1!=v2:
                g.edge(v1,v2,add_missing=True)

                
class take_step():
    def __init__(self,possible_values):
        self.stepsize = 2
        self.possible_values = np.array(possible_values)
    def __call__(self,x):
        selections = np.random.randint(0,len(x),size=int(self.stepsize)+1)
        y = x.copy()
        y[selections] = np.random.choice(self.possible_values,size=int(self.stepsize)+1,replace=True)
        return y

def greedy_search(eval_func:callable,init_x:np.ndarray,take_step_func:callable,stopping_cost=0):
    x = init_x.copy()
    cost = eval_func(x)
    while cost>stopping_cost:
        y = take_step_func(x)
        new_cost = eval_func(y)
        if new_cost<=cost or np.random.random()<np.exp(-(new_cost-cost)):
            x=y
            cost = new_cost
            #if hasattr(take_step_func,"stepsize"):
            #    take_step_func.stepsize*=1.1
        #else:
            #if hasattr(take_step_func,"stepsize"):
            #    take_step_func.stepsize*=0.9
    return x,cost

# This isn't to quick. If we need speed, maybe implement as C graph-tool extension
def is_fully_connected(g:Graph,vertices:Iterator[int]) -> bool:
    """Checks if a list of vertices is fully connected.

    Args:
        g: A undirected graph-tools graph
        vertices: A list of vertices from that graph
    Returns:
        Whether the vertices are fully connected
    """
    for v1,v2 in double_loop_iterator(vertices):
        if not g.edge(v1,v2):
            return False
    return True
