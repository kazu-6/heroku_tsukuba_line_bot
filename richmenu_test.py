from constants import CHANNEL_ACCESS_TOKEN
from richmenu import RichMenuManager, RichMenu


rmm = RichMenuManager(CHANNEL_ACCESS_TOKEN)
rms = rmm.get_list()

# menu_init_rm = [rm for rm in rms["richmenus"] if rm["name"] == "q1"][0]
# latest_menu_id = menu_init_rm['richMenuId']
# rmm.remove(latest_menu_id)
# print(f"richmenu {latest_menu_id} deleted")
#
# menu_init_rm = [rm for rm in rms["richmenus"] if rm["name"] == "q2"][0]
# latest_menu_id = menu_init_rm['richMenuId']
# rmm.remove(latest_menu_id)
# print(f"richmenu {latest_menu_id} deleted")


def register_survey_richmenu(index):
    global id, rm, res
    i = index + 1

    q1_rm_ids = [rm["richMenuId"] for rm in rms["richmenus"] if rm["name"] == f"q{i}"]

    for id in q1_rm_ids:
        rmm.remove(id)
        print(f"richmenu q{i} {id} deleted")

    rm = RichMenu(name=f"q{i}", chat_bar_text=f"質問{i}", size_full=True)
    rm.add_area(0, 0, 752, 142, "postback", f"back_to_q{i-1}")
    rm.add_area(2000, 0, 750, 140, "postback", "init")
    rm.add_area(13, 876, 458, 480, "postback", f"q{i}=1")
    rm.add_area(516, 876, 458, 480, "postback", f"q{i}=2")
    rm.add_area(1019, 876, 458, 480, "postback", f"q{i}=3")
    rm.add_area(1522, 876, 458, 480, "postback", f"q{i}=4")
    rm.add_area(2025, 876, 458, 480, "postback", f"q{i}=5")
    res = rmm.register(rm, f"/Users/ryo/gitWorks/heroku_tsukuba_line_bot/richmenus/survey – {i}.jpg")


if __name__ == '__main__':

    for i in range(3):
        register_survey_richmenu(i)

    rms = rmm.get_list()
    print(rms)
