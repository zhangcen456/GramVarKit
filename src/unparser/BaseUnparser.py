from contextlib import contextmanager
from collections import defaultdict
from ..utils import *
from ..parse_config import *
from ..wrapper import Wrapper
from ..language_config import language_config
from ..aux_class import SentinelNode,CustomException

DEBUG=False

class BaseUnparser:
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
            root_node=Wrapper.construct_node(None,tree.root_node,tree.root_node.type,False,False,None)
        else:
            root_node=tree.root_node
        self.visit(root_node)
        #execute writing operations
        self.exec=True
        for operation in self.writing_operations:
            writing_op=getattr(self,operation[0])
            self.context=operation[3]
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
        # total_len=len(node.children)
        while index<len(node.children):
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
            node=node.parent
            defaults["index"]=index
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
    def maybe_space(self):
        if(len(self.current_line)>0 and self.current_line[-1]!=" "):
            self.write(" ")

    # @writing_op
    # def enable_write_comment(self,state):
    #     if(state):
    #         self.write_comment_immediate=True
    #         for com in self.comments:
    #             self.maybe_indent()
    #             self.write(com)
    #             self.maybe_newline()
    #         self.comments.clear()
    #     else:
    #         self.write_comment_immediate=False


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
                node.children[index[0]]=Wrapper.construct_node(node,node.children[index[0]],node.children[index[0]].type,False,False,None)
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
            defaults={"index":None,"child_type":old_type}
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
        if(not self.is_zero_len_token(node,index,child_type)):#externals that do not appear in parse tree
            Wrapper.get_children(node,index[0])
            self.skip_extras(node,index)
            assert self.check_type(node.children[index[0]].type,child_type),"type not match"
        if(field_name is not None):
            assert node.field_name_for_child(index[0])==field_name,"field name not match"

        information=self.get_information(node,index,child_type)

        original_ops=self.writing_operations[:]
        self.writing_operations=list()
        if(self.is_zero_len_token(node,index,child_type)):
            if(self.spy_to_py):
                # Wrapper.zero_len_token_rules(node,index,child_type)
                Wrapper.construct_node(node,None,child_type,True,True,None)
            child_node=SentinelNode(node)#must be inline node -> visit SentinelNode.parent
            current_node=node
            # if(not self.delete_rules(information) and not self.replace_rules(information)):
            inline=self.visit(child_node,child_type,index)
            if(self.spy_to_py):
                Wrapper.node_exit(child_node,index[0])
        elif(node.children[index[0]].is_named or child_type in self.inline_symbols):#check inline type using function attributes
            if(self.spy_to_py):
                if(child_type in self.inline_symbols):#for inline nodes, append the child_type to node.types instead of node.children.types
                    Wrapper.construct_node(node,None,child_type,True,False,index[0])#insertion rules before and after inline symbols
                    wrapped_node=SentinelNode(node)
                    current_node=node
                else:
                    if(child_type in self.aliases):
                        actual_type=self.aliases[child_type][0]
                    else:
                        actual_type=child_type
                    node.children[index[0]]=Wrapper.construct_node(node,node.children[index[0]],actual_type,False,False,None)
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
        if(not self.delete_rules(information) and not self.replace_rules(information)
           and not self.custom_replace_rules(current_node,information)):
            #if any delete rules are applied, then no replace rules will apply?
            self.writing_operations.extend(new_ops)
        self.insert_after_rules(information)
        self.custom_after_rules(current_node,information)
    
    def is_zero_len_token(self,node,index,child_type):
        return child_type in self.zero_len_token

    def recur_func(self,node,index,child_type):
        if(isinstance(child_type,str)):
            child_type={"type":child_type}
        if(child_type["type"]=="optional()"):
            self.optional(node,index,**child_type["params"])
        elif(child_type["type"]=="seq()"):
            self.seq(node,index,**child_type["params"])
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
        # self.indent=0
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
        is_zero_len=self.is_zero_len_token(node,index,child_type)
        if(is_zero_len):
            is_symbol=True
        elif(child_type in self.inline_symbols and node.children[index[0]].type!=child_type):#TODO:differentiate symbols and strings when calling child()
            is_symbol=True
        else:
            is_symbol=node.children[index[0]].is_named
        field_name_for_prev=node.field_name_for_child(left) if left>=0 else None
        prev_symbol=node.children[left].is_named if left>=0 else None
        return {"type":child_type,"parent_type":parent_type,"field":field_name,
                "actual_type":actual_type,
                "symbol":is_symbol,
                "zero_len":is_zero_len,
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
    
    def skip_rules(self,rule,is_zero_len,next_sibling):
        def any_in_condition(keys:list,conditions):
            for key in keys:
                if(key in conditions.keys()):
                    return True
            return False
        
        if(is_zero_len and not any_in_condition(["type","prev_sibling_inline"],rule['condition'])
           and next_sibling):
            #zero_len_token will be recorded by prev_sibling_inline(except for custom externals)
            #zero_len_token does not appear in parse tree, if positions are determined using only next_sibling/prev_sibling, rules will be applied repeatedly
            return True
        else:
            return False

    def insert_before_rules(self,information):
        for rule in self.transfer_rules['insert_before']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                self.write(rule['content'])
                if(DEBUG):
                    print(rule)

    def insert_after_rules(self,information):
        for rule in self.transfer_rules['insert_after']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                self.write(rule['content'])
                if(DEBUG):
                    print(rule)

    def delete_rules(self,information):
        for rule in self.transfer_rules['delete']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                if(DEBUG):
                    print(rule)
                return True
        return False

    def replace_rules(self,information):
        egli_rules=list()
        for rule in self.transfer_rules['replace']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
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
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                custom_method=getattr(self,rule['content'])
                custom_method(current_node,**rule.get("params",{}))
                if(DEBUG):
                    print(rule)
    
    def custom_before_rules(self,current_node,information):
        for rule in self.transfer_rules['custom_before']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                custom_method=getattr(self,rule['content'])
                custom_method(current_node,**rule.get("params",{}))
                if(DEBUG):
                    print(rule)
    
    def custom_replace_rules(self,current_node,information):#TODO: throw exception in custom method to cancel a rule?/custom condition check
        for rule in self.transfer_rules['custom_replace']:
            if(self.skip_rules(rule,information['zero_len'],information['next_sibling'])):
                continue
            if(check_conditions(rule['condition'],rule.get('not_condition',None),information)):
                custom_method=getattr(self,rule['content'])
                custom_method(current_node,**rule.get("params",{}))
                if(DEBUG):
                    print(rule)
                return True
        return False