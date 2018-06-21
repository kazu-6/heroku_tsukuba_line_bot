from PIL import Image, ImageDraw, ImageFont
import numpy
import math
from constants import line_bot_api
from linebot.models import (
    RichMenu, RichMenuArea, RichMenuSize, RichMenuBounds, MessageAction
)


def draw_text_at_center(img, text):
    draw = ImageDraw.Draw(img)
    draw.font = ImageFont.truetype('/Library/Fonts/ヒラギノ明朝 ProN.ttc', 75)
    img_size = numpy.array(img.size)
    txt_size = numpy.array(draw.font.getsize(text))
    pos = (img_size - txt_size) / 2
    draw.text(pos, text, (255, 255, 255))


def calculate_grid_position(enum, column_count):
    column = enum % column_count
    row = int(enum / column_count)
    return row, column


def get_position(row, column):
    x = column * grid_width
    y = row * grid_height
    return x, y


large_image_res = (2500, 1686)
small_image_res = (2500, 843)
canvas = Image.new('RGB', small_image_res, (255, 255, 255))

border_image_res = (2500, 1)
border = Image.new('RGB', border_image_res, (2, 24, 255))

trigger_words = ['マイナンバー関連', '印鑑登録関連', '各種証明書', '住所異動',
                 'ダミー', 'ダミー2', '計測スタート', '計測終了']
column_count = 4
row_count = 2
grid_width = int(small_image_res[0] / column_count)
grid_height = int(math.ceil(small_image_res[1] / row_count))

rms = line_bot_api.get_rich_menu_list()
menu_init_rm_ids = [rm.rich_menu_id for rm in rms if rm.name == "menu_init"]
for id in menu_init_rm_ids:
    line_bot_api.delete_rich_menu(id)
    print(f"richmenu {id} deleted")

areas = []

for i, word in enumerate(trigger_words):
    img = Image.new('RGB', (grid_width, grid_height), (128, 128, 128))
    text = f"{word}"
    draw_text_at_center(img, text)
    row, column = calculate_grid_position(i, column_count)
    x, y = get_position(row, column)
    canvas.paste(img, (x, y))
    # rm.add_area(x, y, grid_width, grid_height, "message", word)
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=x, y=y, width=grid_width, height=grid_height),
        action=MessageAction(label=f'q{i+1}', text=word)
        )
    )

canvas.show()
canvas.save('richmenu_init.jpg', 'JPEG', quality=100, optimize=True)

rm = RichMenu(name="menu_init", chat_bar_text="問合わせ分類", size=RichMenuSize(width=2500, height=843), areas=areas,
              selected=False)

rich_menu_id = line_bot_api.create_rich_menu(rm)

with open('richmenu_init.jpg', 'rb') as f:
    line_bot_api.set_rich_menu_image(rich_menu_id, 'image/jpeg', f)

print("Registered as " + rich_menu_id)

rms = line_bot_api.get_rich_menu_list()
print(rms)

# Apply to user
# user_id = "U64ba20ff7114cb5be9d20ba125662033"
# rmm.apply(user_id, richmenu_id)
