import posixpath
import json


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


def extract_path_and_image_from_mqtt_message(payload, save_loc, camera_name, b64_field_name='image_b64',
                                             save_latest_format='latest_{}.jpg', thumbnails_subdir='thumbnails'):
    path = None
    base64_str = None
    error = None
    thumbnail_path = None

    # If it doesn't start with a { assume it's a b64 encoded image. Generate paths and get the image data
    if payload and len(payload) > 1000 and payload[0] != "{":
        # A large image payload was received that isn't JSON.  See if it's a bit64 image
        path = posixpath.join(save_loc, save_latest_format.format(camera_name))
        thumbnail_path = posixpath.join(save_loc, thumbnails_subdir, save_latest_format.format(camera_name))
        base64_str = payload

    elif payload and 'path' in payload and b64_field_name in payload:
        # This is likely JSON, try to extract and use it
        try:
            payload_obj = json.loads(payload)

            path = add_field_to_path_if_exists(payload_obj, save_loc, 'path')
            thumbnail_path = add_field_to_path_if_exists(payload_obj, save_loc, 'path', thumbnails_subdir)
            base64_str = payload_obj[b64_field_name] if b64_field_name in payload_obj else ""
            # self.log("Image {} extracted, size {}".format(path, len(base64_str)))
        except ValueError:
            error = "Received an alert JSON payload that threw an exception"
    else:
        error = "Invalid JSON or image data received"

    return base64_str, path, thumbnail_path, error


def get_zone_name_from_camera_and_zone(camera_name, zone_id):
    zone_name = camera_name
    zone_shortname = ""

    if camera_name == "TestCam":
        zone_name = "simulated in the holodeck"
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
        if "A" in zone_id:
            zone_name = "in the back yard"
        elif "B" in zone_id:
            zone_name = "on the patio"
        elif "C" in zone_id:
            zone_name = "near the hot tub"
    elif camera_name == "eufy2":
        zone_shortname = "basement"
        zone_name = "in the basement"
    else:
        zone_shortname = "unknown"
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
