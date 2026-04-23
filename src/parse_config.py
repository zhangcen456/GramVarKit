from collections import defaultdict
import json
import os
import shutil

from .language_config import language_config
from .utils import get_dict_hash
from .grammar_trans import modify_grammar_json,build_tree,StringNode,SymbolNode,SentinelNode,dedup_list,get_type

FIELDS=['type','field','prev_sibling','prev_sibling_inline','prev_sibling_field','next_sibling','next_sibling_field']
CONDS=FIELDS+['parent_type','actual_type']
ACTIONS=['insert_before','insert_after','replace','delete','custom_before','custom_replace','custom_after']

def read_rules(filepath):
    with open(filepath,'r') as f:
        rules=json.load(f)

    classified_rules=defaultdict(list)
    for rule in rules:
        rule_list=classified_rules.get(rule['action'],list())
        rule_list.append(rule)
        classified_rules[rule['action']]=rule_list
    return classified_rules
    # classified_rules={}
    # count=0
    # for rule in rules:
    #     rule['index']=count
    #     count+=1
    #     parent_type=rule['condition'].get("parent_type","other_rules")
    #     rule_for_type=classified_rules.get(parent_type,defaultdict(list))
    #     rule_list=rule_for_type.get(rule['action'],list())
    #     rule_list.append(rule)
    #     rule_for_type[rule['action']]=rule_list
    #     classified_rules[parent_type]=rule_for_type
    # return classified_rules

def build_symbol_name(name,symbol:bool):
    if(not name):
        return None
    if(symbol):
        return f"${name}"
    else:
        return name

def check_conditions(conditions:dict,not_conditions:dict,information):
    for k,v in conditions.items():
        if(k not in information):
            return False
        inf_value=information[k]
        if(k=='type'):
            inf_value=build_symbol_name(inf_value,information['symbol'])
        elif(k=='prev_sibling'):
            inf_value=build_symbol_name(inf_value,information['prev_symbol'])
        elif(k=='next_sibling'):
            inf_value=build_symbol_name(inf_value,information['next_symbol'])
        elif(k=='prev_sibling_inline'):
            inf_value=build_symbol_name(inf_value,True)
        if(isinstance(v,list)):
            if(not inf_value in v):
                return False
        elif(inf_value!=v):
            return False
    if(not_conditions):
        for k,v in not_conditions.items():
            if(k not in information):
                return False
            inf_value=information[k]
            if(k=='type'):
                inf_value=build_symbol_name(inf_value,information['symbol'])
            elif(k=='prev_sibling'):
                inf_value=build_symbol_name(inf_value,information['prev_symbol'])
            elif(k=='next_sibling'):
                inf_value=build_symbol_name(inf_value,information['next_symbol'])
            if(isinstance(v,list)):
                if(inf_value in v):
                    return False
            elif(inf_value==v):
                return False
    return True

def read_tree_rules(filepath):
    with open(filepath,'r') as f:
        rules=json.load(f)

    classified_rules={}#classified by parent types
    count=0
    for rule in rules:
        rule['index']=count
        count+=1
        parent_type=rule['condition'].get("parent_type","other_rules")
        rule_for_type=classified_rules.get(parent_type,defaultdict(list))
        rule_list=rule_for_type.get(rule['action'],list())
        rule_list.append(rule)
        rule_for_type[rule['action']]=rule_list
        classified_rules[parent_type]=rule_for_type
    return classified_rules

def get_rules_for_parent(classified_rules,parent_type):
    #parent_type + other_rules(no specified parent type)
    parent_rules=classified_rules.get(parent_type,defaultdict(list)).copy()
    if("other_rules" in classified_rules):
        for k,v in classified_rules['other_rules'].items():
            parent_rules[k]+=v
    return parent_rules

