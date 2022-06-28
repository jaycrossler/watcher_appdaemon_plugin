# "Watcher" HASSIO AppDaemon plugin
Respond to MQTT messages from NVRs (vision recorders like BlueIris), parse those, extract key events like faces or
analysis, and then group them and prioritize them and resend those for Home Assistant to use.

Built inside the AppDaemon addon to Home Assistant.  Currently needs to be installed manually, but configured with
a YAML file.

Optionally uses an additional face recognition service (such as SenseAI or DeepStack) to add face information if it wasn't provided.

## Intention
This is a fun passion project to refresh my understanding of python, Home Assistant, neural networks, object correlation tools and video processing.  Ideally, I can add into my home cameras and automation system as well.  Possibly even release it for others to use...

# Installation and configuration

Download all files into an AppDaemon folder, I suggest: `/config/appdaemon/apps/watcher/`
create a test folder: `/config/appdaemon/apps/watcher/test` and a 
test/thumbnails folder: `/config/appdaemon/apps/watcher/test/thumbnails`

You can either put configuration variables in `apps.yaml` or in the `config.yaml` file (recommended)

I recommend using PyCharm as a development environment.  As the app runs within the AppDaemon environment, it is difficult
to get a quality set of logs as output.  In the meantime, this works pretty well:
- Use the test.py script as the main entry point into the app.  This just calls the same class that AppDaemon does
- Capture messages from BlueIris and save them for testing and playback.  This makes it easier to debug code using
PyCharm and doesn't send annoying final output messages to Home Assistant.

Note that when you make changes to any classes, AppDaemon 'reloads' them each time (but doesn't actually update the 
definitions or code or internal variables, so when you're ready to move from testing to production, just restart
AppDaemon)

Currently, just required the Pillow library to be installed, both in AppDaemon and locally

## Setting up AppDaemon apps.yaml
Edit apps.yaml, and add:

```
watcher:
  module: MessageRouter
  class: MessageRouter
  config:
    config_file: /config/appdaemon/apps/watcher/config.yaml
    saving:
      thumbnail_max_size: 300
      days_to_keep_images: 14
```

## After all libraries are installed:
Create a `test` directory, and put a 'thumbnails' directory within it.  Test items will be stored here

You can now debug or run the program from pycharm, or from AppDaemon


# Feature and to-do List
- Integrate the Fixed Camera Object Tracker within
- Have better description of scenes and events
- Show event groups on a dashboard and timeline

