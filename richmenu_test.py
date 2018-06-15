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

q1_rm_ids = [rm["richMenuId"] for rm in rms["richmenus"] if rm["name"] == "q1"]
for id in q1_rm_ids:
    rmm.remove(id)
    print(f"richmenu q1 {id} deleted")

q2_rm_ids = [rm["richMenuId"] for rm in rms["richmenus"] if rm["name"] == "q2"]
for id in q2_rm_ids:
    rmm.remove(id)
    print(f"richmenu q2 {id} deleted")

rm = RichMenu(name="q1", chat_bar_text="質問1", size_full=True)
rm.add_area(0, 0, 200, 200, "postback", "init")
rm.add_area(19, 603, 458, 480, "postback", "q1=1")
rm.add_area(502, 603, 458, 480, "postback", "q1=2")
rm.add_area(1025, 603, 458, 480, "postback", "q1=3")
rm.add_area(1528, 603, 458, 480, "postback", "q1=4")
rm.add_area(2031, 603, 458, 480, "postback", "q1=5")

res = rmm.register(rm, "./richmenus/survey.jpg")

rm = RichMenu(name="q2", chat_bar_text="質問2", size_full=True)
rm.add_area(0, 0, 200, 200, "postback", "init")
rm.add_area(19, 603, 458, 480, "postback", "q2=1")
rm.add_area(502, 603, 458, 480, "postback", "q2=2")
rm.add_area(1025, 603, 458, 480, "postback", "q2=3")
rm.add_area(1528, 603, 458, 480, "postback", "q2=4")
rm.add_area(2031, 603, 458, 480, "postback", "q2=5")

res = rmm.register(rm, "./richmenus/survey – 1.jpg")
rms = rmm.get_list()
print(rms)