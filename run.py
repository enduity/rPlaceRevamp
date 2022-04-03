import json
import math
import os
import random
import threading
import time
from io import BytesIO

import requests
from PIL import Image
from packaging import version
from requests.auth import HTTPBasicAuth
from websocket import create_connection

users = []
im_draw = None
available = []
color_lookup = {}
available_times = []
last_place = [0, 0]

def load_config():
    conf_file = open("./config.json", "r")
    return json.loads(conf_file.read())


def update_access_token(user_index):
    global users

    if not users[user_index]["banned"]:
        data = {
            "grant_type": "password",
            "username": users[user_index]["name"],
            "password": users[user_index]["pw"],
        }

        r = requests.post(
            "https://ssl.reddit.com/api/v1/access_token",
            data=data,
            auth=HTTPBasicAuth(users[user_index]["client_id"], users[user_index]["secret_key"]),
            headers={"User-agent": f"{random.randint(1, 100000)}{random.randint(1, 100000)}"},
        )

        response_data = r.json()

        users[user_index]["access_token"] = response_data["access_token"]

        threading.Timer(int(response_data["expires_in"]), update_access_token, (user_index,)).start()


def load_image_url(url):
    global im_draw

    # read and load the image to draw and get its dimensions
    try:
        im_resp = requests.get(url, stream=True, timeout=60)
    except requests.exceptions.ReadTimeout:
        print('Image download timed out')
        print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
    else:
        if im_resp.status_code not in [200, 301, 302]:
            print('HTTP', im_resp.status_code)
            print('Image download failed')
            print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')

            return 1
        else:
            print("New image downloaded: " + url)
            im = Image.open(im_resp.raw).convert("RGB")
            im_draw = im
            return 0


def image_updater(image_e, conf):
    url = conf["version_url"]
    status = "continue"
    image_version = "0.0.1"
    tries = 0

    while True:
        if tries >= 10:
            print('Failed to update image after 10 tries. Exiting.')
            os._exit(1)
        try:
            resp = requests.get(url, timeout=5)
        except requests.exceptions.ReadTimeout:
            print('Request timed out')
            print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
            status = "retry"
        else:
            if resp.status_code not in [200, 301, 302]:
                print('HTTP', resp.status_code)
                print('Request failed')
                print('Trying again in 1 minute. After 10 tries, the script will stop automatically.')
                status = "retry"
            else:
                data = resp.json()
        if status == "continue":
            if version.parse(data["version"]) > version.parse(image_version):
                image_version = data["version"]
                print('New image version available. Downloading.')
                result = load_image_url(
                    conf["images_base_url"] + data["filename"])
                if result:
                    tries += 1
                    time.sleep(60)
                else:
                    tries = 0
                    print('Downloaded new image version.')
                    image_e.set()
                    time.sleep(60)
            else:
                tries = 0
                time.sleep(60)
        else:
            tries += 1
            time.sleep(60)


def get_board():
    ws = create_connection(
        "wss://gql-realtime-2.reddit.com/query", origin="https://hot-potato.reddit.com"
    )
    ws.send(
        json.dumps(
            {
                "type": "connection_init",
                "payload": {"Authorization": "Bearer " + users[0]["access_token"]},
            }
        )
    )
    ws.recv()
    ws.send(
        json.dumps(
            {
                "id": "1",
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CONFIG",
                            }
                        }
                    },
                    "extensions": {},
                    "operationName": "configuration",
                    "query": "subscription configuration($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on ConfigurationMessageData {\n          colorPalette {\n            colors {\n              hex\n              index\n              __typename\n            }\n            __typename\n          }\n          canvasConfigurations {\n            index\n            dx\n            dy\n            __typename\n          }\n          canvasWidth\n          canvasHeight\n          __typename\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }
        )
    )
    res = json.loads(ws.recv())

    while True:
        temp = json.loads(ws.recv())
        if temp["type"] == "data":
            place_config = temp["payload"]["data"]["subscribe"]["data"]
            canvas_config = place_config["canvasConfigurations"]
            break

    canvas_iter = 0
    canvas_images = []
    for i in canvas_config:
        req_data = {
                "id": str(2+canvas_iter),
                "type": "start",
                "payload": {
                    "variables": {
                        "input": {
                            "channel": {
                                "teamOwner": "AFD2022",
                                "category": "CANVAS",
                                "tag": str(canvas_iter),
                            }
                        }
                    },
                    "extensions": {},
                    "operationName": "replace",
                    "query": "subscription replace($input: SubscribeInput!) {\n  subscribe(input: $input) {\n    id\n    ... on BasicMessage {\n      data {\n        __typename\n        ... on FullFrameMessageData {\n          __typename\n          name\n          timestamp\n        }\n        ... on DiffFrameMessageData {\n          __typename\n          name\n          currentTimestamp\n          previousTimestamp\n        }\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
                },
            }
        ws.send(json.dumps(req_data))
        file = ""
        while True:
            temp = json.loads(ws.recv())
            if temp["type"] == "data":
                msg = temp["payload"]["data"]["subscribe"]
                if msg["data"]["__typename"] == "FullFrameMessageData":
                    file = msg["data"]["name"]
                    break
        canvas_images.append(BytesIO(requests.get(file, stream=True).content))

        canvas_iter += 1
    ws.close()
    converted_images = [Image.open(x).convert("RGB") for x in canvas_images]

    max_dim = [1000, 1000]
    for i in canvas_config:
        if (i["dx"] != 0) and ((i["dx"] + 1000) > max_dim[0]):
            max_dim[0] = i["dx"] + 1000
        if (i["dy"] != 0) and ((i["dy"] + 1000) > max_dim[1]):
            max_dim[1] = i["dy"] + 1000

    new_im = Image.new("RGB", tuple(max_dim))

    paste_iter = 0
    for i in canvas_config:
        new_im.paste(converted_images[paste_iter], (i["dx"], i["dy"]))
        paste_iter += 1

    return [new_im, place_config]


