from typing import List
from collections import defaultdict
import ast
from tree_sitter import Node as tree_sitter_node

#define a wrapper node for tree-sitter nodes
from .parse_config import read_tree_rules,check_conditions,get_rules_for_parent,find_specific_rule
# tree_rules=read_tree_rules()
from .language_config import language_config
from .aux_class import SentinelNode,StringNode,AuxInf

class Wrapper:#the origin node cannot be modified
    @classmethod
    def load_tree_rules(cls,filepath):
        cls.tree_rules=read_tree_rules(filepath)

    @classmethod
    def construct_node(cls,parent_node,origin_node,actual_type,is_inline,is_zero_len,index):
        if(is_zero_len):
            parent_node.types.append(actual_type)
            parent_node.zero_len_token_before_rules(index)
            return parent_node
        elif(is_inline): #actual_type in inline_symbols
            parent_node.types.append(actual_type)
            parent_node.before_rules(index)
            return parent_node
        elif(not origin_node.is_named):#node is not named & assumed_type is inline
            return origin_node           
        else:
            assert not parent_node or isinstance(parent_node,cls)#parent node is a wrapper node
            return cls(origin_node,parent_node,actual_type)
        
    @classmethod
    def node_exit(cls,node,index):
        if(isinstance(node,SentinelNode)):
            node=node.parent
        if(isinstance(node,cls)):
            node.exit(index)

    @classmethod
    def get_children(cls,node,index):
        if(isinstance(node,cls) and isinstance(node.origin_node,tree_sitter_node)):
            return node.get_item_apply_rules(index)
        else:
            return node.children[index]
        
    # @classmethod
    # def zero_len_token_rules(cls,node,index,child_type):
    #     if(isinstance(node,cls)):
    #         information={"parent_type":node.types[-1],"type":child_type}
    #         rules=get_rules_for_parent(tree_rules,node.types[-1])['zero_len']
    #         for r in rules:
    #             if(check_conditions(r['condition'],r.get("not_condition",None),information)):
    #                 custom_method=getattr(node.children,r['content'])
    #                 custom_method(index,**r.get("params",{}))#update index, contents and auxiliary information list
    #     else:
    #         return

    def __init__(self,origin_node,parent_node,actual_type):
        self.parent=parent_node#the parent of a wrapper node is also a wrapper node
        self.origin_node=origin_node
        self.types=[actual_type]
        self.type=origin_node.type
        # self.children=ChildList(origin_node.children,self)
        self.is_named=origin_node.is_named
        self.children=origin_node.children[:]
        self.aux_infs=list()
        for i in range(len(origin_node.children)):
            self.aux_infs.append(AuxInf(field_name=origin_node.field_name_for_child(i)))

        self.exist=True#for debug
        self.information_stack=list()

        # for attr in dir(origin_node):
        #     if(not hasattr(self,attr)):
        #         setattr(self,attr,getattr(origin_node,attr))
        self.text=origin_node.text
        

    def save_states(self):
        children=[c.origin_node if isinstance(c,self.__class__) else c for c in self.children]
        state=(self.types[:],self.information_stack[:],children,[aux.to_str() for aux in self.aux_infs])
        return state
    
    def restore_states(self,state):
        self.types=state[0][:]
        self.information_stack=state[1][:]
        self.children=state[2][:]
        self.aux_infs=[AuxInf.load_from_str(string) for string in state[3]]

    def exit(self,index):
        exit_type=self.types.pop()
        #if(not self.types): self.exist=False
        if(not len(self.types)):
            self.exist=False
        elif(self.information_stack[-1]['zero_len']):
            self.zero_len_token_after_rules(index,exit_type)#index not changed
        else:#for inline symbols
            self.after_rules(index-1,exit_type)#index point to the next children

    def field_name_for_child(self,index):
        if(index<0 or index>=len(self.children)):
            return None
        return self.aux_infs[index].field_name
    
    def children_by_field_name(self,field_name):
        children=list()
        for i in range(len(self.children)):
            self.get_item_apply_rules(i)
            if(self.children[i].type not in language_config.extras and self.aux_infs[i].field_name==field_name):
                children.append(self.children[i])
        return children
    
    def before_rules(self,index):
        information={"parent_type":self.types[-2],"type":self.types[-1],"field":self.aux_infs[index].field_name,
                     "symbol":True,
                     "zero_len":False,
                     **self.get_prev_sibling(index)}
        rules=get_rules_for_parent(self.__class__.tree_rules,self.types[-2])
        new_index=self.insert_before_rules(index,rules['insert_before'],information)
        self.custom_before_rules(new_index,rules['custom_before'],information)
        self.information_stack.append(information)

    def zero_len_token_before_rules(self,index):
        information={"parent_type":self.types[-2],"type":self.types[-1],"symbol":True,"zero_len":True}
        rules=get_rules_for_parent(self.__class__.tree_rules,self.types[-2])
        #insertion before a zero_len_token(always inline) is useless
        self.custom_before_rules(index,rules['custom_before'],information)
        self.information_stack.append(information)

    def after_rules(self,index,exit_type):
        information=self.information_stack.pop()
        assert information['type']==exit_type,"wrapper after rules not paired"
        information.update(self.get_next_sibling(index))
        rules=get_rules_for_parent(self.__class__.tree_rules,self.types[-1])
        new_index=self.insert_after_rules(index,rules['insert_after'],information)
        self.custom_after_rules(new_index,rules['custom_after'],information)

    def zero_len_token_after_rules(self,index,token_type):
        information=self.information_stack.pop()
        assert information['type']==token_type,"wrapper after rules not paired"
        rules=get_rules_for_parent(self.__class__.tree_rules,self.types[-1])
        new_index=self.insert_after_rules(index,rules['insert_after'],information)
        self.custom_after_rules(new_index,rules['custom_after'],information)

    def end_clear(self,ended_index):
        try:
            for i in range(ended_index,len(self.children)):
                self.__class__.get_children(self,i)#delete items at the end
        except IndexError as e:
            pass

    def uni_idx_to_new(self,ori_idx):#get target position after rules applied
        if(ori_idx=="node_end"):
            self.end_clear(0)
            return len(self.children)
        i=0
        while i<len(self.children) and self.aux_infs[i].ori_idx!=ori_idx:
            #the target node will not be deleted(deleted in find_children_position or not processed when target is checked)
            i+=1
        return i
    
    def get_uni_idx(self,index):
        if(index>=len(self.children)):
            return "node_end"
        elif(self.aux_infs[index].ori_idx):#if a children has been selected to be the target
            return self.aux_infs[index].ori_idx
        else:
            self.aux_infs[index].ori_idx=index
            return index
        
    def get_item_apply_rules(self,index):
        parent_rules=get_rules_for_parent(self.__class__.tree_rules,self.types[-1])
        information=self.get_information(index)
        new_index=self.apply_rule(index,parent_rules,information)
        if(new_index>=index):
            return self.children[index]
        # elif(index>=len(self.contents)): #IndexError
        #     raise TestException("delete the last few elements")
        return self.get_item_apply_rules(index)#consecutive deletion
    
    def apply_rule(self,index,rules,information):
        new_index=self.insert_before_rules(index,rules['insert_before'],information)
        new_index=self.custom_before_rules(new_index,rules['custom_before'],information)
        new_index=self.replace_rules(new_index,rules['replace'],information)
        new_index=self.custom_replace_rules(new_index,rules['custom_replace'],information)#e.g. put children into the list and delete itself
        new_index=self.delete_rules(new_index,rules['delete'],information)
        new_index=self.insert_after_rules(new_index,rules['insert_after'],information)
        new_index=self.custom_after_rules(new_index,rules['custom_after'],information)
        return new_index

    def get_information(self,index):
        parent_type=self.types[-1]
        node_type=self.children[index].type
        is_symbol=self.children[index].is_named
        field=self.aux_infs[index].field_name
        prev_inf=self.get_prev_sibling(index)
        next_inf=self.get_next_sibling(index)
        
        return {"type":node_type,"parent_type":parent_type,"field":field,"symbol":is_symbol,
                "zero_len":False,
                **prev_inf,
                **next_inf}
    
    def get_prev_sibling(self,index):
        left=index-1
        while(left>=0 and (self.children[left].type in language_config.extras)):
            left-=1
        prev_sibling=self.children[left] if left>=0 else None
        field_name_for_prev=self.field_name_for_child(left) if left>=0 else None
        prev_symbol=self.children[left].is_named if left>=0 else None
        return {"prev_sibling":prev_sibling.type if prev_sibling else None,
                "prev_sibling_field":field_name_for_prev,
                "prev_symbol":prev_symbol
                }
    
    def get_next_sibling(self,index):
        right=index+1
        while(right<len(self.children) and self.children[right].type in language_config.extras):
            right+=1
        next_sibling=self.children[right] if right<len(self.children) else None
        field_name_for_next=self.field_name_for_child(right) if right<len(self.children) else None
        next_symbol=self.children[right].is_named if right<len(self.children) else None
        return {"next_sibling":next_sibling.type if next_sibling else None,
                "next_sibling_field":field_name_for_next,
                "next_symbol":next_symbol
                }
    
    def insert_before_rules(self,index,rules,information):
        for r in rules:#if multiple rules are applied simutaneously(usually not), the rules encountered later during traversal will be inserted behind
            if (not self.aux_infs[index].rules_applied(r['index']) and check_conditions(r['condition'],r.get('not_condition',None),information)):
                # ori_idx=self.aux_infs[index].ori_idx
                if(isinstance(r['content'],list)):
                    self.children=self.children[:index]+[StringNode(s) for s in r['content']]+self.children[index:]
                    fields=[it['field'] if (isinstance(it,dict) and "field" in it) else None for it in r['content']]
                    self.aux_infs=self.aux_infs[:index]+[AuxInf(field_name=fields[i],applied_rules=[r['index']]) for i in range(len(fields))]+self.aux_infs[index:]
                    index+=len(r['content'])
                    # self.bound=index
                else:
                    self.children.insert(index,StringNode(r['content']))
                    field=r['content']['field'] if isinstance(r['content'],dict) and 'field' in r['content'] else None
                    self.aux_infs.insert(index,AuxInf(field_name=field,applied_rules=[r['index']]))
                    index+=1
                    # self.bound=index
                self.aux_infs[index].add_rule(r['index'])
        return index#the index of the original element is moved backwards
    
    def custom_before_rules(self,index,rules,information):
        new_index=index
        for r in rules:
            if((not information['zero_len']) and self.aux_infs[index].rules_applied(r['index'])):
                continue
            if (check_conditions(r['condition'],r.get('not_condition',None),information)):
                custom_method=getattr(self,r['content'])
                new_index=custom_method(new_index,**r.get("params",{}))#update index, contents and auxiliary information list
                if(new_index):
                    self.aux_infs[new_index].add_rule(r['index'])
        return new_index

    custom_replace_rules=custom_before_rules
    custom_after_rules=custom_before_rules
    
    def replace_rules(self,index,rules,information):#only for 1 to 1 correspondence
        egli_rules=list()
        for r in rules:
            if(not self.aux_infs[index].rules_applied(r['index']) and check_conditions(r['condition'],r.get('not_condition',None),information)):#if more than one replace rule exists, there will be contradiction
                #if multiple rules are satisfied
                egli_rules.append(r)
        #choose one rule
        if(len(egli_rules)==0):
            return index
        elif(len(egli_rules)>1):
            replace_content=set([r['content']['type'] if isinstance(r['content'],dict) else r['content'] for r in egli_rules])
            if(len(replace_content)==1):
                apply_rule=egli_rules[0]
            else:
                apply_rule=find_specific_rule(egli_rules)
                if(not apply_rule):
                    print("multiple replace rule")
                    return index
        else:
            apply_rule=egli_rules[0]
        self.children[index]=StringNode(apply_rule['content'])
        # self.bound=index
        if(isinstance(apply_rule['content'],dict) and 'field' in apply_rule['content']):
            self.aux_infs[index].field_name=apply_rule['content']['field']
        self.aux_infs[index].add_rule(apply_rule['index'])
        return index
    
    def delete_rules(self,index,rules,information):
        for r in rules:
            if(not self.aux_infs[index].rules_applied(r['index']) and check_conditions(r['condition'],r.get('not_condition',None),information)):#delete rule会被重复应用吗？
                self.children.pop(index)
                self.aux_infs.pop(index)
                index-=1
                # self.bound=index
                return index
        return index
    
    def insert_after_rules(self,index,rules,information):
        for r in rules:#the rules encountered later during traversal will be inserted in the front
            if((not information['zero_len']) and self.aux_infs[index].rules_applied(r['index'])):
                continue
            if (check_conditions(r['condition'],r.get('not_condition',None),information)):
                # ori_idx=self.aux_infs[index].ori_idx
                if(isinstance(r['content'],list)):
                    self.children=self.children[:index+1]+[StringNode(s) for s in r['content']]+self.children[index+1:]
                    # self.bound=index+len(r['content'])
                    fields=[it['field'] if (isinstance(it,dict) and "field" in it) else None for it in r['content']]
                    self.aux_infs=self.aux_infs[:index+1]+[AuxInf(applied_rules=[r['index']],field_name=fields[i]) for i in range(len(fields))]+self.aux_infs[index+1:]
                else:
                    self.children.insert(index+1,StringNode(r['content']))
                    field=r['content']['field'] if isinstance(r['content'],dict) and 'field' in r['content'] else None
                    # self.bound=index+1
                    self.aux_infs.insert(index+1,AuxInf(applied_rules=[r['index']],field_name=field))
                self.aux_infs[index].add_rule(r['index'])
        return index