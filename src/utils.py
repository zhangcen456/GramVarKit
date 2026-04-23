class TreeDumper:
    def __init__(self):
        self.indent=0
        self.current_line=''
        self.lines=[]
    
    def clear(self):
        self.indent=0
        self.current_line=''
        self.lines.clear()

    def print_with_indent(self,s):
        self.current_line+=("  " * self.indent + s)

    def write(self,s):
        self.current_line+=s

    def new_line(self):
        self.lines.append(self.current_line)
        self.current_line=''

    def dump(self,root_node):
        self.clear()
        self.dump_tree(root_node)
        if(self.current_line):
            self.new_line()

    def dump_tree(self,root_node):
        if(root_node.named_child_count>0):
            if(self.current_line):
                self.write("({}".format(root_node.type))
                self.new_line()
            else:
                self.print_with_indent("({}".format(root_node.type))
                self.new_line()
            self.indent += 1
            cnt=0
            for i,child in enumerate(root_node.children):
                if(child.is_named):
                    cnt+=1
                    field_name=root_node.field_name_for_child(i)
                    if(field_name):
                        self.print_with_indent("{}:".format(field_name))
                    else:
                        self.print_with_indent("")
                    self.dump_tree(child)
                    if(cnt!=root_node.named_child_count):
                        self.new_line()
            self.indent -= 1
            self.write(")")
        else:
            self.write(f"({root_node.type})")
            # self.new_line()

def print_tree(tree):
    dumper=TreeDumper()
    dumper.dump(tree.root_node)
    for line in dumper.lines:
        print(line)

def inline(func):
    setattr(func,'inline',True)
    return func

def writing_op(func):
    def wrapper(*args,**kwargs):
        obj=args[0]
        exec=obj.exec
        if(exec):
            func(*args,**kwargs)
        else:
            obj.writing_operations.append([func.__name__,args[1:],kwargs,{"rule":obj.stack[-1]}])#exclude self
    return wrapper

def get_dict_hash(d:dict):
    d_str=str(sort_dict(d))
    return hash(d_str)

def sort_dict(d:dict):
    new_d=dict()
    for k,v in d.items():
        if(isinstance(v,dict)):
            new_d[k]=str(sort_dict(v))
        else:
            new_d[k]=str(v)
    return sorted(new_d.items())

def compare_trees(tree1,tree2):
    #how to ignore all comments?
    return compare_nodes(tree1.root_node,tree2.root_node)

def skip_extra(node,index):
    while(index<len(node.children) and node.children[index].type in ['comment','line_continuation']):
        index+=1
    return index

def skip_bracket(node,index):#special case
    while(index<len(node.children) and node.type in ['with_clause','import_from_statement','future_import_statement'] and node.children[index].type in ['(',')']):
        index+=1
    index=skip_extra(node,index)
    return index

def compare_nodes(node1,node2):
    i=0
    len1=len(node1.children)
    j=0
    len2=len(node2.children)
    while i<len1 and j<len2:
        i=skip_bracket(node1,skip_extra(node1,i))
        if(i>=len1):
            break
        j=skip_bracket(node2,skip_extra(node2,j))
        if(j>=len2):
            break
        
        #special case
        if(node1.type=='subscript' and node2.type=='subscript'):
            if(node1.children[i].type=='slice' and (i+2)<len(node1.children) and node1.children[i+2].type=='string'
               and node2.children[j].type=='slice' and node2.children[j].children[-1].type=='string'):
                return True
            if(node1.children[i].type=='slice' and (i+2)<len(node1.children) 
               and node1.children[i+2].children and node1.children[i+2].children[0].type=='string'
               and node2.children[j].type=='slice' and node2.children[j].children[1].type=='string'):
                return True

        if not compare_nodes(node1.children[i],node2.children[j]):
            return False
        i+=1
        j+=1
    i=skip_bracket(node1,skip_extra(node1,i))
    j=skip_bracket(node2,skip_extra(node2,j))
    if(i<len1 or j<len2):
        return False
    return node1.type==node2.type