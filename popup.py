"""Popup window for editing transcriptions using PyObjC."""

import AppKit
from AppKit import (
    NSApplication, NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
    NSWindowStyleMaskResizable, NSBackingStoreBuffered, NSTextField, NSButton,
    NSFont, NSColor, NSTextView, NSScrollView, NSBezelStyleRounded, NSMakeRect,
    NSFloatingWindowLevel, NSApp, NSViewWidthSizable, NSViewHeightSizable,
    NSScreen
)
from PyObjCTools import AppHelper
import objc


class TranscriptTextView(NSTextView):
    """Custom NSTextView that handles Enter key."""

    popup = objc.ivar()

    def keyDown_(self, event):
        # Enter key (without shift) = Done
        if event.keyCode() == 36 and not (event.modifierFlags() & (1 << 17)):  # Shift
            if self.popup:
                self.popup.onDone_(None)
            return
        # Escape = Cancel
        if event.keyCode() == 53:
            if self.popup:
                self.popup.onCancel_(None)
            return
        # Pass other keys to super
        super().keyDown_(event)


class TranscriptionPopup:
    """Popup window for viewing/editing transcription before saving."""

    def __init__(self):
        self.result = None
        self.window = None
        self.text_view = None

    def show(self, transcription: str, duration: float) -> dict:
        """Show popup with transcription. Returns when user takes action."""
        self.original_text = transcription
        self.result = {'action': 'cancel', 'text': transcription, 'was_edited': False, 'needs_review': False}

        # Get screen size for centering
        screen = NSScreen.mainScreen().frame()
        width, height = 600, 300
        x = (screen.size.width - width) / 2
        y = (screen.size.height - height) / 2 + 100  # Slightly above center

        # Create window
        frame = NSMakeRect(x, y, width, height)
        style = NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskResizable
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, style, NSBackingStoreBuffered, False
        )
        self.window.setTitle_(f"🦜 Panokeet")
        self.window.setLevel_(NSFloatingWindowLevel)
        self.window.setMinSize_((400, 200))

        content = self.window.contentView()

        # Dark background
        content.setWantsLayer_(True)
        bg_color = NSColor.colorWithRed_green_blue_alpha_(0.12, 0.12, 0.14, 1.0)
        content.layer().setBackgroundColor_(bg_color.CGColor())

        # Orange accent
        orange = NSColor.colorWithRed_green_blue_alpha_(1.0, 0.6, 0.2, 1.0)

        # Duration label (top right)
        duration_label = NSTextField.labelWithString_(f"⏱ {duration:.1f}s")
        duration_label.setFrame_(NSMakeRect(width - 80, height - 45, 60, 20))
        duration_label.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12, 0.3))
        duration_label.setTextColor_(NSColor.secondaryLabelColor())
        content.addSubview_(duration_label)

        # Header
        header = NSTextField.labelWithString_("Transcription")
        header.setFrame_(NSMakeRect(20, height - 45, 200, 25))
        header.setFont_(NSFont.boldSystemFontOfSize_(16))
        header.setTextColor_(orange)
        content.addSubview_(header)

        # Text view in scroll view
        scroll_frame = NSMakeRect(20, 60, width - 40, height - 110)
        scroll = NSScrollView.alloc().initWithFrame_(scroll_frame)
        scroll.setHasVerticalScroller_(True)
        scroll.setBorderType_(0)  # No border
        scroll.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        scroll.setDrawsBackground_(False)

        text_frame = NSMakeRect(0, 0, scroll_frame.size.width - 20, scroll_frame.size.height)
        self.text_view = TranscriptTextView.alloc().initWithFrame_(text_frame)
        self.text_view.popup = self
        self.text_view.setString_(transcription)
        self.text_view.setFont_(NSFont.systemFontOfSize_(15))
        self.text_view.setTextColor_(NSColor.whiteColor())
        self.text_view.setBackgroundColor_(NSColor.colorWithRed_green_blue_alpha_(0.18, 0.18, 0.2, 1.0))
        self.text_view.setRichText_(False)
        self.text_view.setInsertionPointColor_(orange)

        scroll.setDocumentView_(self.text_view)
        content.addSubview_(scroll)

        # Hint label
        hint = NSTextField.labelWithString_("↵ Enter = Copy & Save  |  Esc = Cancel")
        hint.setFrame_(NSMakeRect(20, 20, 300, 20))
        hint.setFont_(NSFont.systemFontOfSize_(11))
        hint.setTextColor_(NSColor.tertiaryLabelColor())
        content.addSubview_(hint)

        # Done button
        done_btn = NSButton.alloc().initWithFrame_(NSMakeRect(width - 120, 15, 100, 32))
        done_btn.setTitle_("Done")
        done_btn.setBezelStyle_(NSBezelStyleRounded)
        done_btn.setTarget_(self)
        done_btn.setAction_(objc.selector(self.onDone_, signature=b'v@:@'))
        done_btn.setKeyEquivalent_("\r")
        content.addSubview_(done_btn)

        # Show and focus
        self.window.makeKeyAndOrderFront_(None)
        self.window.makeFirstResponder_(self.text_view)
        self.text_view.selectAll_(None)

        # Run modal
        NSApp.runModalForWindow_(self.window)

        return self.result

    def _get_text(self):
        return self.text_view.string()

    def _was_edited(self):
        return self._get_text() != self.original_text

    @objc.python_method
    def _close(self):
        NSApp.stopModal()
        self.window.close()

    def onDone_(self, sender):
        """Copy to clipboard AND save - the primary action."""
        text = self._get_text()
        was_edited = self._was_edited()

        # Copy to clipboard
        pb = AppKit.NSPasteboard.generalPasteboard()
        pb.clearContents()
        pb.setString_forType_(text, AppKit.NSPasteboardTypeString)

        self.result = {
            'action': 'done',
            'text': text,
            'was_edited': was_edited,
            'needs_review': not was_edited  # Flag for training data review
        }
        self._close()

    def onCancel_(self, sender):
        self.result = {
            'action': 'cancel',
            'text': self.original_text,
            'was_edited': False
        }
        self._close()


def show_transcription_popup(transcription: str, duration: float) -> dict:
    """
    Show popup for editing transcription.

    Args:
        transcription: The whisper transcription text
        duration: Audio duration in seconds

    Returns:
        dict with:
            - action: 'done' or 'cancel'
            - text: Final text (edited or original)
            - was_edited: True if user modified the text
            - needs_review: True if not edited (for training data QA)
    """
    popup = TranscriptionPopup()
    return popup.show(transcription, duration)