def find_specific_rule(rules):
    #find the rule with most specific condition
    def compare_condition(condition1:dict,condition2:dict):
        #if condition1 is satisfied, condition2 must be satisfied
        for k,v in condition2.items():
            if(k not in condition1 or condition1[k]!=v):
                return False
        return True 
    
    def compare_not_condition(condition1,condition2):
        for k,v2 in condition2.items():
            if(k not in condition1):
                return False
            else:
                v1=condition1[k]
                if(isinstance(v1,list) and isinstance(v2,list)):
                    for v in v2:
                        if(v not in v1):
                            return False
                elif(isinstance(v1,list)):
                    if v2 not in v1:
                        return False
                elif(isinstance(v2,list)):
                    return False
                else:
                    if(v1!=v2):
                        return False
        return True
    
    supertypes=[None]*len(rules)
    for i in range(len(rules)):
        for j in range(i+1,len(rules)):
            if(compare_condition(rules[i]['condition'],rules[j]['condition']) 
               and compare_not_condition(rules[i].get("not_condition",{}),rules[j].get("not_condition",{}))):
                supertypes[j]=i
            elif(compare_condition(rules[j]['condition'], rules[i]['condition'])
                 and compare_not_condition(rules[j].get("not_condition",{}),rules[i].get("not_condition",{}))):
                supertypes[i]=j

    if(supertypes.count(None)!=1):
        return None
    return rules[supertypes.index(None)]

def warning(message):
    print("[warning] "+message)

def error(message):
    print("[error] "+message)
    raise RuntimeError(message)

def read_rules_from_json(filepath,grammar_modification=None):
    #import config
    with open("config.json",'r') as f:
        config=json.load(f)
    #import rules
    filepath=os.path.abspath(filepath)
    import_files=[filepath]
    visited=set()
    rules=defaultdict(list)
    while import_files:
        import_file=import_files.pop()
        new_imports=import_rules(import_file,visited,rules)
        import_files.extend(new_imports)
    #deduplicate
    for k,v in rules.items():
        rules[k]=dedup_rules(v)
    #compile rules
    py_to_spy,spy_to_py,customs=compile_rules(rules)
    py_to_spy.extend(preprocess_ori_to_new(rules['ori_to_new']))
    spy_to_py.extend(preprocess_new_to_ori(rules['new_to_ori']))
    #modify grammar rules
    original_grammar_json=os.path.join(config['original_grammar'],"src","grammar.json")
    with open(original_grammar_json,'r') as f:
        grammar=json.load(f)
    new_grammar_rules=modify_grammar_json(grammar['rules'],py_to_spy,custom_modifications=grammar_modification)
    new_grammar={**grammar}
    new_grammar['rules']=new_grammar_rules
    if(not os.path.exists(config['new_grammar'])):
        # os.makedirs(config['new_grammar'])
        shutil.copytree(config['original_grammar'],config['new_grammar'])
    new_grammar_json=os.path.join(config['new_grammar'],"src","grammar.json")
    with open(new_grammar_json,'w') as f:
        json.dump(new_grammar,f,indent=2)

    py_to_spy,spy_to_py=check_rules(py_to_spy,spy_to_py,grammar['rules'],new_grammar['rules'])

    #write rules to json file
    dirname,filename=os.path.split(filepath)
    ori_to_new_path=os.path.join(dirname,filename.replace(".json",".ori_to_new.json"))
    with open(ori_to_new_path,'w') as f:
        json.dump(py_to_spy,f,indent=2)
    new_to_ori_path=os.path.join(dirname,filename.replace(".json",".new_to_ori.json"))
    with open(new_to_ori_path,'w') as f:
        json.dump(spy_to_py,f,indent=2)
    customs_path=os.path.join(dirname,filename.replace(".json",".customs.json"))
    with open(customs_path,'w') as f:
        json.dump(customs,f,indent=2)

def preprocess_uni_rule(rule):
    if(rule.get("action",None) not in ACTIONS):
        error(f"Invalid action {str(rule)}")
    if("condition" not in rule):
        error(f"Empty condition {str(rule)}")
    condition=rule['condition']
    for cond in condition:
        if(cond not in CONDS):
            error(f"Invalid condition {str(rule)}")
    if(rule['action'].startswith("custom")):
        if(not isinstance(rule['content'],str)):
            error(f"Content attribute should refer to function name {str(rule)}")
    else:
        if(rule['action']!='delete'):
            rule['content']=unify_form(rule['content'])

def preprocess_ori_to_new(ori_to_new):
    delete_rules=list()
    for i,rule in enumerate(ori_to_new):
        try:
            preprocess_uni_rule(rule)
            if(rule['action']=='replace' and 'ori_element' not in rule):
                rule['ori_element']=rule['content']
            elif(rule['action'] in ['insert_before','insert_after'] and 'ori_elements' not in rule):
                rule['ori_elements']=rule['content']
            if(isinstance(rule.get("content",None),list)):
                new_insert_list=[it['text'] for it in rule['content']]
                new_string=" ".join(new_insert_list)
                if(len(new_insert_list)>1):
                    warning(f"symbols {str(new_insert_list)} in new grammar are merged as {new_string}")
                rule['content']=new_string
            elif(isinstance(rule.get("content",None),dict)):
                rule['content']=rule['content']['text']
        except RuntimeError:
            delete_rules.append(i)

    ori_to_new=[ori_to_new[i] for i in range(len(ori_to_new)) if i not in delete_rules]
    return ori_to_new
    

