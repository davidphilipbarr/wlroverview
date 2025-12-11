#!/usr/bin/env python3
import math
import subprocess
import ast
import gi
import json
import os
from datetime import datetime

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib

# ---------- CSS ---------- #
CSS = """
#fullblur {
    background-color: rgba(22,22,22,.72);
}

window {
    background-color: transparent;
}

.tile {
    background-color: #38383b;
    color: white;
    border-radius: 15px;
    border: none;
    padding: 15px;
    font-size: 16px;
}

.round-tile {
    background-color: #38383b;
    border-radius: 9999px;
    padding: 12px;
}

.round-tile:hover  
{
background: #303030;
}
.close-overlay {
    padding: 8px;
    border-radius: 6px;
    opacity: 0.0;
    transition: opacity 150ms ease;
}

.tile:hover .close-overlay {
    opacity: 1.0;
}

.close-overlay:hover {
    background-color: rgba(0,0,0,0.45);
    border-radius: 6px;
}

.close-overlay image {
    color: rgba(255,255,255,0.95);
}

.dock-background {
    padding: 12px 12px;
    background-color: rgba(45,45,50,0.55);
    border-radius: 24px;
    box-shadow: rgba(255, 255, 255, 0.17) 0px 0px 0px 1px inset;
}

.dock-icon {
    padding: 5px;
    border-radius: 15px;
    margin: 0;
    transition: transform 120ms ease, background-color 120ms ease;
}

.dock-icon:hover {
    background-color: rgba(255,255,255,0.10);
}

.tile:focus-visible,
.round-tile:focus-visible {
    outline: 5px solid rgba(255,255,255,0.9);
}

.tile:hover
{
    box-shadow: inset 0 0 0 6px rgba(41,128,185,1);
}

.tile label {
    font-size: 15px;
}

.round-tile image {
    color:white;
}

.clock-label {
    color: white;
    font-size: 13px;
    font-weight: 600;
}
"""


# ---------- WINDOW LIST ---------- #
def get_windows():
    try:
        raw = subprocess.check_output(
            ["wlrctl", "toplevel", "list"], text=True
        )
    except Exception:
        return []
    windows = []
    for line in raw.splitlines():
        if ":" not in line:
            continue
        appid, title = line.split(":", 1)
        windows.append((appid.strip(), title.strip()))
    return windows


