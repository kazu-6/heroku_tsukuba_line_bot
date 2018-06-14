from constants import CHANNEL_ACCESS_TOKEN
from richmenu import RichMenuManager, RichMenu

rmm = RichMenuManager(CHANNEL_ACCESS_TOKEN)
print(rmm.get_list())
print(rmm.get_list()['richmenus'][0]['richMenuId'])

menu_init_rm = [rm for rm in rmm.get_list()["richmenus"] if rm["name"] == "menu_init"][0]

print(menu_init_rm)

# Setup RichMenu to register
# rm = RichMenu(name="menu_init", chat_bar_text="問い合わせ分類", size_full=False)
