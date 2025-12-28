#!/usr/bin/env python3
from datetime import datetime
import json
import os
import math
import subprocess
import shlex
import gi
import unicodedata
import re
from gi.repository import Gtk, Gdk, GLib, Pango

gi.require_version("Gtk", "4.0")

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


.running-dot {

    background-color: white;
    border-radius: 999px;
    min-width: 6px;
    min-height: 6px;
    opacity: 0.9;
}


/* ---- Close button (hover only) ---- */
.tile-close {
    margin: 6px;
    padding: 2px;
    border-radius: 9999px;
    background: rgba(0,0,0,0.6);
    opacity: 0;
    transition: opacity 120ms ease-out, background 120ms ease-out;
}
.tile:hover .tile-close {
    opacity: 1;
}
.tile-close:hover {
    background: rgba(200,60,60,0.9);
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
    box-shadow: rgba(255,255,255,0.17) 0 0 0 1px inset;
    border-radius: 28px;
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

# ---------------- TITLE NORMALIZATION ---------------- #
_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
    "\u2043": "-",  # hyphen bullet
})

_ZERO_WIDTH_RE = re.compile(r"[\u200B-\u200D\uFEFF]")

def normalize_title(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = _ZERO_WIDTH_RE.sub("", s)
    s = s.translate(_DASH_TRANSLATION)
    return " ".join(s.split())


# ---------------- HELPERS ---------------- #



def get_windows():
    try:
        raw = subprocess.check_output(["wlrctl", "toplevel", "list"], text=True)
    except Exception:
        return []

    out = []
    for line in raw.splitlines():
        if ":" not in line:
            continue

        appid, title = line.split(":", 1)
        appid = appid.strip()
        title = title.strip()

        if appid == "org.broomlabs.wloverview" or title.lower() == "wloverview":
            continue

        out.append((appid, title, normalize_title(title)))

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

def get_running_app_ids():
    wins = get_windows()
    return {appid for appid, *_ in wins}

def expand_tokens(argv):
    return [os.path.expanduser(os.path.expandvars(t)) for t in argv]


# ---------------- MAIN WINDOW ---------------- #
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("wloverview")
        self.set_decorated(False)
        self.fullscreen()

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

        # Bluetooth
        self.add_sys_button(
            sys_buttons,
            "bluetooth-active-symbolic",
            lambda *_: (subprocess.Popen(["blueman-manager"]), self.close())
        )

        # Labwc tweaks
        self.add_sys_button(
            sys_buttons,
            "applications-system-symbolic",
            lambda *_: (subprocess.Popen(["labwc-tweaks-gtk"]), self.close())
        )

        # Lock
        self.add_sys_button(
            sys_buttons,
            "system-lock-screen-symbolic",
            lambda *_: (subprocess.Popen(["swaylock", "-f", "-c", "000000"]), self.close())
        )

        # -------- Center --------
        center = Gtk.CenterBox()
        center.set_halign(Gtk.Align.CENTER)
        center.set_valign(Gtk.Align.CENTER)
        overlay.add_overlay(center)

        self.center_overlay = Gtk.Overlay()
        wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        wrapper.set_halign(Gtk.Align.CENTER)
        wrapper.set_valign(Gtk.Align.CENTER)

        self.grid = Gtk.Grid(column_spacing=22, row_spacing=16)
        wrapper.append(self.grid)

        self.center_overlay.set_child(wrapper)
        center.set_center_widget(self.center_overlay)

        GLib.idle_add(self._update_center_size)
        GLib.idle_add(self.populate)
        self.build_dock(overlay)

        # -------- Background click-to-close --------
        bg_click = Gtk.GestureClick()
        bg_click.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

        def on_bg_click(_g, _n, x, y):
            picked = self.pick(x, y, Gtk.PickFlags.DEFAULT)
            w = picked
            while w:
                if isinstance(w, Gtk.Button):
                    return
                w = w.get_parent()
            self.close()

        bg_click.connect("pressed", on_bg_click)
        self.add_controller(bg_click)

    # ---------------- Layout ---------------- #
    def _update_center_size(self):
        w = self.get_allocated_width()
        h = self.get_allocated_height()
        if w < 200 or h < 200:
            return True
        self.center_overlay.set_size_request(int(w * 0.75), int(h * 0.6))
        return False

    # ---------------- Helpers ---------------- #
    def add_sys_button(self, parent, icon_name, callback):
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        btn = Gtk.Button(child=icon)
        btn.add_css_class("round-tile")
        btn.set_focusable(False)
        btn.connect("clicked", callback)
        parent.append(btn)

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

    def focus_window(self, appid, title_raw, title_norm):
        tries = [
            ["wlrctl", "toplevel", "focus", f"app_id:{appid}", f"title:{title_raw}"],
            ["wlrctl", "toplevel", "focus", f"app_id:{appid}", f"title:{title_norm}"],
            ["wlrctl", "toplevel", "focus", f"title:{title_raw}"],
            ["wlrctl", "toplevel", "focus", f"title:{title_norm}"],
            ["wlrctl", "toplevel", "focus", f"app_id:{appid}"],
        ]
        for cmd in tries:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return

    def update_clock(self):
        self.clock.set_text(datetime.now().strftime("%a %b %-d · %H:%M"))
        return True

    # ---------------- UI ---------------- #
    def populate(self):
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt

        wins = get_windows()
        if not wins:
            return True

        w = self.get_allocated_width()
        h = self.get_allocated_height()
        if w < 200 or h < 200:
            return True

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

                appid, title_raw, title_norm = wins[i]

                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                content.set_halign(Gtk.Align.CENTER)
                content.set_valign(Gtk.Align.CENTER)

                icon_name = appid if icon_theme.has_icon(appid) else "applications-system"
                icon = Gtk.Image.new_from_icon_name(icon_name)
                icon.set_pixel_size(96)

                label = Gtk.Label(label=title_raw)
                label.set_xalign(0.5)
                label.set_ellipsize(Pango.EllipsizeMode.END)
                label.set_max_width_chars(18)
                label.set_single_line_mode(True)

                content.append(icon)
                content.append(label)

                tile_overlay = Gtk.Overlay()
                tile_overlay.set_child(content)

                close_icon = Gtk.Image.new_from_icon_name("window-close-symbolic")
                close_icon.set_pixel_size(16)
                close_btn = Gtk.Button(child=close_icon)
                close_btn.add_css_class("tile-close")
                close_btn.set_focusable(False)
                close_btn.set_halign(Gtk.Align.END)
                close_btn.set_valign(Gtk.Align.START)

                gesture = Gtk.GestureClick()
                gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

                def on_close(_g, _n, _x, _y, appid=appid, title=title_norm):
                    subprocess.Popen(
                        ["wlrctl", "toplevel", "close",
                         f"app_id:{appid}", f"title:{title}"]
                    )
                    _g.set_state(Gtk.EventSequenceState.CLAIMED)

                gesture.connect("pressed", on_close)
                close_btn.add_controller(gesture)
                tile_overlay.add_overlay(close_btn)

                btn = Gtk.Button()
                btn.add_css_class("tile")
                btn.set_child(tile_overlay)
                btn.set_size_request(tile_w, tile_h)
                btn.connect(
                    "clicked",
                    lambda _btn, a=appid, tr=title_raw, tn=title_norm:
                        (self.focus_window(a, tr, tn), self.close())
                )

                self.grid.attach(btn, c, r, 1, 1)
                i += 1

        return False

    def build_dock(self, overlay):
        cfg = load_dock_config()
        if not cfg:
            return

    # Which apps are currently running
        running_apps = {appid for appid, *_ in get_windows()}

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

            overlay_btn = Gtk.Overlay()
            overlay_btn.set_child(btn)

            app_id = e.get("app_id") or e.get("icon")
            cmd = e.get("exec")
            is_running = app_id in running_apps

        # ---- Running indicator ----
            if is_running:
                dot = Gtk.Box()
                dot.add_css_class("running-dot")
                dot.set_halign(Gtk.Align.CENTER)
                dot.set_valign(Gtk.Align.START)
                dot.set_margin_top(70)
                overlay_btn.add_overlay(dot)

        # ---- Click handling ----
            gesture = Gtk.GestureClick()
            gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

            def on_click(gesture, n_press, x, y,
                        app_id=app_id,
                        cmd=cmd,
                        is_running=is_running):
                button = gesture.get_current_button()

            # Middle click → always launch new instance
                if button == 2:
                    self.launch(cmd)

            # Left click
                elif button == 1:
                    if is_running:
                        subprocess.run(
                            ["wlrctl", "toplevel", "focus", f"app_id:{app_id}"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        self.close()
                    else:
                        self.launch(cmd)

                gesture.set_state(Gtk.EventSequenceState.CLAIMED)

            gesture.connect("pressed", on_click)
            btn.add_controller(gesture)

            dock.append(overlay_btn)

        overlay.add_overlay(dock)
        GLib.idle_add(dock.add_css_class, "dock-visible")


    def launch(self, cmd):
        if not cmd:
            self.close()
            return
        argv = expand_tokens(shlex.split(cmd))
        subprocess.Popen(argv)
        self.close()


def main():
    app = Gtk.Application(application_id="org.broomlabs.wloverview")
    app.connect("activate", lambda app: (w := MainWindow(), app.add_window(w), w.present()))
    app.run(None)


if __name__ == "__main__":
    main()