def preprocess_new_to_ori(new_to_ori):
    delete_rules=list()
    for i,rule in enumerate(new_to_ori):
        try:
            preprocess_uni_rule(rule)
            if(rule['action'] in ['insert_before','insert_after','replace']):
                rule['content']=build_insertion_node(rule['content'])
        except RuntimeError:
            delete_rules.append(i)
    
    new_to_ori=[new_to_ori[i] for i in range(len(new_to_ori)) if i not in delete_rules]
    return new_to_ori

def import_rules(filepath,visited:set,rules:dict):
    visited.add(filepath)
    directory,name=os.path.split(filepath)
    with open(filepath,'r') as f:
        content=json.load(f)
    new_imports=list()
    if(content.get("import",None)):
        for it in content['import']:
            if(os.path.isabs(it)):
                import_path=it
            else:
                import_path=os.path.join(directory,it)
            if(import_path not in visited):
                new_imports.append(import_path)#build relative path
    for k in ['both',"ori_to_new","new_to_ori"]:
        if(content.get(k,None)):
            rules[k].extend(content[k])
    return new_imports

def dedup_rules(rules:list):
    new_rules=list()
    exist=set()
    for r in rules:
        hashnum=get_dict_hash(r)
        if(not hashnum in exist):
            new_rules.append(r)
            exist.add(hashnum)
    return new_rules

def compile_rules(rules):
    """
    bidirectional rules -> unidirectional rules
    """

    py_to_spy=list()
    spy_to_py=list()
    for r in rules['both']:
        try:
            python_items=unify_form(r['original'])
            spython_items=unify_form(r['new'])
            if(isinstance(spython_items,dict)):
                spython_items=[spython_items]
            if(isinstance(python_items,dict)):
                python_items=[python_items]
            if(isinstance(python_items,dict)):#1-1 replace rules
                assert isinstance(spython_items,dict)
                py_to_spy_condition={}
                spy_to_py_condition={}
                if("parent" in r):
                    py_to_spy_condition['parent_type']=r['parent']
                    spy_to_py_condition['parent_type']=r['parent']
                current_node_condition(python_items,py_to_spy_condition)
                current_node_condition(spython_items,spy_to_py_condition)
                py_to_spy.append({"condition":py_to_spy_condition,"action":"replace","content":spython_items['text'],"ori_element":spython_items})
                spy_to_py.append({"condition":spy_to_py_condition,"action":"replace","content":build_insertion_node(python_items)})
            else:
                py_anchors=find_anchors(python_items)
                spy_anchors=find_anchors(spython_items)
                assert len(py_anchors)==len(spy_anchors)
                if(len(py_anchors)==0):
                    py_to_spy_temp,spy_to_py_temp=compare_list(python_items,spython_items)
                    if("parent" in r):
                        for rule in py_to_spy_temp:
                            rule['condition']['parent_type']=r['parent']
                        for rule in spy_to_py_temp:
                            rule['condition']['parent_type']=r['parent']
                    py_to_spy.extend(py_to_spy_temp)
                    spy_to_py.extend(spy_to_py_temp)
                else:
                    for i in range(len(py_anchors)+1):
                        if(i==0):
                            py_list=python_items[:py_anchors[0]]
                            spy_list=spython_items[:spy_anchors[0]]
                            prev_anchor=None
                            prev_anchor_spy=None
                            next_anchor=python_items[py_anchors[0]]
                            next_anchor_spy=spython_items[spy_anchors[0]]
                        elif(i==len(py_anchors)):
                            py_list=python_items[py_anchors[i-1]+1:]
                            spy_list=spython_items[spy_anchors[i-1]+1:]
                            prev_anchor=python_items[py_anchors[i-1]]
                            prev_anchor_spy=spython_items[spy_anchors[i-1]]
                            next_anchor=None
                            next_anchor_spy=None
                        else:
                            py_list=python_items[py_anchors[i-1]+1:py_anchors[i]]
                            spy_list=spython_items[spy_anchors[i-1]+1:spy_anchors[i]]
                            prev_anchor=python_items[py_anchors[i-1]]
                            prev_anchor_spy=spython_items[spy_anchors[i-1]]
                            next_anchor=python_items[py_anchors[i]]
                            next_anchor_spy=spython_items[spy_anchors[i]]
                        py_to_spy_temp,spy_to_py_temp=compare_list(py_list,spy_list,prev_anchor,prev_anchor_spy,next_anchor,next_anchor_spy)
                        if("parent" in r):
                            for rule in py_to_spy_temp:
                                rule['condition']['parent_type']=r['parent']
                            for rule in spy_to_py_temp:
                                rule['condition']['parent_type']=r['parent']
                        py_to_spy.extend(py_to_spy_temp)
                        spy_to_py.extend(spy_to_py_temp)
        except RuntimeError as e:
            print(f"Error occurs when processing {r}")
            continue
    customs={"ori_to_new":set(),"new_to_ori":set()}
    for r in rules['ori_to_new']:
        if(r['action'].startswith("custom")):
            customs['ori_to_new'].add(r['content'])
    for r in rules['new_to_ori']:
        if(r['action'].startswith("custom")):
            customs['new_to_ori'].add(r['content'])
    for k in customs:
        customs[k]=list(customs[k])
    return py_to_spy,spy_to_py,customs

