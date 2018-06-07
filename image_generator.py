from PIL import Image, ImageDraw, ImageFont
import numpy
import math
from constants import CHANNEL_ACCESS_TOKEN
from richmenu import RichMenuManager, RichMenu


def draw_text_at_center(img, text):
    draw = ImageDraw.Draw(img)
    draw.font = ImageFont.truetype('/Library/Fonts/ヒラギノ明朝 ProN.ttc', 75)
    img_size = numpy.array(img.size)
    txt_size = numpy.array(draw.font.getsize(text))
    pos = (img_size - txt_size) / 2
    draw.text(pos, text, (255, 255, 255))


def calculate_grid_position(enum, column_count):
    column = enum % column_count
    row = int(enum/column_count)
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
                 '5', '6', '計測スタート', '計測終了']
column_count = 4
row_count = 2
grid_width = int(small_image_res[0]/column_count)
grid_height = math.ceil(small_image_res[1]/row_count)

# Setup RichMenuManager
rmm = RichMenuManager(CHANNEL_ACCESS_TOKEN)
print(rmm.get_list())
rmm.remove_all()
print("richmenu images deleted")

# Setup RichMenu to register
rm = RichMenu(name="menu_init", chat_bar_text="問い合わせ分類", size_full=False)

for i, word in enumerate(trigger_words):

    img = Image.new('RGB', (grid_width, grid_height), (128, 128, 128))
    text = f"{word}"
    draw_text_at_center(img, text)
    row, column = calculate_grid_position(i, column_count)
    x, y = get_position(row, column)
    canvas.paste(img, (x, y))
    rm.add_area(x, y, grid_width, grid_height, "message", word)

canvas.show()
canvas.save('richmenu_init.jpg', 'JPEG', quality=100, optimize=True)

res = rmm.register(rm, "./richmenu_init.jpg")
richmenu_id = res["richMenuId"]
print("Registered as " + richmenu_id)
with open('latest_richmenu.txt', 'w') as f:
    f.write(f'{richmenu_id}')


# Apply to user
user_id = "U0a028f903127e2178bd789b4b4046ba7"
# rmm.apply(user_id, richmenu_id)
# # # Check
# res = rmm.get_applied_menu(user_id)
# print(user_id + ":" + res["richMenuId"])
#
#
rmm.detach(user_id)
# res = rmm.get_applied_menu(user_id)
# print(res)

