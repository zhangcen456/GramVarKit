from contextlib import contextmanager
from collections import defaultdict
from .utils import *
from .parse_config import *
from .wrapper import Wrapper
from .language_config import language_config
from .aux_class import SentinelNode,CustomException

DEBUG=False

class Unparser:
    def __init__(self,py_to_spy=False,spy_to_py=False,rule_path=None):
        self.lines=[]
        self.current_line=""
        self.writing_operations=[]
        self.comments=[]
        # self.write_comment_immediate=True
        self.target=-1
        self.stack=[]#root node to current node
        self.aliases={}
        # self.recorded_index={}
        self.prev_sibling_inline=None#including inline sibling
        self.get_inline_symbols()
        self.externals=language_config.externals+language_config.custom_externals
        self.zero_len_token=language_config.zero_len_tokens
        self.extras=language_config.extras
        self.transfer_rules=self.__class__.transfer_rules if py_to_spy else defaultdict(list)
        self.spy_to_py=spy_to_py
        if(self.spy_to_py):
            Wrapper.load_tree_rules(rule_path)

    @classmethod
    def load_transfer_rules(cls,rule_path):
        if(hasattr(cls,"transfer_rules")):
            return
        cls.transfer_rules=read_rules(rule_path)

    def get_inline_symbols(self):
        visit_methods=[attr for attr in dir(self) if attr.startswith("visit_")]
        self.inline_symbols = []
        for method_name in visit_methods:
            method = getattr(self, method_name)
            if getattr(method, 'inline', False):
                # Extract symbol name by removing 'visit_' prefix
                symbol = method_name[6:]  # len('visit_') == 6
                self.inline_symbols.append(symbol)

    def unparse(self,tree):
        if(not self.check_node(tree.root_node)):#error in parse tree
            return False
        self.clear()
        self.exec=False
        if(self.spy_to_py):
            root_node=Wrapper.construct_node(None,tree.root_node,tree.root_node.type,False,None)
        else:
            root_node=tree.root_node
        self.visit(root_node)
        #execute writing operations
        self.exec=True
        for operation in self.writing_operations:
            writing_op=getattr(self,operation[0])
            writing_op(*operation[1],**operation[2])
        self.maybe_newline()
        return True
    
    def get_code(self):
        return "\n".join(self.lines)

    def clear(self):
        self.lines.clear()
        self.current_line=""
        self.writing_operations.clear()
        self.comments.clear()
        self.target=-1
        self.stack.clear()
        self.aliases.clear()
        self.prev_sibling_inline=None

    def check_node(self,node):
        if(node.type=='ERROR'):
            return False
        for child in node.children:
            if(not self.check_node(child)):
                return False
            if(not child.parent==node):
                return False
        return True

    def save_states(self):
        states=(None,None,None,self.comments[:],self.target,self.stack[:],self.aliases.copy(),self.prev_sibling_inline,self.writing_operations[:])
        return states

    def restore_states(self,states):
        # self.lines=states[0][:]
        # self.indent=states[1]
        # self.current_line=states[2]
        self.comments=states[3][:]
        self.target=states[4]
        self.stack=states[5][:]
        self.aliases=states[6].copy()
        self.prev_sibling_inline=states[7]
        self.writing_operations=states[8][:]
        # self.write_comment_immediate=states[9]

    def find_children_position(self,node,index,target_type):
        """
        look for the children comply with the type(from index)
        TODO: how to deal with optional, choice, ...?
        """
        total_len=len(node.children)
        while index<total_len:
            if(Wrapper.get_children(node,index).type==target_type):
                return index
            index += 1
        raise CustomException("can't find target")
    
    def set_target(self,node,target):
        if(self.spy_to_py):
            target=node.get_uni_idx(target)
        self.target=target

    def visit(self,node,child_type=None,index=None):
        if(child_type is None):
            child_type=node.type

        is_inline=getattr(getattr(self,"visit_"+child_type,self.generic_visit),"inline",False)
        defaults={}
        if(child_type in self.aliases.keys()):
            old_type=child_type
            child_type,defaults,_=self.aliases[child_type]
            del self.aliases[old_type]

        self.stack.append(child_type)
        if(child_type=='recur_func()'):
            visitor=self.recur_func
        else:
            method_name="visit_"+child_type
            visitor=getattr(self,method_name,self.generic_visit)
        
        try:
            if(visitor==self.generic_visit):
                visitor(node,child_type)
            # elif(getattr(visitor,'inline',False)):
            elif(is_inline):
                visitor(node.parent,index)
                # if(self.target!=-1): #self.target already checked in choice()
                #     assert index[0]==self.target
                if(child_type not in self.extras and child_type not in language_config.custom_externals):
                    self.prev_sibling_inline=child_type
                return True
            else:#visit funcions that are not inline do not have an 'index' parameter
                if(child_type not in self.extras):
                    self.prev_sibling_inline=None#enter a new node
                ended_index=visitor(node,**defaults)
                self.skip_extras(node,ended_index)
                if(self.spy_to_py and isinstance(node,Wrapper)):#extra type node will not be wrapped
                    node.end_clear(ended_index[0])
                assert ended_index[0]==len(node.children),"avoid partial match"
                if(child_type not in self.extras):
                    self.prev_sibling_inline=child_type
                return False
        finally:
            self.stack.pop()
    
    def generic_visit(self,node,type):
        # raise Exception("No visit_{} method".format(node.type))
        if(DEBUG):
            print("No visit_{} method".format(type))
            print(node.text)
        raise CustomException("No visit_{} method".format(type))
    
    @writing_op
    def write(self,text):
        self.current_line+=text

    @writing_op
    def maybe_newline(self,add_comment=True):
        if(self.current_line and not self.current_line.isspace()):
            self.lines.append(self.current_line)
            self.current_line=""
        if(add_comment and self.comments):
            # self.lines.extend(self.comments[:])
            self.lines[-1]+=" ".join(self.comments)
            self.comments=[]
        # self.maybe_indent()
                

    @writing_op
    def maybe_spaceline(self):
        if(self.current_line):
            self.lines.append(self.current_line)
            self.current_line=""
        if(self.lines and self.lines[-1]!=""):
            self.lines.append("")     

    @writing_op
    def maybe_indent(self):
        if(self.current_line=="" or self.current_line.endswith("\n")):
            self.write(" "*self.indent)

    @writing_op
    def maybe_space(self):
        if(len(self.current_line)>0 and self.current_line[-1]!=" "):
            self.write(" ")

    @writing_op
    def write_comment(self,comment_content):
        if(not self.current_line):
        # self.maybe_newline()
            self.maybe_indent()
            self.write(str(comment_content,encoding="utf8"))
            self.maybe_newline()
        # comment may start a new line where there would otherwise be no line breaks; write the comments after starting a new line
        else:
            self.comments.append(str(comment_content,encoding="utf8"))
        # self.maybe_indent()
        # self.write(str(comment_content,encoding='utf8'))
        # self.maybe_newline()

    @writing_op
    def enable_write_comment(self,state):
        if(state):
            self.write_comment_immediate=True
            for com in self.comments:
                self.maybe_indent()
                self.write(com)
                self.maybe_newline()
            self.comments.clear()
        else:
            self.write_comment_immediate=False


    def check_type(self,node_type,target_type):
        #TODO: use information in node-types.json, take inline_symbols and aliases into account
        if(node_type==target_type):
            return True
        # if(target_type in self.inline_symbols or (target_type.startswith('_') and len(target_type)>1)):#对于inline_symbols，在原node上继续调用visit，后续会再进行检查？
        if(target_type in self.inline_symbols):
            return True
        # if(node_type in self.aliases):#if new name is a string?
        #     return self.check_type(self.aliases[node_type][0],target_type)
        return False

    def skip_extras(self,node,index):
        while(index[0]<len(node.children) and node.children[index[0]].type in self.extras):
            Wrapper.get_children(node,index[0])
            if(self.spy_to_py):
                node.children[index[0]]=Wrapper.construct_node(node,node.children[index[0]],node.children[index[0]].type,False,None)
            self.visit(node.children[index[0]],None,index)
            index[0]+=1

    def optional(self,node,index:list,child_type:dict):
        origin=index[0]
        states=self.save_states()
        if(self.spy_to_py):
            node_states=node.save_states()
        if(isinstance(child_type,str)):
            child_type={"type":child_type}
        try:
            self.recur_func(node,index,child_type)
        except (AssertionError,IndexError,CustomException) as e:
            index[0]=origin
            self.restore_states(states)
            if(self.spy_to_py):
                node.restore_states(node_states)

    def seq(self,node,index,child_types:list):
        for child_type in child_types:
            self.recur_func(node,index,child_type)

    def repeat(self,node,index,child_type,target=None):#target:minimun repeat times,for repeat1.
        cnt=0
        if(isinstance(child_type,str)):
            child_type={"type":child_type,"params":None}
        while True:
            origin=index[0]
            states=self.save_states()
            if(self.spy_to_py):
                node_states=node.save_states()
            try:        
                self.recur_func(node,index,child_type)
                cnt+=1
            except (AssertionError,IndexError,CustomException) as e:#index out of range & no match
                index[0]=origin
                self.restore_states(states)
                if(self.spy_to_py):
                    node.restore_states(node_states)
                if(target):
                    assert cnt>=target,"repeat1"
                break
    
    def choice(self,node,index,child_types:list,recorded_choice=None):
        origin=index[0]
        if(self.target!=-1):
            target=self.target
            self.target=-1
        else:
            target=None
        states=self.save_states()
        if(self.spy_to_py):
            node_states=node.save_states()
        if(recorded_choice):
            if(isinstance(recorded_choice,list)):
                recorded_choice=recorded_choice.pop(0)
            self.recur_func(node,index,child_types[recorded_choice])
            return recorded_choice
        for i,child_type in enumerate(child_types):
            try:        
                self.recur_func(node,index,child_type)
                if(target):
                    if(self.spy_to_py):
                        target=node.uni_idx_to_new(target)
                    self.skip_extras(node,index)
                    assert index[0]==target,"avoid partial match in choice"
            except (AssertionError,IndexError,CustomException) as e:
                index[0]=origin
                self.restore_states(states)
                if(self.spy_to_py):
                    node.restore_states(node_states)
            else:
                if(DEBUG):
                    print(child_type["type"])
                return i
        raise CustomException("No choice matched")

    @contextmanager
    def alias(self,old_type,new_type,in_string=False,is_old_func=False):
        """
        visitor of new type -> visitor of old type (once)
        in_string=True: new_type is a terminal(anonymous?)
        is_old_func=True: old_type is built-in func; use recur_func(set default params)
        new_type can not be built-in func or inline rule
        """
        defaults={}
        if(in_string):
            assert new_type not in self.aliases or self.aliases[new_type][0]==old_type,"alias conflict"
        elif(is_old_func):
            #if old_type is built-in function(e.g.seq), it will be passed as a dictionary: {"type":"seq()","params":{...}}
            defaults={"index":[0],"child_type":old_type}
            old_type="recur_func()"
        else:
            assert new_type not in self.aliases,"alias conflict"
            old_func_name="visit_"+old_type
            old_func=getattr(self,old_func_name,self.generic_visit)
            old_func_inline=getattr(old_func,'inline',False)
            new_func_name="visit_"+new_type
            new_func=getattr(self,new_func_name,self.generic_visit)
            new_func_inline=getattr(new_func,'inline',False)
            #if new_func doesn't exist, new_func_inline = False(is_inline=False in visit())
            if(old_func_inline and not new_func_inline):
                defaults["index"]=[0]

        self.aliases[new_type]=(old_type,defaults,not is_old_func)
        try:
            yield
        except Exception:
            raise
        finally:
            if(new_type in self.aliases):
                del self.aliases[new_type]



    def field(self,node,index,child_type,field_name):
        self.skip_extras(node,index)
        if(index[0]<len(node.children)):#field(optional(...))
            Wrapper.get_children(node,index[0])
            assert node.field_name_for_child(index[0])==field_name,"field name not match"
        if(isinstance(child_type,str)):#simple
            child_type={"type":child_type}
        self.recur_func(node,index,child_type)
        # if(child_type["type"]=="choice()"):
        #     self.choice(node,index,**child_type["params"])
        # else:
        #     self.child(node,index,child_type,None)

    def child(self,node,index,child_type,field_name=None):
        self.skip_extras(node,index)
        if(isinstance(child_type,dict)):
            child_type=child_type["type"]
        if(not child_type in self.zero_len_token):#externals that do not appear in parse tree
            Wrapper.get_children(node,index[0])
            self.skip_extras(node,index)
            assert self.check_type(node.children[index[0]].type,child_type),"type not match"
        if(field_name is not None):
            assert node.field_name_for_child(index[0])==field_name,"field name not match"

        information=self.get_information(node,index,child_type)

        original_ops=self.writing_operations[:]
        self.writing_operations=list()
        if(child_type in self.zero_len_token):
            if(self.spy_to_py):
                # Wrapper.zero_len_token_rules(node,index,child_type)
                Wrapper.construct_node(node,None,child_type,True,None)
            child_node=SentinelNode(node)#must be inline node -> visit SentinelNode.parent
            current_node=node
            # if(not self.delete_rules(information) and not self.replace_rules(information)):
            inline=self.visit(child_node,child_type,index)
            if(self.spy_to_py):
                Wrapper.node_exit(child_node,index[0])
        elif(node.children[index[0]].is_named or child_type in self.inline_symbols):#check inline type using function attributes
            if(self.spy_to_py):
                if(child_type in self.inline_symbols):#for inline nodes, append the child_type to node.types instead of node.children.types
                    Wrapper.construct_node(node,None,child_type,True,index[0])#insertion rules before and after inline symbols
                    wrapped_node=SentinelNode(node)
                    current_node=node
                else:
                    if(child_type in self.aliases):
                        actual_type=self.aliases[child_type][0]
                    else:
                        actual_type=child_type
                    node.children[index[0]]=Wrapper.construct_node(node,node.children[index[0]],actual_type,False,None)
                    wrapped_node=node.children[index[0]]
                    current_node=wrapped_node
            else:
                wrapped_node=node.children[index[0]]
                current_node=wrapped_node
            inline=self.visit(wrapped_node,child_type,index)
            if(not inline):
                index[0]+=1
            if(self.spy_to_py):
                Wrapper.node_exit(wrapped_node,index[0])
        else:
            self.write(node.children[index[0]].type)#write(decode(node.children[index[0]].text,'utf8')?
            current_node=node.children[index[0]]
            index[0]+=1
        new_ops=self.writing_operations
        self.writing_operations=original_ops

        self.get_next_sibling(node,index,information)
        # rules=get_rules_for_parent(self.transfer_rules,information['parent_type'])
        self.insert_before_rules(information)
        self.custom_before_rules(current_node,information)
        if(not self.delete_rules(information) and not self.replace_rules(information)):
            #if any delete rules are applied, then no replace rules will apply?
            self.writing_operations.extend(new_ops)
        self.insert_after_rules(information)
        self.custom_after_rules(current_node,information)
        

    def recur_func(self,node,index,child_type):
        if(isinstance(child_type,str)):
            child_type={"type":child_type}
        if(child_type["type"]=="optional()"):
            self.optional(node,index,**child_type["params"])
        elif(child_type["type"]=="seq()"):
            self.seq(node,index,**child_type["params"])
        elif(child_type["type"]=="sep1()"):
            self.sep1(node,index,**child_type["params"])
        elif(child_type["type"]=="commaSep1()"):
            self.commaSep1(node,index,**child_type["params"])
        elif(child_type["type"]=="repeat()"):
            self.repeat(node,index,**child_type["params"])
        elif(child_type["type"]=="choice()"):
            self.choice(node,index,**child_type["params"])
        elif(child_type["type"]=="alias()"):
            with self.alias(**child_type["params"]):
                self.recur_func(node,index,child_type["params"]["new_type"])
        elif(child_type["type"]=="field()"):
            self.field(node,index,**child_type["params"])
        else:
            self.child(node,index,child_type["type"])

    def reset(self):
        self.lines=[]
        self.indent=0
        self.current_line=""
        self.aliases={}
        self.target=-1

    #transfer_rules
    
    def get_information(self,node,index,child_type):
        parent_type=self.stack[-1]
        field_name=node.field_name_for_child(index[0])
        left=index[0]-1
        while(left>=0 and node.children[left].type in self.extras):#skip extras
            left-=1
        prev_sibling=node.children[left] if left>=0 else None
        # right=index[0] if child_type in self.zero_len_token else index[0]+1
        # while(right<len(node.children) and node.children[right].type in self.extras):
        #     right+=1
        # next_sibling=node.children[right] if right<len(node.children) else None
        if(child_type in self.aliases.keys()):
            actual_type,_,symbol_old=self.aliases[child_type]
            actual_type="$"+actual_type if symbol_old else actual_type
        else:
            actual_type=None
        if(child_type in language_config.zero_len_tokens):
            is_symbol=True
        elif(child_type in language_config.inline_symbols and node.children[index[0]].type!=child_type):#TODO:differentiate symbols and strings when calling child()
            is_symbol=True
        else:
            is_symbol=node.children[index[0]].is_named
        field_name_for_prev=node.field_name_for_child(left) if left>=0 else None
        prev_symbol=node.children[left].is_named if left>=0 else None
        return {"type":child_type,"parent_type":parent_type,"field":field_name,
                "actual_type":actual_type,
                "symbol":is_symbol,
                "prev_sibling":prev_sibling.type if prev_sibling else None,
                # "next_sibling":next_sibling.type if next_sibling else None,
                "prev_sibling_field":field_name_for_prev,
                "prev_symbol":prev_symbol,
                "prev_sibling_inline":self.prev_sibling_inline}

    def get_next_sibling(self,node,index,information):
        children_len=len(node.children)
        right=index[0]
        while(right<children_len and node.children[right].type in self.extras):
            right+=1
        next_sibling=node.children[right] if right<children_len else None
        field_name_for_next=node.field_name_for_child(right) if right<children_len else None
        next_symbol=node.children[right].is_named if right<children_len else None
        information["next_sibling"]=next_sibling.type if next_sibling else None
        information["next_sibling_field"]=field_name_for_next
        information["next_symbol"]=next_symbol
    
    def skip_rules(self,rule,child_type,next_sibling):
        def any_in_condition(keys:list,conditions):
            for key in keys:
                if(key in conditions.keys()):
                    return True
            return False
        
        if(child_type in self.zero_len_token and not any_in_condition(["type","prev_sibling_inline"],rule['condition'])
           and next_sibling):
            #zero_len_token will be recorded by prev_sibling_inline(except for custom externals)
            #zero_len_token does not appear in parse tree, if positions are determined using only next_sibling/prev_sibling, rules will be applied repeatedly
            return True
        else:
            return False

    def insert_before_rules(self,information):
        for rule in self.transfer_rules['insert_before']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                self.write(rule['content'])
                if(DEBUG):
                    print(rule)

    def insert_after_rules(self,information):
        for rule in self.transfer_rules['insert_after']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                self.write(rule['content'])
                if(DEBUG):
                    print(rule)

    def delete_rules(self,information):
        for rule in self.transfer_rules['delete']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                if(DEBUG):
                    print(rule)
                return True
        return False

    def replace_rules(self,information):
        egli_rules=list()
        for rule in self.transfer_rules['replace']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                egli_rules.append(rule)
                # self.write(rule['content'])
                # if(DEBUG):
                #     print(rule)
                # return True
        if(len(egli_rules)==0):
            return False
        elif(len(egli_rules)>1):
            apply_rule=find_specific_rule(egli_rules)
            if(not apply_rule):
                print("multiple replace rule")
                return False
        else:
            apply_rule=egli_rules[0]
        self.write(apply_rule['content'])
        if(DEBUG):
            print(apply_rule)
        return True  

    def custom_after_rules(self,current_node,information):
        for rule in self.transfer_rules['custom_after']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                custom_method=getattr(self,rule['content'])
                custom_method(current_node,**rule.get("params",{}))
                if(DEBUG):
                    print(rule)
    
    def custom_before_rules(self,current_node,information):
        for rule in self.transfer_rules['custom_before']:
            if(self.skip_rules(rule,information['type'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                custom_method=getattr(self,rule['content'])
                custom_method(current_node,**rule.get("params",{}))
                if(DEBUG):
                    print(rule)

class PythonUnparser(Unparser):
    def __init__(self,py_to_spy=False,spy_to_py=False,rule_path=None):
        super().__init__(py_to_spy,spy_to_py,rule_path)
        self.rule_path=rule_path
        self.indent=0

    def clear(self):
        super().clear()
        self.indent=0

    @writing_op
    def change_indent(self,delta):
        self.indent+=delta
        self.indent=max(self.indent,0)
        if(self.current_line.isspace()):
            self.current_line=""

    def sep1(self,node,index,child_type,separator):
        if(isinstance(child_type,str)):
            child_type={"type":child_type,"params":None}
        #add a {"type":"_space"} after {"type":separator} if the output need to be "x, y" instead of "x,y"
        # if(separator in [",",";"]):
        #     seq2_params={"child_types":[{"type":separator},{"type":"_space"},{"type":child_type['type'],"params":child_type['params']}]}
        # else:
        seq2_params={"child_types":[{"type":separator},{"type":child_type['type'],"params":child_type['params']}]}
        repeat_params={"child_type":{"type":"seq()","params":seq2_params}}
        seq1_params={"child_types":[{"type":child_type["type"],"params":child_type["params"]},{"type":"repeat()","params":repeat_params}]}
        self.seq(node,index,**seq1_params)

    def commaSep1(self,node,index,child_type):
        self.sep1(node,index,child_type,",")

    #rules
    def visit_module(self,node):
        index=[0]
        self.repeat(node,index=index,child_type={"type":"_statement"})
        return index

    @inline
    def visit__statement(self,node,index):
        self.choice(node,index=index,child_types=[{"type":"_simple_statements"},{"type":"_compound_statement"}])
        return index

    @inline
    def visit__simple_statements(self,node,index):
        self.child(node,index=index,child_type="_space")
        # self.maybe_newline()
        # self.child(node,index,"_indent")
        self.sep1(node,index=index,child_type="_simple_statement",separator=";")
        self.optional(node,index=index,child_type=";")
        self.child(node,index=index,child_type="_newline")
        # self.child(node,index,"_dedent")
        return index

    @inline
    def visit__simple_statement(self,node,index):
        """
        _simple_statement: $ => choice(
        $.future_import_statement,
        $.import_statement,
        $.import_from_statement,
        $.print_statement,
        $.assert_statement,
        $.expression_statement,
        $.return_statement,
        $.delete_statement,
        $.raise_statement,
        $.pass_statement,
        $.break_statement,
        $.continue_statement,
        $.global_statement,
        $.nonlocal_statement,
        $.exec_statement,
        $.type_alias_statement,
        ),
        """
        types=["future_import_statement","import_statement","import_from_statement",
               "print_statement","assert_statement","expression_statement","return_statement",
               "delete_statement","raise_statement","pass_statement","break_statement",
               "continue_statement","global_statement","nonlocal_statement","exec_statement",
               "type_alias_statement"]
        self.child(node,index=index,child_type="_start_line")
        self.skip_extras(node,index)
        node_type=Wrapper.get_children(node,index[0]).type
        if(node_type not in types):
            raise CustomException("No choice matched")
        choice_index=types.index(node_type)
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_index)
        return index

    def visit_import_statement(self,node):
        """
        import_statement: $ => seq(
        'import',
        $._import_list,
        ),
        """
        index=[0]
        self.child(node,index=index,child_type="import")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="_import_list")
        return index
    
    def visit_import_prefix(self,node):
        index=[0]
        self.repeat(node,index=index,child_type=".",target=1)
        return index
    
    def visit_relative_import(self,node):
        index=[0]
        self.child(node,index=index,child_type="import_prefix")
        self.optional(node,index=index,child_type="dotted_name")
        return index
    
    def visit_future_import_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="from")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="__future__")
        self.child(node,index,"_space")
        self.child(node,index=index,child_type="import")
        self.child(node,index,"_space")
        seq_params={"child_types":[{"type":"("},{"type":"_import_list"},{"type":")"}]}
        self.choice(node,index=index,child_types=[{"type":"seq()","params":seq_params},{"type":"_import_list"}])
        return index
    
    def visit_import_from_statement(self,node):
        """
            import_from_statement: $ => seq(
            'from',
            field('module_name', choice(
                $.relative_import,
                $.dotted_name,
            )),
            'import',
            choice(
                $.wildcard_import,
                $._import_list,
                seq('(', $._import_list, ')'),
            ),
            ),
        """
        index=[0]
        self.child(node,index=index,child_type="from")
        self.child(node,index,"_space")
        choice_params={"child_types":[{"type":"relative_import"},{"type":"dotted_name"}]}
        field_params={"child_type":{"type":"choice()","params":choice_params},"field_name":"module_name"}
        self.field(node,index=index,**field_params)
        self.child(node,index,"_space")
        self.child(node,index=index,child_type="import")
        self.child(node,index,"_space")
        seq_params={"child_types":[{"type":"("},{"type":"_import_list"},{"type":")"}]}
        self.choice(node,index=index,child_types=[{"type":"wildcard_import"},{"type":"seq()","params":seq_params},{"type":"_import_list"}])
        return index
        
    @inline
    def visit__import_list(self,node,index):
        """
        _import_list: $ => seq(
        commaSep1(field('name', choice(
            $.dotted_name,
            $.aliased_import,
        ))),
        optional(','),
        ),
        """
        choice_params={"child_types":[{"type":"dotted_name"},{"type":"aliased_import"}]}
        field_params={"child_type":{"type":"choice()","params":choice_params},"field_name":"name"}
        commaSep1_params={"child_type":{"type":"field()","params":field_params}}
        self.commaSep1(node,index=index,**commaSep1_params)
        self.optional(node,index=index,child_type=",")
        return index
    
    def visit_aliased_import(self,node):
        index=[0]
        self.field(node,index=index,child_type="dotted_name",field_name="name")
        self.child(node,index,"_space")
        self.child(node,index=index,child_type="as")
        self.child(node,index,"_space")
        self.field(node,index=index,child_type="identifier",field_name="alias")
        return index
    
    def visit_wildcard_import(self,node):
        index=[0]
        self.child(node,index=index,child_type="*")
        return index
    
    def visit_print_statement(self,node):
        """
            print_statement: $ => choice(
            prec(1, seq(
                'print',
                $.chevron,
                repeat(seq(',', field('argument', $.expression))),
                optional(',')),
            ),
            prec(-3, prec.dynamic(-1, seq(
                'print',
                commaSep1(field('argument', $.expression)),
                optional(','),
            ))),
            ),
        """
        index=[0]
        inner_seq_params={"child_types":[{"type":","},{"type":"field()","params":{"child_type":"expression","field_name":"argument"}}]}
        repeat_params={"child_type":{"type":"seq()","params":inner_seq_params}}
        seq1_params={"child_types":[{"type":"print"},{"type":"_space"},{"type":"chevron"},{"type":"repeat()","params":repeat_params},{"type":"optional()","params":{"child_type":","}}]}
        seq2_params={"child_types":[{"type":"print"},{"type":"_space"},{"type":"commaSep1()","params":{"child_type":{"type":"field()","params":{"child_type":"expression","field_name":"argument"}}}},{"type":"optional()","params":{"child_type":","}}]}
        self.choice(node,index=index,child_types=[{"type":"seq()","params":seq1_params},{"type":"seq()","params":seq2_params}])
        return index
    
    def visit_chevron(self,node):
        index=[0]
        self.child(node,index=index,child_type=">>")
        # self.maybe_space()
        self.child(node,index=index,child_type="expression")
        return index

    def visit_assert_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="assert")
        self.child(node,index=index,child_type="_space")
        self.commaSep1(node,index=index,child_type="expression")
        return index

    def visit_expression_statement(self,node):
        """
        expression_statement: $ => choice(
        $.expression,
        seq(commaSep1($.expression), optional(',')),
        $.assignment,
        $.augmented_assignment,
        $.yield,
        ),
        """
        index=[0]
        seq_params={"child_types":[{"type":"commaSep1()","params":{"child_type":"expression"}},{"type":"optional()","params":{"child_type":","}}]}
        self.set_target(node,len(node.children))
        self.choice(node,index=index,child_types=[{"type":"expression"},{"type":"seq()","params":seq_params},{"type":"assignment"},{"type":"augmented_assignment"},{"type":"yield"}])
        return index

    def visit_named_expression(self,node):
        index=[0]
        self.field(node,index=index,child_type="_named_expression_lhs",field_name="name")
        # self.maybe_space()
        self.child(node,index=index,child_type=":=")
        # self.maybe_space()
        self.field(node,index=index,child_type="expression",field_name="value")
        return index
    
    @inline
    def visit__named_expression_lhs(self,node,index):
        self.choice(node,index=index,child_types=[{"type":"identifier"},{"type":"keyword_identifier"}])
        return index
    
    def visit_return_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="return")
        self.child(node,index=index,child_type="_space")
        self.optional(node,index=index,child_type="_expressions")
        return index
    
    def visit_delete_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="del")
        self.child(node,index=index,child_type="_space")
        self.optional(node,index=index,child_type="_expressions")
        return index

    @inline
    def visit__expressions(self,node,index):
        self.choice(node,index=index,child_types=[{"type":"expression"},{"type":"expression_list"}])
        return index
    
    def visit_raise_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="raise")
        self.child(node,index=index,child_type="_space")
        self.optional(node,index=index,child_type="_expressions")
        field_params={"child_type":"expression","field_name":"cause"}
        seq_params={"child_types":[{"type":"_space"},{"type":"from"},{"type":"_space"},{"type":"field()","params":field_params}]}
        self.optional(node,index=index,child_type={"type":"seq()","params":seq_params})
        return index
    
    def visit_pass_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="pass")
        return index
    
    def visit_break_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="break")
        return index
    
    def visit_continue_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="continue")
        return index
    
    @inline
    def visit__compound_statement(self,node,index):
        """
        _compound_statement: $ => choice(
            $.if_statement,
            $.for_statement,
            $.while_statement,
            $.try_statement,
            $.with_statement,
            $.function_definition,
            $.class_definition,
            $.decorated_definition,
            $.match_statement,
            ),
        """
        types=["if_statement","for_statement","while_statement","try_statement",
               "with_statement","function_definition","class_definition","decorated_definition",
               "match_statement"]
        # self.maybe_spaceline()
        self.skip_extras(node,index)
        node_type=Wrapper.get_children(node,index[0]).type
        if(node_type not in types):
            raise CustomException("No choice matched")
        choice_idx=types.index(node_type)
        self.child(node,index=index,child_type="_start_line")
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index
    
    def visit_if_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="if")
        self.child(node,index=index,child_type="_space")
        self.field(node,index=index,child_type="expression",field_name="condition")
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="consequence")
        self.repeat(node,index=index,child_type={"type":"field()","params":{"child_type":"elif_clause","field_name":"alternative"}})
        self.optional(node,index=index,child_type={"type":"field()","params":{"child_type":"else_clause","field_name":"alternative"}})
        return index
    
    def visit_elif_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index=index,child_type="elif")
        self.child(node,index=index,child_type="_space")
        self.field(node,index=index,child_type="expression",field_name="condition")
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="consequence")
        return index
    
    def visit_else_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index=index,child_type="else")
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="body")
        return index
    
    def visit_match_statement(self,node):
        """
        match_statement: $ => seq(
            'match',
            commaSep1(field('subject', $.expression)),
            optional(','),
            ':',
            field('body', alias($._match_block, $.block)),
            ),
        """
        index=[0]
        self.child(node,index=index,child_type="match")
        self.child(node,index=index,child_type="_space")
        field_params={"child_type":"expression","field_name":"subject"}
        commaSep1_params={"child_type":{"type":"field()","params":field_params}}
        self.commaSep1(node,index=index,**commaSep1_params)
        self.optional(node,index=index,child_type=",")
        self.child(node,index=index,child_type=":")
        alias_params={"old_type":"_match_block","new_type":"block"}
        self.field(node,index=index,child_type={"type":"alias()","params":alias_params},field_name="body")
        return index
    
    @inline
    def visit__match_block(self,node,index):
        repeat_params={"child_type":{"type":"field()","params":{"child_type":"case_clause","field_name":"alternative"}}}
        seq_params={"child_types":[{"type":"_indent"},{"type":"repeat()","params":repeat_params},{"type":"_dedent"}]}
        self.set_target(node,len(node.children))
        self.choice(node,index=index,child_types=[{"type":"seq()","params":seq_params},{"type":"_newline"}])
        return index
    
    def visit_case_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index=index,child_type="case")
        self.child(node,index=index,child_type="_space")
        self.commaSep1(node,index=index,child_type="case_pattern")
        self.optional(node,index=index,child_type=",")
        seq_params={"child_types":[{"type":"_space"},{"type":"field()","params":{"child_type":"if_clause","field_name":"guard"}}]}
        self.optional(node,index=index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index=index,child_type=":")
        # self.maybe_newline()
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="consequence")
        return index
    
    def visit_for_statement(self,node):
        index=[0]
        self.optional(node,index=index,child_type="async")
        if(index[0]>0):
            self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="for")
        self.child(node,index=index,child_type="_space")
        self.set_target(node,self.find_children_position(node,index[0],target_type="in"))
        self.field(node,index=index,child_type="_left_hand_side",field_name="left")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="in")
        self.child(node,index=index,child_type="_space")
        self.set_target(node,self.find_children_position(node,index[0],target_type=":"))
        self.field(node,index=index,child_type="_expressions",field_name="right")
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="body")
        optional_params={"child_type":"else_clause"}
        self.field(node,index=index,child_type={"type":"optional()","params":optional_params},field_name="alternative")
        return index
    
    def visit_while_statement(self,node):
        index=[0]
        self.child(node,index=index,child_type="while")
        self.child(node,index=index,child_type="_space")
        self.field(node,index=index,child_type="expression",field_name="condition")
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="body")
        field_params={"child_type":"else_clause","field_name":"alternative"}
        self.optional(node,index=index,child_type={"type":"field()","params":field_params})
        return index
    
    def visit_try_statement(self,node):
        index=[0]
        self.child(node,index,"try")
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.field(node,index,"_suite",field_name="body")
        def get_choice_index():
            self.skip_extras(node,index)
            node_type=Wrapper.get_children(node,index[0]).type
            if(node_type=='except_clause'):
                choice_idx=0
            elif(node_type=='except_group_clause'):
                choice_idx=1
            else:
                choice_idx=2
            return choice_idx
        choice_idx=get_choice_index()
        seq1_params={"child_types":[{"type":"repeat()","params":{"child_type":"except_clause","target":1}},{"type":"optional()","params":{"child_type":"else_clause"}},{"type":"optional()","params":{"child_type":"finally_clause"}}]}
        seq2_params={"child_types":[{"type":"repeat()","params":{"child_type":"except_group_clause","target":1}},{"type":"optional()","params":{"child_type":"else_clause"}},{"type":"optional()","params":{"child_type":"finally_clause"}}]}
        self.choice(node,index,child_types=[{"type":"seq()","params":seq1_params},{"type":"seq()","params":seq2_params},{"type":"finally_clause"}],recorded_choice=choice_idx)
        return index
    
    def visit_except_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index,"except")
        seq_params={"child_types":[{"type":"_space"},{"type":"choice()","params":{"child_types":[{"type":"as"},{"type":","}]}},{"type":"_space"},{"type":"expression"}]}
        optional_params={"child_type":{"type":"seq()","params":seq_params}}
        self.optional(node,index,child_type={"type":"seq()","params":{"child_types":[{"type":"_space"},{"type":"expression"},{"type":"optional()","params":optional_params}]}})
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.child(node,index,"_suite")
        return index

    def visit_except_group_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index,"except*")
        self.child(node,index=index,child_type="_space")
        seq_params={"child_types":[{"type":"_space"},{"type":"as"},{"type":"_space"},{"type":"expression"}]}
        self.seq(node,index,child_types=[{"type":"expression"},{"type":"optional()","params":{"child_type":{"type":"seq()","params":seq_params}}}])
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.child(node,index,"_suite")
        return index
    
    def visit_finally_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index,"finally")
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.child(node,index,"_suite")
        return index
    
    def visit_with_statement(self,node):
        index=[0]
        self.optional(node,index,"async")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"with")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"with_clause")
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.field(node,index,"_suite",field_name="body")
        return index

    def visit_with_clause(self,node):
        index=[0]
        seq1_params={"child_types":[{"type":"commaSep1()","params":{"child_type":"with_item"}},{"type":"optional()","params":{"child_type":","}}]}
        seq2_params={"child_types":[{"type":"("},{"type":"commaSep1()","params":{"child_type":"with_item"}},{"type":"optional()","params":{"child_type":","}},{"type":")"}]}
        self.choice(node,index,child_types=[{"type":"seq()","params":seq1_params},{"type":"seq()","params":seq2_params}])
        return index
    
    def visit_with_item(self,node):
        index=[0]
        self.field(node,index,"expression",field_name="value")
        return index

    def visit_function_definition(self,node):
        """
        function_definition: $ => seq(
      optional('async'),
      'def',
      field('name', $.identifier),
      field('type_parameters', optional($.type_parameter)),
      field('parameters', $.parameters),
      optional(
        seq(
          '->',
          field('return_type', $.type),
        ),
      ),
      ':',
      field('body', $._suite),
    ),
        """
        index=[0]
        self.optional(node,index=index,child_type={"type":"async"})
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="def")
        self.child(node,index=index,child_type="_space")
        self.field(node,index=index,child_type="identifier",field_name="name")
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"type_parameter","field_name":"type_parameters"}})
        self.field(node,index,"parameters",field_name="parameters")
        seq_params={
            "child_types":[{"type":"->"},
                           {"type":"field()","params":{"child_type":"type","field_name":"return_type"}}]
        }
        self.optional(node,index=index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index=index,child_type=":")
        # self.enable_write_comment(False)
        self.field(node,index=index,child_type="_suite",field_name="body")
        return index

    def visit_parameters(self,node):
        """
        parameters: $ => seq(
        '(',
        optional($._parameters),
        ')',
        ),
        """
        index=[0]
        self.child(node,index=index,child_type="(")
        self.optional(node,index=index,child_type={"type":"_parameters"})
        self.child(node,index=index,child_type=")")
        return index
    
    def visit_lambda_parameters(self,node):
        index=[0]
        self.child(node,index=index,child_type="_parameters")
        return index
    
    def visit_list_splat(self,node):
        index=[0]
        self.child(node,index,"*")
        self.child(node,index,"expression")
        return index
    
    def visit_dictionary_splat(self,node):
        index=[0]
        self.child(node,index,"**")
        self.child(node,index,"expression")
        return index
    
    def visit_global_statement(self,node):
        index=[0]
        self.child(node,index,"global")
        self.child(node,index=index,child_type="_space")
        self.commaSep1(node,index,"identifier")
        return index
    
    def visit_nonlocal_statement(self,node):
        index=[0]
        self.child(node,index,"nonlocal")
        self.child(node,index=index,child_type="_space")
        self.commaSep1(node,index,"identifier")
        return index
    
    def visit_exec_statement(self,node):
        index=[0]
        self.child(node,index,"exec")
        self.child(node,index=index,child_type="_space")
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"string"},{"type":"identifier"}]}},field_name="code")
        seq_params={"child_types":[{"type":"_space"},{"type":"in"},{"type":"_space"},{"type":"commaSep1()","params":{"child_type":"expression"}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        return index
    
    def visit_type_alias_statement(self,node):
        index=[0]
        self.child(node,index,"type")#not named_children
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"type")
        # self.maybe_space()
        self.child(node,index,"=")
        # self.maybe_space()
        self.child(node,index,"type")
        return index
    
    def visit_class_definition(self,node):
        index=[0]
        self.child(node,index,"class")
        self.child(node,index=index,child_type="_space")
        self.field(node,index,"identifier",field_name="name")
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"type_parameter","field_name":"type_parameters"}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"argument_list","field_name":"superclasses"}})
        self.child(node,index,":")
        # self.enable_write_comment(False)
        self.field(node,index,"_suite",field_name="body")
        return index
    
    def visit_type_parameter(self,node):
        index=[0]
        self.child(node,index,"[")
        self.commaSep1(node,index,"type")
        self.optional(node,index,",")
        self.child(node,index,"]")
        return index
    
    def visit_parenthesized_list_splat(self,node):
        index=[0]
        self.child(node,index,"(")
        alias_params={"old_type":"parenthesized_list_splat","new_type":"parenthesized_expression"}
        self.choice(node,index,child_types=[{"type":"alias()","params":alias_params},{"type":"list_splat"}])
        self.child(node,index,")")
        return index
    
    def visit_argument_list(self,node):
        index=[0]
        self.child(node,index,"(")
        alias_params={"old_type":"parenthesized_list_splat","new_type":"parenthesized_expression"}
        choice_params={"child_types":[{"type":"expression"},{"type":"list_splat"},{"type":"dictionary_splat"},{"type":"alias()","params":alias_params},{"type":"keyword_argument"}]}
        self.optional(node,index,child_type={"type":"commaSep1()","params":{"child_type":{"type":"choice()","params":choice_params}}})
        self.optional(node,index,",")
        self.child(node,index,")")
        return index
    
    def visit_decorated_definition(self,node):
        index=[0]
        # seq_params={"child_types":[{"type":"_start_line"},{"type":"decorator"}]}
        self.repeat(node,index,"decorator",target=1)
        # self.repeat(node,index,child_type={"type":"seq()","params":seq_params},target=1)
        self.child(node,index=index,child_type="_start_line")
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"class_definition"},{"type":"function_definition"}]}},field_name="definition")
        return index
    
    def visit_decorator(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.child(node,index,"@")
        self.child(node,index,"expression")
        self.child(node,index,"_newline")
        return index
    
    @inline
    def visit__suite(self,node,index):
        """
        _suite: $ => choice(
        alias($._simple_statements, $.block),
        seq($._indent, $.block),
        alias($._newline, $.block),
            ),
        """
        self.child(node,index=index,child_type="_start_line")
        alias1_params={"old_type":"_simple_statements","new_type":"block"}
        seq1_params={"child_types":[{"type":"_indent"},{"type":"block"}]}
        alias2_params={"old_type":"_newline","new_type":"block"}
        self.choice(node,index=index,child_types=[{"type":"seq()","params":seq1_params},{"type":"alias()","params":alias1_params},{"type":"alias()","params":alias2_params}])
        return index

    def visit_block(self,node):
        index=[0]
        # self.enable_write_comment(True)
        self.repeat(node,index=index,child_type={"type":"_statement"})
        self.child(node,index=index,child_type="_dedent")
        return index
    
    def visit_expression_list(self,node):
        index=[0]
        self.child(node,index=index,child_type="expression")
        inner_seq_params={"child_types":[{"type":","},{"type":"expression"}]}
        repeat_params={"child_type":{"type":"seq()","params":inner_seq_params},"target":1}
        outer_seq_params={"child_types":[{"type":"repeat()","params":repeat_params},{"type":"optional()","params":{"child_type":","}}]}
        self.set_target(node,len(node.children))
        self.choice(node,index=index,child_types=[{"type":","},{"type":"seq()","params":outer_seq_params}])
        return index
    
    def visit_dotted_name(self,node):
        index=[0]
        self.sep1(node,index=index,child_type="identifier",separator=".")
        return index
    
    def visit_case_pattern(self,node):
        index=[0]
        alias_params={"old_type":"_as_pattern","new_type":"as_pattern"}
        self.choice(node,index=index,child_types=[{"type":"alias()","params":alias_params},
                                                  {"type":"keyword_pattern"},
                                                  {"type":"_simple_pattern"}])
        return index

    @inline
    def visit__simple_pattern(self,node,index):
        simple_types=["class_pattern","splat_pattern","union_pattern",
                      "dict_pattern","string","concatenated_string","true","false","none",
                      "complex_pattern","dotted_name","_"]#'_' should not be a named children
        #alias types and seq
        alias_params1={"old_type":"_list_pattern","new_type":"list_pattern"}
        alias_params2={"old_type":"_tuple_pattern","new_type":"tuple_pattern"}
        seq_params={"child_types":[{"type":"optional()","params":{"child_type":"-"}},{"type":"choice()","params":{"child_types":[{"type":"integer"},{"type":"float"}]}}]}
        def get_choice_index():
            self.skip_extras(node,index)
            node_type=Wrapper.get_children(node,index[0]).type
            if(node_type in simple_types):
                choice_idx=simple_types.index(node_type)
            elif(node_type=="list_pattern"):
                choice_idx=-3
            elif(node_type=='tuple_pattern'):
                choice_idx=-2
            else:
                choice_idx=-1
            return choice_idx
        choice_idx=get_choice_index()
        self.choice(node,index=index,child_types=[{"type":t} for t in simple_types]+[{"type":"alias()","params":alias_params1},{"type":"alias()","params":alias_params2},{"type":"seq()","params":seq_params}],recorded_choice=choice_idx)
        return index
    
    @inline
    def visit__as_pattern(self,node,index):
        self.child(node,index=index,child_type="case_pattern")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="as")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="identifier")
        return index
    
    def visit_union_pattern(self,node):
        index=[0]
        seq_params={"child_types":[{"type":"|"},{"type":"_simple_pattern"}]}
        self.child(node,index,"_simple_pattern")
        self.repeat(node,index,child_type={"type":"seq()","params":seq_params},target=1)
        return index
    
    @inline
    def visit__list_pattern(self,node,index):
        self.child(node,index,"[")
        seq_params={"child_types":[{"type":"commaSep1()","params":{"child_type":"case_pattern"}},{"type":"optional()","params":{"child_type":","}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index,"]")
        return index
    
    @inline
    def visit__tuple_pattern(self,node,index):
        self.child(node,index,"(")
        seq_params={"child_types":[{"type":"commaSep1()","params":{"child_type":"case_pattern"}},{"type":"optional()","params":{"child_type":","}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index,")")
        return index
    
    def visit_dict_pattern(self,node):
        index=[0]
        self.child(node,index,"{")
        choice_params={"child_types":[{"type":"_key_value_pattern"},{"type":"splat_pattern"}]}
        seq_params={"child_types":[{"type":"commaSep1()","params":{"child_type":{"type":"choice()","params":choice_params}}},{"type":"optional()","params":{"child_type":","}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index,"}")
        return index
    
    @inline
    def visit__key_value_pattern(self,node,index):
        self.field(node,index,"_simple_pattern",field_name="key")
        self.child(node,index,":")
        # self.maybe_space()
        self.field(node,index,"case_pattern",field_name="value")
        return index
    
    def visit_keyword_pattern(self,node):
        index=[0]
        self.child(node,index,"identifier")
        self.child(node,index,"=")
        self.child(node,index,"_simple_pattern")
        return index
    
    def visit_splat_pattern(self,node):
        index=[0]
        self.choice(node,index,child_types=[{"type":"*"},{"type":"**"}])
        self.choice(node,index,child_types=[{"type":"identifier"},{"type":"_"}])
        return index
    
    def visit_class_pattern(self,node):
        index=[0]
        self.child(node,index,"dotted_name")
        self.child(node,index,"(")
        seq_params={"child_types":[{"type":"commaSep1()","params":{"child_type":"case_pattern"}},{"type":"optional()","params":{"child_type":","}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        self.child(node,index,")")
        return index
    
    def visit_complex_pattern(self,node):
        index=[0]
        self.optional(node,index,"-")
        self.choice(node,index,child_types=[{"type":"integer"},{"type":"float"}])
        # self.maybe_space()
        self.choice(node,index,child_types=[{"type":"+"},{"type":"-"}])
        # self.maybe_space()
        self.choice(node,index,child_types=[{"type":"integer"},{"type":"float"}])
        return index

    @inline
    def visit__parameters(self,node,index):
        self.commaSep1(node,index,"parameter")
        self.optional(node,index,",")
        return index
    
    @inline
    def visit__patterns(self,node,index):
        self.commaSep1(node,index,"pattern")
        self.optional(node,index,",")
        return index
    
    @inline
    def visit_parameter(self,node,index):
        types=["identifier","typed_parameter","default_parameter","typed_default_parameter",
               "list_splat_pattern","tuple_pattern","keyword_separator","positional_separator",
               "dictionary_splat_pattern"]
        self.skip_extras(node,index)
        node_type=Wrapper.get_children(node,index[0]).type
        if(node_type not in types):
            raise CustomException("No choice matched")
        choice_idx=types.index(node_type)
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index
    
    @inline
    def visit_pattern(self,node,index):
        types=["identifier","keyword_identifier","subscript","attribute","list_splat_pattern","tuple_pattern","list_pattern"]
        self.skip_extras(node,index)
        node_type=Wrapper.get_children(node,index[0]).type
        if(node_type not in types):
            raise CustomException("No choice matched")
        choice_idx=types.index(node_type)
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index
    
    def visit_tuple_pattern(self,node):
        index=[0]
        self.child(node,index,"(")
        self.optional(node,index,"_patterns")
        self.child(node,index,")")
        return index
    
    def visit_list_pattern(self,node):
        index=[0]
        self.child(node,index,"[")
        self.optional(node,index,"_patterns")
        self.child(node,index,"]")
        return index
    
    def visit_default_parameter(self,node):
        index=[0]
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"identifier"},{"type":"tuple_pattern"}]}},field_name="name")
        # self.maybe_space()
        self.child(node,index,"=")
        # self.maybe_space()
        self.field(node,index,child_type="expression",field_name="value")
        return index
    
    def visit_typed_default_parameter(self,node):
        index=[0]
        self.field(node,index,"identifier",field_name="name")
        self.child(node,index,":")
        # self.maybe_space()
        self.field(node,index,"type",field_name="type")
        # self.maybe_space()
        self.child(node,index,"=")
        # self.maybe_space()
        self.field(node,index,"expression",field_name="value")
        return index
    
    def visit_list_splat_pattern(self,node):
        index=[0]
        self.child(node,index,"*")
        self.choice(node,index,child_types=[{"type":"identifier"},{"type":"keyword_identifier"},{"type":"subscript"},{"type":"attribute"}])
        return index

    def visit_dictionary_splat_pattern(self,node):
        index=[0]
        self.child(node,index,"**")
        self.choice(node,index,child_types=[{"type":"identifier"},{"type":"keyword_identifier"},{"type":"subscript"},{"type":"attribute"}])
        return index

    def visit_as_pattern(self,node):
        index=[0]
        self.child(node,index=index,child_type="expression")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="as")
        self.child(node,index=index,child_type="_space")
        alias_params={"old_type":"expression","new_type":"as_pattern_target"}
        self.field(node,index=index,child_type={"type":"alias()","params":alias_params},field_name="alias")
        return index

    @inline
    def visit__expression_within_for_in_clause(self,node,index):
        self.choice(node,index,child_types=[{"type":"expression"},{"type":"alias()","params":{"old_name":"lambda_within_for_in_clause","new_name":"lambda"}}])
        return index

    @inline
    def visit_expression(self,node,index):
        # index=[0]
        types=["comparison_operator","not_operator","boolean_operator","lambda","primary_expression",
               "conditional_expression","named_expression","as_pattern"]
        self.skip_extras(node,index)
        node_type=Wrapper.get_children(node,index[0]).type
        if(node_type not in types):
            choice_idx=4
        else:
            choice_idx=types.index(node_type)
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index
    
    @inline
    def visit_primary_expression(self,node,index):
        """
        primary_expression: $ => choice(
        $.await,
        $.binary_operator,
        $.identifier,
        $.keyword_identifier,
        $.string,
        $.concatenated_string,
        $.integer,
        $.float,
        $.true,
        $.false,
        $.none,
        $.unary_operator,
        $.attribute,
        $.subscript,
        $.call,
        $.list,
        $.list_comprehension,
        $.dictionary,
        $.dictionary_comprehension,
        $.set,
        $.set_comprehension,
        $.tuple,
        $.parenthesized_expression,
        $.generator_expression,
        $.ellipsis,
        alias($.list_splat_pattern, $.list_splat),
        ),
        """
        # index=[0]
        types=["await","binary_operator","identifier","keyword_identifier","string","concatenated_string","integer",
               "float","true","false","none","unary_operator","attribute","subscript","call","list","list_comprehension",
               "dictionary","dictionary_comprehension","set","set_comprehension","tuple","parenthesized_expression",
               "generator_expression","ellipsis"]
        alias_params={"old_type":"list_splat_pattern","new_type":"list_splat"}
        def get_choice_index():
            self.skip_extras(node,index)
            node_type=Wrapper.get_children(node,index[0]).type
            if(node_type in types):
                choice_idx=types.index(node_type)
            elif(node_type=='list_splat'):
                choice_idx=-1
            else:
                raise CustomException("No choice matched")
            return choice_idx
        choice_idx=get_choice_index()
        self.choice(node,index=index,child_types=[{"type":t} for t in types]+[{"type":"alias()","params":alias_params}],recorded_choice=choice_idx)
        return index
    
    def get_operator_type(self,node):
        i=0
        while i<len(node.children):
            if(node.field_name_for_child(i)=="operator"):
                break
            i+=1
        op=Wrapper.get_children(node,i)
        return op.type

    def visit_not_operator(self,node):
        index=[0]
        self.child(node,index=index,child_type="not")
        self.child(node,index=index,child_type="_space")
        self.field(node,index=index,child_type="expression",field_name="argument")
        return index
    
    def visit_boolean_operator(self,node):
        """
        boolean_operator: $ => choice(
        seq($.expression, 'and', $.expression),
        seq($.expression, 'or', $.expression),
        ),
        """
        index=[0]
        seq1_params={"child_types":[{"type":"field()","params":{"child_type":"expression","field_name":"left"}},{"type":"_space"},{"type":"and"},{"type":"_space"},{"type":"field()","params":{"child_type":"expression","field_name":"right"}}]}
        seq2_params={"child_types":[{"type":"field()","params":{"child_type":"expression","field_name":"left"}},{"type":"_space"},{"type":"or"},{"type":"_space"},{"type":"field()","params":{"child_type":"expression","field_name":"right"}}]}
        def get_choice_index():
            node_type=self.get_operator_type(node)
            choice_idx=0 if node_type=='and' else 1
            return choice_idx
        choice_idx=get_choice_index()
        self.choice(node,index=index,child_types=[{"type":"seq()","params":seq1_params},{"type":"seq()","params":seq2_params}],recorded_choice=choice_idx)
        return index
    
    def visit_binary_operator(self,node):
        """
        const table = [
        [prec.left, '+', PREC.plus],
        [prec.left, '-', PREC.plus],
        [prec.left, '*', PREC.times],
        [prec.left, '@', PREC.times],
        [prec.left, '/', PREC.times],
        [prec.left, '%', PREC.times],
        [prec.left, '//', PREC.times],
        [prec.right, '**', PREC.power],
        [prec.left, '|', PREC.bitwise_or],
        [prec.left, '&', PREC.bitwise_and],
        [prec.left, '^', PREC.xor],
        [prec.left, '<<', PREC.shift],
        [prec.left, '>>', PREC.shift],
      ];
        """
        index=[0]
        operator=['+','-','*','@','/','%','//','**','|','&','^','<<','>>']
        field_left_params={"child_type":"primary_expression","field_name":"left"}
        field_right_params={"child_type":"primary_expression","field_name":"right"}
        choice_child_types=[{"type":"seq()","params":{"child_types":[{"type":"field()","params":field_left_params},{"type":operator[i]},{"type":"field()","params":field_right_params}]}} for i in range(len(operator))]
        def get_choice_index():
            # assert node.field_name_for_child(1)=='operator'
            idx=operator.index(self.get_operator_type(node))
            return idx
        # record_node=node.origin_node if self.spy_to_py else node
        # if(record_node in self.recorded_index):
        #     record=self.recorded_index[record_node].get("binary_operator",None)
        # else:
        #     record=None
        choice_idx=get_choice_index()
        choosed_index=self.choice(node,index=index,child_types=choice_child_types,recorded_choice=choice_idx)
        # self.recorded_index[record_node]={"binary_operator":choosed_index}
        return index
    
    def visit_unary_operator(self,node):
        index=[0]
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"+"},{"type":"-"},{"type":"~"}]}},field_name="operator")
        self.field(node,index,"primary_expression",field_name="argument")
        return index
    
    @inline
    def visit__not_in(self,node,index):#not used
        pass

    @inline
    def visit__is_not(self,node,index):
        pass
    
    def visit_comparison_operator(self,node):
        index=[0]
        self.child(node,index,"primary_expression")
        operators=['<','<=','==','!=','>=','>','<>','in','is']
        def get_choice_idx():
            operator_nodes=node.children_by_field_name("operators")
            choice_idxes=list()
            for op in operator_nodes:
                node_type=op.type
                if(node_type in operators):
                    choice_idx=operators.index(node_type)
                elif(node_type=='not in'):
                    choice_idx=-2
                else:
                    choice_idx=-1
                choice_idxes.append(choice_idx)
            return choice_idxes
        choice_idx=get_choice_idx()
        choice_params={"child_types":[{"type":t} for t in operators]+[{"type":"alias()","params":{"old_type":"_not_in","new_type":"not in","in_string":True}},{"type":"alias()","params":{"old_type":"_is_not","new_type":"is not","in_string":True}}],"recorded_choice":choice_idx}
        field_params={"child_type":{"type":"choice()","params":choice_params},"field_name":"operators"}
        seq_params={"child_types":[{"type":"_space"},{"type":"field()","params":field_params},{"type":"_space"},{"type":"primary_expression"}]}
        self.repeat(node,index,child_type={"type":"seq()","params":seq_params},target=1)
        return index
    
    def visit_lambda(self,node):
        index=[0]
        self.child(node,index,"lambda")
        seq_params={"child_types":[{"type":"_space"},{"type":"field()","params":{"child_type":"lambda_parameters","field_name":"parameters"}}]}
        self.optional(node,index,child_type={"type":"seq()","params":seq_params})
        # self.field(node,index,child_type={"type":"optional()","params":{"child_type":"lambda_parameters"}},field_name="parameters")
        self.child(node,index,":")
        # self.maybe_space()
        self.field(node,index,"expression",field_name="body")
        return index

    def visit_lambda_within_for_in_clause(self,node):
        index=[0]
        self.child(node,index,"lambda")
        self.child(node,index=index,child_type="_space")
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"lambda_parameters","field_name":"parameters"}})
        # self.field(node,index,child_type={"type":"optional()","params":{"child_type":"lambda_parameters"}},field_name="parameters")
        self.child(node,index,":")
        self.field(node,index,"_expression_within_for_in_clause",field_name="body")
        return index
    
    def visit_assignment(self,node):
        index=[0]
        self.field(node,index,"_left_hand_side",field_name="left")
        seq1_params={"child_types":[{"type":"="},{"type":"field()","params":{"child_type":"_right_hand_side","field_name":"right"}}]}
        seq2_params={"child_types":[{"type":":"},{"type":"field()","params":{"child_type":"type","field_name":"type"}}]}
        seq3_params={"child_types":[{"type":":"},{"type":"field()","params":{"child_type":"type","field_name":"type"}},{"type":"="},{"type":"field()","params":{"child_type":"_right_hand_side","field_name":"right"}}]}
        self.set_target(node,len(node.children))
        self.choice(node,index,child_types=[{"type":"seq()","params":seq1_params},{"type":"seq()","params":seq2_params},{"type":"seq()","params":seq3_params}])
        return index
    
    def visit_augmented_assignment(self,node):
        index=[0]
        self.field(node,index,"_left_hand_side",field_name="left")
        operators=['+=', '-=', '*=', '/=', '@=', '//=', '%=', '**=',
        '>>=', '<<=', '&=', '^=', '|=']
        # self.maybe_space()
        def get_choice_idx():
            node_type=self.get_operator_type(node)
            if(node_type in operators):
                choice_idx=operators.index(node_type)
            else:
                raise CustomException("No choice matched")
            return choice_idx
        choice_idx=get_choice_idx()
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":t} for t in operators],"recorded_choice":choice_idx}},field_name="operator")
        # self.maybe_space()
        self.field(node,index,"_right_hand_side",field_name="right")
        return index
    
    @inline
    def visit__left_hand_side(self,node,index):
        self.choice(node,index=index,child_types=[{"type":"pattern"},{"type":"pattern_list"}])
        return index
    
    def visit_pattern_list(self,node):
        index=[0]
        self.child(node,index,child_type="pattern")
        repeat_params={"child_type":{"type":"seq()","params":{"child_types":[{"type":","},{"type":"pattern"}]}},"target":1}
        seq_params={"child_types":[{"type":"repeat()","params":repeat_params},{"type":"optional()","params":{"child_type":","}}]}
        self.set_target(node,len(node.children))
        self.choice(node,index=index,child_types=[{"type":","},{"type":"seq()","params":seq_params}])
        return index
    
    @inline
    def visit__right_hand_side(self,node,index):
        types=["expression","expression_list","assignment","augmented_assignment","pattern_list","yield"]
        def get_choice_index():
            self.skip_extras(node,index)
            node_type=Wrapper.get_children(node,index[0]).type
            if(node_type in types):
                choice_idx=types.index(node_type)
            else:
                choice_idx=0
            return choice_idx
        choice_idx=get_choice_index()
        self.choice(node,index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index
    
    def visit_yield(self,node):
        index=[0]
        self.child(node,index,"yield")
        self.child(node,index=index,child_type="_space")
        seq_params={"child_types":[{"type":"from"},{"type":"_space"},{"type":"expression"}]}
        self.choice(node,index,child_types=[{"type":"seq()","params":seq_params},{"type":"optional()","params":{"child_type":"_expressions"}}])
        return index
    
    def visit_attribute(self,node):
        index=[0]
        self.field(node,index,"primary_expression",field_name="object")
        self.child(node,index,".")
        self.field(node,index,"identifier",field_name="attribute")
        return index

    def visit_subscript(self,node):
        index=[0]
        self.field(node,index=index,child_type="primary_expression",field_name="value")
        self.child(node,index=index,child_type="[")
        choice_params={"child_types":[{"type":"expression"},{"type":"slice"}]}
        field_params={"child_type":{"type":"choice()","params":choice_params},"field_name":"subscript"}
        self.commaSep1(node,index=index,**{"child_type":{"type":"field()","params":field_params}})
        self.optional(node,index=index,child_type=",")
        self.child(node,index=index,child_type="]")
        return index
    
    def visit_slice(self,node):
        index=[0]
        self.optional(node,index=index,child_type="expression")
        self.child(node,index=index,child_type=":")
        self.optional(node,index=index,child_type="expression")
        optional_params={"child_type":{"type":"expression"}}
        seq_params={"child_types":[{"type":":"},{"type":"optional()","params":optional_params}]}
        self.optional(node,index=index,child_type={"type":"seq()","params":seq_params})
        return index
    
    def visit_ellipsis(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        # self.write("...")
        self.child(node,index,"_node_content")
        return index
    
    def visit_call(self,node):
        index=[0]
        self.field(node,index,"primary_expression",field_name="function")
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"generator_expression"},{"type":"argument_list"}]}},field_name="arguments")
        return index
    
    def visit_typed_parameter(self,node):
        index=[0]
        self.choice(node,index,child_types=[{"type":"identifier"},{"type":"list_splat_pattern"},{"type":"dictionary_splat_pattern"}])
        self.child(node,index,":")
        # self.maybe_space()
        self.field(node,index,"type",field_name="type")
        return index
    
    def visit_type(self,node):
        index=[0]
        types=["expression","splat_type","generic_type","union_type","constrained_type","member_type"]
        def get_choice_index():
            self.skip_extras(node,index)
            node_type=Wrapper.get_children(node,index[0]).type
            if(node_type in types):
                choice_idx=types.index(node_type)
            else:
                choice_idx=0
            return choice_idx
        choice_idx=get_choice_index()
        self.choice(node,index=index,child_types=[{"type":t} for t in types],recorded_choice=choice_idx)
        return index

    def visit_splat_type(self,node):
        index=[0]
        self.choice(node,index,child_types=[{"type":"*"},{"type":"**"}])
        self.child(node,index,"identifier")
        return index
    
    def visit_generic_type(self,node):
        index=[0]
        self.child(node,index,"identifier")
        self.child(node,index,"type_parameter")
        return index
    
    def visit_union_type(self,node):
        index=[0]
        self.child(node,index,"type")
        self.child(node,index,"|")
        self.child(node,index,"type")
        return index
    
    def visit_constrained_type(self,node):
        index=[0]
        self.child(node,index,"type")
        self.child(node,index,":")
        # self.maybe_space()
        self.child(node,index,"type")
        return index
    
    def visit_member_type(self,node):
        index=[0]
        self.child(node,index,"type")
        self.child(node,index,".")
        self.child(node,index,"identifier")
        return index
    
    def visit_keyword_argument(self,node):
        index=[0]
        self.field(node,index,child_type={"type":"choice()","params":{"child_types":[{"type":"identifier"},{"type":"keyword_identifier"}]}},field_name="name")
        self.child(node,index,"=")
        self.field(node,index,"expression",field_name="value")
        return index
    
    def visit_list(self,node):
        index=[0]
        self.child(node,index,"[")
        self.optional(node,index,"_collection_elements")
        self.child(node,index,"]")
        return index
    
    def visit_set(self,node):
        index=[0]
        self.child(node,index,"{")
        self.child(node,index,"_collection_elements")
        self.child(node,index,"}")
        return index

    def visit_tuple(self,node):
        index=[0]
        self.child(node,index,"(")
        self.optional(node,index,"_collection_elements")
        self.child(node,index,")")
        return index
    
    def visit_dictionary(self,node):
        index=[0]
        self.child(node,index,"{")
        commasep1_params={"child_type":{"type":"choice()","params":{"child_types":[{"type":"pair"},{"type":"dictionary_splat"}]}}}
        self.optional(node,index,child_type={"type":"commaSep1()","params":commasep1_params})
        self.optional(node,index,",")
        self.child(node,index,"}")
        return index
    
    def visit_pair(self,node):
        index=[0]
        self.field(node,index,"expression",field_name="key")
        self.child(node,index,":")
        # self.maybe_space()
        self.field(node,index,"expression",field_name="value")
        return index
    
    def visit_list_comprehension(self,node):
        index=[0]
        self.child(node,index,"[")
        self.field(node,index,"expression",field_name="body")
        self.child(node,index,"_comprehension_clauses")
        self.child(node,index,"]")
        return index
    
    def visit_dictionary_comprehension(self,node):
        index=[0]
        self.child(node,index,"{")
        self.field(node,index,"pair",field_name="body")
        self.child(node,index,"_comprehension_clauses")
        self.child(node,index,"}")
        return index
    
    def visit_set_comprehension(self,node):
        index=[0]
        self.child(node,index,"{")
        self.field(node,index,"expression",field_name="body")
        self.child(node,index,"_comprehension_clauses")
        self.child(node,index,"}")
        return index
    
    def visit_generator_expression(self,node):
        index=[0]
        self.child(node,index,"(")
        self.field(node,index,"expression",field_name="body")
        self.child(node,index,"_comprehension_clauses")
        self.child(node,index,")")
        return index
    
    @inline
    def visit__comprehension_clauses(self,node,index):
        self.child(node,index,"for_in_clause")
        choice_params={"child_types":[{"type":"for_in_clause"},{"type":"if_clause"}]}
        self.repeat(node,index,child_type={"type":"seq()","params":{"child_types":[{"type":"_space"},{"type":"choice()","params":choice_params}]}})
        return index
    
    
    def visit_parenthesized_expression(self,node):
        index=[0]
        self.child(node,index=index,child_type="(")
        self.choice(node,index=index,child_types=[{"type":"expression"},{"type":"yield"}])
        self.child(node,index=index,child_type=")")
        return index
    
    @inline
    def visit__collection_elements(self,node,index):
        types=["expression","yield","list_splat","parenthesized_list_splat"]
        choice_params={"child_types":[{"type":t} for t in types]}
        self.commaSep1(node,index,child_type={"type":"choice()","params":choice_params})
        self.optional(node,index,",")
        return index
    
    def visit_for_in_clause(self,node):
        index=[0]
        self.child(node,index=index,child_type="_space")
        self.optional(node,index,child_type="async")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"for")
        self.child(node,index=index,child_type="_space")
        self.field(node,index,"_left_hand_side",field_name="left")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"in")
        self.child(node,index=index,child_type="_space")
        self.field(node,index,child_type={"type":"commaSep1()","params":{"child_type":"_expression_within_for_in_clause"}},field_name="right")
        self.optional(node,index,",")
        return index
    
    def visit_if_clause(self,node):
        index=[0]
        # self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="if")
        self.child(node,index=index,child_type="_space")
        self.child(node,index=index,child_type="expression")
        return index

    def visit_conditional_expression(self,node):
        index=[0]
        self.child(node,index,"expression")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"if")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"expression")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"else")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"expression")
        return index
    
    def visit_concatenated_string(self,node):
        index=[0]
        self.child(node,index,"string")#space between strings?
        # self.maybe_space()
        seq_params={"child_types":[{"type":"_space"},{"type":"string"}]}
        # self.repeat(node,index,"string",target=1)
        self.repeat(node,index,child_type={"type":"seq()","params":seq_params},target=1)
        return index
    
    def visit_string(self,node):
        index=[0]
        self.child(node,index=index,child_type="string_start")
        choice_params={"child_types":[{"type":"interpolation"},{"type":"string_content"}]}
        self.repeat(node,index=index,child_type={"type":"choice()","params":choice_params})
        self.child(node,index=index,child_type="string_end")
        return index

    def visit_string_content(self,node):
        # index=[0]
        # choice_params={"child_types":[{"type":"escape_interpolation"},{"type":"escape_sequence"},{"type":"_not_escape_sequence"},{"type":"_string_content"}]}
        # self.repeat(node,index=index,child_type={"type":"choice()","params":choice_params},target=1)
        # return index
        self.write(str(node.text,encoding="utf8"))
        return [len(node.children)]
    
    def visit_interpolation(self,node):
        index=[0]
        self.child(node,index=index,child_type="{")
        self.maybe_space()
        self.field(node,index=index,child_type="_f_expression",field_name="expression")
        self.optional(node,index=index,child_type="=")
        self.optional(node,index=index,child_type={"type":"field()","params":{"child_type":"type_conversion","field_name":"type_conversion"}})
        self.optional(node,index=index,child_type={"type":"field()","params":{"child_type":"format_specifier","field_name":"format_specifier"}})
        self.child(node,index,"_space")
        self.child(node,index=index,child_type="}")
        return index
        # self.write(str(node.text,encoding="utf8"))
        # return [len(node.children)]
    
    @inline
    def visit__f_expression(self,node,index):
        self.choice(node,index=index,child_types=[{"type":"expression"},{"type":"expression_list"},{"type":"pattern_list"},{"type":"yield"}])
        return index
    
    def visit_escape_sequence(self,node):#no children
        self.write(str(node.text,encoding="utf8"))
        return [0]
    
    @inline
    def visit__not_escape_sequence(self,node,index):
        self.write(str(node.text,encoding="utf8"))
        return index
    
    def visit_format_specifier(self,node):
        index=[0]
        self.child(node,index=index,child_type=":")
        node_str=str(node.text,encoding='utf8')
        prev_end=1
        while index[0]<len(node.children):
            child=Wrapper.get_children(node,index[0])
            child_str=str(child.text,encoding='utf8')
            cur_start=node_str.index(child_str)
            self.write(node_str[prev_end:cur_start])
            prev_end=cur_start+len(child_str)
            with self.alias("interpolation","format_expression"):
                self.child(node,index,child_type="format_expression")
        self.write(str(node.text,encoding="utf8")[prev_end:])
        return [len(node.children)]
    
    def visit_type_conversion(self,node):#no children
        self.write(str(node.text,encoding="utf8"))
        return [0]
    
    def visit_integer(self,node):
        self.write(str(node.text,encoding="utf8"))
        return [0]
    
    def visit_float(self,node):
        self.write(str(node.text,encoding="utf8"))
        return [0]
    
    def visit_identifier(self,node):
        index=[0]
        self.child(node,index=index,child_type="_start_line")
        self.write(str(node.text,encoding="utf8"))
        return index
    
    @inline
    def visit_keyword_identifier(self,node,index):
        """
        keyword_identifier: $ => choice(
            prec(-3, alias(
                choice(
                'print',
                'exec',
                'async',
                'await',
                ),
                $.identifier,
            )), 
            alias(
                choice('type', 'match'),
                $.identifier,
            ),
            ),
        """
        old_types=["print","exec","async","await","type","match"]
        self.choice(node,index=index,child_types=[{"type":"alias()","params":{"old_type":t,"new_type":"identifier","is_old_func":True}} for t in old_types])
        return index
    
    def visit_true(self,node):
        index=[0]
        self.child(node,index,"_node_content")
        # self.write("True")
        return index
    
    def visit_false(self,node):
        index=[0]
        self.child(node,index,"_node_content")
        # self.write("False")
        return index

    def visit_none(self,node):
        index=[0]
        self.child(node,index,"_node_content")
        # self.write("None")
        return index
    
    def visit_await(self,node):
        index=[0]
        self.child(node,index,"await")
        self.child(node,index=index,child_type="_space")
        self.child(node,index,"primary_expression")
        return index

    def visit_comment(self,node):
        self.write_comment(node.text)
        return [0]
    
    def visit_line_continuation(self,node):
        #line_continuation exist
        index=[0]
        self.child(node,index=index,child_type="_space")
        # self.write("\\")
        # self.maybe_newline(False)
        # self.write(str(node.text,encoding='utf8'))
        self.child(node,index,"_node_content")
        return index
    
    def visit_positional_separator(self,node):
        index=[0]
        self.child(node,index,"/")
        return index
    
    def visit_keyword_separator(self,node):
        index=[0]
        self.child(node,index,"*")
        return index
    
    # externals
    @inline
    def visit__indent(self,node,index):
        self.change_indent(4)
        self.maybe_newline()
        # self.indent+=4
        

    @inline
    def visit__dedent(self,node,index):
        # self.indent-=4
        self.change_indent(-4)
        self.maybe_newline()

    def visit_string_start(self,node):
        self.write(str(node.text,encoding='utf8'))#write the delimiter back
        return [0]

    def visit_string_end(self,node):
        self.write(str(node.text,encoding='utf8'))
        return [0]

    def visit_escape_interpolation(self,node):#external token, no children
        self.write(str(node.text,encoding="utf8"))
        return [len(node.children)]
    
    @inline
    def visit__string_content(self,node,index):
        self.write(str(node.text,encoding="utf8"))
        return [len(node.children)]
    
    @inline
    def visit__newline(self,node,index):
        self.maybe_newline()
        return [0]#alias($._newline,$.block)
    
    @inline
    def visit__space(self,node,index):
        self.maybe_space()

    @inline
    def visit__start_line(self,node,index):
        self.maybe_indent()
    
    @inline
    def visit__space_line(self,node,index):
        self.maybe_spaceline()

    @inline
    def visit__node_content(self,node,index):
        self.write(str(node.text,encoding='utf8'))