def unify_form(items):
    if(isinstance(items,list)):
        return [unify_form(i) for i in items]
    elif(isinstance(items,dict)):
        if(items.get("anchor",False)):
            return items
        #infer intree
        if("type" in items and "intree" not in items):
            intree=not get_symbol_name(items['type']) in language_config.inline_symbols
            items['intree']=intree
        if("text" not in items and "type" in items):
            if(items["type"].startswith("$") and not items.get("anchor",False)
               and items['intree']):
                error(f"Insertion or deletion of named node {items['type']}")
            else:
                items['text']=items['type']
        if("type" not in items and not items.get("anchor",False)):
            error(f"Unspecified type {items}")
        return items
    elif(isinstance(items,str)):
        if(get_symbol_name(items) in language_config.inline_symbols):
            return {"type":items,"intree":False}
        elif(items.startswith("$")):#'intree' is judged in the previous branch
            error(f"Insertion or deletion of named node {items}")
        else:
            return {"type":items,"text":items}
    else:
        error("Unexpected item type")

def find_anchors(l:list):
    #return the indexes
    anc=list()
    for i in range(len(l)):
        if(isinstance(l[i],dict) and l[i].get("anchor",False)):
            anc.append(i)
    return anc


def insert_after_condition(prev_anchor,next_anchor):
    condition={}
    if(not prev_anchor.get("optional",False)):
        for f in FIELDS:
            if f in prev_anchor:
                condition[f]=prev_anchor[f]
    if(next_anchor and not next_anchor.get("optional",False)):
        if("type" in next_anchor):
            condition['next_sibling']=next_anchor['type']
        if("field" in next_anchor):
            condition['next_sibling_field']=next_anchor['field']
    return condition

def insert_before_condition(next_anchor):
    condition={}
    if(not next_anchor.get("optional",False)):
        for f in FIELDS:
            if f in next_anchor:
                condition[f]=next_anchor[f]
    return condition

def prev_sibling_condition(anchor,condition):
    if(anchor.get("optional",False)):
        return
    if("type" in anchor):
        condition['prev_sibling']=anchor['type']
    if("field" in anchor):
        condition['prev_sibling_field']=anchor['field']

def next_sibling_condition(anchor,condition):
    if(anchor.get("optional",False)):
        return
    if("type" in anchor):
        condition['next_sibling']=anchor['type']
    if("field" in anchor):
        condition['next_sibling_field']=anchor['field']

def current_node_condition(node,condition):
    for f in FIELDS:
        if f in node:
            condition[f]=node[f]

def build_insertion_node(node):
    """
    get text & field information
    """
    if(isinstance(node,list)):
        return [build_insertion_node(n) for n in node]
    new_node=dict()
    new_node['type']=node['text']
    if("field" in node):
        new_node['field']=node['field']
    return new_node

