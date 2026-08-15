"""System tray icon and context menu, shown only when the
"minimize to system tray" setting is enabled (off by default)."""
import wx
import wx.adv


class AppTrayIcon(wx.adv.TaskBarIcon):
    def __init__(self, on_open_settings, on_revert_target, on_quit):
        super().__init__()
        self.on_open_settings = on_open_settings
        self.on_revert_target = on_revert_target
        self.on_quit = on_quit
        icon = wx.Icon(wx.ArtProvider.GetBitmap(wx.ART_INFORMATION, wx.ART_OTHER, (16, 16)))
        self.SetIcon(icon, "Access-Translate")
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, lambda e: self.on_open_settings())

    def CreatePopupMenu(self):
        menu = wx.Menu()

        open_item = menu.Append(wx.ID_ANY, "&Open Settings")
        self.Bind(wx.EVT_MENU, lambda e: self.on_open_settings(), open_item)

        revert_item = menu.Append(wx.ID_ANY, "&Revert target language to default")
        self.Bind(wx.EVT_MENU, lambda e: self.on_revert_target(), revert_item)

        menu.AppendSeparator()

        quit_item = menu.Append(wx.ID_ANY, "&Quit")
        self.Bind(wx.EVT_MENU, lambda e: self.on_quit(), quit_item)

        return menu
