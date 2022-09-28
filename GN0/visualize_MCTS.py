from graph_tool.all import Graph,Vertex,graph_draw,radial_tree_layout
from GN0.MCTS import MCTS,Node,Leafnode,upper_confidence_bound
from graph_game.shannon_node_switching_game import Node_switching_game
from graph_game.graph_tools_games import get_graph_only_hex_game
import numpy as np
from GN0.MCTS_player import get_pre_defined_mcts_model
from typing import Union
import os
import time

def dummy_nn(game:Node_switching_game):
    moves = game.get_actions()
    prob = np.array(list(range(len(moves))),dtype=float)+1
    prob/=np.sum(prob)
    value = 0.7 if game.view.gp["m"] else 0.3
    return moves,prob,value

def graph_from_root(root:Union[Node,Leafnode],to_show="num_visits"):
    def recursive_add(cur_node:Node,cur_vertex:Vertex):
        ucb = upper_confidence_bound(cur_node,1)
        for tv,child,q,visits,one_ucb,prior in zip(cur_node.total_value,cur_node.children,cur_node.Q,cur_node.visits,ucb,cur_node.priors):
            v = g.add_vertex()
            g.add_edge(cur_vertex,v)
            color[v] = "blue" if cur_node.storage.gp["m"] else "red"
            if to_show=="num_visits":
                text[v] = str(visits)
            elif to_show == "q":
                text[v] = f"{q:.2f}"[1:] if q<1 else "1"
            elif to_show == "value":
                if isinstance(child,Node):
                    text[v] = f"{tv:.1f}"
                else:
                    text[v] = child.value
            elif to_show == "prior":
                text[v] = f"{prior:.1f}"
            elif to_show == "m":
                if isinstance(child,Node):
                    text[v] = ""
                else:
                    text[v] = "" if child.move is None else child.move
            elif to_show=="numbers":
                text[v] = str(int(v))
            elif to_show=="ucb":
                text[v] = f"{float(one_ucb):.1f}"

            number_to_node[int(v)] = child
            if isinstance(child,Node):
                shape[v] = "circle"
                recursive_add(child,v)
            else:
                shape[v] = "square"

    number_to_node = {}
    g = Graph(directed=True)
    color = g.new_vertex_property("string")
    shape = g.new_vertex_property("string")
    text = g.new_vertex_property("string")
    size = g.new_vertex_property("int")
    pen_width = g.new_vertex_property("int")
    g.vp.g = size
    g.vp.c = color
    g.vp.s = shape
    g.vp.t = text
    g.vp.p = pen_width

    v = g.add_vertex()
    if isinstance(root,Node):
        recursive_add(root,v)
    makerturn = root.makerturn if isinstance(root,Leafnode) else root.storage.gp["m"]
    color[v] = "red" if makerturn else "blue"
    shape[v] = "square" if isinstance(root,Leafnode) else "circle"
    text[v] = ""
    size.a = 25
    return g,number_to_node


def visualize_MCTS():
    game = get_graph_only_hex_game(2)
    show_game = Node_switching_game.from_graph(Graph(game.view))
    nn = get_pre_defined_mcts_model()

    mcts = MCTS(game,nn)
    mode = "num_visits"
    while 1:
        g,number_to_node = graph_from_root(mcts.root,to_show=mode)
        graph_draw(g,radial_tree_layout(g,g.vertex(0)),vprops={"pen_width":g.vp.p,"shape":g.vp.s,"fill_color":g.vp.c,"text":g.vp.t,"size":g.vp.g},bg_color="black",output="mcts.pdf")
        os.system("pkill mupdf")
        os.system("nohup mupdf mcts.pdf > /dev/null 2>&1 &")
        time.sleep(0.1)
        os.system("bspc node -f west")
        while 1:
            command = input()
            if command=="n":
                mode = "numbers"
                break
            elif command=="v":
                mode = "num_visits"
                break
            elif command=="q":
                mode = "q"
                break
            elif command=="t":
                mode = "value"
                break
            elif command=="m":
                mode = "m"
                break
            elif command=="p":
                mode = "prior"
                break
            elif command=="u":
                mode = "ucb"
                break
            elif command=="r":
                print(mcts.extract_result(0))
            elif command=="":
                value = mcts.single_iteration()
                print(f"got value {value}")
                if mcts.done:
                    print("MCTS is done")
                break
            else:
                node = number_to_node[int(command)]
                if isinstance(node,Node):
                    show_game.set_to_graph(node.storage)
                    show_game.draw_me(fname="uff.pdf")
                    os.system("nohup mupdf uff.pdf > /dev/null 2>&1 &")
                    time.sleep(0.1)
                    os.system("bspc node -f west")
                nd = node.__dict__.copy()
                del nd["parent"]
                del nd["children"]
                print(nd)

if __name__=="__main__":
    visualize_MCTS()
