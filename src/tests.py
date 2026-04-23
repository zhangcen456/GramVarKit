from .utils import TreeDumper,compare_trees
from .unparser import BaseUnparser
from .build_parser import build_parser

parser=build_parser(True)
spy_parser=build_parser(False)

def test_round_trip(source_code,unparser1:BaseUnparser,unparser2:BaseUnparser):
    tree = parser.parse(bytes(source_code, 'utf8'))
    unparser1.clear()
    success=unparser1.unparse(tree)
    if(not success):#ERROR node in py parse tree
        return True
    new_code="\n".join(unparser1.lines)
    new_tree=spy_parser.parse(bytes(new_code,'utf8'))
    unparser2.clear()
    unparser2.unparse(new_tree)
    twice_code="\n".join(unparser2.lines)
    twice_tree=parser.parse(bytes(twice_code,'utf8'))
    return compare_trees(tree,twice_tree)