def rgb_to_hex(rgb):
    return ("#%02x%02x%02x" % rgb).upper()


def rgb_to_color_index(rgb):
    hex = rgb_to_hex(rgb)
    return color_lookup[hex]


def log_username(index):
    return "(" + users[index]["name"] + ")"


def place_pixel(x, y, color, user_index):
    global last_place
    global available
    canvas_index = 0

    orig_coord = (x, y)
    while x > 999:
        canvas_index += 1
        x -= 1000

    while y > 999:
        canvas_index += 1
        x -= 1000

    color_index = rgb_to_color_index(color)

    url = "https://gql-realtime-2.reddit.com/query"

    payload = json.dumps(
        {
            "operationName": "setPixel",
            "variables": {
                "input": {
                    "actionName": "r/replace:set_pixel",
                    "PixelMessageData": {
                        "coordinate": {"x": x, "y": y},
                        "colorIndex": color_index,
                        "canvasIndex": canvas_index,
                    },
                }
            },
            "query": "mutation setPixel($input: ActInput!) {\n  act(input: $input) {\n    data {\n      ... on BasicMessage {\n        id\n        data {\n          ... on GetUserCooldownResponseMessageData {\n            nextAvailablePixelTimestamp\n            __typename\n          }\n          ... on SetPixelResponseMessageData {\n            timestamp\n            __typename\n          }\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n}\n",
        }
    )
    headers = {
        "origin": "https://hot-potato.reddit.com",
        "referer": "https://hot-potato.reddit.com/",
        "apollographql-client-name": "mona-lisa",
        "Authorization": "Bearer " + users[user_index]["access_token"],
        "Content-Type": "application/json",
    }
    response = requests.request("POST", url, headers=headers, data=payload)

    if response.json()["data"] == None:
        success = 0
        wait_time = math.floor(math.floor(
            response.json()["errors"][0]["extensions"]["nextAvailablePixelTs"]
        ) / 1000)
        print("Placing failed: need to wait for " + str(wait_time - math.floor(time.time())) + " seconds " + log_username(user_index))
    else:
        success = 1
        wait_time = math.floor(int(
            response.json()["data"]["act"]["data"][0]["data"]["nextAvailablePixelTimestamp"]
        ) / 1000)
        print("Placing succeeded: placed " + rgb_to_hex(color) + " to coordinates " + str(orig_coord[0]) + ", " + str(orig_coord[1]) + " " + log_username(user_index))
        print("Worker delayed for " + str(wait_time - math.floor(time.time())) + "s " + log_username(user_index))

    curr_time = math.floor(time.time())
    if (curr_time - last_place[user_index]) < 10:
        available[user_index] = False
    last_place[user_index] = curr_time

    return success, wait_time


def make_available(user_index):
    global available
    print("Worker now available " + log_username(user_index))
    available[user_index] = True


