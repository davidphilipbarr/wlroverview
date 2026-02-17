#!/usr/bin/env python3
from datetime import datetime
import json
import os
import math
import subprocess
import shlex
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Gio", "2.0")
try:
    gi.require_version("GdkPixbuf", "2.0")
except ValueError:
    pass # Might be already loaded or not required explicitly if typelib is found
import unicodedata
import re
import threading
from gi.repository import Gtk, Gdk, GLib, Pango, Gio, GdkPixbuf

# ---------------- KEYBINDINGS / ACTIONS ---------------- #

ACTIONS = {
##    "lock_screen": {
 #       "type": "exec",
 #       "command": "swaylock -f -c 000000",
 #   },
 #   "conf": {
 #       "type": "exec",
 #       "command": "labwc-tweaks-gtk",
 #   },
  #  "bluetooth": {
  #      "type": "exec",
  #      "command": "blueman-manager",
 #   },
}


def run_action(name):
        action = ACTIONS.get(name)
        if not action:
            print(f"[wloverview] Unknown action: {name}")
            return

        atype = action.get("type")
        cmd = action.get("command")
        if not cmd:
            return


        if atype == "wlrctl":
            subprocess.Popen(["/home/david/bin/wlrctlx"] + shlex.split(cmd))
        elif atype == "exec":
            subprocess.Popen(shlex.split(cmd))

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
    transition: background-color 200ms ease, opacity 200ms ease;
}
.tile:hover {
    box-shadow: inset 0 0 0 6px rgba(41,128,185,1);
}

/* State-specific styles */
.tile.minimized {


    box-shadow: inset 0 0 0 6px rgba(255,255,255,.1);
}
.tile.minimized:hover {
    opacity: 1.0;
    border-color: #ff4444;
}

.tile.activated {
    box-shadow: inset 0 0 0 6px rgba(41,128,185,1);

}
.tile.activated:hover {
    border-color: #ffff44;
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
    background:transparent;
    color: white;
}
.dock-icon:hover {
    background-color: rgba(255,255,255,0.10);
}
/* Custom Tooltip Popover */
popover.dock-popover contents {
    background-color: rgba(22, 22, 26, 0.95);
    color: white;
    border-radius: 12px;
    padding: 6px 12px;
    border: 1px solid rgba(255,255,255,0.1);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    margin-bottom: 12px;
}
.dock-popover-label {
    font-size: 13px;
    font-weight: 600;
}
.dock-popover-label.minimized {
    opacity: 0.5;
}

/* Workspace List */
.workspace-tile {
    background-color: #222226;
    color: #cccccc;
    border-radius: 15px;
    padding: 0px 0px;
    font-size: 14px;
    font-weight: 600;
    transition: background 160ms ease-out;
    color: rgba(255,255,255,.5);

}
.workspace-tile:hover {
    background-color: #444447;
    color: white;
}
.workspace-tile.current {
background-color:#343437;
    color: white;
    box-shadow: inset 0 0 0 2px rgba(41,128,185,1);
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
def load_user_css():
    path = os.path.expanduser("~/.config/wloverview/style.css")
    if not os.path.exists(path):
        return

    provider = Gtk.CssProvider()
    try:
        provider.load_from_path(path)
    except Exception as e:
        print(f"[wloverview] Failed to load user CSS: {e}")
        return

    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_USER,
    )

load_user_css()






