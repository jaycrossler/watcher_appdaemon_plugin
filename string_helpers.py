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


def get_face_contents_from_analysis(analysis):
    _results = extract_face_predictions(analysis)
    people = []

    # Extract face titles from results
    for face in _results:
        if 'userid' in face:
            face_title = face['userid']
            name = substring_before(face_title, "_")
            if name.lower() != "unknown":
                # If the name is not 'unknown' add it to the list of people if unique
                if name.title() not in people:
                    people.append(name.title())
    return people, _results


def get_image_contents_from_memo(memo_from_deepstack, faces_list):
    matches = memo_from_deepstack.split(",")

    people = 0
    dogs = 0
    cars = 0
    _msg = []
    for match in matches:
        m_pieces = match.split(":")
        tag = m_pieces[0]
        # confidence = m_pieces[1]
        if tag == "person":
            people += 1
        elif tag == "dog":
            dogs += 1
        elif tag == "car":
            cars += 1
    #                    _msg = _msg.append["{} ({} confidence)".format(tag, confidence)]

    if people == 1:
        text = "A person"
        if faces_list and len(faces_list):
            text = faces_list[0]
        _msg.append(text)
    elif people > 1:
        text = "{} people".format(people)
        if faces_list and len(faces_list):
            text = ", ".join(faces_list)  # Add face names
        _msg.append(text)

    if dogs == 1:
        _msg.append("A dog")
    elif dogs > 1:
        _msg.append("{} dogs".format(dogs))

    if cars == 1:
        _msg.append("A car")
    elif cars > 1:
        _msg.append("{} cars".format(cars))

    message = ", and ".join(_msg).capitalize()
    return message, people + dogs + cars


def add_field_to_path_if_exists(payload_obj, source_dir, field, prefix=""):
    if prefix and field in payload_obj:
        return posixpath.join(source_dir, prefix, payload_obj[field])
    elif field in payload_obj:
        return posixpath.join(source_dir, payload_obj[field])
    return ''


def get_zone_name_from_camera_and_zone(camera_name, zone_id):

    if camera_name in ["TestCam", "eufy1"]:
        zone_name = "simulated in the holodeck"
        zone_shortname = "testing"
    elif camera_name == "annke1hd":
        zone_name = "near the mudroom"
        zone_shortname = "mudroom"
    elif camera_name == "annke2hd":
        zone_name = "in the driveway"
        zone_shortname = "driveway_front"
    elif camera_name == "annke3hd":
        zone_name = "by the front porch"
        zone_shortname = "front_porch"
    elif camera_name == "annke4hd":
        zone_name = "on the deck"
        zone_shortname = "deck"
    elif camera_name == "reolink5hd":
        zone_name = "in the driveway"
        zone_shortname = "driveway_side"
    elif camera_name == "reolink6":
        zone_shortname = "pavilion"
        if "B" in zone_id:
            zone_name = "on the patio"
        elif "C" in zone_id:
            zone_name = "near the hot tub"
        else:
            zone_name = "in the back yard"
    elif camera_name == "eufy2":
        zone_shortname = "basement"
        zone_name = "in the basement"
    else:
        zone_shortname = "not matched"
        zone_name = "- {} {}".format(camera_name, zone_id)

    return zone_name, zone_shortname


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
