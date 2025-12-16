import AppKit
import SwiftUI

/// A floating panel that stays above other windows and has a modern translucent appearance
class FloatingPanel: NSPanel {

    override init(contentRect: NSRect, styleMask style: NSWindow.StyleMask, backing backingStoreType: NSWindow.BackingStoreType, defer flag: Bool) {
        super.init(
            contentRect: contentRect,
            styleMask: [.titled, .closable, .fullSizeContentView, .nonactivatingPanel],
            backing: .buffered,
            defer: false
        )

        configure()
    }

    convenience init() {
        self.init(contentRect: .zero, styleMask: [], backing: .buffered, defer: false)
    }

    private func configure() {
        // Always on top - above everything including fullscreen apps
        level = .screenSaver
        collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary, .stationary]

        // Appearance
        isMovableByWindowBackground = true
        titlebarAppearsTransparent = true
        titleVisibility = .hidden
        backgroundColor = .clear
        isOpaque = false
        hasShadow = true

        // Don't hide on deactivate
        hidesOnDeactivate = false

        // Allow key input
        isReleasedWhenClosed = false

        // Ensure it's on top
        orderFrontRegardless()
    }

    // Allow the panel to become key window for keyboard input
    override var canBecomeKey: Bool {
        return true
    }

    override var canBecomeMain: Bool {
        return true
    }

    // Center on screen with slight upward offset
    override func center() {
        guard let screen = NSScreen.main else {
            super.center()
            return
        }

        let screenFrame = screen.visibleFrame
        let windowFrame = frame

        let x = screenFrame.midX - windowFrame.width / 2
        let y = screenFrame.midY - windowFrame.height / 2 + 50 // Slightly above center

        setFrameOrigin(NSPoint(x: x, y: y))
    }
}

/// SwiftUI wrapper for showing the floating panel
struct FloatingPanelPresenter<Content: View>: NSViewRepresentable {
    let content: Content
    @Binding var isPresented: Bool

    func makeNSView(context: Context) -> NSView {
        return NSView()
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        if isPresented {
            showPanel(content: content)
        }
    }

    private func showPanel(content: Content) {
        let panel = FloatingPanel()
        let hostingView = NSHostingView(rootView: content)
        panel.contentView = hostingView
        panel.setContentSize(hostingView.fittingSize)
        panel.center()
        panel.makeKeyAndOrderFront(nil)
    }
}