def compare_list(py_list,spy_list,prev_anchor=None,prev_anchor_spy=None,next_anchor=None,next_anchor_spy=None):
    #py -> spy: str(text); spy -> py: text [+ field]
    py_to_spy_temp=list()
    spy_to_py_temp=list()
    if(len(py_list)==0):
        for i,it in enumerate(spy_list):#prev anchor will be the previous sibling of every item, next anchor applies to only the last one
            if(not it.get("intree",True)):#it does not appear in parse tree of spy
                continue
            condition={}
            if(prev_anchor_spy):
                prev_sibling_condition(prev_anchor_spy,condition)
            if i<len(spy_list)-1:
                next_sibling_condition(spy_list[i+1],condition)
            elif(next_anchor_spy):
                next_sibling_condition(next_anchor_spy,condition)
            current_node_condition(it,condition)
            spy_to_py_temp.append({"condition":condition,"action":"delete"})

        spy_insert_list=[it['text'] for it in spy_list]
        # ori_elements=[it for it in spy_list if it.get('intree',True)]
        ori_elements=spy_list
        if(len(spy_insert_list)==0):
            return py_to_spy_temp,spy_to_py_temp
        spy_string=" ".join(spy_insert_list)
        if(len(spy_insert_list)>1):
            warning(f"symbols {str(spy_insert_list)} in new grammar are merged as {spy_string}")
        if(prev_anchor):
            condition=insert_after_condition(prev_anchor,next_anchor)
            py_to_spy_temp.append({"condition":condition,"action":"insert_after","content":spy_string,"ori_elements":ori_elements})
        elif(next_anchor):
            condition=insert_before_condition(next_anchor)
            py_to_spy_temp.append({"condition":condition,"action":"insert_before","content":spy_string,"ori_elements":ori_elements})
        else:
            error("ori to new: insertion location not specified")
    elif(len(spy_list)==0):
        for i,it in enumerate(py_list):
            condition={}
            if(i>0):
                prev_sibling_condition(py_list[i-1],condition)
            elif(prev_anchor):
                prev_sibling_condition(prev_anchor,condition)
            if(i<len(py_list)-1):
                next_sibling_condition(py_list[i+1],condition)
            elif(next_anchor):
                next_sibling_condition(next_anchor,condition)
            current_node_condition(it,condition)
            py_to_spy_temp.append({"condition":condition,"action":"delete"})

        py_insert_list=[build_insertion_node(it) for it in py_list if it.get('intree',True)]
        if(len(py_insert_list)==0):
            return py_to_spy_temp,spy_to_py_temp
        if(prev_anchor_spy):
            condition=insert_after_condition(prev_anchor_spy,next_anchor_spy)
            spy_to_py_temp.append({"condition":condition,"action":"insert_after","content":py_insert_list})
        elif(next_anchor_spy):
            condition=insert_before_condition(next_anchor_spy)
            spy_to_py_temp.append({"condition":condition,"action":"insert_before","content":py_insert_list})
        else:
            error("new to ori: insertion location not specified")
    else:
        i=0
        while(i<len(py_list) and i<len(spy_list)):
            condition={}
            if(i>0):
                prev_sibling_condition(py_list[i-1],condition)
                # condition['prev_sibling']=py_list[i-1]['type']
            elif(prev_anchor):
                prev_sibling_condition(prev_anchor,condition)
            if(i<len(py_list)-1):
                next_sibling_condition(py_list[i+1],condition)
                # condition['next_sibling']=py_list[i+1]['type']
            elif(next_anchor):
                next_sibling_condition(next_anchor,condition)
            current_node_condition(py_list[i],condition)
            py_to_spy_temp.append({"condition":condition,
                                    "action":"replace","content":spy_list[i]['text'],
                                    "ori_element":spy_list[i]})
            i+=1
        
        if(i<len(py_list)):#delete py_list
            for j in range(i,len(py_list)):
                condition={}
                if(j>0):
                    prev_sibling_condition(py_list[j-1],condition)
                elif(prev_anchor):
                    prev_sibling_condition(prev_anchor,condition)
                if(j<len(py_list)-1):
                    next_sibling_condition(py_list[j+1],condition)
                elif(next_anchor):
                    next_sibling_condition(next_anchor,condition)
                current_node_condition(py_list[j],condition)
                py_to_spy_temp.append({"condition":condition,
                                       "action":"delete"})
        elif(i<len(spy_list)):#insert spy_list
            spy_insert_list=[spy_list[j]['text'] for j in range(i,len(spy_list))]
            spy_string=" ".join(spy_insert_list)#len(spy_insert_list)>=1
            # ori_elements=[spy_list[j] for j in range(i,len(spy_list)) if spy_list[j].get("intree",True)]
            ori_elements=spy_list[i:]
            if(len(spy_insert_list)>1):
                warning(f"symbols {str(spy_insert_list)} in new grammar are merged as {spy_string}")
            condition=insert_after_condition(py_list[i-1],next_anchor)
            py_to_spy_temp.append({"condition":condition,"action":"insert_after","content":spy_string,
                                   "ori_elements":ori_elements})
        

        py_insert_list=[it for it in py_list if it.get("intree",True)]
        spy_insert_list=[it for it in spy_list if it.get("intree",True)] 
        i=0
        while(i<len(py_insert_list) and i<len(spy_insert_list)):
            condition={}
            if(i>0):
                # condition['prev_sibling']=py_list[i-1]['type']
                prev_sibling_condition(py_insert_list[i-1],condition)
            elif(prev_anchor_spy):
                prev_sibling_condition(prev_anchor_spy,condition)
            if(i<len(spy_insert_list)-1):
                # condition['next_sibling']=spy_list[i+1]['type']
                next_sibling_condition(spy_insert_list[i+1],condition)
            elif(next_anchor_spy):
                next_sibling_condition(next_anchor_spy,condition)
            current_node_condition(spy_insert_list[i],condition)
            spy_to_py_temp.append({"condition":condition,
                                   "action":"replace","content":build_insertion_node(py_insert_list[i])})
            i+=1

        if(i<len(py_insert_list)):#insert py
            if(i>0):
                condition=insert_after_condition(spy_insert_list[i-1],next_anchor_spy)
                spy_to_py_temp.append({"condition":condition,"action":"insert_after","content":build_insertion_node(py_insert_list[i:])})
            elif(prev_anchor_spy):
                condition=insert_after_condition(prev_anchor_spy,next_anchor_spy)
                spy_to_py_temp.append({"condition":condition,"action":"insert_after","content":build_insertion_node(py_insert_list[i:])})
            elif(next_anchor_spy):
                condition=insert_before_condition(next_anchor_spy)
                spy_to_py_temp.append({"condition":condition,"action":"insert_before","content":build_insertion_node(py_insert_list[i:])})
            else:
                error("new to ori: insertion location not specified")
        elif(i<len(spy_insert_list)):#delete spy
            for j in range(i,len(spy_insert_list)):
                condition={}
                if(i>0):
                    prev_sibling_condition(py_insert_list[i-1],condition)
                elif(prev_anchor_spy):
                    prev_sibling_condition(prev_anchor_spy,condition)
                if(j<len(spy_insert_list)-1):
                    next_sibling_condition(spy_insert_list[j+1],condition)
                elif(next_anchor_spy):
                    next_sibling_condition(next_anchor_spy,condition)
                current_node_condition(spy_insert_list[j],condition)
                spy_to_py_temp.append({"condition":condition,
                                       "action":"delete"})
    
    return py_to_spy_temp,spy_to_py_temp

