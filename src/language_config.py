class PythonConfig:
    extras=['comment',"line_continuation"]
    zero_len_tokens=['_indent','_dedent',"_newline","_string_content","_space","_start_line","_space_line","_node_content"]
    inline_symbols=['_as_pattern', '_collection_elements', '_compound_statement', '_comprehension_clauses', 
                    '_dedent', '_expression_within_for_in_clause', '_expressions', '_f_expression', '_import_list', 
                    '_indent', '_is_not', '_key_value_pattern', '_left_hand_side', '_list_pattern', '_match_block', 
                    '_named_expression_lhs', '_newline', '_node_content', '_not_escape_sequence', '_not_in', 
                    '_parameters', '_patterns', '_right_hand_side', '_simple_pattern', '_simple_statement', 
                    '_simple_statements', '_space', '_space_line', '_start_line', '_statement', '_string_content', 
                    '_suite', '_tuple_pattern', 'expression', 'keyword_identifier', 'parameter', 'pattern', 
                    'primary_expression']
    externals=["_indent","_dedent","string_start","string_end","_newline","comment","_string_content","escape_interpolation"]
    custom_externals=["_space","_start_line","_space_line","_node_content"]
    supertypes=["_simple_statement","_compound_statement","expression","primary_expression",
                "pattern","parameter"]

class JavaConfig:
    extras=["line_comment","block_comment"]
    zero_len_tokens=["_space","_start_line","_space_line","_node_content","_newline","_indent","_dedent","_string_token"]
    externals=[]
    custom_externals=["_space","_start_line","_space_line","_node_content","_newline","_indent","_dedent","_string_token"]
    supertypes=["expression","declaration","statement","primary_expression","_literal","_type","_simple_type","_unannotated_type","module_directive"]
    inline_symbols=['_annotation', '_class_body_declaration', '_constructor_declarator', '_default_value', '_element_value', '_escape_sequence', '_literal', '_method_declarator', '_method_header', '_multiline_string_fragment', '_multiline_string_literal', '_name', '_reserved_identifier', '_simple_type', '_string_literal', '_toplevel_statement', '_type', '_unannotated_type', '_unqualified_object_creation_expression', '_variable_declarator_id', '_variable_declarator_list', '_variable_initializer', '_wildcard_bounds', 'declaration', 'expression', 'module_directive', 'primary_expression', 'statement',
                    '_space','_start_line','_space_line','_node_content','_newline','_indent','_dedent','_string_token']

import json
with open("config.json",'r') as f:
    config=json.load(f)
if(config['language']=='python'):
    language_config=PythonConfig
elif(config['language']=='java'):
    language_config=JavaConfig
else:
    raise NotImplementedError(f"language {config['language']} not implemented")