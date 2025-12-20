#!/usr/bin/env python3
import math
import subprocess
import gi
import json
import os
from datetime import datetime

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib, Pango

# ---------------- CSS ---------------- #
CSS = """
#fullblur {
    background-color: rgba(22,22,26,.62);
}

window { background: transparent; }

.tile {
    background-color: #38383b;
    color: white;
    border-radius: 15px;
    padding: 15px;
}
.tile:hover {
    box-shadow: inset 0 0 0 6px rgba(41,128,185,1);
}

.tile label {
    font-size: 15px;
}

.round-tile {
    background-color: #38383b;
    border-radius: 9999px;
    padding: 10px;
}
.round-tile:hover { background: #303030; }

.round-tile image {
    color: white;
}

.clock-label {
    color: white;
    font-size: 13px;
    font-weight: 600;
}

/* Dock */
.dock-background {
    padding: 12px;
    background-color: rgba(45,45,50,0.75);
    border-radius: 28px;
    box-shadow: rgba(255,255,255,0.17) 0 0 0 1px inset;
    opacity: 0;
    transform: translateY(10px);
    transition: opacity 140ms ease-out, transform 140ms ease-out;
}
.dock-background.dock-visible {
    opacity: 1;
    transform: translateY(0);
}
.dock-icon {
    padding: 5px;
    border-radius: 15px;
    background:transparent
}
.dock-icon:hover {
    background-color: rgba(255,255,255,0.10);
}
"""

# ---------------- HELPERS ---------------- #
def get_windows():
    try:
        raw = subprocess.check_output(
            ["wlrctl", "toplevel", "list"], text=True
        )
    except Exception:
        return []

    out = []

    for line in raw.splitlines():
        if ":" not in line:
            continue

        appid, title = line.split(":", 1)
        appid = appid.strip()
        title = title.strip().lower()

        # Exclude this overview window
        if appid == "org.broomlabs.wloverview" or title == "wloverview":
            continue

        out.append((appid, title.strip()))

    return out




