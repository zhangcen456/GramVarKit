from .BaseUnparser import BaseUnparser,writing_op,inline,Wrapper,CustomException

class JavaUnparser(BaseUnparser):
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

    @writing_op
    def maybe_indent(self):
        if(self.current_line=="" or self.current_line.endswith("\n")):
            self.write(" "*self.indent)

    @writing_op
    def write(self,text):#TODO: 在两个write间用lexer检查？
        def need_split(end_char,start_char):
            return ((end_char.isalnum() or end_char in ["_","$"]) and (start_char.isalnum() or start_char in ["_","$"])) or (end_char==start_char and end_char in ["+","-"])

        if(self.current_line and need_split(self.current_line[-1],text[0])):
            self.maybe_space()
        self.current_line+=text

    @writing_op
    def maybe_newline(self):
        if(self.current_line and not self.current_line.isspace()):
            self.lines.append(self.current_line)
            self.current_line=""
        self.maybe_indent()

    def recur_func(self,node,index,child_type):
        if(isinstance(child_type,str)):
            child_type={"type":child_type,"params":None}
        if(child_type["type"]=="optional()"):
            self.optional(node,index,**child_type["params"])
        elif(child_type["type"]=="seq()"):
            self.seq(node,index,**child_type["params"])
        elif(child_type["type"]=="sep1()"):
            self.sep1(node,index,**child_type["params"])
        elif(child_type["type"]=="commaSep()"):
            self.commaSep(node,index,**child_type["params"])
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
        elif(child_type['type']=="child()"):
            self.child(node,index,**child_type["params"])
        else:
            self.child(node,index,child_type["type"])

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

    def commaSep(self,node,index,child_type):
        self.optional(node,index,child_type={"type":"commaSep1()","params":{"child_type":child_type}})

    #rules
    def visit_program(self,node):
        index=[0]
        self.repeat(node,index,child_type='_toplevel_statement')
        return index

    @inline
    def visit__toplevel_statement(self,node,index):
        self.choice(node,index,child_types=['statement', 'method_declaration'])
        return index

    @inline
    def visit__literal(self,node,index):
        types=['decimal_integer_literal', 'hex_integer_literal', 'octal_integer_literal', 'binary_integer_literal', 'decimal_floating_point_literal', 'hex_floating_point_literal', 'true', 'false', 'character_literal', 'string_literal', 'null_literal']
        actual_type=node.children[index[0]].type
        if(actual_type not in types):
            raise CustomException("No choice matched")
        # choice_idx=types.index(actual_type) if actual_type in types else 0
        # self.choice(node,index,child_types=types)
        self.child(node,index,child_type=actual_type)
        return index

    def visit_decimal_integer_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_hex_integer_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_octal_integer_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_binary_integer_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_decimal_floating_point_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_hex_floating_point_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_true(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index
    
    def visit_false(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_character_literal(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_string_literal(self,node):
        index=[0]
        self.choice(node,index,child_types=['_string_literal', '_multiline_string_literal'])
        return index

    @inline
    def visit__string_literal(self,node,index):
        self.child(node,index,'"')
        self.repeat(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['string_fragment', 'escape_sequence', 'string_interpolation']}})
        self.child(node,index,'"')
        return index

    @inline
    def visit__multiline_string_literal(self,node,index):
        self.child(node,index,'"""')
        self.repeat(node,index,child_type={'type':'seq()','params':{"child_types":["_string_token",{'type': 'choice()', 'params': {'child_types': [{'type': 'alias()', 'params': {'old_type': '_multiline_string_fragment', 'new_type': 'multiline_string_fragment'}}, '_escape_sequence', 'string_interpolation']}}]}})
        self.child(node,index,"_string_token")
        self.child(node,index,'"""')
        return index

    def visit_string_fragment(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    @inline
    def visit__multiline_string_fragment(self,node,index):
        self.child(node,index,"_node_content")
        return index

    def visit_string_interpolation(self,node):
        index=[0]
        self.child(node,index,'\\{')
        self.child(node,index,'expression')
        self.child(node,index,'}')
        return index

    @inline
    def visit__escape_sequence(self,node,index):
        self.child(node,index,child_type="escape_sequence")
        return index

    def visit_escape_sequence(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        return index

    def visit_null_literal(self,node):
        index=[0]
        self.child(node,index,"_node_content")
        return index

    @inline
    def visit_expression(self,node,index):
        expression_types=['assignment_expression', 'binary_expression', 'instanceof_expression', 'lambda_expression', 'ternary_expression', 'update_expression', 'primary_expression', 'unary_expression', 'cast_expression', 'switch_expression']
        actual_type=node.children[index[0]].type
        choice_idx=expression_types.index(actual_type) if actual_type in expression_types else 6
        # self.choice(node,index,child_types=expression_types,recorded_choice=choice_idx)
        self.child(node,index,child_type=expression_types[choice_idx])
        return index

    def visit_cast_expression(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': ['(', {'type': 'field()', 'params': {'field_name': 'type', 'child_type': '_type'}}, ')', {'type': 'field()', 'params': {'field_name': 'value', 'child_type': 'expression'}}]}}, {'type': 'seq()', 'params': {'child_types': ['(', {'type': 'sep1()', 'params': {'child_type': {'type': 'field()', 'params': {'field_name': 'type', 'child_type': '_type'}},'separator':'&'}}, ')', {'type': 'field()', 'params': {'field_name': 'value', 'child_type': {'type': 'choice()', 'params': {'child_types': ['primary_expression', 'lambda_expression']}}}}]}}])
        return index

    def visit_assignment_expression(self,node):
        index=[0]
        self.seq(node,index,child_types=[{'type': 'field()', 'params': {'field_name': 'left', 'child_type': {'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier', 'field_access', 'array_access']}}}}, {'type': 'field()', 'params': {'field_name': 'operator', 'child_type': {'type': 'choice()', 'params': {'child_types': ['=', '+=', '-=', '*=', '/=', '&=', '|=', '^=', '%=', '<<=', '>>=', '>>>=']}}}}, {'type': 'field()', 'params': {'field_name': 'right', 'child_type': 'expression'}}])
        return index

    def visit_binary_expression(self,node):
        index=[0]
        operators=['>','<','>=','<=','==',"!=",'&&','||','+','-','*','/','&','|','^','%','<<','>>','>>>']
        field_left_params={"child_type":"expression","field_name":"left"}
        field_right_params={"child_type":"expression","field_name":"right"}
        choice_child_types=[{"type":"seq()","params":{"child_types":[{"type":"field()","params":field_left_params},{"type":"field()","params":{"child_type":operators[i],"field_name":"operator"}},{"type":"field()","params":field_right_params}]}} for i in range(len(operators))]
        def get_choice_index():
            # assert node.field_name_for_child(1)=='operator'
            idx=operators.index(self.get_operator_type(node))
            return idx
        choice_idx=get_choice_index()
        self.choice(node,index=index,child_types=choice_child_types,recorded_choice=choice_idx)
        return index
    
    def get_operator_type(self,node):
        i=0
        while i<len(node.children):
            if(node.field_name_for_child(i)=="operator"):
                break
            i+=1
        op=Wrapper.get_children(node,i)
        return op.type

    def visit_instanceof_expression(self,node):
        index=[0]
        self.field(node,index,field_name='left',child_type='expression')
        self.child(node,index,'instanceof')
        self.optional(node,index,child_type='final')
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'right', 'child_type': '_type'}}, {'type': 'optional()', 'params': {'child_type': {'type': 'field()', 'params': {'field_name': 'name', 'child_type': {'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}}}}}}]}}, {'type': 'field()', 'params': {'field_name': 'pattern', 'child_type': 'record_pattern'}}])
        return index

    def visit_lambda_expression(self,node):
        index=[0]
        self.field(node,index,field_name='parameters',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', 'formal_parameters', 'inferred_parameters', '_reserved_identifier']}})
        self.child(node,index,'->')
        self.field(node,index,field_name='body',child_type={'type': 'choice()', 'params': {'child_types': ['expression', 'block']}})
        return index

    def visit_inferred_parameters(self,node):
        index=[0]
        self.child(node,index,'(')
        self.commaSep1(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}})
        self.child(node,index,')')
        return index

    def visit_ternary_expression(self,node):
        index=[0]
        self.field(node,index,field_name='condition',child_type='expression')
        self.child(node,index,'?')
        self.field(node,index,field_name='consequence',child_type='expression')
        self.child(node,index,':')
        self.field(node,index,field_name='alternative',child_type='expression')
        return index

    def visit_unary_expression(self,node):
        index=[0]
        operators=['+','-','!','~']
        field_operand_params={"child_type":"expression","field_name":"operand"}
        choice_child_types=[{"type":"seq()","params":{"child_types":[{"type":"field()","params":{"field_name":"operator","child_type":operators[i]}},{"type":"field()","params":field_operand_params}]}} for i in range(len(operators))]
        self.choice(node,index,child_types=choice_child_types)
        return index

    def visit_update_expression(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': ['expression', '++']}}, {'type': 'seq()', 'params': {'child_types': ['expression', '--']}}, {'type': 'seq()', 'params': {'child_types': ['++', 'expression']}}, {'type': 'seq()', 'params': {'child_types': ['--', 'expression']}}])
        return index

    @inline
    def visit_primary_expression(self,node,index):
        types=['_literal', 'class_literal', 'this', 'identifier', '_reserved_identifier', 'parenthesized_expression', 'object_creation_expression', 'field_access', 'array_access', 'method_invocation', 'method_reference', 'array_creation_expression', 'template_expression']
        actual_type=node.children[index[0]].type
        choice_idx=types.index(actual_type) if actual_type in types else 0
        # self.choice(node,index,child_types=types)
        self.child(node,index,child_type=types[choice_idx])
        return index

    def visit_array_creation_expression(self,node):
        index=[0]
        self.child(node,index,'new')
        self.repeat(node,index,child_type='_annotation')
        self.field(node,index,field_name='type',child_type='_simple_type')
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'dimensions', 'child_type': {'type': 'repeat()', 'params': {'child_type': 'dimensions_expr', 'target': 1}}}}, {'type': 'optional()', 'params': {'child_type': {'type': 'field()', 'params': {'field_name': 'dimensions', 'child_type': 'dimensions'}}}}]}}, {'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'dimensions', 'child_type': 'dimensions'}}, {'type': 'field()', 'params': {'field_name': 'value', 'child_type': 'array_initializer'}}]}}])
        return index

    def visit_dimensions_expr(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        self.child(node,index,'[')
        self.child(node,index,'expression')
        self.child(node,index,']')
        return index

    def visit_parenthesized_expression(self,node):
        index=[0]
        self.child(node,index,'(')
        self.child(node,index,'expression')
        self.child(node,index,')')
        return index

    def visit_class_literal(self,node):
        index=[0]
        self.child(node,index,'_unannotated_type')
        self.child(node,index,'.')
        self.child(node,index,'class')
        return index

    def visit_object_creation_expression(self,node):
        index=[0]
        self.choice(node,index,child_types=['_unqualified_object_creation_expression', {'type': 'seq()', 'params': {'child_types': ['primary_expression', '.', '_unqualified_object_creation_expression']}}])
        return index

    @inline
    def visit__unqualified_object_creation_expression(self,node,index):
        self.child(node,index,'new')
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'repeat()', 'params': {'child_type': '_annotation'}}, {'type': 'field()', 'params': {'field_name': 'type_arguments', 'child_type': 'type_arguments'}}, {'type': 'repeat()', 'params': {'child_type': '_annotation'}}]}}, {'type': 'repeat()', 'params': {'child_type': '_annotation'}}])
        self.field(node,index,field_name='type',child_type='_simple_type')
        self.field(node,index,field_name='arguments',child_type='argument_list')
        self.optional(node,index,child_type='class_body')
        return index

    def visit_field_access(self,node):
        index=[0]
        self.field(node,index,field_name='object',child_type={'type': 'choice()', 'params': {'child_types': ['primary_expression', 'super']}})
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['.', 'super']}})
        self.child(node,index,'.')
        self.field(node,index,field_name='field',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier', 'this']}})
        return index

    def visit_template_expression(self,node):
        index=[0]
        self.field(node,index,field_name='template_processor',child_type='primary_expression')
        self.child(node,index,'.')
        self.field(node,index,field_name='template_argument',child_type='string_literal')
        return index

    def visit_array_access(self,node):
        index=[0]
        self.field(node,index,field_name='array',child_type='primary_expression')
        self.child(node,index,'[')
        self.field(node,index,field_name='index',child_type='expression')
        self.child(node,index,']')
        return index

    def visit_method_invocation(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'field()', 'params': {'field_name': 'name', 'child_type': {'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}}}}, {'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'object', 'child_type': {'type': 'choice()', 'params': {'child_types': ['primary_expression', 'super']}}}}, '.', {'type': 'optional()', 'params': {'child_type': {'type': 'seq()', 'params': {'child_types': ['super', '.']}}}}, {'type': 'optional()', 'params': {'child_type': {'type': 'field()', 'params': {'child_type': 'type_arguments','field_name':'type_arguments'}}}}, {'type': 'field()', 'params': {'field_name': 'name', 'child_type': {'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}}}}]}}])
        self.field(node,index,field_name='arguments',child_type='argument_list')
        return index

    def visit_argument_list(self,node):
        index=[0]
        self.child(node,index,'(')
        self.commaSep(node,index,child_type='expression')
        self.child(node,index,')')
        return index

    def visit_method_reference(self,node):
        index=[0]
        self.choice(node,index,child_types=['_type', 'primary_expression', 'super'])
        self.child(node,index,'::')
        self.optional(node,index,child_type='type_arguments')
        self.choice(node,index,child_types=['new', 'identifier'])
        return index

    def visit_type_arguments(self,node):
        index=[0]
        self.child(node,index,'<')
        self.commaSep(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['_type', 'wildcard']}})
        self.child(node,index,'>')
        return index

    def visit_wildcard(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        self.child(node,index,'?')
        self.optional(node,index,child_type='_wildcard_bounds')
        return index

    @inline
    def visit__wildcard_bounds(self,node,index):
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': ['extends', '_type']}}, {'type': 'seq()', 'params': {'child_types': ['super', '_type']}}])
        return index

    def visit_dimensions(self,node):
        index=[0]
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': [{'type': 'repeat()', 'params': {'child_type': '_annotation'}}, '[', ']']}},target=1)
        return index

    def visit_switch_expression(self,node):
        index=[0]
        self.child(node,index,'switch')
        self.field(node,index,field_name='condition',child_type='parenthesized_expression')
        self.field(node,index,field_name='body',child_type='switch_block')
        return index

    def visit_switch_block(self,node):
        index=[0]
        self.child(node,index,'{')
        self.set_target(node,self.find_children_position(node,index[0],target_type="}"))
        self.choice(node,index,child_types=[{'type': 'repeat()', 'params': {'child_type': 'switch_block_statement_group'}}, {'type': 'repeat()', 'params': {'child_type': 'switch_rule'}}])
        self.child(node,index,'}')
        return index

    def visit_switch_block_statement_group(self,node):
        index=[0]
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['switch_label', ':']}},target=1)
        self.repeat(node,index,child_type='statement')
        return index

    def visit_switch_rule(self,node):
        index=[0]
        self.child(node,index,'switch_label')
        self.child(node,index,'->')
        self.choice(node,index,child_types=['expression_statement', 'throw_statement', 'block'])
        return index

    def visit_switch_label(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': ['case', {'type': 'choice()', 'params': {'child_types': ['pattern', {'type': 'commaSep1()', 'params': {'child_type': 'expression'}}]}}, {'type': 'optional()', 'params': {'child_type': 'guard'}}]}}, 'default'])
        return index

    def visit_pattern(self,node):
        index=[0]
        self.choice(node,index,child_types=['type_pattern', 'record_pattern'])
        return index

    def visit_type_pattern(self,node):
        index=[0]
        self.child(node,index,'_unannotated_type')
        self.choice(node,index,child_types=['identifier', '_reserved_identifier'])
        return index

    def visit_record_pattern(self,node):
        index=[0]
        self.choice(node,index,child_types=['identifier', '_reserved_identifier', 'generic_type'])
        self.child(node,index,'record_pattern_body')
        return index

    def visit_record_pattern_body(self,node):
        index=[0]
        self.child(node,index,'(')
        self.commaSep(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['record_pattern_component', 'record_pattern']}})
        self.child(node,index,')')
        return index

    def visit_record_pattern_component(self,node):
        index=[0]
        self.choice(node,index,child_types=['underscore_pattern', {'type': 'seq()', 'params': {'child_types': ['_unannotated_type', {'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}}]}}])
        return index

    def visit_underscore_pattern(self,node):
        index=[0]
        self.child(node,index,'_node_content')
        return index

    def visit_guard(self,node):
        index=[0]
        self.child(node,index,'when')
        self.child(node,index,'expression')
        return index

    @inline
    def visit_statement(self,node,index):
        types=['declaration', 'expression_statement', 'labeled_statement', 'if_statement', 'while_statement', 'for_statement', 'enhanced_for_statement', 'block', ';', 'assert_statement', 'do_statement', 'break_statement', 'continue_statement', 'return_statement', 'yield_statement', 'switch_expression', 'synchronized_statement', 'local_variable_declaration', 'throw_statement', 'try_statement', 'try_with_resources_statement']
        actual_type=node.children[index[0]].type
        choice_idx=types.index(actual_type) if actual_type in types else 0
        # self.choice(node,index,child_types=types)
        self.child(node,index,child_type=types[choice_idx])
        self.child(node,index,"_newline")
        return index

    def visit_block(self,node):
        index=[0]
        self.child(node,index,'{')
        self.child(node,index,"_indent")
        self.repeat(node,index,child_type='statement')
        self.child(node,index,"_dedent")
        self.child(node,index,'}')
        return index

    def visit_expression_statement(self,node):
        index=[0]
        self.child(node,index,'expression')
        self.child(node,index,';')
        return index

    def visit_labeled_statement(self,node):
        index=[0]
        self.child(node,index,'identifier')
        self.child(node,index,':')
        self.child(node,index,'statement')
        return index

    def visit_assert_statement(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': ['assert', 'expression', ';']}}, {'type': 'seq()', 'params': {'child_types': ['assert', 'expression', ':', 'expression', ';']}}])
        return index

    def visit_do_statement(self,node):
        index=[0]
        self.child(node,index,'do')
        self.field(node,index,field_name='body',child_type='statement')
        self.child(node,index,'while')
        self.field(node,index,field_name='condition',child_type='parenthesized_expression')
        self.child(node,index,';')
        return index

    def visit_break_statement(self,node):
        index=[0]
        self.child(node,index,'break')
        self.optional(node,index,child_type='identifier')
        self.child(node,index,';')
        return index

    def visit_continue_statement(self,node):
        index=[0]
        self.child(node,index,'continue')
        self.optional(node,index,child_type='identifier')
        self.child(node,index,';')
        return index

    def visit_return_statement(self,node):
        index=[0]
        self.child(node,index,'return')
        self.optional(node,index,child_type='expression')
        self.child(node,index,';')
        return index

    def visit_yield_statement(self,node):
        index=[0]
        self.child(node,index,'yield')
        self.child(node,index,'expression')
        self.child(node,index,';')
        return index

    def visit_synchronized_statement(self,node):
        index=[0]
        self.child(node,index,'synchronized')
        self.child(node,index,'parenthesized_expression')
        self.field(node,index,field_name='body',child_type='block')
        return index

    def visit_throw_statement(self,node):
        index=[0]
        self.child(node,index,'throw')
        self.child(node,index,'expression')
        self.child(node,index,';')
        return index

    def visit_try_statement(self,node):
        index=[0]
        self.child(node,index,'try')
        self.field(node,index,field_name='body',child_type='block')
        self.set_target(node,len(node.children))
        self.choice(node,index,child_types=[{'type': 'repeat()', 'params': {'child_type': 'catch_clause', 'target': 1}}, {'type': 'seq()', 'params': {'child_types': [{'type': 'repeat()', 'params': {'child_type': 'catch_clause'}}, 'finally_clause']}}])
        return index

    def visit_catch_clause(self,node):
        index=[0]
        self.child(node,index,'catch')
        self.child(node,index,'(')
        self.child(node,index,'catch_formal_parameter')
        self.child(node,index,')')
        self.field(node,index,field_name='body',child_type='block')
        return index

    def visit_catch_formal_parameter(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'catch_type')
        self.child(node,index,'_variable_declarator_id')
        return index

    def visit_catch_type(self,node):
        index=[0]
        self.sep1(node,index,child_type='_unannotated_type',separator="|")
        return index

    def visit_finally_clause(self,node):
        index=[0]
        self.child(node,index,'finally')
        self.child(node,index,'block')
        return index

    def visit_try_with_resources_statement(self,node):
        index=[0]
        self.child(node,index,'try')
        self.field(node,index,field_name='resources',child_type='resource_specification')
        self.field(node,index,field_name='body',child_type='block')
        self.repeat(node,index,child_type='catch_clause')
        self.optional(node,index,child_type='finally_clause')
        return index

    def visit_resource_specification(self,node):
        index=[0]
        self.child(node,index,'(')
        self.sep1(node,index,child_type='resource',separator=";")
        self.optional(node,index,child_type=';')
        self.child(node,index,')')
        return index

    def visit_resource(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'optional()', 'params': {'child_type': 'modifiers'}}, {'type': 'field()', 'params': {'field_name': 'type', 'child_type': '_unannotated_type'}}, '_variable_declarator_id', '=', {'type': 'field()', 'params': {'field_name': 'value', 'child_type': 'expression'}}]}}, 'identifier', 'field_access'])
        return index

    def visit_if_statement(self,node):
        index=[0]
        self.child(node,index,'if')
        self.field(node,index,field_name='condition',child_type='parenthesized_expression')
        # self.child(node,index,"_space")
        self.field(node,index,field_name='consequence',child_type='statement')
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['else', {'type': 'child()', 'params': {'field_name': 'alternative', 'child_type': 'statement'}}]}})
        return index

    def visit_while_statement(self,node):
        index=[0]
        self.child(node,index,'while')
        self.field(node,index,field_name='condition',child_type='parenthesized_expression')
        self.field(node,index,field_name='body',child_type='statement')
        return index

    def visit_for_statement(self,node):
        index=[0]
        self.child(node,index,'for')
        self.child(node,index,'(')
        self.choice(node,index,child_types=[{'type': 'field()', 'params': {'field_name': 'init', 'child_type': 'local_variable_declaration'}}, {'type': 'seq()', 'params': {'child_types': [{'type': 'commaSep()', 'params': {'child_type': {'type': 'field()', 'params': {'field_name': 'init', 'child_type': 'expression'}}}}, ';']}}])
        # self.field(node,index,field_name='condition',child_type={'type': 'optional()', 'params': {'child_type': 'expression'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"expression","field_name":"condition"}})
        self.child(node,index,';')
        self.commaSep(node,index,child_type={'type': 'field()', 'params': {'field_name': 'update', 'child_type': 'expression'}})
        self.child(node,index,')')
        self.field(node,index,field_name='body',child_type='statement')
        return index

    def visit_enhanced_for_statement(self,node):
        index=[0]
        self.child(node,index,'for')
        self.child(node,index,'(')
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        self.child(node,index,'_variable_declarator_id')
        self.child(node,index,':')
        self.field(node,index,field_name='value',child_type='expression')
        self.child(node,index,')')
        self.field(node,index,field_name='body',child_type='statement')
        return index

    @inline
    def visit__annotation(self,node,index):
        self.choice(node,index,child_types=['marker_annotation', 'annotation'])
        return index

    def visit_marker_annotation(self,node):
        index=[0]
        self.child(node,index,'@')
        self.field(node,index,field_name='name',child_type='_name')
        self.child(node,index,"_newline")
        return index

    def visit_annotation(self,node):
        index=[0]
        self.child(node,index,'@')
        self.field(node,index,field_name='name',child_type='_name')
        self.field(node,index,field_name='arguments',child_type='annotation_argument_list')
        return index

    def visit_annotation_argument_list(self,node):
        index=[0]
        self.child(node,index,'(')
        self.choice(node,index,child_types=['_element_value', {'type': 'commaSep()', 'params': {'child_type': 'element_value_pair'}}])
        self.child(node,index,')')
        return index

    def visit_element_value_pair(self,node):
        index=[0]
        self.field(node,index,field_name='key',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}})
        self.child(node,index,'=')
        self.field(node,index,field_name='value',child_type='_element_value')
        return index

    @inline
    def visit__element_value(self,node,index):
        self.choice(node,index,child_types=['expression', 'element_value_array_initializer', '_annotation'])
        return index

    def visit_element_value_array_initializer(self,node):
        index=[0]
        self.child(node,index,'{')
        self.commaSep(node,index,child_type='_element_value')
        self.optional(node,index,child_type=',')
        self.child(node,index,'}')
        return index

    @inline
    def visit_declaration(self,node,index):
        types=['module_declaration', 'package_declaration', 'import_declaration', 'class_declaration', 'record_declaration', 'interface_declaration', 'annotation_type_declaration', 'enum_declaration']
        actual_type=node.children[index[0]].type
        if(actual_type not in types):
            raise CustomException("No choice matched")
        # self.choice(node,index,child_types=types)
        self.child(node,index,actual_type)
        return index

    def visit_module_declaration(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        self.optional(node,index,child_type='open')
        self.child(node,index,'module')
        self.field(node,index,field_name='name',child_type='_name')
        self.field(node,index,field_name='body',child_type='module_body')
        return index

    def visit_module_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.repeat(node,index,child_type='module_directive')
        self.child(node,index,'}')
        return index

    @inline
    def visit_module_directive(self,node,index):
        types=['requires_module_directive', 'exports_module_directive', 'opens_module_directive', 'uses_module_directive', 'provides_module_directive']
        actual_type=node.children[index[0]].type
        if(actual_type not in types):
            raise CustomException("No choice matched")
        self.child(node,index,child_type=actual_type)
        # self.choice(node,index,child_types=['requires_module_directive', 'exports_module_directive', 'opens_module_directive', 'uses_module_directive', 'provides_module_directive'])
        return index

    def visit_requires_module_directive(self,node):
        index=[0]
        self.child(node,index,'requires')
        self.repeat(node,index,child_type={'type': 'field()', 'params': {'field_name': 'modifiers', 'child_type': 'requires_modifier'}})
        self.field(node,index,field_name='module',child_type='_name')
        self.child(node,index,';')
        return index

    def visit_requires_modifier(self,node):
        index=[0]
        self.choice(node,index,child_types=['transitive', 'static'])
        return index

    def visit_exports_module_directive(self,node):
        index=[0]
        self.child(node,index,'exports')
        self.field(node,index,field_name='package',child_type='_name')
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['to', {'type': 'field()', 'params': {'field_name': 'modules', 'child_type': '_name'}}, {'type': 'repeat()', 'params': {'child_type': {'type': 'seq()', 'params': {'child_types': [',', {'type': 'field()', 'params': {'field_name': 'modules', 'child_type': '_name'}}]}}}}]}})
        self.child(node,index,';')
        return index

    def visit_opens_module_directive(self,node):
        index=[0]
        self.child(node,index,'opens')
        self.field(node,index,field_name='package',child_type='_name')
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['to', {'type': 'field()', 'params': {'field_name': 'modules', 'child_type': '_name'}}, {'type': 'repeat()', 'params': {'child_type': {'type': 'seq()', 'params': {'child_types': [',', {'type': 'field()', 'params': {'field_name': 'modules', 'child_type': '_name'}}]}}}}]}})
        self.child(node,index,';')
        return index

    def visit_uses_module_directive(self,node):
        index=[0]
        self.child(node,index,'uses')
        self.field(node,index,field_name='type',child_type='_name')
        self.child(node,index,';')
        return index

    def visit_provides_module_directive(self,node):
        index=[0]
        self.child(node,index,'provides')
        self.field(node,index,field_name='provided',child_type='_name')
        self.child(node,index,'with')
        self.child(node,index,'_name')
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': [',', {'type': 'field()', 'params': {'field_name': 'provider', 'child_type': '_name'}}]}})
        self.child(node,index,';')
        return index

    def visit_package_declaration(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        self.child(node,index,'package')
        self.child(node,index,'_name')
        self.child(node,index,';')
        return index

    def visit_import_declaration(self,node):
        index=[0]
        self.child(node,index,'import')
        self.optional(node,index,child_type='static')
        self.child(node,index,'_name')
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['.', 'asterisk']}})
        self.child(node,index,';')
        return index

    def visit_asterisk(self,node):
        index=[0]
        self.child(node,index,'*')
        return index

    def visit_enum_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'enum')
        self.field(node,index,field_name='name',child_type='identifier')
        # self.field(node,index,field_name='interfaces',child_type={'type': 'optional()', 'params': {'child_type': 'super_interfaces'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"super_interfaces",'field_name':"interfaces"}})
        self.field(node,index,field_name='body',child_type='enum_body')
        return index

    def visit_enum_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.commaSep(node,index,child_type='enum_constant')
        self.optional(node,index,child_type=',')
        self.optional(node,index,child_type='enum_body_declarations')
        self.child(node,index,'}')
        return index

    def visit_enum_body_declarations(self,node):
        index=[0]
        self.child(node,index,';')
        self.repeat(node,index,child_type='_class_body_declaration')
        return index

    def visit_enum_constant(self,node):
        index=[0]
        self.optional(node,index,'modifiers')
        self.field(node,index,'identifier',field_name='name')
        # self.field(node,index,child_type={'type': 'optional()', 'params': {'child_type': 'argument_list'}},field_name='arguments')
        self.optional(node,index,child_type={"type":"field()","params":{"field_name":"arguments","child_type":"argument_list"}})
        # self.field(node,index,child_type={'type': 'optional()', 'params': {'child_type': 'class_body'}},field_name='body')
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"class_body","field_name":"body"}})
        return index

    def visit_class_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'class')
        self.field(node,index,field_name='name',child_type='identifier')
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'type_parameters', 'child_type': 'type_parameters'}})
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'superclass', 'child_type': 'superclass'}})
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'interfaces', 'child_type': 'super_interfaces'}})
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'permits', 'child_type': 'permits'}})
        self.field(node,index,field_name='body',child_type='class_body')
        return index

    def visit_modifiers(self,node):
        index=[0]
        self.repeat(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['_annotation', 'public', 'protected', 'private', 'abstract', 'static', 'final', 'strictfp', 'default', 'synchronized', 'native', 'transient', 'volatile', 'sealed', 'non-sealed']}},target=1)
        return index

    def visit_type_parameters(self,node):
        index=[0]
        self.child(node,index,'<')
        self.commaSep1(node,index,child_type='type_parameter')
        self.child(node,index,'>')
        return index

    def visit_type_parameter(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        with self.alias(old_type='identifier',new_type='type_identifier'):
            self.child(node,index,child_type='type_identifier')
        self.optional(node,index,child_type='type_bound')
        return index

    def visit_type_bound(self,node):
        index=[0]
        self.child(node,index,'extends')
        self.child(node,index,'_type')
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['&', '_type']}})
        return index

    def visit_superclass(self,node):
        index=[0]
        self.child(node,index,'extends')
        self.child(node,index,'_type')
        return index

    def visit_super_interfaces(self,node):
        index=[0]
        self.child(node,index,'implements')
        self.child(node,index,'type_list')
        return index

    def visit_type_list(self,node):
        index=[0]
        self.child(node,index,'_type')
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': [',', '_type']}})
        return index

    def visit_permits(self,node):
        index=[0]
        self.child(node,index,'permits')
        self.child(node,index,'type_list')
        return index

    def visit_class_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.child(node,index,"_indent")
        self.repeat(node,index,child_type='_class_body_declaration')
        self.child(node,index,"_dedent")
        self.child(node,index,'}')
        return index

    @inline
    def visit__class_body_declaration(self,node,index):
        self.choice(node,index,child_types=['field_declaration', 'record_declaration', 'method_declaration', 'compact_constructor_declaration', 'class_declaration', 'interface_declaration', 'annotation_type_declaration', 'enum_declaration', 'block', 'static_initializer', 'constructor_declaration', ';'])
        return index

    def visit_static_initializer(self,node):
        index=[0]
        self.child(node,index,'static')
        self.child(node,index,'block')
        return index

    def visit_constructor_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'_constructor_declarator')
        self.optional(node,index,child_type='throws')
        self.field(node,index,field_name='body',child_type='constructor_body')
        return index

    @inline
    def visit__constructor_declarator(self,node,index):
        # self.field(node,index,field_name='type_parameters',child_type={'type': 'optional()', 'params': {'child_type': 'type_parameters'}})
        self.optional(node,index,child_type={"type":"field()","params":{"field_name":"type_parameters","child_type":"type_parameters"}})
        self.field(node,index,field_name='name',child_type='identifier')
        self.field(node,index,field_name='parameters',child_type='formal_parameters')
        return index

    def visit_constructor_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.optional(node,index,child_type='explicit_constructor_invocation')
        self.repeat(node,index,child_type='statement')
        self.child(node,index,'}')
        return index

    def visit_explicit_constructor_invocation(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'optional()', 'params': {'child_type': {'type': 'field()', 'params': {'child_type': 'type_arguments','field_name': 'type_arguments'}}}}, {'type': 'field()', 'params': {'field_name': 'constructor', 'child_type': {'type': 'choice()', 'params': {'child_types': ['this', 'super']}}}}]}}, {'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'object', 'child_type': {'type': 'choice()', 'params': {'child_types': ['primary_expression']}}}}, '.', {'type': 'optional()', 'params': {'child_type': {'type': 'field()', 'params': {'child_type': 'type_arguments','field_name': 'type_arguments'}}}}, {'type': 'field()', 'params': {'field_name': 'constructor', 'child_type': 'super'}}]}}])
        self.field(node,index,field_name='arguments',child_type='argument_list')
        self.child(node,index,';')
        return index

    @inline
    def visit__name(self,node,index):
        self.choice(node,index,child_types=['identifier', '_reserved_identifier', 'scoped_identifier'])
        return index

    def visit_scoped_identifier(self,node):
        index=[0]
        self.field(node,index,field_name='scope',child_type='_name')
        self.child(node,index,'.')
        self.field(node,index,field_name='name',child_type='identifier')
        return index

    def visit_field_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        self.child(node,index,'_variable_declarator_list')
        self.child(node,index,';')
        return index

    def visit_record_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'record')
        self.field(node,index,field_name='name',child_type='identifier')
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'type_parameters', 'child_type': 'type_parameters'}})
        self.field(node,index,field_name='parameters',child_type='formal_parameters')
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'interfaces', 'child_type': 'super_interfaces'}})
        self.field(node,index,field_name='body',child_type='class_body')
        return index

    def visit_annotation_type_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'@interface')
        self.field(node,index,field_name='name',child_type='identifier')
        self.field(node,index,field_name='body',child_type='annotation_type_body')
        return index

    def visit_annotation_type_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.repeat(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['annotation_type_element_declaration', 'constant_declaration', 'class_declaration', 'interface_declaration', 'enum_declaration', 'annotation_type_declaration', ';']}})
        self.child(node,index,'}')
        return index

    def visit_annotation_type_element_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        self.field(node,index,field_name='name',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}})
        self.child(node,index,'(')
        self.child(node,index,')')
        # self.field(node,index,field_name='dimensions',child_type={'type': 'optional()', 'params': {'child_type': 'dimensions'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"dimensions","field_name":"dimensions"}})
        self.optional(node,index,child_type='_default_value')
        self.child(node,index,';')
        return index

    @inline
    def visit__default_value(self,node,index):
        self.child(node,index,'default')
        self.field(node,index,field_name='value',child_type='_element_value')
        return index

    def visit_interface_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'interface')
        self.field(node,index,field_name='name',child_type='identifier')
        # self.field(node,index,field_name='type_parameters',child_type={'type': 'optional()', 'params': {'child_type': 'type_parameters'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"type_parameters","field_name":"type_parameters"}})
        self.optional(node,index,child_type='extends_interfaces')
        self.optional(node,index,child_type={'type': 'field()', 'params': {'field_name': 'permits', 'child_type': 'permits'}})
        self.field(node,index,field_name='body',child_type='interface_body')
        return index

    def visit_extends_interfaces(self,node):
        index=[0]
        self.child(node,index,'extends')
        self.child(node,index,'type_list')
        return index

    def visit_interface_body(self,node):
        index=[0]
        self.child(node,index,'{')
        self.repeat(node,index,child_type={'type': 'choice()', 'params': {'child_types': ['constant_declaration', 'enum_declaration', 'method_declaration', 'class_declaration', 'interface_declaration', 'record_declaration', 'annotation_type_declaration', ';']}})
        self.child(node,index,'}')
        return index

    def visit_constant_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        self.child(node,index,'_variable_declarator_list')
        self.child(node,index,';')
        return index

    @inline
    def visit__variable_declarator_list(self,node,index):
        self.commaSep1(node,index,child_type={'type': 'field()', 'params': {'field_name': 'declarator', 'child_type': 'variable_declarator'}})
        return index

    def visit_variable_declarator(self,node):
        index=[0]
        self.child(node,index,'_variable_declarator_id')
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['=', {'type': 'field()', 'params': {'field_name': 'value', 'child_type': '_variable_initializer'}}]}})
        return index

    @inline
    def visit__variable_declarator_id(self,node,index):
        self.field(node,index,field_name='name',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier', 'underscore_pattern']}})
        # self.field(node,index,field_name='dimensions',child_type={'type': 'optional()', 'params': {'child_type': 'dimensions'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"dimensions","field_name":"dimensions"}})
        return index

    @inline
    def visit__variable_initializer(self,node,index):
        self.choice(node,index,child_types=['expression', 'array_initializer'])
        return index

    def visit_array_initializer(self,node):
        index=[0]
        self.child(node,index,'{')
        self.commaSep(node,index,child_type='_variable_initializer')
        self.optional(node,index,child_type=',')
        self.child(node,index,'}')
        return index

    @inline
    def visit__type(self,node,index):
        self.choice(node,index,child_types=['_unannotated_type', 'annotated_type'])
        return index

    @inline
    def visit__unannotated_type(self,node,index):
        self.choice(node,index,child_types=['_simple_type', 'array_type'])
        return index

    @inline
    def visit__simple_type(self,node,index):
        self.choice(node,index,child_types=['void_type', 'integral_type', 'floating_point_type', 'boolean_type', {'type': 'alias()', 'params': {'old_type': 'identifier', 'new_type': 'type_identifier'}}, 'scoped_type_identifier', 'generic_type'])
        return index

    def visit_annotated_type(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation',target=1)
        self.child(node,index,'_unannotated_type')
        return index

    def visit_scoped_type_identifier(self,node):
        index=[0]
        self.choice(node,index,child_types=[{'type': 'alias()', 'params': {'old_type': 'identifier', 'new_type': 'type_identifier'}}, 'scoped_type_identifier', 'generic_type'])
        self.child(node,index,'.')
        self.repeat(node,index,child_type='_annotation')
        with self.alias(old_type='identifier',new_type='type_identifier'):
            self.child(node,index,"type_identifier")
        return index

    def visit_generic_type(self,node):
        index=[0]
        self.seq(node,index,child_types=[{'type': 'choice()', 'params': {'child_types': [{'type': 'alias()', 'params': {'old_type': 'identifier', 'new_type': 'type_identifier'}}, 'scoped_type_identifier']}}, 'type_arguments'])
        return index

    def visit_array_type(self,node):
        index=[0]
        self.field(node,index,field_name='element',child_type='_unannotated_type')
        self.field(node,index,field_name='dimensions',child_type='dimensions')
        return index

    def visit_integral_type(self,node):
        index=[0]
        self.choice(node,index,child_types=['byte', 'short', 'int', 'long', 'char'])
        return index

    def visit_floating_point_type(self,node):
        index=[0]
        self.choice(node,index,child_types=['float', 'double'])
        return index

    def visit_boolean_type(self,node):
        index=[0]
        self.child(node,index,'_node_content')
        return index

    def visit_void_type(self,node):
        index=[0]
        self.child(node,index,'_node_content')
        return index

    @inline
    def visit__method_header(self,node,index):
        self.optional(node,index,child_type={'type': 'seq()', 'params': {'child_types': [{'type': 'field()', 'params': {'field_name': 'type_parameters', 'child_type': 'type_parameters'}}, {'type': 'repeat()', 'params': {'child_type': '_annotation'}}]}})
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        # self.child(node,index,"_space")
        self.child(node,index,'_method_declarator')
        self.optional(node,index,child_type='throws')
        return index

    @inline
    def visit__method_declarator(self,node,index):
        self.field(node,index,field_name='name',child_type={'type': 'choice()', 'params': {'child_types': ['identifier', '_reserved_identifier']}})
        self.field(node,index,field_name='parameters',child_type='formal_parameters')
        # self.field(node,index,field_name='dimensions',child_type={'type': 'optional()', 'params': {'child_type': 'dimensions'}})
        self.optional(node,index,child_type={"type":"field()","params":{"child_type":"dimensions","field_name":"dimensions"}})
        return index

    def visit_formal_parameters(self,node):
        index=[0]
        self.child(node,index,'(')
        self.set_target(node,self.find_children_position(node,index[0],')'))
        self.choice(node,index,child_types=[{'type': 'seq()', 'params': {'child_types': [{'type': 'optional()', 'params': {'child_type': {'type': 'seq()', 'params': {'child_types': ['receiver_parameter', ',']}}}}, {'type': 'commaSep()', 'params': {'child_type': {'type': 'choice()', 'params': {'child_types': ['formal_parameter', 'spread_parameter']}}}}]}},'receiver_parameter'])
        self.child(node,index,')')
        return index

    def visit_formal_parameter(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        # self.child(node,index,"_space")
        self.child(node,index,'_variable_declarator_id')
        return index

    def visit_receiver_parameter(self,node):
        index=[0]
        self.repeat(node,index,child_type='_annotation')
        self.child(node,index,'_unannotated_type')
        self.repeat(node,index,child_type={'type': 'seq()', 'params': {'child_types': ['identifier', '.']}})
        self.child(node,index,'this')
        return index

    def visit_spread_parameter(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'_unannotated_type')
        self.child(node,index,'...')
        self.repeat(node,index,child_type='_annotation')
        self.child(node,index,'variable_declarator')
        return index

    def visit_throws(self,node):
        index=[0]
        # self.child(node,index,"_space")
        self.child(node,index,'throws')
        self.commaSep1(node,index,child_type='_type')
        return index

    def visit_local_variable_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='type',child_type='_unannotated_type')
        # self.child(node,index,"_space")
        self.child(node,index,'_variable_declarator_list')
        self.child(node,index,';')
        return index

    def visit_method_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.child(node,index,'_method_header')
        self.choice(node,index,child_types=[{'type': 'field()', 'params': {'field_name': 'body', 'child_type': 'block'}}, ';'])
        self.child(node,index,"_newline")
        return index

    def visit_compact_constructor_declaration(self,node):
        index=[0]
        self.optional(node,index,child_type='modifiers')
        self.field(node,index,field_name='name',child_type='identifier')
        self.field(node,index,field_name='body',child_type='block')
        return index

    @inline
    def visit__reserved_identifier(self,node,index):
        old_types=["open","module",'record','with','sealed','yield']
        self.choice(node,index=index,child_types=[{"type":"alias()","params":{"old_type":t,"new_type":"identifier","is_old_func":True}} for t in old_types])
        return index

    def visit_this(self,node):
        index=[0]
        self.child(node,index,'_node_content')
        return index
    
    def visit_super(self,node):
        index=[0]
        self.child(node,index,'_node_content')
        return index

    def visit_identifier(self,node):
        index=[0]
        self.write(str(node.text,encoding='utf8'))
        return index

    def visit_line_comment(self,node):
        index=[0]
        # self.child(node,index,"_newline")
        self.child(node,index,child_type='_node_content')
        # self.child(node,index,"_newline")
        self.maybe_newline()
        return index

    def visit_block_comment(self,node):
        index=[0]
        self.child(node,index,child_type='_node_content')
        self.child(node,index,child_type="_newline")
        return index

    #externals
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

    @inline
    def visit__indent(self,node,index):
        self.change_indent(4)
        self.maybe_newline()

    @inline
    def visit__dedent(self,node,index):
        self.change_indent(-4)
        self.maybe_newline()

    @inline
    def visit__string_token(self,node,index):#TODO: change the python implementation
        def convert_point_to_index(point):
            start_point=node.start_point if hasattr(node, 'start_point') else node.origin_node.start_point
            if(point[0]==start_point[0]):
                return point[1]-start_point[1]
            else:
                node_str=node.text.decode("utf-8")
                lines=node_str.split("\n")
                return sum([len(l)+1 for l in lines[:point[0]-start_point[0]]])+point[1]

        if(index[0]>0):
            prev_end_point=node.children[index[0]-1].end_point if hasattr(node.children[index[0]-1], 'end_point') else node.children[index[0]-1].origin_node.end_point
            cur_start_point=node.children[index[0]].start_point if hasattr(node.children[index[0]], 'start_point') else node.children[index[0]].origin_node.start_point
            if(prev_end_point!=cur_start_point):
                #get the content between
                node_str=node.text.decode("utf-8")
                content=node_str[convert_point_to_index(prev_end_point):convert_point_to_index(cur_start_point)]
                self.write(content)
        return index