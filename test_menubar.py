#!/usr/bin/env python3
"""Simple test to see if menu bar icon shows."""
import rumps

class TestApp(rumps.App):
    def __init__(self):
        super().__init__("Test", title="🎤")
        self.menu = ["Click me", "Quit"]

    @rumps.clicked("Click me")
    def click(self, _):
        rumps.alert("It works!")

    @rumps.clicked("Quit")
    def quit(self, _):
        rumps.quit_application()

if __name__ == "__main__":
    print("Starting menu bar app...")
    TestApp().run()
