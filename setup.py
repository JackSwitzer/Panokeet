"""
Setup script for building Panokeet.app
Run: uv run python setup.py py2app
"""

from setuptools import setup

APP = ['app.py']
DATA_FILES = []
OPTIONS = {
    'argv_emulation': False,
    'iconfile': None,  # Add icon later if desired
    'plist': {
        'CFBundleName': 'Panokeet',
        'CFBundleDisplayName': 'Panokeet',
        'CFBundleIdentifier': 'com.panokeet.whisper-dictate',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'LSUIElement': True,  # Hide from dock (menu bar app)
        'NSMicrophoneUsageDescription': 'Panokeet needs microphone access for voice transcription.',
        'NSAppleEventsUsageDescription': 'Panokeet needs accessibility access for global hotkeys.',
    },
    'packages': ['rumps', 'sounddevice', 'numpy', 'pynput', 'pyperclip'],
    'includes': [
        'AppKit', 'Foundation', 'Quartz', 'PyObjCTools',
        'recorder', 'transcriber', 'popup'
    ],
}

setup(
    name='Panokeet',
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)
