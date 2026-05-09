## GramVarKit: A Rule-Driven Toolkit Generator for Exploring AI-Oriented Grammar Variants
### Introduction
GramVarKit is a configurable tool designed to simplify the development of toolkits for AI-oriented grammars. 
Built on top of [tree-sitter](https://github.com/tree-sitter/tree-sitter), GramVarKit generates two parsers and two unparsers. The parsers convert source code into parse trees, while the unparsers perform grammar-aware conversions during the unparsing process. By specifying grammar differences in a user-defined configuration file, users can define how code should be transformed without manually implementing the conversion logic.

### Prerequisites
The [tree-sitter](https://github.com/tree-sitter/tree-sitter) CLI and its [Python bindings](https://github.com/tree-sitter/py-tree-sitter) are required.

### Configuration file
The configuration file defines the grammar differences between the original and the new grammar. It consists of four sections: `import`,`both`,`ori_to_new` and `new_to_ori`.

`import` specifies a list of additional transformation rule files to be included, allowing modular rule organization.

The basic bidirectional transformation rules are contained in the `both` section, which will be parsed into two sets of conversion rules for conversions in both directions.

`ori_to_new` and `new_to_ori` contain unidirectional rules.

#### Basic transform rules
Basic transform rules can be used to describe how new grammar rules differ from their corresponding original grammar rules when only terminal symbols (represented as simple strings in the grammar file) are modified. The attribute `prod_rule` refers to the name of the rule, while `original` and `new` specify the differing parts.

##### Keyword replacement
In tree-sitter, grammar rules are written in JavaScript. For example, consider the rule for defining `import_statement` in Python.
Original grammar rule:
```
import_statement: $ => seq(
    'import',
    $._import_list,
)
```
New grammar rule:
```
import_statement: $ => seq(
    '<import_stmt>',
    $._import_list,
)
```
In this case, the keyword `import` in the original grammar is transformed to `<import_stmt>` in the new grammar. The corresponding transform rule is:
```
{"prod_rule":"import_statement","original":"import","new":"<import_stmt>"}
```

##### Handling multiple keywords
In some cases, keywords do not have an one-to-one correspondence. For example, the `if_statement` rule in Python:
```
if_statement: $ => seq(
    'if',
    field('condition', $.expression),
    ':',
    field('consequence', $._suite),
    repeat(field('alternative', $.elif_clause)),
    optional(field('alternative', $.else_clause)),
)
```
The new grammar rule:
```
if_statement: $ => seq(
    '<if_stmt>',
    field('condition', $.expression),
    field('consequence', $._suite),
    repeat(field('alternative', $.elif_clause)),
    optional(field('alternative', $.else_clause)),
)
```
Here, the keyword `if` is transformed to `<if_stmt>`, and the `:` is removed. The transform rule is:
```
{"prod_rule":"if_statement","original":["if",{"field":"condition","anchor":true},":"],"new":["<if_stmt>",{"field":"condition","anchor":true}]}
```
Elements in the `original` and `new` lists must appear in the same order as they do in the grammar, with no elements skipped.

We introduce anchor points to provide positional references by setting the `anchor` attribute to `true`. These symbols remain unchanged during the transformation.
The number of anchors in `original` and `new` should be the same and have one-to-one correspondence in order.

In this example, the keyword `:` is added after the children whose field name is `condition` when transforming from new grammar back to the original. 

##### Handling optional keywords
When working with elements that don't necessarily appear in the parse tree (such as those within the `optional` or `repeat` functions), rules should be written separately for each individual part. This ensures that the transformation can handle cases where those elements are absent in the parse tree.

Original rule for `with_statement`:
```
with_statement: $ => seq(
    optional('async'),
    'with',
    $.with_clause,
    ':',
    field('body', $._suite),
)
```
New rule:
```
with_statement: $ => seq( 
    optional('<async_keyword>'),
    '<with_stmt>',
    $.with_clause,
    field('body', $._suite),
)
```
The problematic transformation rule:
```
{"prod_rule":"with_statement","original":["async","with",{"type":"$with_clause","anchor":true},":"],"new":["<async_keyword>","<with_stmt>",{"type":"$with_clause","anchor":true}]}
```
In the rule above, `async` is expected to appear directly before the keyword `with`. If `async` does not appear in the original parse tree, the transformation rule will not trigger, and the subsequent transformation from `with` to `<with_stmt>` will not take place.

Instead, we need to separate the transformation of `async` and the transformation of `with` to ensure that each transformation is handled independently. This way, the absence of `async` does not interfere with transforming `with`.
Correct transformation rules:
```
{"prod_rule":"with_statement","original":"async","new":"<async_keyword>"},
{"prod_rule":"with_statement","original":["with",{"type":"$with_clause","anchor":true},":"],
    "new":["<with_stmt>",{"type":"$with_clause","anchor":true}]}
```
The symbol `$` preceding `$with_clause` indicates that this refers to a non-terminal symbol, specifically the `with_clause` rule.

##### Attributes
Expressing an element as a simple string, such as `"if"`, is equivalent to specifying its type, e.g., `{"type":"if"}`. Elements can also include other attributes for more accurate positioning.
For the `parameters` rule, the original grammar rule is:
```
parameters: $ => seq(
    '(',
    optional($._parameters),
    ')',
)
```
The new grammar rule:
```
parameters: $ => seq(
    optional($._parameters),
)
``` 
The transform rules are:
```
{"prod_rule":"parameters","original":[{"type":"(","prev_sibling":null},{"anchor":true}],"new":[{"anchor":true,"prev_sibling":null}]},

{"prod_rule":"parameters","original":[{"anchor":true},{"type":")","next_sibling":null}],"new":[{"anchor":true,"next_sibling":null}]}
```
By assigning the `null` value to attribute `prev_sibling`, `(` is only removed if it is the first child of the parameters node. Similarly, `")"` is deleted if it is the last child.

The list of all attributes available:
```
'type','field','prev_sibling','prev_sibling_field','next_sibling','next_sibling_field'
```

##### Generated conversion rules
Based on the basic transformation rules defined in the `both` section, GramVarKit automatically generates two sets of conversion rules: one for original-to-new transformation and the other for new-to-original transformation.

Each generated rule may carry a `content` attribute, which provides the necessary symbol information for insertion or replacement operations. This content can be a simple string, a JSON object, or a list of symbols. For nonterminal symbols, fully describing its content is required since simply specifying the symbol type is insufficient for generating valid code during unparsing.

#### Unidirectional conversion rules
Unidirectional rules handle cases where changes in one direction do not need to be fully reversed.
For example, the original grammar rule for `future_import_statement` is:
```
future_import_statement: $ => seq(
    'from',
    '__future__',
    'import',
    choice(
    $._import_list,
    seq('(', $._import_list, ')'),
    ),
)
```
The new grammar rule is:
```
future_import_statement: $ => seq(
    '<import_from_future_stmt>',
    choice(
    $._import_list,
    // seq('(', $._import_list, ')'),
    ),
)
```
In this case, the parentheses should be removed when transforming from the original grammar to the new one. However, it is not necessary to reinsert them when transforming from the new grammar back to the original one. Therefore, the transform rules are defined in the `ori_to_new` section:
```
{"condition":{"parent_type":"future_import_statement","type":"("},"action":"delete"},
{"condition":{"parent_type":"future_import_statement","type":")"},"action":"delete"}
```

#### Custom rules
For more complex conversions beyond basic edits of terminal symbols, custom conversion functions can be defined in `src/custom_rules`.

GramVarKit also supports custom grammar modifications during new grammar generation, which can be defined in `src/custom_grammar`.

##### Transforming from original grammar to the new one
For example, to separate two statements using either `<line_sep>` or comments, the conversion rule would be:
```
{"condition":{"type":"$_statement","prev_sibling":"$_statement"},"action":"custom_before","content":"choice_comment_line_sep"}
```
- `action` can be `custom_before` or `custom_after`, indicating whether the function should be executed before or after the element is visited.
- `content` specifies the name of the custom function.

Inline rules in tree-sitter do not create nodes in the syntax tree, so if `prev_sibling` refers to inline rule names, it will be transformed to all possible node types that can serve as the first node of the inline rule. The same applies to `next_sibling`.

For rules transforming from the original grammar to the new one, `prev_sibling_inline` can be used as an alternative. This allows the conversion rule to also be written as:
```
{"condition":{"type":"$_statement","prev_sibling_inline":"$_statement"},"action":"custom_before","content":"choice_comment_line_sep"}
```

The function `choice_comment_line_sep` is defined as follows:
```
@writing_op
def choice_comment_line_sep(self,node,**kwargs):
    if(self.comments):
        self.maybe_newline(add_comment=True)
    else:
        self.write("<line_sep>")
```
- The first argument of the function, `self`, refers to the unparser instance. 
- The `node` parameter represents the current node being processed.

The following functions can be used to modify the regenerated code:
- `write(self,text)` appends the `text` to the generated code.
- `write_comment(self,comment_content)` writes the `comment_content` if it is at the start of a new line, otherwise records the comment. 
- `maybe_newline(self,add_comment)` starts a new line in the generation process. If `add_comment` is set to `True`, recorded comments are appended to the end of the previous line if they exist.
- `maybe_indent(self)` writes indentation at the beginning of a new line.
- `maybe_space(self)` appends a space to the code.
- `change_indent(self,delta)` changes the level of indentation.
If any of the above functions are called in the custom conversion function, the annotation `@writing_op` should be used.

##### Transfroming from new grammar to the original one
For the `function_definition` rule, the original grammar is:
```
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
)
```
The new grammar rule:
```
function_definition: $ => seq(
    optional('<async_keyword>'),
    '<def_stmt>',
    field('name', $.identifier),
    field('type_parameters', optional($.type_parameter)),
    field('parameters', optional(alias($._parameters, $.parameters))),
    optional(
    seq(
        '<arrow>',
        field('return_type', $.type),
    ),
    ),
    field('body', $._suite),
)
```
If the parameters of the function definition are empty, the syntax node `parameters` will be missing in the new parse tree and needs to be inserted.

The conversion rule for this insertion is:
```
{"condition":{"parent_type":"function_definition","type":"$identifier","field":"name"},"action":"custom_after","content":"empty_parameters"}
```
The definition of the custom conversion function `empty_parameters` is:
```
def empty_parameters(self,index,**args):
    assert self.children[index].type=='identifier'
    new_index=index
    if(self.children[new_index+1].type=='type_parameter'): # type_parameter is optional
        new_index=new_index+1
    if(self.children[new_index+1].type!='parameters'):
        parameter_node=TreeNode(type="parameters",is_named=True,children=[StringNode("("),StringNode(")")],field_names=[None,None],text=b'()')
        self.children.insert(new_index+1,parameter_node)
        self.aux_infs.insert(new_index+1,AuxInf(field_name="parameters"))
    return index
```
- `self.children` refers to the list of children of the syntax node `function_definition`.
- `self.aux_infs` stores information about the child node, such as its field name.
- The return value of the function should point to the same element that the original argument `index` referred to at the beginning of the function. In this example, the `parameters` node is inserted after the `identifier` node, thus the position of `identifier` remains unchanged, and the same `index` is returned.

The `params` attribute in custom conversion rules specifies the arguments that will be passed to the custom conversion function.
For example, to modify the `text` of the syntax node `true`, the conversion rule would be:
```
{"condition":{"type":"$true"},"action":"custom_replace","content":"text_replace","params":{"text":"True"}}
```
The definition of the custom conversion function `text_replace` is:
```
def text_replace(self,index,**args):
    text=args['text']
    node_type=self.children[index].type
    self.children[index]=TreeNode(node_type,True,list(),list(),text.encode("utf8"))
    return index
```

##### Formatting
`$_space` refers to spaces added during the unparsing process to delimit tokens. To eliminate these spaces, use the following conversion rule:
```
{"condition":{"type":"$_space"},"action":"delete"}
```

### Running GramVarKit
To begin using GramVarKit, first download the grammar file for the original grammar provided by tree-sitter.

#### Parsing the configuration file
To generate the rules for transforming between the original and new grammar formats, run the following command:
```
python parse_configuration.py --rule_path ${path_of_configuration_file}
```
This will generate three JSON files:
- The `*.ori_to_new.json` file contains rules for transforming code from the original grammar to the new grammar.
- The `*.new_to_ori.json` file contains rules for transforming code from the new grammar to the original grammar.
- The `*.customs.json` file contains all the custom conversion functions used in the process.

Some generated rules may be invalid:
- If a rule has an empty `condition`.
- If there are multiple rules with the same `condition` and `action`, only one will be retained.

During postprocessing, certain conditions may be modified:
- If `prev_sibling` or `next_sibling` references an inline rule name, it will be expanded to all possible node types that can be the last or first node of the inline rule, respectively.
- If `new_to_ori` conversion rules include a `type` condition referring to an inline rule name with an `insert_before` action, it will be transformed similarily as above.
- For `new_to_ori` rules, if the `type` condition refers to an inline rule name, the `next_sibling` condition will be removed.

#### Generating the new parser
Once the transformation rules are parsed, they will be applied to update the `grammar.json` file. 
For complicated cases, such as those requiring custom conversion functions, the corresponding transformation rules may not be applied to the grammar automatically and will be flagged for manual handling.

The paths for the original grammar file and the new grammar file are defined in `config.json`. Ensure that these paths are correctly set before proceeding.

To regenerate the parser based on the updated grammar file, run the following command:
```
tree-sitter generate ${path_of_new_grammar_json}
```
After successfully generating the parser, use the following API call to build the dynamic library:
```
from tree_sitter import Language
Language.build_library()
```

#### Building the unparser
To build the unparser, import the following:
```
from src.build_unparser import build_unparser
```
To transform from the original grammar to new grammar:
```
unparser=build_unparser(ori_to_new=True,new_to_ori=False,filepath=${path_of_ori_to_new_conversion_rule_file})
unparser.unparse(parse_tree)
```
`parse_tree` refers to the parse tree generated by tree-sitter.

To transform from the new grammar to original grammar:
```
unparser=build_unparser(ori_to_new=False,new_to_ori=True,filepath=${path_of_new_to_ori_conversion_rule_file})
unparser.unparse(parse_tree)
```