def load_dock_config():
    path = os.path.expanduser("~/.config/wloverview/config.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return []


# ---------------- MAIN WINDOW ---------------- #
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("wloverview")
      #   self.set_role("overview")
        self.set_decorated(False)
        self.fullscreen()

        # CSS
        provider = Gtk.CssProvider()
        provider.load_from_string(CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

        overlay = Gtk.Overlay()
        self.set_child(overlay)

        # -------- Background --------
        blur = Gtk.Box(name="fullblur")
        blur.set_hexpand(True)
        blur.set_vexpand(True)
        overlay.set_child(blur)

        # -------- Clock --------
        self.clock = Gtk.Label()
        self.clock.add_css_class("clock-label")
        self.clock.set_halign(Gtk.Align.CENTER)
        self.clock.set_valign(Gtk.Align.START)
        self.clock.set_margin_top(8)
        overlay.add_overlay(self.clock)
        self.update_clock()
        GLib.timeout_add_seconds(60, self.update_clock)

        # -------- Top-right buttons --------
        sys_buttons = Gtk.Box(spacing=10)
        sys_buttons.set_halign(Gtk.Align.END)
        sys_buttons.set_valign(Gtk.Align.START)
        sys_buttons.set_margin_top(12)
        sys_buttons.set_margin_end(12)
        overlay.add_overlay(sys_buttons)

        # Volume
        self.vol_icon = Gtk.Image.new_from_icon_name("audio-volume-high-symbolic")
        self.vol_icon.set_pixel_size(18)
        vol_btn = Gtk.Button(child=self.vol_icon)
        vol_btn.add_css_class("round-tile")
        vol_btn.set_focusable(False)
        vol_btn.connect("clicked", lambda *_: subprocess.Popen(["pavucontrol"]))
        sys_buttons.append(vol_btn)
        GLib.timeout_add(400, self.update_volume_icon)
        self.update_volume_icon()


         # Lock
        self.add_sys_button(
            sys_buttons,
            "bluetooth-active-symbolic",
            lambda *_: (subprocess.Popen(["blueman-manager"]), self.close())
        )
        
            # Lock
        self.add_sys_button(
            sys_buttons,
            "applications-system-symbolic",
            lambda *_: (subprocess.Popen(["labwc-tweaks-gtk"]), self.close())
        )


        # Lock
        self.add_sys_button(
            sys_buttons,
            "system-lock-screen-symbolic",
            lambda *_: (subprocess.Popen(["loginctl", "lock-session"]), self.close())
        )

        # -------- Center area --------
        center = Gtk.CenterBox()
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        overlay.add_overlay(center)

        center_overlay = Gtk.Overlay()
        center_overlay.set_hexpand(True)
        center_overlay.set_vexpand(True)
        center_overlay = Gtk.Overlay()
        center_overlay.set_size_request(
            int(self.get_allocated_width() * 0.75),
            int(self.get_allocated_height() * 0.6),
        )
        self.center_overlay = center_overlay

        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        wrapper.set_halign(Gtk.Align.CENTER)
        wrapper.set_valign(Gtk.Align.CENTER)

        # -------- Workspace switcher (centered) --------
        ws_box = Gtk.Box(spacing=6)
        ws_box.set_halign(Gtk.Align.CENTER)

        prev_btn = Gtk.Button(child=Gtk.Image.new_from_icon_name("go-previous-symbolic"))
        prev_btn.add_css_class("round-tile")
        prev_btn.set_focusable(False)
        prev_btn.connect(
            "clicked",
            lambda *_: subprocess.Popen(
                ["ydotool", "key", "56:1", "105:1", "105:0", "56:0"]
            )
        )

        next_btn = Gtk.Button(child=Gtk.Image.new_from_icon_name("go-next-symbolic"))
        next_btn.add_css_class("round-tile")
        next_btn.set_focusable(False)
        next_btn.connect(
            "clicked",
            lambda *_: subprocess.Popen(
                ["ydotool", "key", "56:1", "106:1", "106:0", "56:0"]
            )
        )

        ws_box.append(prev_btn)
        ws_box.append(next_btn)

        # -------- Window grid --------
        self.grid = Gtk.Grid(column_spacing=22, row_spacing=16)

        wrapper.append(ws_box)
        wrapper.append(self.grid)

        center_overlay.set_child(wrapper)
        center.set_center_widget(center_overlay)

        GLib.idle_add(self.populate)
        self.build_dock(overlay)

     # -------- Background click (window-level, safe) --------
        bg_click = Gtk.GestureClick()
        bg_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_any_empty_click(_g, _n, x, y):
            picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)

            w = picked
            while w:
        # Any button anywhere should NOT close (tiles, dock, sys buttons, workspace buttons)
                if isinstance(w, Gtk.Button):
                    return
                w = w.get_parent()

    # No button in the ancestry => empty space (background OR container gaps) => close
            self.close()

        bg_click.connect("pressed", on_any_empty_click)
        self.add_controller(bg_click)

    # ---------------- HELPERS ---------------- #
    def add_sys_button(self, parent, icon_name, callback):
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        btn = Gtk.Button(child=icon)
        btn.add_css_class("round-tile")
        btn.set_focusable(False)
        btn.connect("clicked", callback)
        parent.append(btn)

    def workspace_prev(self):
        subprocess.Popen(["wlrctl", "workspace", "prev"])

    def workspace_next(self):
        subprocess.Popen(["wlrctl", "workspace", "next"])

    def get_volume_icon(self):
        try:
            out = subprocess.check_output(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                text=True
            ).strip()
        except Exception:
            return "audio-volume-muted-symbolic"

        if "MUTED" in out:
            return "audio-volume-muted-symbolic"

        try:
            vol = float(out.split()[-1])
        except Exception:
            return "audio-volume-muted-symbolic"

        if vol == 0:
            return "audio-volume-muted-symbolic"
        elif vol < 0.33:
            return "audio-volume-low-symbolic"
        elif vol < 0.66:
            return "audio-volume-medium-symbolic"
        else:
            return "audio-volume-high-symbolic"

    def update_volume_icon(self):
        self.vol_icon.set_from_icon_name(self.get_volume_icon())
        return True

    # ---------------- UI ---------------- #
    def update_clock(self):
        self.clock.set_text(datetime.now().strftime("%a %b %-d · %H:%M"))
        return True

    def on_center_area_click(self, gesture, n_press, x, y):
        widget = self.center_overlay.pick(x, y, Gtk.PickFlags.DEFAULT)

    # Walk up the widget tree
        while widget:
        # If we clicked ANY button, do nothing
            if isinstance(widget, Gtk.Button):
                return
            widget = widget.get_parent()

    # Otherwise: empty space inside center overlay
        self.close()


    def populate(self):
    # Clear grid (GTK4-safe: Grid has no remove_all)
        child = self.grid.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.grid.remove(child)
            child = next_child

        wins = get_windows()
        if not wins:
            return True  # retry until windows exist

        w = self.get_allocated_width()
        h = self.get_allocated_height()
        if w < 200 or h < 200:
            return True  # wait until window has a real size

        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())

        count = len(wins)
        spacing = 22
        best_cols, best_w = 1, 0

        for cols in range(1, count + 1):
            rows = math.ceil(count / cols)
            max_w = (w * 0.85 - (cols - 1) * spacing) / cols
            max_h = (h * 0.6 - (rows - 1) * spacing) / rows
            tw = min(max_w, max_h * (4 / 3))
            if tw > best_w:
                best_w, best_cols = tw, cols

        rows = math.ceil(count / best_cols)
        tile_w = int(best_w)
        tile_h = int(tile_w * 0.75)

        i = 0
        for r in range(rows):
            for c in range(best_cols):
                if i >= count:
                    break

                appid, title = wins[i]

                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                content.set_halign(Gtk.Align.CENTER)
                content.set_valign(Gtk.Align.CENTER)

                icon_name = appid if icon_theme.has_icon(appid) else "applications-system"
                icon = Gtk.Image.new_from_icon_name(icon_name)
                icon.set_pixel_size(96)

                label = Gtk.Label(label=title)
                label.set_xalign(0.5)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_max_width_chars(18)
                label.set_single_line_mode(True)

                content.append(icon)
                content.append(label)

                btn = Gtk.Button()
                btn.add_css_class("tile")
                btn.set_child(content)
                btn.set_size_request(tile_w, tile_h)
                btn.connect("clicked", lambda *_: self.close())

                self.grid.attach(btn, c, r, 1, 1)
                i += 1

        return False  # STOP idle_add once tiles are built


    

    def build_dock(self, overlay):
        cfg = load_dock_config()
        if not cfg:
            return

        dock = Gtk.Box(spacing=4)
        dock.add_css_class("dock-background")
        dock.set_halign(Gtk.Align.CENTER)
        dock.set_valign(Gtk.Align.END)
        dock.set_margin_bottom(8)

        for e in cfg:
            icon = Gtk.Image.new_from_icon_name(e.get("icon"))
            icon.set_pixel_size(64)

            btn = Gtk.Button(child=icon)
            btn.add_css_class("dock-icon")
            btn.set_focusable(False)
            btn.set_size_request(74, 74)
            cmd = e.get("exec")
            btn.connect("clicked", lambda _btn, cmd=cmd: self.launch(cmd))
            dock.append(btn)

        overlay.add_overlay(dock)
        GLib.idle_add(dock.add_css_class, "dock-visible")

    def launch(self, cmd):
        subprocess.Popen(cmd.split())
        self.close()


def main():
    app = Gtk.Application(application_id="org.broomlabs.wloverview")
    app.connect("activate", lambda app: (w := MainWindow(), app.add_window(w), w.present()))
    app.run(None)


if __name__ == "__main__":
    main()