def get_symbol_name(name):
    if(not name):
        return None
    if(name.startswith("$")):
        return name[1:]
    else:
        return None
    
def inline_prev_sibling(conditions,grammar_rules,phase):
    if('prev_sibling' in conditions):
        if(isinstance(conditions['prev_sibling'],str)):
            symbol_name=get_symbol_name(conditions['prev_sibling'])
            if(symbol_name in language_config.custom_externals):
                v=conditions['prev_sibling']
                del conditions['prev_sibling']
                warning(f"{phase}: delete prev_sibling:{v} (parent type:{conditions.get('parent_type','undefined')})")
            elif(symbol_name in language_config.inline_symbols):
                v=conditions['prev_sibling']
                lasts=dedup_list(get_leaf_last(grammar_rules,get_symbol_name(v)))
                lasts=[get_type(la) for la in lasts]
                if(len(lasts)==1):
                    lasts=lasts[0]
                conditions['prev_sibling']=lasts
                warning(f"{phase}: change inline prev_sibling:{v} to prev_sibling:{str(lasts)} (parent type:{conditions.get('parent_type','undefined')})")
        elif(isinstance(conditions['prev_sibling'],list)):
            prev_siblings=list()
            for sym in conditions['prev_sibling']:
                symbol_name=get_symbol_name(sym)
                if(symbol_name in language_config.custom_externals):
                    warning(f"{phase}: delete prev_sibling:{symbol_name} (parent type:{conditions.get('parent_type','undefined')})")
                elif(symbol_name in language_config.inline_symbols):
                    lasts=dedup_list(get_leaf_last(grammar_rules,symbol_name))
                    lasts=[get_type(la) for la in lasts]
                    prev_siblings.extend(lasts)
                    warning(f"{phase}: change inline prev_sibling:{symbol_name} to prev_sibling:{str(lasts)} (parent type:{conditions.get('parent_type','undefined')})")
            conditions['prev_sibling']=prev_siblings

