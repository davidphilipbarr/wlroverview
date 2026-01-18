#!/usr/bin/env python3
import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GObject, GLib  # noqa: E402


CONFIG_PATH = Path.home() / ".config" / "wloverview" / "config.json"


# ------------------------
# Helpers
# ------------------------
def ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def atomic_write_text(path: Path, text: str) -> None:
    ensure_parent_dir(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def reload_wloverview() -> None:
    # Soft reload wloverview (ignore errors)
    subprocess.run(
        ["pkill", "-USR1", "wloverview"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def icon_to_gicon(icon_str: Optional[str]) -> Optional[Gio.Icon]:
    """
    Supports:
      - absolute/relative file path to an image or icon file -> Gio.FileIcon
      - themed icon name -> Gio.ThemedIcon
    """
    if not icon_str:
        return None

    s = icon_str.strip()
    if not s:
        return None

    p = Path(s).expanduser()
    if p.exists():
        try:
            return Gio.FileIcon.new(Gio.File.new_for_path(str(p)))
        except Exception:
            return None

    # themed icon name
    try:
        return Gio.ThemedIcon.new(s)
    except Exception:
        return None


def best_icon_for_item(item: Dict[str, Any]) -> Optional[Gio.Icon]:
    # Prefer explicit icon; fall back to app_id if present
    ico = icon_to_gicon(item.get("icon"))
    if ico:
        return ico

    app_id = item.get("app_id")
    if isinstance(app_id, str) and app_id.strip():
        return icon_to_gicon(app_id.strip())

    return None


def safe_str(v: Any) -> str:
    return "" if v is None else str(v)


# ------------------------
# Backend
# ------------------------
class WlOverviewBackend:
    def __init__(self, path: Path = CONFIG_PATH):
        self.path = path
        self.apps: List[Dict[str, Any]] = []
        self.load()

    def load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            self.apps = []
            return self.apps

        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self.apps = data
            else:
                self.apps = []
        except Exception:
            self.apps = []

        # Ensure each item is a dict
        self.apps = [a for a in self.apps if isinstance(a, dict)]
        return self.apps

    def save(self) -> None:
        text = json.dumps(self.apps, indent=4, ensure_ascii=False) + "\n"
        atomic_write_text(self.path, text)
        reload_wloverview()

    def get_apps(self) -> List[Dict[str, Any]]:
        return list(self.apps)

    def add_app(self, item: Dict[str, Any]) -> None:
        self.apps.append(item)
        self.save()

    def remove_app(self, index: int) -> None:
        if not (0 <= index < len(self.apps)):
            return
        self.apps.pop(index)
        self.save()

    def move_app(self, old_index: int, new_index: int) -> None:
        if not (0 <= old_index < len(self.apps)):
            return
        if not (0 <= new_index < len(self.apps)):
            return
        item = self.apps.pop(old_index)
        self.apps.insert(new_index, item)
        self.save()

    def update_app(self, index: int, item: Dict[str, Any]) -> None:
        if not (0 <= index < len(self.apps)):
            return
        self.apps[index] = item
        self.save()


# ------------------------
# GTK model item
# ------------------------
class AppRow(GObject.GObject):
    __gtype_name__ = "AppRow"

    title = GObject.Property(type=str, default="")
    exec_cmd = GObject.Property(type=str, default="")
    icon = GObject.Property(type=str, default="")
    app_id = GObject.Property(type=str, default="")

    def __init__(self, d: Dict[str, Any]):
        super().__init__()
        self.title = safe_str(d.get("title"))
        self.exec_cmd = safe_str(d.get("exec"))
        self.icon = safe_str(d.get("icon"))
        self.app_id = safe_str(d.get("app_id"))

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {"title": self.title, "exec": self.exec_cmd}
        if self.icon.strip():
            d["icon"] = self.icon.strip()
        if self.app_id.strip():
            d["app_id"] = self.app_id.strip()
        return d


# ------------------------
# Edit dialog (GTK4-friendly)
# ------------------------
class EditDialog(Adw.Window):
    def __init__(self, parent: Gtk.Window, *, title: str, initial: AppRow):
        super().__init__(transient_for=parent, modal=True)
        self.set_title(title)
        self.set_default_size(520, 260)

        self._result: Optional[AppRow] = None

        root = Adw.ToolbarView()
        self.set_content(root)

        header = Adw.HeaderBar()
        root.add_top_bar(header)

        cancel_btn = Gtk.Button(label="Cancel")
        cancel_btn.connect("clicked", lambda *_: self.close())
        header.pack_start(cancel_btn)

        save_btn = Gtk.Button(label="Save")
        save_btn.add_css_class("suggested-action")
        header.pack_end(save_btn)

        # Content
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        group = Adw.PreferencesGroup(title="WlOverview item")
        box.append(group)

        self.title_entry = Gtk.Entry()
        self.title_entry.set_text(initial.title)
        row1 = Adw.ActionRow(title="Title")
        row1.add_suffix(self.title_entry)
        row1.set_activatable_widget(self.title_entry)
        group.add(row1)

        self.exec_entry = Gtk.Entry()
        self.exec_entry.set_text(initial.exec_cmd)
        row2 = Adw.ActionRow(title="Exec")
        row2.add_suffix(self.exec_entry)
        row2.set_activatable_widget(self.exec_entry)
        group.add(row2)

        self.icon_entry = Gtk.Entry()
        self.icon_entry.set_text(initial.icon)
        row3 = Adw.ActionRow(title="Icon (themed name or file path)")
        row3.add_suffix(self.icon_entry)
        row3.set_activatable_widget(self.icon_entry)
        group.add(row3)

        self.appid_entry = Gtk.Entry()
        self.appid_entry.set_text(initial.app_id)
        row4 = Adw.ActionRow(title="app_id (optional)")
        row4.add_suffix(self.appid_entry)
        row4.set_activatable_widget(self.appid_entry)
        group.add(row4)

        root.set_content(box)

        def do_save(*_args):
            r = AppRow(
                {
                    "title": self.title_entry.get_text().strip(),
                    "exec": self.exec_entry.get_text().strip(),
                    "icon": self.icon_entry.get_text().strip(),
                    "app_id": self.appid_entry.get_text().strip(),
                }
            )
            self._result = r
            self.close()

        save_btn.connect("clicked", do_save)

    def get_result(self) -> Optional[AppRow]:
        return self._result


# ------------------------
# Main window
# ------------------------
class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application, backend: WlOverviewBackend):
        super().__init__(application=app)
        self.backend = backend

        self.set_title("WlOverview Config Editor")
        self.set_default_size(720, 520)

        # Toast overlay (set child ONCE; avoids assertion)
        self.toast_overlay = Adw.ToastOverlay()
        self.set_content(self.toast_overlay)

        toolbar = Adw.ToolbarView()
        self.toast_overlay.set_child(toolbar)

        header = Adw.HeaderBar()
        toolbar.add_top_bar(header)

        # Buttons
        self.btn_add = Gtk.Button(label="Add")
        self.btn_add.add_css_class("suggested-action")
        self.btn_add.connect("clicked", self.on_add)
        header.pack_start(self.btn_add)

        self.btn_remove = Gtk.Button(label="Remove")
        self.btn_remove.connect("clicked", self.on_remove)
        header.pack_start(self.btn_remove)

        self.btn_up = Gtk.Button(icon_name="go-up-symbolic")
        self.btn_up.set_tooltip_text("Move Up")
        self.btn_up.connect("clicked", self.on_move_up)
        header.pack_end(self.btn_up)

        self.btn_down = Gtk.Button(icon_name="go-down-symbolic")
        self.btn_down.set_tooltip_text("Move Down")
        self.btn_down.connect("clicked", self.on_move_down)
        header.pack_end(self.btn_down)

        self.btn_reload = Gtk.Button(label="Reload from disk")
        self.btn_reload.connect("clicked", self.on_reload)
        header.pack_end(self.btn_reload)

        # Model
        self.store = Gio.ListStore(item_type=AppRow)
        self.selection = Gtk.SingleSelection(model=self.store)
        self.selection.connect("notify::selected", lambda *_: self.update_status())

        # ListView factory with icon previews
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self.on_setup_row)
        factory.connect("bind", self.on_bind_row)

        self.listview = Gtk.ListView(model=self.selection, factory=factory)
        self.listview.set_vexpand(True)

        # Double click to edit (activate)
        self.listview.connect("activate", self.on_activate_row)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.set_child(self.listview)

        # Bottom status bar
        bottom = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bottom.set_margin_top(6)
        bottom.set_margin_bottom(10)
        bottom.set_margin_start(12)
        bottom.set_margin_end(12)

        self.status = Gtk.Label(xalign=0)
        bottom.append(self.status)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        content.append(scroller)
        content.append(bottom)

        toolbar.set_content(content)

        self.load_into_store()

    def toast(self, text: str) -> None:
        # IMPORTANT: plain text, not markup (prevents '&' parsing crash)
        t = Adw.Toast.new(text)
        self.toast_overlay.add_toast(t)

    def update_status(self) -> None:
        n = self.store.get_n_items()
        sel = self.selection.get_selected()
        if sel == Gtk.INVALID_LIST_POSITION:
            self.status.set_text(f"{n} item(s). Double-click an item to edit.")
        else:
            self.status.set_text(f"{n} item(s). Selected: #{sel + 1}. Double-click to edit.")

    def load_into_store(self) -> None:
        self.store.remove_all()
        self.backend.load()
        for d in self.backend.get_apps():
            self.store.append(AppRow(d))
        self.update_status()

    def save_from_store(self) -> None:
        apps: List[Dict[str, Any]] = []
        for i in range(self.store.get_n_items()):
            row = self.store.get_item(i)
            apps.append(row.to_dict())
        self.backend.apps = apps
        self.backend.save()

    # --- ListView row UI ---
    def on_setup_row(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        # Row: [icon]  Title (subtitle exec)
        h = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        h.set_margin_top(8)
        h.set_margin_bottom(8)
        h.set_margin_start(12)
        h.set_margin_end(12)

        img = Gtk.Image()
        img.set_pixel_size(32)

        v = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(xalign=0)
        title.add_css_class("title-4")
        subtitle = Gtk.Label(xalign=0)
        subtitle.add_css_class("dim-label")
        subtitle.set_wrap(True)

        v.append(title)
        v.append(subtitle)

        h.append(img)
        h.append(v)

        # stash widgets on the list_item
        list_item.set_child(h)
        list_item._img = img  # type: ignore[attr-defined]
        list_item._title = title  # type: ignore[attr-defined]
        list_item._subtitle = subtitle  # type: ignore[attr-defined]

    def on_bind_row(self, factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem) -> None:
        row: AppRow = list_item.get_item()
        img: Gtk.Image = list_item._img  # type: ignore[attr-defined]
        title: Gtk.Label = list_item._title  # type: ignore[attr-defined]
        subtitle: Gtk.Label = list_item._subtitle  # type: ignore[attr-defined]

        title.set_text(row.title if row.title else "(no title)")
        subtitle.set_text(row.exec_cmd if row.exec_cmd else "(no exec)")

        gicon = best_icon_for_item(row.to_dict())
        if gicon is not None:
            img.set_from_gicon(gicon)
        else:
            img.set_from_icon_name("application-x-executable-symbolic")

    # --- Actions ---
    def get_selected_index(self) -> int:
        idx = self.selection.get_selected()
        return -1 if idx == Gtk.INVALID_LIST_POSITION else int(idx)

    def on_reload(self, *_args) -> None:
        self.load_into_store()
        self.toast("Reloaded from disk")

    def on_add(self, *_args) -> None:
        initial = AppRow({"title": "", "exec": "", "icon": "", "app_id": ""})
        dlg = EditDialog(self, title="Add item", initial=initial)
        dlg.connect(
            "close-request",
            lambda *_: self._finish_add(dlg),
        )
        dlg.present()

    def _finish_add(self, dlg: EditDialog) -> bool:
        res = dlg.get_result()
        if res is not None:
            # basic validation
            if not res.title.strip() or not res.exec_cmd.strip():
                self.toast("Title and Exec are required")
            else:
                self.store.append(res)
                self.save_from_store()
                self.update_status()
                self.toast("Saved and reloaded wloverview")
        return False  # allow close

    def on_remove(self, *_args) -> None:
        idx = self.get_selected_index()
        if idx < 0:
            self.toast("Select an item to remove")
            return

        self.store.remove(idx)
        self.save_from_store()
        self.update_status()
        self.toast("Removed, saved and reloaded")

    def on_move_up(self, *_args) -> None:
        idx = self.get_selected_index()
        if idx <= 0:
            return
        item = self.store.get_item(idx)
        self.store.remove(idx)
        self.store.insert(idx - 1, item)
        self.selection.set_selected(idx - 1)
        self.save_from_store()
        self.update_status()
        self.toast("Reordered, saved and reloaded")

    def on_move_down(self, *_args) -> None:
        idx = self.get_selected_index()
        n = self.store.get_n_items()
        if idx < 0 or idx >= n - 1:
            return
        item = self.store.get_item(idx)
        self.store.remove(idx)
        self.store.insert(idx + 1, item)
        self.selection.set_selected(idx + 1)
        self.save_from_store()
        self.update_status()
        self.toast("Reordered, saved and reloaded")

    def on_activate_row(self, _listview: Gtk.ListView, position: int) -> None:
        if not (0 <= position < self.store.get_n_items()):
            return
        current: AppRow = self.store.get_item(position)

        dlg = EditDialog(self, title=f"Edit item #{position+1}", initial=current)
        dlg.connect(
            "close-request",
            lambda *_: self._finish_edit(dlg, position),
        )
        dlg.present()

    def _finish_edit(self, dlg: EditDialog, index: int) -> bool:
        res = dlg.get_result()
        if res is not None:
            if not res.title.strip() or not res.exec_cmd.strip():
                self.toast("Title and Exec are required")
            else:
                self.store.remove(index)
                self.store.insert(index, res)
                self.selection.set_selected(index)
                self.save_from_store()
                self.update_status()
                self.toast("Saved and reloaded wloverview")
        return False  # allow close


# ------------------------
# App
# ------------------------
class DockEditApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.example.WlOverviewConfigEditor",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.backend = WlOverviewBackend(CONFIG_PATH)

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = MainWindow(self, self.backend)
        win.present()


def main() -> None:
    Adw.init()
    app = DockEditApp()
    app.run(None)


if __name__ == "__main__":
    main()

