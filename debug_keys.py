#!/usr/bin/env python3
"""
Debug script to see what keycodes your keyboard actually sends.
Run this and press various keys to see their codes.
Press Esc to quit.
"""

from pynput import keyboard

def on_press(key):
    print(f"PRESS:   {key}")
    if hasattr(key, 'vk'):
        print(f"         vk={key.vk}")
    if hasattr(key, 'char'):
        print(f"         char={repr(key.char)}")
    print()

def on_release(key):
    if key == keyboard.Key.esc:
        print("Goodbye!")
        return False

print("=" * 50)
print("Key Debug Tool")
print("=" * 50)
print("Press any key to see its code.")
print("Try: Numpad 7, Numpad 8, Cmd, etc.")
print("Press Esc to quit.")
print("=" * 50)
print()

with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
    listener.join()
