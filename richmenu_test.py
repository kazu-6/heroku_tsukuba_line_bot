from constants import line_bot_api
from linebot.models import (
    RichMenu, RichMenuArea, RichMenuSize, RichMenuBounds, PostbackAction
)

from os.path import join, dirname
rms = line_bot_api.get_rich_menu_list()

# menu_init_rm = [rm for rm in rms if rm.name == "q1"][0]
# latest_menu_id = menu_init_rm.rich_menu_id
# line_bot_api.delete_rich_menu(latest_menu_id)
# print(f"richmenu q1{latest_menu_id} deleted")
#
# menu_init_rm = [rm for rm in rms if rm.name == "q2"][0]
# latest_menu_id = menu_init_rm.rich_menu_id
# line_bot_api.delete_rich_menu(latest_menu_id)
# print(f"richmenu q2{latest_menu_id} deleted")


def register_survey_richmenu(index):
    global id, rm, res
    i = index + 1

    q1_rm_ids = [rm.rich_menu_id for rm in rms if rm.name == f"q{i}"]

    for id in q1_rm_ids:
        line_bot_api.delete_rich_menu(id)
        print(f"richmenu q{i} {id} deleted")

    areas = []
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=0, y=0, width=750, height=140),
        action=PostbackAction(label=f'q{i+1}', text="前の質問に戻る", data=f"back_to_q{i-1}")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=2000, y=0, width=750, height=140),
        action=PostbackAction(label=f'q{i+1}', text='計測をキャンセル', data="cancel")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=13, y=876, width=458, height=480),
        action=PostbackAction(label=f'q{i+1}', text=f"q{i}=1", data=f"q{i}=1")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=516, y=876, width=458, height=480),
        action=PostbackAction(label=f'q{i+1}', text=f"q{i}=2", data=f"q{i}=2")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=1019, y=876, width=458, height=480),
        action=PostbackAction(label=f'q{i+1}', text=f"q{i}=3", data=f"q{i}=3")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=1522, y=876, width=458, height=480),
        action=PostbackAction(label=f'q{i+1}', text=f"q{i}=4", data=f"q{i}=4")
    )
    )
    areas.append(RichMenuArea(
        bounds=RichMenuBounds(x=2025, y=876, width=458, height=480),
        action=PostbackAction(label=f'q{i+1}', text=f"q{i}=5", data=f"q{i}=5")
    )
    )

    rm = RichMenu(name=f"q{i}", chat_bar_text=f"質問{i}", size=RichMenuSize(width=2500, height=1686), areas=areas, selected=False)
    rich_menu_id = line_bot_api.create_rich_menu(rm)

    path = join(dirname(__file__), f'richmenus/survey – {index+1}.jpg')

    with open(path, 'rb') as f:
        line_bot_api.set_rich_menu_image(rich_menu_id, 'image/jpeg', f)

    print("Registered as " + rich_menu_id)


if __name__ == '__main__':

    for i in range(3):
        register_survey_richmenu(i)

    rms = line_bot_api.get_rich_menu_list()
    print(rms)