def get_windows():
    """
    wlrctlx toplevel list output lines are expected as:
      appid [unique_id]: title [state]
      e.g. org.gnome.Console [332db085...]: david@huber: ~ minimized
    """
    try:
        raw = subprocess.check_output(["/home/david/bin/wlrctlx", "toplevel", "list"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    out = []
    # Regex to match: appid [id]: title
    # We parse the line manually to account for the optional state suffix
    pattern = re.compile(r"^(.+?)\s+\[([a-f0-9]+)\]:\s+(.*)$")

    for line in raw.splitlines():
        match = pattern.match(line)
        if not match:
            continue

        appid, uid, title_rest = match.groups()
        appid = appid.strip()
        uid = uid.strip()
        title_rest = title_rest.strip()
        
        state = ""
        # Check for known states at the end of the string
        if title_rest.endswith(" minimized"):
            state = "minimized"
            title = title_rest[:-10].strip() # 10 = len(" minimized")
        elif title_rest.endswith(" activated"):
            state = "activated"
            title = title_rest[:-10].strip() # 10 = len(" activated")
        else:
            title = title_rest

        # Exclude this overview window
        if appid == "org.broomlabs.wloverview" :
            continue

        out.append((appid, title, normalize_title(title), uid, state))

    return out

def get_workspaces():
    try:
        raw = subprocess.check_output(["/home/david/bin/wlrctlx", "workspace", "list"], text=True)
        return [line.strip() for line in raw.splitlines() if line.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

def get_current_workspace():
    try:
        return subprocess.check_output(["/home/david/bin/wlrctlx", "workspace", "current"], text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""

def goto_workspace(name):
    subprocess.Popen(["/home/david/bin/wlrctlx", "workspace", "activate", name])


def load_dock_config():
    path = os.path.expanduser("~/.config/wloverview/config.json")
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

def expand_tokens(argv):
    return [os.path.expanduser(os.path.expandvars(t)) for t in argv]

_ICON_CACHE = {}
_COLOR_CACHE = {}  # appid -> (r, g, b) tuple

def get_icon_color(icon_theme: Gtk.IconTheme, icon_name: str):
    """
    Extracts the dominant color from an icon, blends it with the base tile color,
    and returns an RGB tuple (r, g, b).
    """
    if not icon_name:
        return None
    
    if icon_name in _COLOR_CACHE:
        return _COLOR_CACHE[icon_name]
    
    # Base color for tiles: #38383b -> (56, 56, 59)
    base_r, base_g, base_b = 56, 56, 59
    default_val = None

    try:
        paintable = icon_theme.lookup_icon(
            icon_name, 
            None, 
            32, 
            1, 
            Gtk.TextDirection.NONE, 
            0
        )
        
        if not paintable:
            _COLOR_CACHE[icon_name] = default_val
            return default_val
            
        file = None
        if hasattr(paintable, "get_file"):
            file = paintable.get_file()
        
        if not file:
            _COLOR_CACHE[icon_name] = default_val
            return default_val
            
        path = file.get_path()
        if not path:
             _COLOR_CACHE[icon_name] = default_val
             return default_val
             
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file_at_scale(path, 32, 32, True)
        except Exception:
             _COLOR_CACHE[icon_name] = default_val
             return default_val

        width = pb.get_width()
        height = pb.get_height()
        rowstride = pb.get_rowstride()
        has_alpha = pb.get_has_alpha()
        pixels = pb.get_pixels()
        
        r_total, g_total, b_total, count = 0, 0, 0, 0
        step = 4
        n_channels = 4 if has_alpha else 3
        
        for y in range(0, height, step):
            row_start = y * rowstride
            for x in range(0, width, step):
                offset = row_start + (x * n_channels)
                if offset + n_channels > len(pixels):
                    continue
                
                if has_alpha:
                    alpha = pixels[offset + 3]
                    if alpha < 20: 
                        continue
                
                r_total += pixels[offset]
                g_total += pixels[offset + 1]
                b_total += pixels[offset + 2]
                count += 1
        
        if count == 0:
            _COLOR_CACHE[icon_name] = default_val
            return default_val
            
        ir = r_total // count
        ig = g_total // count
        ib = b_total // count
        
        # Blend with base color
        # 30% icon color, 70% base color
        ratio = 0.27
                
        fr = int(base_r * (1 - ratio) + ir * ratio)
        fg = int(base_g * (1 - ratio) + ig * ratio)
        fb = int(base_b * (1 - ratio) + ib * ratio)
        
        result = (fr, fg, fb)
        _COLOR_CACHE[icon_name] = result
        return result
        
    except Exception as e:
        print(f"Error calculating color for {icon_name}: {e}")
        _COLOR_CACHE[icon_name] = default_val
        return default_val

def pick_icon_name(icon_theme: Gtk.IconTheme, appid: str) -> str:
    """
    Resolve an icon name for a tile from an app_id.
    Tries:
      1) Cache lookup
      2) exact appid
      3) dashified appid (common theme naming)
      4) fallback
    """
    if not appid:
        return "applications-system"
    
    if appid in _ICON_CACHE:
        return _ICON_CACHE[appid]

    res = "applications-system"
    if icon_theme.has_icon(appid):
        res = appid
    else:
        dashified = appid.replace(".", "-").replace("_", "-")
        if dashified and icon_theme.has_icon(dashified):
            res = dashified
    
    _ICON_CACHE[appid] = res
    return res

# ---------------- MAIN WINDOW ---------------- #
class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__()
        self.set_title("wloverview")
        self.set_decorated(False)
        self.fullscreen()

        # Initialize responsive spacing attributes to satisfy linter
        self.ws_h = 100
        self.ws_spacing = 10
        self.wrapper_spacing = 60
        self.grid_col_spacing = 22
        self.grid_row_spacing = 16

        self.active_popover = None

# Load config + actions EARLY
# deal with this later
   #     self.config = load_config()
     #   self.actions = self.config.get("actions", {})
        
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

        # -------- Clock (Top Left) --------
        self.clock = Gtk.Label()
        self.clock.add_css_class("clock-label")
        self.clock.set_halign(Gtk.Align.START)
        self.clock.set_valign(Gtk.Align.START)
        self.clock.set_margin_top(12)
        self.clock.set_margin_start(12)
        overlay.add_overlay(self.clock)
        self.update_clock()
        GLib.timeout_add_seconds(60, self.update_clock)


        # Cache data once
        self.windows = get_windows()
        self.workspaces = get_workspaces()
        self.current_ws = get_current_workspace()

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
        self.vol_btn = Gtk.Button(child=self.vol_icon)
        self.vol_btn.add_css_class("round-tile")
        self.vol_btn.set_focusable(False)
        vol_gesture = Gtk.GestureClick()
        vol_gesture.set_button(1)
        vol_gesture.connect("pressed", lambda *_: subprocess.Popen(["pavucontrol"]))
        self.vol_btn.add_controller(vol_gesture)
        sys_buttons.append(self.vol_btn)
        
        # Battery (placeholder button)
        self.bat_icon = Gtk.Image()
        self.bat_icon.set_pixel_size(18)
        self.bat_btn = Gtk.Button(child=self.bat_icon)
        self.bat_btn.add_css_class("round-tile")
        self.bat_btn.set_focusable(False)
        self.bat_btn.set_visible(False)
        sys_buttons.append(self.bat_btn)

        # Defer status updates
        def defer_status():
            self.update_volume_icon()
            self._update_battery_status()
            GLib.timeout_add_seconds(60, self._update_battery_status)
            return False

        GLib.idle_add(defer_status)
        GLib.timeout_add(2000, self.update_volume_icon)
        # Bluetooth
       #   self.add_sys_button(
       #       sys_buttons,
        #      "bluetooth-active-symbolic",
        #      lambda *_: (run_action("bluetooth"), self.close()),
        #      "Bluetooth"
        #  )

        # Labwc tweaks
      #    self.add_sys_button(
     #         sys_buttons,
     #         "applications-system-symbolic",
     #         lambda *_: (run_action("conf"), self.close()),
     #         "Settings"
    #      )

        # Lock
       #   self.add_sys_button(
       #       sys_buttons,
       #       "system-lock-screen-symbolic",
       #       lambda *_: (run_action("lock_screen"), self.close()),
      #        "Lock Screen"
      #    )

        # -------- Center --------
        self.center_box = Gtk.CenterBox()
        self.center_box.set_halign(Gtk.Align.CENTER)
        self.center_box.set_valign(Gtk.Align.START)
        overlay.add_overlay(self.center_box)

        # Workspace list (Stacked on top of tiles)
        self.workspace_box = Gtk.Box()
        self.workspace_box.set_halign(Gtk.Align.CENTER)
        self.workspace_box.set_valign(Gtk.Align.CENTER)
        # Size and spacing will be set in _update_center_size

        self.center_overlay = Gtk.Overlay()
        self.wrapper = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.wrapper.set_halign(Gtk.Align.CENTER)
        self.wrapper.set_valign(Gtk.Align.CENTER)
        # Margins are now handled responsively in _update_center_size

        self.grid = Gtk.Grid()
        
        self.wrapper.append(self.workspace_box)
        self.wrapper.append(self.grid)

        self.center_overlay.set_child(self.wrapper)
        self.center_box.set_center_widget(self.center_overlay)

        GLib.idle_add(self._update_layout)

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
    def _update_layout(self):
        w = self.get_width()
        h = self.get_height()
        if w < 200 or h < 200: # Wait for a reasonable size
            return True
            
        # Update size calc first so populate can use the results
        self._update_center_size()
        self.populate()
        return False

    # ---------------- Layout ---------------- #
    def _update_center_size(self):
        w = self.get_width()
        h = self.get_height()
        if w < 200 or h < 200:
            return True
        
        # Take 80% of width and 75% of height for the content area
        target_h = int(h * 0.75)
        self.center_overlay.set_size_request(int(w * 0.8), target_h)
        
        # Responsive spacing calculations
        self.ws_h = int(h * 0.055) # ~2/3 of previous 100 on typical 1080p
        self.ws_spacing = int(w * 0.005) # ~10px on typical 1920w
        self.wrapper_spacing = int(h * 0.05) # ~54px on typical 1080h
        self.grid_col_spacing = int(w * 0.011) # ~21px on typical 1920w
        self.grid_row_spacing = int(h * 0.015) # ~16px on typical 1080h

        self.workspace_box.set_spacing(self.ws_spacing)
        self.workspace_box.set_size_request(-1, self.ws_h)
        self.wrapper.set_spacing(self.wrapper_spacing)
        self.grid.set_column_spacing(self.grid_col_spacing)
        self.grid.set_row_spacing(self.grid_row_spacing)

        # Set top margin to 8% (updated from 9.5% to better balance the 2/3 workspace size)
        self.center_box.set_margin_top(int(h * 0.08))
        return False

    # ---------------- Helpers ---------------- #
    
    
    
    
    
    
    def add_sys_button(self, parent, icon_name, callback, tooltip=None):
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        btn = Gtk.Button(child=icon)
        btn.add_css_class("round-tile")
        btn.set_focusable(False)
        if tooltip:
            btn.set_tooltip_text(tooltip)
        gesture = Gtk.GestureClick()
        gesture.set_button(1)
        gesture.connect("pressed", lambda *_: callback())
        btn.add_controller(gesture)
        parent.append(btn)

    def get_volume_info(self):
        try:
            out = subprocess.check_output(
                ["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"],
                text=True
            ).strip()
        except (subprocess.CalledProcessError, FileNotFoundError):
            return "audio-volume-muted-symbolic", "Volume: Muted"

        is_muted = "MUTED" in out
        
        try:
            # Output can be "Volume: 0.15" or "Volume: 0.15 [MUTED]"
            # We want the number part.
            parts = out.split()
            vol_val = 0.0
            for p in parts:
                try:
                    vol_val = float(p)
                    break
                except ValueError:
                    continue
            
            vol_pct = int(round(vol_val * 100))
        except Exception:
            vol_pct = 0

        tooltip = f"{vol_pct}%"
        if is_muted:
            tooltip += " (muted)"
            return "audio-volume-muted-symbolic", tooltip

        if vol_pct == 0:
            icon = "audio-volume-muted-symbolic"
        elif vol_pct < 33:
            icon = "audio-volume-low-symbolic"
        elif vol_pct < 66:
            icon = "audio-volume-medium-symbolic"
        else:
            icon = "audio-volume-high-symbolic"
            
        return icon, tooltip

    def update_volume_icon(self):
        def _bg():
            icon, tooltip = self.get_volume_info()
            def _ui():
                self.vol_icon.set_from_icon_name(icon)
                self.vol_btn.set_tooltip_text(tooltip)
            GLib.idle_add(_ui)
        
        threading.Thread(target=_bg, daemon=True).start()
        return True

    def _update_battery_status(self):
        def _bg():
            icon, tooltip = self.get_battery_info()
            def _ui():
                if icon:
                    self.bat_icon.set_from_icon_name(icon)
                    self.bat_btn.set_tooltip_text(tooltip)
                    self.bat_btn.set_visible(True)
                else:
                    self.bat_btn.set_visible(False)
            GLib.idle_add(_ui)

        threading.Thread(target=_bg, daemon=True).start()
        return True

    def get_battery_info(self):
        """
        Returns (icon_name, tooltip) or (None, None) if no battery found
        """
        try:
            device = subprocess.check_output(
                ["upower", "-e"],
                text=True
            ).splitlines()

            battery = next(d for d in device if "battery" in d)
        except Exception:
            return None, None

        try:
            info = subprocess.check_output(
                ["upower", "-i", battery],
                text=True
            )
        except Exception:
            return None, None

        percentage = None
        state = ""

        for line in info.splitlines():
            if "percentage:" in line:
                percentage = int(line.split(":")[1].strip().rstrip("%"))
            elif "state:" in line:
                state = line.split(":")[1].strip()

        if percentage is None:
            return None, None

        # Icon selection
        if percentage >= 90:
            icon = "battery-full-symbolic"
        elif percentage >= 60:
            icon = "battery-good-symbolic"
        elif percentage >= 30:
            icon = "battery-medium-symbolic"
        elif percentage >= 10:
            icon = "battery-low-symbolic"
        else:
            icon = "battery-caution-symbolic"

        tooltip = f"Battery: {percentage}% ({state})"
        return icon, tooltip




    # ---------- wlrctl  helpers ----------
    def focus_window(self, uid):
        """
        Focus window using wlrctlx unique ID.
        Uses run() to ensure the compositor receives the command before we close.
        """
        try:
            subprocess.run(
                ["/home/david/bin/wlrctlx", "toplevel", "focus", f"id:{uid}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False
            )
        except Exception as e:
            print(f"Error focusing window {uid}: {e}")

    def focus_appid_best(self, appid: str):
        """
        Dock focusing - use the first window that matches appid
        """
        wins = self.windows
        candidates = [(a, tr, tn, u, st) for (a, tr, tn, u, st) in wins if a == appid] # updated unpacking

        if candidates:
            _, _, _, u, _ = candidates[0]
            self.focus_window(u)
        else:
            # fallback - if no window open, we might want to launch it, 
            # but for now we just try focus by appid if wlrctlx supports it 
            # (though the ID is the preferred way)
            subprocess.Popen(
                ["/home/david/bin/wlrctlx", "toplevel", "focus", f"appid:{appid}"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

    def update_clock(self):
        self.clock.set_text(datetime.now().strftime("%A  %B %-d  %H:%M"))
        return True

    def _apply_tint_async(self, btn, icon_theme, icon_name, uid):
        """
        Calculates the icon dominant color in a background thread and updates the button's background.
        """
        def _bg_calc():
            try:
                rgb = get_icon_color(icon_theme, icon_name)
                if not rgb:
                    return

                def _ui_update():
                    # If button was destroyed or not attached, skip
                    if not btn.get_root():
                        return
                        
                    r, g, b = rgb
                    # Calculate hover color (lighten by ~20%)
                    hr = min(255, int(r * 1.2))
                    hg = min(255, int(g * 1.2))
                    hb = min(255, int(b * 1.2))
                    
                    color_css = f"rgb({r},{g},{b})"
                    hover_css = f"rgb({hr},{hg},{hb})"

                    # GTK 4.10+ replacement for per-widget provider
                    # Use unique class to avoid collision on display-level provider
                    safe_uid = "".join(c for c in uid if c.isalnum())
                    class_name = f"tint-{safe_uid}"
                    btn.add_css_class(class_name)

                    color_provider = Gtk.CssProvider()
                    css_str = f"""
                    .{class_name} {{
                        background-color: {color_css};
                    }}
                    .{class_name}:hover {{
                        background-color: {hover_css};
                    }}
                    """
                    color_provider.load_from_string(css_str)
                    
                    display = Gdk.Display.get_default()
                    Gtk.StyleContext.add_provider_for_display(display, color_provider, 601)
                    
                    # Cleanup to avoid leaking providers on the display
                    def _cleanup(_w):
                        Gtk.StyleContext.remove_provider_for_display(display, color_provider)
                    btn.connect("destroy", _cleanup)

                GLib.idle_add(_ui_update)
            except Exception as e:
                print(f"[ERROR] Async tint failed for {icon_name}: {e}")

        threading.Thread(target=_bg_calc, daemon=True).start()

    def populate(self):
        """
        Populate the grid and workspace list from cached data.
        """
        # Clear grid
        child = self.grid.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.grid.remove(child)
            child = nxt

        # Clear workspace box
        child = self.workspace_box.get_first_child()
        while child:
            nxt = child.get_next_sibling()
            self.workspace_box.remove(child)
            child = nxt

        # ---- Populate Workspaces ----
        workspaces = self.workspaces
        current_ws = self.current_ws

        ws_h = self.ws_h
        # Use a stable 16:9 ratio to prevent "flipping" while the window resizes on load
        ws_w = int(ws_h * (21/9))

        for ws in workspaces:
            btn = Gtk.Button()
            btn.add_css_class("workspace-tile")
            if ws == current_ws:
                btn.add_css_class("current")
            
            btn.set_size_request(ws_w, ws_h)

            # Custom Tooltip via Popover (matching dock style)
            tt_label = Gtk.Label(label=ws)
            tt_label.add_css_class("dock-popover-label")

            popover = Gtk.Popover()
            popover.set_child(tt_label)
            popover.set_parent(btn)
            popover.set_has_arrow(False)
            popover.set_position(Gtk.PositionType.TOP)
            popover.add_css_class("dock-popover")
            popover.set_autohide(False)

            hover_ctrl = Gtk.EventControllerMotion()
            hover_ctrl.connect("enter", lambda *_, p=popover: p.popup())
            hover_ctrl.connect("leave", lambda *_, p=popover: p.popdown())
            btn.add_controller(hover_ctrl)

            ws_gesture = Gtk.GestureClick()
            ws_gesture.set_button(1)
            ws_gesture.connect("pressed", lambda _g, _n, _x, _y, w=ws: (goto_workspace(w), self.close()))
            btn.add_controller(ws_gesture)
            self.workspace_box.append(btn)


        wins = self.windows
        if not wins:
            return False

        w = self.get_width()
        h = self.get_height()
        
        if w < 200 or h < 200:
            return True

        is_compact = w <= 1366
        icon_theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())  # pylint: disable=no-value-for-parameter

        count = len(wins)
        # Account for workspace box + wrapper spacing + margins
        # ws_h = self.ws_h, wrapper spacing = self.wrapper_spacing
        # We want to use the height of the center_overlay for calculations
        overlay_h = int(h * 0.75)
        available_h = overlay_h - self.ws_h - self.wrapper_spacing
        if available_h < 200: available_h = 200 # fallback

        spacing = self.grid_col_spacing
        best_cols, best_w = 1, 0

        for cols in range(1, count + 1):
            rows = math.ceil(count / cols)
            max_w = (w * 0.85 - (cols - 1) * spacing) / cols
            max_h = (available_h - (rows - 1) * spacing) / rows
            
            # Use square ratio for compact mode, 4:3 for normal
            ratio = 1.0 if is_compact else (4 / 3)
            tw = min(max_w, max_h * ratio)
            if tw > best_w:
                best_w, best_cols = tw, cols

        rows = math.ceil(count / best_cols)
        tile_w = int(best_w)
        # Use square ratio for compact mode height
        tile_h = int(tile_w / (1.0 if is_compact else (4 / 3)))

        i = 0
        for r in range(rows):
            for c in range(best_cols):
                if i >= count:
                    break

                appid, title_raw, _, uid, state = wins[i]

                content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
                content.set_halign(Gtk.Align.CENTER)
                content.set_valign(Gtk.Align.CENTER)

                icon_name = pick_icon_name(icon_theme, appid)
                icon = Gtk.Image.new_from_icon_name(icon_name)
                if tile_w >= 460:
                    icon_size = 112
                elif tile_w >= 260:
                    icon_size = 80
                elif tile_w >= 160:
                    icon_size = 64
                else:
                    icon_size = 48

                icon.set_pixel_size(icon_size)

                content.append(icon)
                
                if not is_compact:
                    label = Gtk.Label(label=title_raw)
                    label.set_xalign(0.5)
                    label.set_ellipsize(Pango.EllipsizeMode.END)
                    label.set_max_width_chars(38)
                    label.set_single_line_mode(True)
                    content.append(label)

                tile_overlay = Gtk.Overlay()
                if is_compact:
                    tile_overlay.set_tooltip_text(title_raw)
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

                def on_close(_g, _n, _x, _y, uid=uid):
                    try:
                        subprocess.run(
                            ["/home/david/bin/wlrctlx", "toplevel", "close", f"id:{uid}"],
                            check=False
                        )
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        pass
                    # Close overview to avoid orphan tiles
                    GLib.timeout_add(50, self.close)
                    _g.set_state(Gtk.EventSequenceState.CLAIMED)

                gesture.connect("pressed", on_close)
                close_btn.add_controller(gesture)
                tile_overlay.add_overlay(close_btn)

                btn = Gtk.Button()
                btn.add_css_class("tile")
                if state:
                    btn.add_css_class(state)
                
                # --- Dynamic Tinting (Async) ---
                self._apply_tint_async(btn, icon_theme, icon_name, uid)
                # -------------------------------

                btn.set_child(tile_overlay)
                btn.set_size_request(tile_w, tile_h)
                # Use GestureClick (pressed) for immediate, reliable activation
                # Similar to the dock implementation, this avoids issues with "clicked" (press+release)
                tile_gesture = Gtk.GestureClick()
                tile_gesture.set_button(1) # Left click
                
                def on_tile_click(g, n, x, y, u=uid):
                    self.focus_window(u)
                    # Small delay ensures compositor processes focus before window closes
                    GLib.timeout_add(50, self.close)
                    g.set_state(Gtk.EventSequenceState.CLAIMED)
                
                tile_gesture.connect("pressed", on_tile_click)
                btn.add_controller(tile_gesture)

                self.grid.attach(btn, c, r, 1, 1)
                i += 1

        return False

    def _show_window_menu(self, btn, app_id):
        # Close any existing popover
        if self.active_popover:
            self.active_popover.popdown()
            self.active_popover = None

        # Filter windows for this app
        # wins tuple: (appid, title_raw, normalize_title(title), uid, state)
        wins = [w for w in self.windows if w[0] == app_id]
        
        #  just show it if there are windows, but typically if count > 1 it is most useful.
        if not wins:
            return

        popover = Gtk.Popover()
        popover.set_parent(btn)
        popover.set_position(Gtk.PositionType.TOP)
        popover.set_has_arrow(False)
        popover.add_css_class("dock-popover")
        popover.set_autohide(True)

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        vbox.set_margin_start(4)
        vbox.set_margin_end(4)
        vbox.set_margin_top(4)
        vbox.set_margin_bottom(4)

        for _, title_raw, _, uid, state in wins:
            # We use the raw title for the menu item
            lbl = Gtk.Label(label=title_raw)
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(40)
            lbl.set_xalign(0.0) # Align left inside the button

            item_btn = Gtk.Button()
            item_btn.set_child(lbl)
            item_btn.set_has_frame(False)
            item_btn.add_css_class("dock-popover-label")
            if state == "minimized":
                item_btn.add_css_class("minimized")
            item_btn.set_halign(Gtk.Align.FILL)

            def on_item_clicked(_b, u=uid):
                self.focus_window(u)
                GLib.timeout_add(50, self.close)

            item_btn.connect("clicked", on_item_clicked)
            vbox.append(item_btn)

        popover.set_child(vbox)
        self.active_popover = popover
        
        def on_closed(_p):
            if self.active_popover == _p:
                self.active_popover = None
        
        popover.connect("closed", on_closed)
        popover.popup()

    def build_dock(self, overlay):
        """
        Build and display the dock based on the configuration.

        Args:
            overlay: The Gtk.Overlay widget to add the dock to.
        """
        cfg = load_dock_config()
        if not cfg:
            return

        # Which apps are currently running
        running_apps = {appid for appid, *_ in self.windows}

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

            # Custom Tooltip via Popover
            tt_text = e.get("title") or e.get("app_id") or e.get("icon")
            tt_label = Gtk.Label(label=tt_text)
            tt_label.add_css_class("dock-popover-label")

            popover = Gtk.Popover()
            popover.set_child(tt_label)
            popover.set_parent(btn)
            popover.set_has_arrow(False)
            popover.set_position(Gtk.PositionType.TOP)
            popover.add_css_class("dock-popover")
            popover.set_autohide(False)

            hover_ctrl = Gtk.EventControllerMotion()
            # Only show tooltip if no menu is open to avoid clutter
            def on_enter(*_, p=popover):
                if not self.active_popover:
                    p.popup()
            
            hover_ctrl.connect("enter", on_enter)
            hover_ctrl.connect("leave", lambda *_, p=popover: p.popdown())
            btn.add_controller(hover_ctrl)

            btn.set_size_request(74, 74)

            overlay_btn = Gtk.Overlay()
            overlay_btn.set_child(btn)

            app_id = e.get("app_id") or e.get("icon")
            cmd = e.get("exec")
            is_running = bool(app_id) and (app_id in running_apps)

            # ---- Running indicator ----
            if is_running:
                dot = Gtk.Box()
                dot.add_css_class("running-dot")
                dot.set_halign(Gtk.Align.CENTER)
                dot.set_valign(Gtk.Align.START)
                dot.set_margin_top(70)  # adjust this to move dot down/up
                overlay_btn.add_overlay(dot)

            # ---- Click handling ----
            gesture = Gtk.GestureClick()
            gesture.set_button(0)  # ← CRITICAL: allow left + middle + right
            gesture.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)

            def on_click(g, n_press, x, y, cmd=cmd, app_id=app_id, is_running=is_running, btn=btn):
                button = g.get_current_button()
                g.set_state(Gtk.EventSequenceState.CLAIMED)

                # Middle click: always launch a new instance
                if button == 2:
                    self.launch(cmd)
                    return
                
                # Right click: show window menu if running
                if button == 3 and is_running:
                    self._show_window_menu(btn, app_id)
                    return

                # Left click: focus or launch
                if button == 1:
                    if is_running:
                        self.focus_appid_best(app_id)
                    elif cmd:
                        self.launch(cmd)
                    GLib.timeout_add(50, self.close)
            
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
    app = Gtk.Application(
        application_id="org.broomlabs.wloverview"
    )

    def on_activate(app):
        win = app.get_active_window()
        if win:
            win.present()
            return

        w = MainWindow()
        app.add_window(w)
        w.present()

    app.connect("activate", on_activate)
    app.run(None)


if __name__ == "__main__":
    main()


