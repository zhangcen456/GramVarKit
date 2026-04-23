from .BaseUnparser import BaseUnparser,writing_op,inline,Wrapper,CustomException

class PythonUnparser(BaseUnparser):
    def __init__(self,py_to_spy=False,spy_to_py=False,rule_path=None):
        super().__init__(py_to_spy,spy_to_py,rule_path)
        self.rule_path=rule_path
        self.indent=0

    def clear(self):
        super().clear()
        self.indent=0

    def reset(self):
        super().reset()
        self.indent=0

    @writing_op
    def write(self,text):
        def need_split(current_line,start_char):
            if(self.context['rule'] in ["string","string_content"]):
                return False
            if(self.context['rule']=="string_start" and len(current_line)>=2 and current_line[-2:]=='""' and start_char=='"'):
                return True
            end_char=current_line[-1]
            return (end_char.isalnum() or end_char in ["_"]) and (start_char.isalnum() or start_char in ["_"])

        if(self.current_line and text and need_split(self.current_line,text[0])):
            self.current_line+=" "
        self.current_line+=text

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
        choice_params={"child_types":[{"type":"list_splat"},{"type":"expression"},{"type":"dictionary_splat"},{"type":"alias()","params":alias_params},{"type":"keyword_argument"}]}
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
        self.choice(node,index,child_types=[{"type":"alias()","params":{"old_type":"lambda_within_for_in_clause","new_type":"lambda"}},{"type":"expression"}])
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
        choice_child_types=[{"type":"seq()","params":{"child_types":[{"type":"field()","params":field_left_params},{"type":"field()","params":{"child_type":operator[i],"field_name":"operator"}},{"type":"field()","params":field_right_params}]}} for i in range(len(operator))]
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
        if(node.children[0].type=='integer'):
            self.child(node,index,"_space")
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
        types=["yield","list_splat","parenthesized_list_splat","expression"]
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