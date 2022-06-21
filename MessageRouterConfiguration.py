class MessageRouterConfiguration:

    defaults = {
        'routing': {
            'image_field_name': 'image_b64',
            'dtg_message_format': '%d/%m/%Y %H:%M:%S',
            'dtg_message_format_short': '%H:%M',
            'mqtt_topic_for_camera_intents': "BlueIris/+/Status",
            'mqtt_topic_for_camera_alert_images': "BlueIris/alerts/+",
            'mqtt_publish_to_topic': "homeassistant/camera_intents/description",
            'mqtt_publish_to_for_latest_image': "homeassistant/camera_intents/latest_image",
        },
        'saving': {
            'save_latest_format': 'latest_{}.jpg',  # Set to None to not save the latest image
            'thumbnails_subdir': 'thumbnails',
            'thumbnail_max_size': 300,
            'path_to_save_images': "/config/www/appdaemon_intents/",
            'web_path_to_images': "/local/appdaemon_intents/",
            'days_to_keep_images': None,  # delete old files after n days, or None to keep everything
            'save_latest_json_to_file': 'latest_alert_image_message.json'  # None to not save
        },
        'states': {
            'default_occupancy_off_trigger': '5:00'
        },
        'zones': [

        ]
    }