def closest_color(target_rgb, color_array):
    r, g, b = target_rgb
    if (r == 69) and (g == 42) and (b == 0):
        return 69, 42, 0
    if (r == 69) and (g == 41) and (b == 1):
        return 69, 42, 0
    color_diffs = []
    for color in color_array:
        cr, cg, cb = color
        color_diff = math.sqrt((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2)
        color_diffs.append((color_diff, color))
    return min(color_diffs)[1]


def main_loop(image_e):
    global available
    global im_draw
    global available_times

    print("Starting main loop...")
    image_is_loaded = image_e.wait()
    last_scan = time.time()

    while True:
        if True in available:
            print("Scan started.")
            boardimg, place_config = get_board()
            new_im_draw = Image.new("RGB", boardimg.size)
            new_im_draw.paste((69, 42, 0), [0, 0, boardimg.size[0], boardimg.size[1]])
            new_im_draw.paste(im_draw, (0, 0))
            pix_draw = new_im_draw.load()
            pix_board = boardimg.load()

            for color in place_config["colorPalette"]["colors"]:
                color_lookup[color["hex"]] = color["index"]

            color_table = []
            for color in color_lookup:
                color_table.append(tuple(int(color.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)))

            for y in range(boardimg.size[1]):
                for x in range(boardimg.size[0]):
                    pix_draw[x, y] = closest_color(pix_draw[x, y], color_table)

            startpos = [random.randrange(0, boardimg.size[0]), random.randrange(0, boardimg.size[1])]
            x_pos = startpos[0]
            y_pos = startpos[1]
            did_place = False
            changes_needed = 0
            while True:
                while True:
                    if (pix_draw[x_pos, y_pos] != pix_board[x_pos, y_pos]) and (pix_draw[x_pos, y_pos] != (69, 42, 0)):
                        changes_needed += 1
                        user_index = 0
                        for try_user in available:
                            if not try_user:
                                continue
                            placed, next_time = place_pixel(x_pos, y_pos, pix_draw[x_pos, y_pos], user_index)

                            available[user_index] = False
                            available_in = next_time - math.floor(time.time())

                            if available_in < 100000:
                                threading.Timer(available_in, lambda user_i=user_index: make_available(user_i)).start()
                            else:
                                print("User likely banned. " + log_username(user_index))
                                users[user_index]["banned"] = True
                            available_times[user_index] = next_time
                            user_index += 1

                            if placed:
                                did_place = True
                                changes_needed -= 1
                                break
                    if x_pos == (boardimg.size[0] - 1):
                        x_pos = 0
                    else:
                        x_pos += 1
                    if x_pos == startpos[0]:
                        break
                if y_pos == (boardimg.size[1] - 1):
                    y_pos = 0
                else:
                    y_pos += 1
                if y_pos == startpos[1]:
                    break
            if changes_needed == 0:
                print("Scan finished. Found no pixels to change.")
            elif changes_needed and (not did_place):
                print("Scan finished. There are " + str(changes_needed) + " pixels to change, but no more workers are available.")
            if not did_place:
                curr_time = time.time()
                if (curr_time - last_scan) < 5:
                    time.sleep(30)
                last_scan = curr_time
            else:
                time.sleep(1)
        else:
            next_timestamp = min(available_times)
            if next_timestamp < 0:
                print("Waiting for available workers.")
            else:
                print("Waiting for available workers. Next worker in " + str(next_timestamp - math.floor(time.time())) + "s")
            time.sleep(10)


def main(conf):
    image_config = conf["img_conf"]
    image_event = threading.Event()
    image_thread = threading.Thread(target=image_updater, args=(image_event, image_config,))

    global users
    global available
    global available_times
    global last_place

    user_index = 0
    for u_name, u_conf in conf["accounts"].items():
        if "client_id" in u_conf:
            u_client_id = u_conf["client_id"]
            u_secret_key = u_conf["secret_key"]
        else:
            u_client_id = conf["app"]["client_id"]
            u_secret_key = conf["app"]["secret_key"]

        users.append({
            "name": u_name,
            "pw": u_conf["pw"],
            "client_id": u_client_id,
            "secret_key": u_secret_key,
            "access_token": None,
            "banned": False
        })

        data = {
            "grant_type": "password",
            "username": u_name,
            "password": u_conf["pw"],
        }

        r = requests.post(
            "https://ssl.reddit.com/api/v1/access_token",
            data=data,
            auth=HTTPBasicAuth(u_client_id, u_secret_key),
            headers={"User-agent": f"{random.randint(1, 100000)}{random.randint(1, 100000)}"},
        )

        response_data = r.json()

        users[user_index]["access_token"] = response_data["access_token"]
        print("User " + u_name + " logged in.")

        threading.Timer(int(response_data["expires_in"]) + random.randrange(1, 6), lambda user_i=user_index: update_access_token(user_i)).start()

        user_index += 1
        time.sleep(1)

    available = [True for x in users]
    available_times = [-1 for x in users]
    last_place = [0 for x in users]

    threading.Thread(target=main_loop, args=(image_event,)).start()
    image_thread.start()


if os.path.exists("./config.json"):
    config = load_config()
    main(config)
else:
    exit("No config.json file found. Read the README")