import posixpath
import os
import yaml


def extract_face_predictions(analysis):
    predictions = []
    if analysis:
        for bucket in analysis:
            if 'api' in bucket and bucket['api'] == 'faces':
                # find the 'faces' api if it exists
                if 'found' in bucket:
                    results = bucket['found']
                    if 'success' in results and results['success'] and 'predictions' in results:
                        # Find the 'predictions' if they exist
                        predictions = results['predictions']
                        break
    return predictions


def add_field_to_path_if_exists(payload_obj, source_dir, field, prefix=""):
    if prefix and field in payload_obj:
        return posixpath.join(source_dir, prefix, payload_obj[field])
    elif field in payload_obj:
        return posixpath.join(source_dir, payload_obj[field])
    return ''


def does_needle_match_haystack_topic(needle_string, haystack_string):
    # AppDaemon subscriptions only seem to work with specific topics, no wildcards -
    #   described in https://buildmedia.readthedocs.org/media/pdf/appdaemon/stable/appdaemon.pdf
    # This parses through all message topics (the "haystack"), and returns true if a "needle"  matches
    # Needles can be of the format: "BlueIris/+/Status" or "BlueIris/alerts/+" with + being a wildcard

    needle = needle_string.split("/")
    haystack = haystack_string.split("/")

    # Good solution if equal
    if needle == haystack:
        return True
    if len(needle) < len(haystack):
        return False

    # Check all subtopics for a match or wildcard match
    for i in range(len(needle)):
        s_needle = needle[i]
        if i < len(haystack):
            s_haystack = haystack[i]
        else:
            return False

        # Handle wildcards
        if s_haystack == "#":
            return True
        if not (s_haystack == "+" or s_haystack == s_needle):
            return False

    # Tried all steps, and nothing broke the pattern, so return true
    return True


def substring_after(s, deliminator): return s.partition(deliminator)[2]


def substring_before(s, deliminator): return s.partition(deliminator)[0]


def get_config_var(field, holder, default_val=None):
    # return an item's value from a dictionary
    return holder[field] if field in holder else default_val


def merge_dictionaries(source, destination):
    # """
    # from: https://stackoverflow.com/questions/20656135/python-deep-merge-dictionary-data
    #
    # >>> a = { 'first' : { 'all_rows' : { 'pass' : 'dog', 'number' : '1' } } }
    # >>> b = { 'first' : { 'all_rows' : { 'fail' : 'cat', 'number' : '5' } } }
    # >>> merge(b, a) == { 'first' : { 'all_rows' : { 'pass' : 'dog', 'fail' : 'cat', 'number' : '5' } } }
    # True
    # """
    for key, value in source.items():
        if isinstance(value, dict):
            # get node or create one
            node = destination.setdefault(key, {})
            merge_dictionaries(value, node)
        else:
            destination[key] = value

    return destination


def load_config_file_node(filename, node, default_val, log):
    _config_from_file = default_val
    if os.path.exists(filename):
        with open(filename, 'r') as conf_file:
            _yaml_contents = yaml.safe_load(conf_file)
            if node in _yaml_contents:
                _config_from_file = _yaml_contents[node]
            else:
                log('Error: "{}}" doesnt have "{}}" settings'.format(filename, node))
    else:
        log('Error: "config_file" set in apps.yaml config, but {} doesnt seem to exist'.format(filename))
    return _config_from_file


def clip(val, min_, max_):
    return min_ if val < min_ else max_ if val > max_ else val
