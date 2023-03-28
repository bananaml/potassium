# detect if users environment contains the right packages for model detection
# yes, this is hacky
has_framework = {
    "torch": False,
    "transformers": False
}
try:
    import torch
    has_framework["torch"] = True
except:
    pass
try:
    import transformers
    has_framework["transformers"] = True
except:
    pass

def find_models(context: dict):
    models = []
    drill_dict(context, [], models)
    return models

def assess(item, path, opt_targets):

    if item == None:
        return

    # ignore floats, ints, strings, bools
    if isinstance(item, (float, int, str, bool)):
        return
    
    # test for pytorch instance
    if has_framework["torch"]:
        if isinstance(item, torch.nn.Module):
            opt_target = {
                "model": item,
                "context_path": path
            }
            opt_targets.append(opt_target)
            return

    # test for known complex objects to extract pytorch models
    if has_framework["transformers"]:
        if isinstance(item, transformers.Pipeline):
            # transformers pipelines keep it in the .model
            opt_target = {
                "model": item.model,
                "context_path": path
            }
            opt_targets.append(opt_target)
            return

def drill_list(item_list, path, opt_targets):
    for i, v in enumerate(item_list):
        item_path = path.copy()
        item_path.append(i)
        # depth first drill into dict/list tree
        if isinstance(v, dict):
            drill_dict(v, item_path, opt_targets)
        if isinstance(v, (list, tuple)):
            drill_list(v, item_path, opt_targets)
        assess(v, item_path, opt_targets)

def drill_dict(dictionary, path, opt_targets):
    for k, v in dictionary.items():
        item_path = path.copy()
        item_path.append(k)
        # depth first drill into dict/list tree
        if isinstance(v, dict):
            drill_dict(v, item_path, opt_targets)
        if isinstance(v, (list, tuple)):
            drill_list(v, item_path, opt_targets)
        assess(v, item_path, opt_targets)
