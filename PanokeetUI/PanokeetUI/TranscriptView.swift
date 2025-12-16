import SwiftUI
import AppKit

struct TranscriptView: View {
    @State var text: String
    let duration: Double
    let onSave: (String) -> Void
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            // Header
            HStack {
                Text("Panokeet")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.secondary)

                Spacer()

                HStack(spacing: 4) {
                    Image(systemName: "waveform")
                        .font(.system(size: 11))
                    Text(String(format: "%.1fs", duration))
                        .font(.system(size: 12, weight: .medium, design: .monospaced))
                }
                .foregroundStyle(.secondary)
            }
            .padding(.horizontal, 20)
            .padding(.top, 16)
            .padding(.bottom, 12)

            // Text Editor with key handling
            TranscriptTextEditor(
                text: $text,
                onSubmit: { onSave(text) },
                onCancel: onCancel
            )
            .frame(minHeight: 100)
            .padding(.horizontal, 16)

            // Footer
            HStack {
                Text("Enter = Save & Copy")
                    .foregroundStyle(.tertiary)

                Text("•")
                    .foregroundStyle(.quaternary)

                Text("Esc = Cancel")
                    .foregroundStyle(.tertiary)

                Spacer()

                Button("Cancel") {
                    onCancel()
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(.black.opacity(0.1))
                )

                Button("Save") {
                    onSave(text)
                }
                .buttonStyle(.plain)
                .foregroundStyle(.white)
                .padding(.horizontal, 16)
                .padding(.vertical, 6)
                .background(
                    RoundedRectangle(cornerRadius: 6)
                        .fill(Color.orange)
                )
            }
            .font(.system(size: 12))
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 16)
        }
        .frame(width: 500)
        .frame(minHeight: 200)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(.white.opacity(0.1), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.3), radius: 30, y: 10)
    }
}

// Custom NSTextView wrapper that handles Enter key properly
struct TranscriptTextEditor: NSViewRepresentable {
    @Binding var text: String
    let onSubmit: () -> Void
    let onCancel: () -> Void

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        let textView = CustomTextView()

        textView.delegate = context.coordinator
        textView.isRichText = false
        textView.font = NSFont.systemFont(ofSize: 15)
        textView.textColor = NSColor.labelColor
        textView.backgroundColor = NSColor.black.withAlphaComponent(0.15)
        textView.insertionPointColor = NSColor.orange
        textView.isEditable = true
        textView.isSelectable = true
        textView.allowsUndo = true
        textView.textContainerInset = NSSize(width: 8, height: 8)

        textView.onSubmit = onSubmit
        textView.onCancel = onCancel

        scrollView.documentView = textView
        scrollView.hasVerticalScroller = true
        scrollView.hasHorizontalScroller = false
        scrollView.borderType = .noBorder
        scrollView.drawsBackground = false

        textView.minSize = NSSize(width: 0, height: 0)
        textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        textView.isVerticallyResizable = true
        textView.isHorizontallyResizable = false
        textView.textContainer?.containerSize = NSSize(width: scrollView.contentSize.width, height: CGFloat.greatestFiniteMagnitude)
        textView.textContainer?.widthTracksTextView = true

        // Set initial text and select all
        textView.string = text
        textView.selectAll(nil)

        // Make first responder after a tiny delay
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            textView.window?.makeFirstResponder(textView)
        }

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? CustomTextView else { return }
        if textView.string != text {
            textView.string = text
        }
        textView.onSubmit = onSubmit
        textView.onCancel = onCancel
    }

    func makeCoordinator() -> Coordinator {
        Coordinator(self)
    }

    class Coordinator: NSObject, NSTextViewDelegate {
        var parent: TranscriptTextEditor

        init(_ parent: TranscriptTextEditor) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
        }
    }
}

class CustomTextView: NSTextView {
    var onSubmit: (() -> Void)?
    var onCancel: (() -> Void)?

    override func keyDown(with event: NSEvent) {
        // Enter without shift = submit
        if event.keyCode == 36 && !event.modifierFlags.contains(.shift) {
            onSubmit?()
            return
        }
        // Escape = cancel
        if event.keyCode == 53 {
            onCancel?()
            return
        }
        super.keyDown(with: event)
    }
}

#Preview {
    TranscriptView(
        text: "Hello, this is a test transcription that demonstrates the popup window design.",
        duration: 3.5,
        onSave: { _ in },
        onCancel: { }
    )
    .padding(40)
    .background(Color.gray.opacity(0.3))
}
