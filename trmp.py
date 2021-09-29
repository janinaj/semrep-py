#=just output w/json.dumps &formatting from process_text in main instead of below

#output not processable by jq so
#https://stackoverflow.com/questions/7001606/json-serialize-a-dictionary-with-tuples-as-key
def remap_keys(mapping):
    return [{'key':k, 'value': v} for k, v in mapping.iteritems()] 
