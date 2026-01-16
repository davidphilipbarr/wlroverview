# wloverview
Python gtk4 Dash type thing for Labwc or probably all wlroots compositors. 

The 'philosopy' behind it is that nothing runs in the background, every instance is a snapshot of the current state, and realisitacally each instance will close with a single click action. It's like a super simple gnome-shell overview or xfdashboard.

It's created for Labwc but it should be (more or less) wlroots agnostic and relies only on wlroots and wayland protocols rather than any custon IPC. 

## Needs

Needs wlrctrl and ydotool
- wlrtrl for running windows
- ydotool for keybindings (on labwc, other options are available, theoretically wlrctl can do this, let me know if you figure that out...)
- wpctl for volume status

## Customising

It's not really customisable outside of editing the main file, but you can add items to the dock or style it a little, no dock items = no dock.

Top right buttons are around line 280
Workspace buttons are around line 250 (default alt+left/right for prev/next)


## Paths
Config for dock ~/.config/wloverview/config.json
Custom style ~/.config/wloverview/style.css


## Looks like this(ish):
![](screenshot.png)


## Useful 

- https://github.com/AndreasBackx/waycorner
- https://git.sr.ht/~whynothugo/wlhc


Based on this: https://github.com/alpha6z/wayland-tasklist-overview/
