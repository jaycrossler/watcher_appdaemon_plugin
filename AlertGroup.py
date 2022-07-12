from datetime import datetime, timedelta
from string_helpers import *
from colorhash import ColorHash


class AlertGroup:
    # Has multiple zones within (e.g. "Backyard" can have [Pavilion, Backyard Left, Backyard Right, etc])
    # Tracks multiple 'event groups' that have multiple event messages in them

    def __init__(self, name, event_group_id, settings, log=None):
        self.name = name
        self.group_html_name = name.replace(" ", "_")
        self.zones = []

        self.event_group_id = event_group_id
        self.event_group_sub_id = 1

        self.group_title = ''
        self.icon_string = ''
        self.css_color = ''
        self.css_text_color = ''
        self.earliest_time = None
        self.latest_time = None

        self.events = []
        self.old_events = []

        self._settings = settings
        self._log = log
        self.set_color()

    def __str__(self):
        return f'AlertGroup({self.event_group_id}:{self.name} - {self.group_title})'

    def __repr__(self):
        return f'AlertGroup({self.serialize_events()})'

    def set_color(self):
        self.css_color = ColorHash(self.current_id()).hex
        self.css_text_color = should_text_be_black_or_white(ColorHash(self.current_id()).rgb)

    def add_zone(self, zone):
        self.zones.append(zone)

    def move_any_old_events_to_old(self, seconds_offset=0):
        if len(self.events) == 0:
            return

        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        since_minutes = self.get_setting('timeline', 'minutes_before_event_group_is_old')

        # Find the latest event
        latest_event = datetime.now() - timedelta(hours=12)
        for event in self.events:
            dtg = datetime.strptime(event['time'], _dtg_format)
            if dtg > latest_event:
                latest_event = dtg

        # If the latest event is old, move it to old events
        if latest_event < (datetime.now() - timedelta(minutes=since_minutes) + timedelta(seconds=seconds_offset)):
            # Move current events to be old events and set the current ones to be just the new message
            self.old_events.append(self.serialize_events())
            self.event_group_sub_id += 1
            self.latest_time = None
            self.earliest_time = None
            self.group_title = ""
            self.set_color()

            self.events = []

    def serialize_events(self):
        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        start = self.earliest_time
        end = self.latest_time

        out = {'event_group_id': self.current_id(), 'original_group_id': self.event_group_id,
               'css_color': self.css_color, 'css_text_color': self.css_text_color,
               'events': self.events, 'group_title': self.group_title, 'icon_string': self.icon_string,
               'earliest_time': start,
               'latest_time': end}
        return out

    def add_event(self, message):
        _dtg_format = self.get_setting('routing', 'dtg_message_format')

        # Set the 'title' to be the longest description received so far
        event_text = message['message']
        icon_string = message['icon_string']
        if len(event_text) > len(self.group_title):
            self.group_title = event_text
        if len(icon_string) > len(self.icon_string):
            self.icon_string = icon_string

        # Update group times
        if 'time' in message or 'start_time' in message:
            ev_start = datetime.strptime(field_1_or_2(message, 'start_time', 'time'), _dtg_format)
            ev_end = datetime.strptime(field_1_or_2(message, 'end_time', 'time'), _dtg_format)
            if not self.earliest_time or ev_start < self.earliest_time:
                self.earliest_time = ev_start
            if not self.latest_time or ev_end > self.latest_time:
                self.latest_time = ev_end

        # Add the event
        self.events.append(message)

    def number_of_current_events(self):
        return len(self.events)+1

    def current_id(self):
        return "{}.{}".format(self.event_group_id, self.event_group_sub_id)

    def message_received_for_zone(self, message, zone_id, seconds_offset=0):
        event = message.image_alert
        if event.count_of_important_things == 0:
            return None

        _dtg_format = self.get_setting('routing', 'dtg_message_format')
        _dtg_format_short = self.get_setting('routing', 'dtg_message_format_short')

        # Get the message text to send
        event_text = event.message_text_to_send_to_ha
        icon_string = build_icon_string(event)

        # Move all old messages from self.events to self.old_events
        self.move_any_old_events_to_old(seconds_offset=seconds_offset)

        # Set the priority of the message
        _base_priority = 3
        _people_priority = round(len(event.people)/1.75)
        _current_events = self.number_of_current_events()
        _current_events_priority = -2 if _current_events > 1 else 0

        _priority = _base_priority + _people_priority + _current_events_priority
        if _current_events > 2:
            # This isn't the first event in the group - build the priority based on other sub events

            current_event = self.events[-1:]
            last_events = self.events[:-1]

            _previous_people = max_in_list_of_ioi(last_events, 'person')
            _current_people = max_in_list_of_ioi(current_event, 'person')
            if _current_people > _previous_people:
                _priority += 1

            _previous_cars = max_in_list_of_ioi(last_events, 'car')
            _current_cars = max_in_list_of_ioi(current_event, 'car')
            if _current_cars > _previous_cars:
                _priority += 1

        # Adjust time (used for testing to set an event in the past)
        time_to_use = datetime.now()
        if seconds_offset:
            time_to_use = time_to_use + timedelta(seconds=seconds_offset)
        time_now = time_to_use.strftime(_dtg_format)
        time_short = time_to_use.strftime(_dtg_format_short)

        # Register a new event
        new_event = {
            'event_group_id': self.current_id(),
            'message_id': '{}.{}'.format(self.current_id(), self.number_of_current_events()),
            'events_in_group': len(self.events) + 1,
            'zone_id': zone_id,
            'zone': event.zone_short_name,

            # Serialize the time field properly
            'time': time_now,
            'short_time': time_short,

            'message': event_text,
            'icon_string': icon_string,
            'people': event.people,
            'items_of_interest': event.items_of_interest,
            'priority': _priority
        }
        if event.image:
            new_event['image'] = event.image.web_url
            new_event['thumbnail'] = event.image.thumbnail_url

        self.add_event(new_event)
        return new_event

    def event_as_timeline_json(self, event, show_as="message"):
        content = ""
        if show_as == 'icon':
            if event['icon_string']:
                content = event['icon_string']
        elif show_as == 'thumbnail':
            if event['thumbnail']:
                content = "<img src='{}' />".format(event['thumbnail'])

        if not content:
            content = event['message']

        tags = []
        for i in event['items_of_interest']:
            tags.append(i['label'])
        for p in event['people']:
            tags.append(p['name'])
        tags.append(event['zone'])
        tags = ",".join(tags)

        ev = {'id': event['message_id'],
              'group':  self.event_group_id,
              'className': self.group_html_name,
              'content': content,
              'original_content': content,
              'tags': tags,
              'priority': event['priority'],
              'title': "{}<br/><img src='{}' />".format(event['message'].title(), event['thumbnail']),
              'type': 'point',
              'start': self._date_in_timeline_format(event['time'])}
        if 'end_time' in event:
            ev['end'] = self._date_in_timeline_format(event['end_time'])
        return ev

    def old_events_as_json(self, include_background=True):
        _dtg_format = self.get_setting('timeline', 'padding_around_event_groups')

        output = []

        for event_group in self.old_events:
            if 'events' in event_group and len(event_group['events']):
                for event in event_group['events']:
                    output.append(self.event_as_timeline_json(event, show_as='thumbnail'))

                if include_background:
                    bg = {'id': 'bg-{}'.format(event_group['event_group_id']),
                          'content': event_group['icon_string'],
                          'className': "bg{}".format(event_group['event_group_id'].replace(".", "-")),
                          'type': 'background', 'group': event_group['original_group_id'],
                          'start': self._date_in_timeline_format(event_group['earliest_time'] - timedelta(minutes=3)),
                          'end': self._date_in_timeline_format(event_group['latest_time'] + timedelta(minutes=3))}
                    output.append(bg)

        return output

    def events_as_json(self, as_of=None, include_background=True):
        _dtg_format = self.get_setting('routing', 'dtg_message_format')

        output = []
        for event in self.events:
            show = False
            # If as_of is set, only show items after that time
            if as_of:
                dtg = datetime.strptime(event['time'], _dtg_format)
                if dtg >= datetime.strptime(as_of, _dtg_format):
                    show = True
            else:
                show = True

            # Build the output timeline data
            if show:
                output.append(self.event_as_timeline_json(event, show_as='thumbnail'))

        if len(self.events) and include_background:

            bg = {'id': 'bg-{}'.format(self.event_group_id),
                  'content': self.icon_string,
                  'className': "bg{}".format(self.event_group_id),
                  'type': 'background', 'group': self.event_group_id,
                  'start': self._date_in_timeline_format(self.earliest_time-timedelta(minutes=3)),
                  'end': self._date_in_timeline_format(self.latest_time+timedelta(minutes=3))}

            output.append(bg)

        return output

    # ==================================

    def log(self, message, level="INFO"):
        # Wrapper to main _log object

        if self._log:
            self._log(message, level=level)
        else:
            print("LOG: {}, severity: {}".format(message, level))

    def get_setting(self, d1, d2):
        if d1 in self._settings:
            if d2 in self._settings[d1]:
                return self._settings[d1][d2]
            else:
                self.log('[ERROR] the setting {} not found in config.{}'.format(d2, d1), level="ERROR")
        else:
            self.log('[ERROR] the setting config.{} not found'.format(d1), level="ERROR")
        return None

    def _date_in_timeline_format(self, dtg):
        if type(dtg) == datetime:
            _dtg_format = self.get_setting('routing', 'dtg_message_format')
            return dtg.strftime(_dtg_format)
        # "2014-04-16", end: "2014-04-19"}
        return dtg



