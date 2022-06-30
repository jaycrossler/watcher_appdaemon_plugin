import json
from pathlib import Path

directory_to_find_json_files = 'test/json_maps/'


class MyJSONEncoder(json.JSONEncoder):

    def iterencode(self, o, _one_shot=False):
        list_lvl = 0
        for s in super(MyJSONEncoder, self).iterencode(o, _one_shot=_one_shot):
            if s.startswith('['):
                list_lvl += 1
                s = s.replace('\n', '').rstrip()
                s = s.replace(' ', '')
            elif list_lvl > 1:
                s = s.replace('\n', '').rstrip()
                if s and s[-1] == ',':
                    s = s[:-1] + self.item_separator
                elif s and s[-1] == ':':
                    s = s[:-1] + self.key_separator
                s = s.replace(' ', '')
            if s.endswith(']'):
                list_lvl -= 1
            yield s


if __name__ == '__main__':

    output = []

    json_dir = Path(directory_to_find_json_files)

    json_file_list = json_dir.glob('*.json')
    for file in json_file_list:

        cam = str(file.name).split('.')[0]

        with file.open() as source:
            file_obj = json.load(source)
            width = file_obj['imageWidth']
            height = file_obj['imageHeight']

            for s in file_obj['shapes']:
                label = s['label']
                points = s['points']

                # Craft the points of the polygon by converting to percentages
                percentage_points = []
                for p in points:
                    x = p[0] / width
                    y = p[1] / height
                    percentage_points.append([round(x, 4), round(y,4)])

                exists_zone = False
                for existing in output:
                    if existing["id"] == label:
                        exists_zone = True

                        exists_cam = False
                        for exist_cam in existing['cameras']:
                            if exist_cam['name'] == cam:
                                exists_cam = True
                                exist_cam['polygons'].append(percentage_points)
                                break

                        if not exists_cam:
                            existing['cameras'].append({"name": cam, "polygons": [percentage_points]})
                if not exists_zone:
                    new_zone = {"id": label, "cameras": [{"name": cam, "polygons": [percentage_points]}]}
                    output.append(new_zone)

    with open('test/extracted_zones.json', 'w', encoding='utf-8') as f:
        out_text = json.dumps(output, indent=2, separators=(',', ':'), cls=MyJSONEncoder)
        out_text = out_text.replace('{"name"', '\n\t\t{"name"')

        f.write(out_text)
