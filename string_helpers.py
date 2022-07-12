import posixpath
import os
import yaml
from datetime import datetime, timedelta
from operator import itemgetter


def extract_face_predictions(analysis):
    predictions = []
    if analysis:
        try:
            for bucket in analysis:
                if 'api' in bucket and bucket['api'] == 'faces':
                    # find the 'faces' api if it exists
                    if 'found' in bucket:
                        results = bucket['found']
                        if 'success' in results and results['success'] and 'predictions' in results:
                            # Find the 'predictions' if they exist
                            predictions = results['predictions']
                            break
        except KeyError as ex:
            print(ex)
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


def max_found(events, field):
    max_num = 0
    for event in events:
        if event[field] > max_num:
            max_num = event[field]
    return max_num


def max_in_list_of_ioi(events, field):
    max_previously_seen = 0
    for ev in events:
        seen = 0
        for poi in ev['items_of_interest']:
            if poi['label'] == field:
                seen += 1
        if seen > max_previously_seen:
            max_previously_seen = seen
    return max_previously_seen


def max_found_list(events, field):
    max_num = 0
    for event in events:
        if len(event[field]) > max_num:
            max_num = len(event[field])
    return max_num


def max_sub_list(events, field, sub_field):
    max_num = 0
    for event in events:
        for f_item in event[field]:
            if f_item[sub_field] > max_num:
                max_num = f_item[sub_field]
    return max_num


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


def should_text_be_black_or_white(rgb):
    yiq = ((rgb[0]*299)+(rgb[1]*587)+(rgb[2]*114))/1000
    return 'black' if yiq >= 128 else 'white'


def field_1_or_2(arr, field_1, field_2, field_3=None, default=None):
    if field_1 in arr:
        return arr[field_1]
    if field_2 in arr:
        return arr[field_2]
    if field_3 and field_3 in arr:
        return arr[field_3]
    return default


def get_time_ranges(events, _dtg_format, minutes_padding=3):

    start = None
    end = None

    for ev in events:
        # Skip if no time information
        ev_start = date_time(field_1_or_2(ev, 'start', 'start_time', 'time'), _dtg_format)
        ev_end = date_time(field_1_or_2(ev, 'end', 'end_time', 'time'), _dtg_format)

        # Find the earliest and latest times
        if not start or ev_start < start:
            start = ev_start
        if ev_end and (not end or ev_end > end):
            end = ev_end

    if minutes_padding:
        start -= timedelta(minutes=minutes_padding)
        end += timedelta(minutes=minutes_padding)

    return start.strftime(_dtg_format), end.strftime(_dtg_format)


def build_icon_string(event):
    sorted_analysis = sorted(event.items_of_interest, key=itemgetter('importance'), reverse=True)
    out = ""
    for obj in sorted_analysis:
        title = obj['name'] if 'name' in obj else obj['label']
        if 'icon' in obj and obj['importance'] > 1:
            out += "<img src='./{}.png' data='{}' onclick='search_icon(this)' title='{}'>".format(
                obj['icon'], obj['label'], title.title())
    return out


def date_time(dtg, _dtg_format):
    if type(dtg) == str:
        dtg = datetime.strptime(dtg, _dtg_format)
    return dtg


def center_of_rect(box, image=None):
    coord = [box['x_min'], box['y_min'], box['x_max'], box['y_max']]
    center = [coord[0] + (coord[2] / 2), coord[1] + (coord[3] / 2)]
    if image and image.image and image.image.height:
        center[0] = center[0] / image.image.width
        center[1] = center[1] / image.image.height
    return center 


def point_in_polygon(polygon, point):
    """
    From: https://www.algorithms-and-technologies.com/point_in_polygon/python

    Raycasting Algorithm to find out whether a point is in a given polygon.
    Performs the even-odd-rule Algorithm to find out whether a point is in a given polygon.
    This runs in O(n) where n is the number of edges of the polygon.
     *
    :param polygon: an array representation of the polygon where polygon[i][0] is the x Value of the i-th point and polygon[i][1] is the y Value.
    :param point:   an array representation of the point where point[0] is its x Value and point[1] is its y Value
    :return: whether the point is in the polygon (not on the edge, just turn < into <= and > into >= for that)
    """

    # A point is in a polygon if a line from the point to infinity crosses the polygon an odd number of times
    odd = False
    # For each edge (In this case for each point of the polygon and the previous one)
    i = 0
    j = len(polygon) - 1
    while i < len(polygon) - 1:
        i = i + 1
        # If a line from the point into infinity crosses this edge
        # One point needs to be above, one below our y coordinate
        # ... and the edge doesn't cross our Y corrdinate before our x coordinate (but between our x coordinate and infinity)

        if (((polygon[i][1] > point[1]) != (polygon[j][1] > point[1])) and (point[0] < (
                (polygon[j][0] - polygon[i][0]) * (point[1] - polygon[i][1]) / (polygon[j][1] - polygon[i][1])) +
                                                                            polygon[i][0])):
            # Invert odd
            odd = not odd
        j = i
    # If the number of crossings was odd, the point is in the polygon
    return odd