# ---------- LOAD DOCK CONFIG JSON ---------- #
def load_dock_config():
    path = os.path.expanduser("~/.config/wloverview/config.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return []


# ---------- MAIN WINDOW ---------- #
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Task Switcher")

        self.set_decorated(False)
        self.fullscreen()
        self.buttons = []
        self.columns = 1

        # Keyboard controller
        key = Gtk.EventControllerKey()
        key.connect("key-pressed", self.on_key)
        self.add_controller(key)

        # Click background to close switcher
        click = Gtk.GestureClick()
        click.connect("pressed", self.on_background_click)
        self.add_controller(click)

        # Apply CSS
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        # Monitor geometry
        display = Gdk.Display.get_default()
        monitor = display.get_monitors().get_item(0)
        geo = monitor.get_geometry()
        screen_w, screen_h = geo.width, geo.height

        winlist = get_windows()
        count = len(winlist)
        est_cols = max(1, min(5, int(math.sqrt(count)) if count else 1))
        rows = math.ceil(count / est_cols)
        height_factor = {1: 0.30, 2: 0.40, 3: 0.50, 4: 0.60}.get(rows, 0.70)

        self.container_w = int(screen_w * 0.75)
        self.container_h = int(screen_h * height_factor)

        # Overlay root
        overlay = Gtk.Overlay()
        self.set_child(overlay)

        # Blur background
        blur_box = Gtk.Box(name="fullblur")
        blur_box.set_hexpand(True)
        blur_box.set_vexpand(True)
        overlay.set_child(blur_box)

        # ---------- TOP-CENTER CLOCK ---------- #
        self.clock_label = Gtk.Label()
        self.clock_label.add_css_class("clock-label")
        self.clock_label.set_halign(Gtk.Align.CENTER)
        self.clock_label.set_valign(Gtk.Align.START)
        self.clock_label.set_margin_top(16)
        overlay.add_overlay(self.clock_label)

        # Initial clock update + refresh every 60s
        self.update_clock()
        GLib.timeout_add_seconds(60, self.update_clock)

        # Center content
        centerbox = Gtk.CenterBox()
        centerbox.set_valign(Gtk.Align.CENTER)
        centerbox.set_size_request(self.container_w, self.container_h)
        overlay.add_overlay(centerbox)

        # Grid container
        self.grid = Gtk.Grid(
            column_spacing=22,
            row_spacing=16,
            column_homogeneous=True
        )
        self.grid.set_valign(Gtk.Align.CENTER)

        self.grid_wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.grid_wrapper.set_halign(Gtk.Align.CENTER)
        self.grid_wrapper.set_valign(Gtk.Align.CENTER)
        self.grid_wrapper.set_hexpand(True)
        self.grid_wrapper.set_vexpand(True)

        # ---------- ROUND WORKSPACE NAV BUTTONS (RESTORED) ---------- #
        nav_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=35)
        nav_row.set_halign(Gtk.Align.CENTER)
        nav_row.set_margin_bottom(35)

        prev_icon = Gtk.Image.new_from_icon_name("go-previous-symbolic")
        btn_prev = Gtk.Button()
        btn_prev.add_css_class("round-tile")
        btn_prev.set_child(prev_icon)
        btn_prev.set_size_request(48, 48)
        btn_prev.connect(
            "clicked",
            lambda *_: subprocess.call(["ydotool", "key", "56:1", "105:1", "105:0", "56:0"])
        )

        next_icon = Gtk.Image.new_from_icon_name("go-next-symbolic")
        btn_next = Gtk.Button()
        btn_next.add_css_class("round-tile")
        btn_next.set_child(next_icon)
        btn_next.set_size_request(48, 48)
        btn_next.connect(
            "clicked",
            lambda *_: subprocess.call(["ydotool", "key", "56:1", "106:1", "106:0", "56:0"])
        )

        nav_row.append(btn_prev)
        nav_row.append(btn_next)

        centerbox.set_center_widget(self.grid_wrapper)

        # Add nav row above grid
        self.grid_wrapper.append(nav_row)
        self.grid_wrapper.append(self.grid)

        # Populate tiles
        self.populate()

        # Build JSON-driven dock
        self.build_dock(overlay)

    # ---------- CLOCK UPDATE ---------- #
    def update_clock(self):
        now = datetime.now()
        # Build GNOME-style text: Tue Feb 11 · 14:33
        # Use the actual numeric day to avoid %-d portability issues
        day = now.day
        time_str = now.strftime("%a %b {day} · %H:%M").format(day=day)
        self.clock_label.set_text(time_str)
        return True  # keep GLib.timeout_add_seconds repeating

    # ---------- JSON DOCK BUILDER ---------- #
    def build_dock(self, overlay):
        config = load_dock_config()
        if not config:
            return

        dock = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        dock.add_css_class("dock-background")
        dock.set_halign(Gtk.Align.CENTER)
        dock.set_valign(Gtk.Align.END)
        dock.set_margin_bottom(8)

        for entry in config:
            title = entry.get("title", "App")
            icon_name = entry.get("icon", "application-x-executable")
            exec_cmd = entry.get("exec")

            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(72)

            icon_box = Gtk.Box()
            icon_box.add_css_class("dock-icon")
            icon_box.append(icon)
            icon_box.set_tooltip_text(title)

            gesture = Gtk.GestureClick()
            gesture.connect("pressed", self.launch_exec, exec_cmd)
            icon_box.add_controller(gesture)

            dock.append(icon_box)

        overlay.add_overlay(dock)

    # ---------- Run Exec Command ---------- #
    def launch_exec(self, gesture, n_press, x, y, exec_cmd):
        if not exec_cmd:
            return
        try:
            subprocess.Popen(exec_cmd.split(" "))
        except Exception:
            pass

    # ---------- WINDOW GRID ---------- #
    def populate(self):
        windows = get_windows()
        if not windows:
            return

        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

        count = len(windows)
        spacing = 22
        MIN_TILE_W = 200
        max_tile_percent = max(0.16, min(0.40, 0.55 / math.sqrt(count)))
        adaptive_max_w = self.container_w * max_tile_percent

        best_cols = 1
        best_tile_w = 0

        for cols in range(1, count + 1):
            rows = math.ceil(count / cols)
            max_w = (self.container_w - (cols - 1) * spacing) / cols
            max_h = (self.container_h - (rows - 1) * spacing) / rows
            tile_w = min(max_w, max_h * (4 / 3), adaptive_max_w)
            tile_w = max(tile_w, MIN_TILE_W)
            if tile_w > best_tile_w:
                best_tile_w = tile_w
                best_cols = cols

        self.columns = best_cols
        rows = math.ceil(count / self.columns)
        tile_w = int(best_tile_w)
        tile_h = int(tile_w * 0.75)

        idx = 0
        for r in range(rows):
            for c in range(self.columns):
                if idx >= count:
                    break

                appid, title = windows[idx]

                vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                vbox.set_valign(Gtk.Align.CENTER)

                icon = Gtk.Image.new_from_icon_name(
                    appid if icon_theme.has_icon(appid) else "applications-system"
                )
                icon.set_pixel_size(96)

                label = Gtk.Label(label=title)
                label.set_wrap(True)
                label.set_max_width_chars(40)
                label.set_xalign(0.5)
                label.set_justify(Gtk.Justification.CENTER)

                vbox.append(icon)
                vbox.append(label)

                overlay = Gtk.Overlay()
                overlay.set_child(vbox)

                close_icon = Gtk.Image.new_from_icon_name("window-close-symbolic")
                close_box = Gtk.Box()
                close_box.add_css_class("close-overlay")
                close_box.set_halign(Gtk.Align.END)
                close_box.set_valign(Gtk.Align.START)
                close_box.set_margin_top(6)
                close_box.set_margin_end(6)
                close_box.append(close_icon)

                gesture = Gtk.GestureClick()
                gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                gesture.connect(
                    "pressed",
                    self.close_window_gesture,
                    appid,
                    title
                )
                close_box.add_controller(gesture)

                overlay.add_overlay(close_box)

                tile_btn = Gtk.Button()
                tile_btn.add_css_class("tile")
                tile_btn.set_child(overlay)
                tile_btn.set_size_request(tile_w, tile_h)
                tile_btn.connect("clicked", self.activate, appid, title)

                self.grid.attach(tile_btn, c, r, 1, 1)
                self.buttons.append(tile_btn)
                idx += 1

        if self.buttons:
            self.buttons[0].grab_focus()

    # ---------- ACTIVATE WINDOW ---------- #
    def activate(self, button, appid, title):
        subprocess.call(["wlrctl", "toplevel", "focus", appid, title])
        self.close()

    # ---------- CLOSE WINDOW ---------- #
    def close_window_gesture(self, gesture, n_press, x, y, appid, title):
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        subprocess.call(["wlrctl", "toplevel", "close", appid, title])
        return True

    # ---------- KEY NAVIGATION ---------- #
    def on_key(self, controller, keyval, keycode, state):
        from gi.repository import Gdk

        if keyval == Gdk.KEY_Escape:
            self.close()
            return True

        if not self.buttons:
            return False

        focused = Gtk.Window.get_focus(self)
        if focused not in self.buttons:
            self.buttons[0].grab_focus()
            return True

        idx = self.buttons.index(focused)

        if keyval == Gdk.KEY_Right:
            idx = (idx + 1) % len(self.buttons)
        elif keyval == Gdk.KEY_Left:
            idx = (idx - 1) % len(self.buttons)
        elif keyval == Gdk.KEY_Down:
            idx = min(idx + self.columns, len(self.buttons) - 1)
        elif keyval == Gdk.KEY_Up:
            idx = max(idx - self.columns, 0)
        elif keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            focused.clicked()
            return True
        else:
            return False

        self.buttons[idx].grab_focus()
        return True

    # ---------- CLICK-BACKGROUND CLOSE ---------- #
    def on_background_click(self, gesture, n_press, x, y):
        widget = self.pick(x, y, Gtk.PickFlags.DEFAULT)
        while widget:
            if isinstance(widget, Gtk.Button):
                return
            widget = widget.get_parent()
        self.close()


# ---------- MAIN ---------- #
def main():
    app = Gtk.Application()
    app.connect(
        "activate",
        lambda app: (
            w := MainWindow(),
            app.add_window(w),
            w.present()
        )
    )
    app.run(None)


if __name__ == "__main__":
    main()

