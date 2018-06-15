from constants import CHANNEL_ACCESS_TOKEN
from richmenu import RichMenuManager, RichMenu


rmm = RichMenuManager(CHANNEL_ACCESS_TOKEN)
rms = rmm.get_list()

menu_init_rm = [rm for rm in rms["richmenus"] if rm["name"] == "q1"][0]
latest_menu_id = menu_init_rm['richMenuId']
rmm.remove(latest_menu_id)
print(f"richmenu {latest_menu_id} deleted")

menu_init_rm = [rm for rm in rms["richmenus"] if rm["name"] == "q2"][0]
latest_menu_id = menu_init_rm['richMenuId']
rmm.remove(latest_menu_id)
print(f"richmenu {latest_menu_id} deleted")

print(rms)

rm = RichMenu(name="q1", chat_bar_text="質問1", size_full=True)
rm.add_area(19, 603, 458, 480, "postback", "1")
rm.add_area(502, 603, 458, 480, "postback", "2")
rm.add_area(1025, 603, 458, 480, "postback", "3")
rm.add_area(1528, 603, 458, 480, "postback", "4")
rm.add_area(2031, 603, 458, 480, "postback", "5")

res = rmm.register(rm, "./richmenus/survey.jpg")

rm = RichMenu(name="q2", chat_bar_text="質問2", size_full=True)
rm.add_area(19, 603, 458, 480, "postback", "1")
rm.add_area(502, 603, 458, 480, "postback", "2")
rm.add_area(1025, 603, 458, 480, "postback", "3")
rm.add_area(1528, 603, 458, 480, "postback", "4")
rm.add_area(2031, 603, 458, 480, "postback", "5")

res = rmm.register(rm, "./richmenus/survey – 1.jpg")
rms = rmm.get_list()
print(rms)