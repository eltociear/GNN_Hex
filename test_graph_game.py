import networkx as nx
from graph_tools_games import Tic_tac_toe,Qango6x6,Qango7x7,Qango7x7_plus
from solve_graph_tools import PN_search
import matplotlib.pyplot as plt
import time
from functools import reduce

def test_moving():
    game = Tic_tac_toe()
    ind = 0
    while game.graph.num_vertices()>0:
        moves = game.get_actions()
        print(moves)
        if moves==True:
            print("win")
            break
        game.draw_me(ind)
        ind+=1
        game.make_move(moves[0])

def test_board_representation():
    game = Tic_tac_toe()
    game.board.position = list("fbf"
                               "wbb"
                               "wfw")
    game.board.onturn = "w"
    game.graph_from_board()
    game.hashme()
    moves = game.get_actions()
    print(moves)
    game.make_move(moves[1])
    game.draw_me(-1)

def test_forced_move_search():
    game = Qango6x6()
    game.board.position = list( "ffffwf"
                                "wbwfbf"
                                "ffffff"
                                "ffffwf"
                                "wbwfbf"
                                "ffffwf")
    game.board.onturn = "b"
    game.graph_from_board()
    game.hashme()
    game.draw_me(-1)
    s = time.perf_counter()
    print(game.forced_move_search())
    print(time.perf_counter()-s)

def test_threat_search():
    game = Qango6x6()
    game.board.position = list( "ffffwf"
                                "wbwfbf"
                                "ffffff"
                                "ffffwf"
                                "wbwfbf"
                                "ffffwf")


    game.board.position = list( "ffffff"
                                "ffffff"
                                "fwffff"
                                "ffbwff"
                                "ffwbbf"
                                "ffffbf")
    game.board.onturn = "b"
    game.graph_from_board()
    game.draw_me(-1)
    s = time.perf_counter()
    defenses,win,movelines = game.threat_search()
    print(time.perf_counter()-s)
    print(win,len(defenses),defenses)
    board_view = []
    for d in defenses:
        val = game.board.node_map[d]
        board_view.append((val%6,val//6))
    print(board_view)
    not_defs = set(game.board.node_map.keys())-defenses
    board_view = []
    for d in not_defs:
        val = game.board.node_map[d]
        board_view.append((val%6,val//6))
    print(board_view)
    for line in movelines:
        print([d if type(d)==str else (game.board.node_map[d]%6,game.board.node_map[d]//6) for d in line[1:]])

def test_win_thread_search():
    game = Qango6x6()
    game.board.position = list( "ffffwf"
                                "wbwfbf"
                                "ffffff"
                                "ffffwf"
                                "wbwfbf"
                                "ffffwf")

    """game.board.position = list( "ffffff"
                                "ffffff"
                                "fwffff"
                                "ffbwff"
                                "ffwbff"
                                "ffffbf")"""
    game.board.onturn = "b"
    game.graph_from_board()
    s = time.perf_counter()
    winmoves = game.win_threat_search(one_is_enough=False)
    print(time.perf_counter()-s)
    print([(game.board.node_map[x]%6,game.board.node_map[x]//6) for x in winmoves])

def test_pos_from_graph():
    game = Qango6x6()
    game.board.position = list( "ffffff"
                                "ffffff"
                                "ffffff"
                                "ffffff"
                                "fffbff"
                                "ffffff")
    game.board.onturn = "w"
    game.graph_from_board()
    game.board.inv_maps()
    reco_pos = game.board.pos_from_graph()
    game.board.draw_me(reco_pos)
    game.make_move(game.board.node_map_rev[3*6+3])
    reco_pos = game.board.pos_from_graph()
    game.board.draw_me(reco_pos)
    #game.make_move(list(game.board.node_map.keys())[9])
    #reco_pos = game.board.pos_from_graph()
    #game.board.draw_me(reco_pos)

def display_wsn():
    game = Qango7x7_plus()
    count = 0
    for wsn in game.board.winsquarenums:
        if len(wsn)!=5:
            continue
        count+=1
        game.board.position = ["f"]*game.board.squares
        for ws in wsn:
            game.board.position[ws] = "W"
        game.board.draw_me()
    print(count)

if __name__ == "__main__":
    #test_moving()
    #test_board_representation()
    #test_forced_move_search()
    #test_threat_search()
    #test_pos_from_graph()
    #test_win_thread_search()
    display_wsn()