def inline_next_sibling(conditions,grammar_rules,phase):
    if('next_sibling' in conditions):
        if(isinstance(conditions['next_sibling'],str)):
            symbol_name=get_symbol_name(conditions['next_sibling'])
            if(symbol_name in language_config.custom_externals):
                v=conditions['next_sibling']
                del conditions['next_sibling']
                warning(f"{phase}: delete next_sibling:{v} (parent type:{conditions.get('parent_type','undefined')})")
            elif(symbol_name in language_config.inline_symbols):
                v=conditions['next_sibling']
                firsts=dedup_list(get_leaf_first(grammar_rules,get_symbol_name(v)))
                firsts=[get_type(la) for la in firsts]
                if(len(firsts)==1):
                    firsts=firsts[0]
                conditions['next_sibling']=firsts
                warning(f"{phase}: change inline next_sibling:{v} to next_sibling:{str(firsts)} (parent type:{conditions.get('parent_type','undefined')})")
        elif(isinstance(conditions['next_sibling'],list)):
            next_siblings=list()
            for sym in conditions['next_sibling']:
                symbol_name=get_symbol_name(sym)
                if(symbol_name in language_config.custom_externals):
                    warning(f"{phase}: delete next_sibling:{symbol_name} (parent type:{conditions.get('parent_type','undefined')})")
                elif(symbol_name in language_config.inline_symbols):
                    firsts=dedup_list(get_leaf_first(grammar_rules,symbol_name))
                    firsts=[get_type(la) for la in firsts]
                    next_siblings.extend(firsts)
                    warning(f"{phase}: change inline next_sibling:{symbol_name} to next_sibling:{str(firsts)} (parent type:{conditions.get('parent_type','undefined')})")
            conditions['next_sibling']=next_siblings

def check_rules(py_to_spy_rules,spy_to_py_rules,grammar_rules,new_grammar_rules):
    # only string(anonymous nodes) can be inserted by rules(custom rules needed for named children)
    # information provided for string node: type + field
    # built-in func can not be used in conditions
    delete_rules=list()
    exist_conditions=set()
    condition_map=defaultdict(list)
    for i,r in enumerate(py_to_spy_rules):
        conditions=r['condition']
        inline_prev_sibling(conditions,grammar_rules,"ori to new")
        inline_next_sibling(conditions,grammar_rules,"ori to new")
        if(len(conditions)==0):
            try:
                error(f"ori to new: empty condition for rule {str(r)}")
            except RuntimeError:
                pass
            delete_rules.append(i)
            continue
        hashnum=get_dict_hash(conditions)
        if(hashnum not in exist_conditions):
            exist_conditions.add(hashnum)
            condition_map[hashnum].append(i)
        else:
            for idx in condition_map[hashnum]:
                if(r['action']==py_to_spy_rules[idx]['action']):#same condition & same action
                    warning("ori to new: redundant rules")
                    print(r)
                    print(py_to_spy_rules[idx])
                    delete_rules.append(i)
                    break
            else:
                condition_map[hashnum].append(i)   
    py_to_spy_rules=[py_to_spy_rules[i] for i in range(len(py_to_spy_rules)) if i not in delete_rules]

    delete_rules=list()
    exist_conditions=set()
    condition_map=defaultdict(list)
    for i,r in enumerate(spy_to_py_rules):
        conditions=r['condition']
        if(isinstance(conditions.get("type",None),str)):
            symbol_name=get_symbol_name(conditions.get("type",None))
            if(symbol_name in language_config.inline_symbols and "next_sibling" in conditions):
                warning(f"new_to_ori: for inline symbol {symbol_name}, next sibling may be inaccurate")
                del conditions['next_sibling']
            if(r['action']=='insert_before' and symbol_name in language_config.inline_symbols):
                v=conditions['type']
                firsts=dedup_list(get_leaf_first(new_grammar_rules,get_symbol_name(v)))
                firsts=[get_type(fi) for fi in firsts]
                if(len(firsts)==1):
                    firsts=firsts[0]
                conditions['type']=firsts
                warning(f"new to ori: insert node before inline symbol {v} is changed to insert before {firsts} \n(parent type:{conditions.get('parent_type','undefined')})")
        elif(isinstance(conditions.get("type",None),list)):
            symbol_types=list()
            for sym in conditions.get("type"):
                symbol_name=get_symbol_name(sym)
                if(symbol_name in language_config.inline_symbols and "next_sibling" in conditions):
                    warning(f"new_to_ori: for inline symbol {symbol_name}, next sibling may be inaccurate")
                    del conditions['next_sibling']
                    symbol_types.append(symbol_name)
                if(r['action']=='insert_before' and symbol_name in language_config.inline_symbols):
                    firsts=dedup_list(get_leaf_first(new_grammar_rules,symbol_name))
                    firsts=[get_type(fi) for fi in firsts]
                    symbol_types.extend(firsts)
                    warning(f"new to ori: insert node before inline symbol {symbol_name} is changed to insert before {firsts} \n(parent type:{conditions.get('parent_type','undefined')})")
        inline_prev_sibling(conditions,grammar_rules,"new to ori")
        inline_next_sibling(conditions,grammar_rules,"new to ori")
        if(len(conditions)==0):
            try:
                error(f"new to ori: empty condition for rule {str(r)}")
            except RuntimeError:
                pass
            delete_rules.append(i)
            continue
        hashnum=get_dict_hash(conditions)
        if(hashnum not in exist_conditions):
            exist_conditions.add(hashnum)
            condition_map[hashnum].append(i)
        else:
            for idx in condition_map[hashnum]:
                if(r['action']==spy_to_py_rules[idx]['action']):#same condition & same action
                    warning("new to ori: redundant rules")
                    print(r)
                    print(spy_to_py_rules[idx])
                    delete_rules.append(i)
                    break
            else:
                condition_map[hashnum].append(i)
            
    spy_to_py_rules=[spy_to_py_rules[i] for i in range(len(spy_to_py_rules)) if i not in delete_rules]
    return py_to_spy_rules,spy_to_py_rules

