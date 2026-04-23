import json
from .unparser import *
from .wrapper import Wrapper
from .parse_config import register_custom_rules

def build_unparser(ori_to_new,new_to_ori,filepath):
    with open("config.json",'r') as f:
        config=json.load(f)
        if(config['language']=='python'):
            unparser_class=PythonUnparser
        elif(config['language']=='java'):
            unparser_class=JavaUnparser
        else:
            raise NotImplementedError(f"language {config['language']} not implemented")
    assert not ori_to_new or not new_to_ori
    if(ori_to_new):
        if(not filepath.endswith("ori_to_new.json")):
            if(filepath.endswith(".json")):
                custom_path=filepath.replace(".json",".customs.json")
                filepath=filepath.replace(".json",".ori_to_new.json")
            else:
                custom_path=filepath+".customs.json"
                filepath+=".ori_to_new.json"
        else:
            custom_path=filepath.replace(".ori_to_new.json",".customs.json")
        with open(custom_path,'r') as f:
            custom_names=json.load(f)
        register_custom_rules(unparser_class,custom_names["ori_to_new"])
        unparser_class.load_transfer_rules(filepath)
        unparser=unparser_class(True,False,filepath)
    elif(new_to_ori):
        if(not filepath.endswith("new_to_ori.json")):
            if(filepath.endswith(".json")):
                custom_path=filepath.replace(".json",".customs.json")
                filepath=filepath.replace(".json",".new_to_ori.json")
            else:
                custom_path=filepath+".customs.json"
                filepath+=".new_to_ori.json"
        else:
            custom_path=filepath.replace(".new_to_ori.json",".customs.json")
        with open(custom_path,'r') as f:
            custom_names=json.load(f)
        register_custom_rules(Wrapper,custom_names['new_to_ori'])
        unparser_class.load_transfer_rules(filepath)
        unparser=unparser_class(False,True,filepath)
    else:
        unparser=unparser_class(False,False)
    return unparser