def register_custom_rules(class_def,rule_names):
    from . import custom_rules
    import inspect
    funcs=inspect.getmembers(custom_rules,inspect.isfunction)
    for name in rule_names:
        f=find_rule_by_name(funcs,name)
        if(not f):
            error(f"custom rule {name} are not defined")
        else:
            setattr(class_def,name,f)

def find_rule_by_name(funcs:list,name:str):
    for f in funcs:
        if(f[0]==name):
            return f[1]
    return None
    

def get_leaf_last(grammar_rules,node):
    if(isinstance(node,StringNode) or isinstance(node,SentinelNode)):
        return [node]
    if(isinstance(node,SymbolNode) and node.name in language_config.zero_len_tokens):
        lst=dedup_list(node.get_prev())
        res=list()
        for n in lst:
            res.extend(get_leaf_last(grammar_rules,n))
        return res
    if(isinstance(node,SymbolNode)):
        if(node.name in language_config.inline_symbols):
            new_root=build_tree(grammar_rules[node.name])
            lst=dedup_list(new_root.get_last())
            res=list()
            for n in lst:
                res.extend(get_leaf_last(grammar_rules,n))
            return res
        else:
            return [node]
    if(isinstance(node,str)):
        new_root=build_tree(grammar_rules[node])
        lst=dedup_list(new_root.get_last())
        res=list()
        for n in lst:
            res.extend(get_leaf_last(grammar_rules,n))
        return res
    error(f"Can't get possible last node for {str(node)}")

def get_leaf_first(grammar_rules,node):
    if(isinstance(node,StringNode) or isinstance(node,SentinelNode)):
        return [node]
    if(isinstance(node,SymbolNode) and node.name in language_config.zero_len_tokens):
        lst=dedup_list(node.get_next())
        res=list()
        for n in lst:
            res.extend(get_leaf_first(grammar_rules,n))
        return res
    if(isinstance(node,SymbolNode)):
        if(node.name in language_config.inline_symbols):
            new_root=build_tree(grammar_rules[node.name])
            lst=dedup_list(new_root.get_first())
            res=list()
            for n in lst:
                res.extend(get_leaf_first(grammar_rules,n))
            return res
        else:
            return [node]
    if(isinstance(node,str)):
        assert node in language_config.inline_symbols
        new_root=build_tree(grammar_rules[node])
        lst=dedup_list(new_root.get_first())
        res=list()
        for n in lst:
            res.extend(get_leaf_first(grammar_rules,n))
        return res
    error(f"Can't get possible first node for {str(node)}")