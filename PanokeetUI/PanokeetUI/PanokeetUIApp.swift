import SwiftUI
import AppKit

@main
struct PanokeetUIApp: App {
    @StateObject private var appState = AppState()

    var body: some Scene {
        MenuBarExtra {
            MenuContent(appState: appState)
        } label: {
            Image(systemName: appState.statusIcon)
                .symbolRenderingMode(appState.isRecording ? .multicolor : .monochrome)
        }
    }
}

// MARK: - App State

class AppState: ObservableObject {
    @Published var status: Status = .ready
    @Published var currentTranscript = ""
    @Published var currentDuration: Double = 0
    @Published var audioLevel: Double = 0.0
    @Published var levelHistory: [Double] = Array(repeating: 0, count: 30)
    @Published var errorMessage: String?

    let apiClient = APIClient()
    var popupWindow: NSWindow?
    var pollTimer: Timer?
    var levelTimer: Timer?
    var previousApp: NSRunningApplication?
    var backendFailCount = 0

    enum Status {
        case ready, recording, transcribing, showingTranscript, error
    }

    var statusIcon: String {
        switch status {
        case .ready: return "mic.fill"
        case .recording: return "record.circle.fill"
        case .transcribing, .showingTranscript: return "ellipsis.circle.fill"
        case .error: return "exclamationmark.triangle.fill"
        }
    }

    var isRecording: Bool {
        status == .recording
    }

    var statusText: String {
        switch status {
        case .ready: return "Ready"
        case .recording: return "Recording..."
        case .transcribing: return "Transcribing..."
        case .showingTranscript: return "Review Transcript"
        case .error: return "Error"
        }
    }

    init() {
        startPolling()
        print("Panokeet UI ready - polling backend")
    }

    func startPolling() {
        pollTimer = Timer.scheduledTimer(withTimeInterval: 0.15, repeats: true) { [weak self] _ in
            self?.checkStatus()
        }
    }

    func checkStatus() {
        Task {
            do {
                let statusResp = try await apiClient.getStatus()
                backendFailCount = 0 // Reset on success

                await MainActor.run {
                    let wasRecording = status == .recording

                    if statusResp.recording && status != .recording {
                        // Just started recording
                        previousApp = NSWorkspace.shared.frontmostApplication
                        status = .recording
                        NSSound(named: "Morse")?.play()
                        showRecordingPopup()
                    } else if !statusResp.recording && wasRecording {
                        // Just stopped recording - SwiftUI will update automatically
                        status = .transcribing
                        NSSound(named: "Tink")?.play()
                        stopLevelPolling()
                    }
                }

                // Check for pending transcript
                let pending = try await apiClient.getPending()
                if pending.hasPending,
                   let transcript = pending.transcript,
                   let duration = pending.duration {
                    await MainActor.run {
                        if status == .transcribing {
                            currentTranscript = transcript
                            currentDuration = duration
                            NSSound(named: "Glass")?.play()
                            // SwiftUI will update automatically when status changes
                            status = .showingTranscript
                        }
                    }
                }
            } catch {
                backendFailCount += 1
                if backendFailCount > 20 { // ~3 seconds of failures
                    await MainActor.run {
                        print("Backend connection lost: \(error)")
                        if status != .ready {
                            status = .error
                            errorMessage = "Backend disconnected"
                            closePopup()
                        }
                    }
                }
            }
        }
    }

    func showRecordingPopup() {
        if previousApp == nil {
            previousApp = NSWorkspace.shared.frontmostApplication
        }

        NSApp.activate(ignoringOtherApps: true)
        startLevelPolling()

        let panel = FloatingPanel()

        let view = PopupView(
            appState: self,
            onSave: { [weak self] finalText in
                guard let self = self else { return }
                self.save(original: self.currentTranscript, final: finalText, duration: self.currentDuration)
                self.closePopup()
            },
            onCancel: { [weak self] in
                self?.cancelRecording()
                self?.closePopup()
            }
        )

        panel.contentView = NSHostingView(rootView: view)
        panel.setContentSize(NSSize(width: 520, height: 220))
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        popupWindow = panel
    }

    func closePopup() {
        stopLevelPolling()
        popupWindow?.close()
        popupWindow = nil
        status = .ready
        refocusPreviousApp()
    }

    func startLevelPolling() {
        levelHistory = Array(repeating: 0, count: 30)
        levelTimer = Timer.scheduledTimer(withTimeInterval: 0.05, repeats: true) { [weak self] _ in
            self?.fetchAudioLevel()
        }
    }

    func stopLevelPolling() {
        levelTimer?.invalidate()
        levelTimer = nil
    }

    func fetchAudioLevel() {
        Task {
            do {
                let level = try await apiClient.getLevel()
                await MainActor.run {
                    audioLevel = level.level
                    levelHistory.append(min(level.level * 10, 1.0))
                    if levelHistory.count > 30 {
                        levelHistory.removeFirst()
                    }
                }
            } catch {
                // Silently ignore level fetch errors - non-critical
            }
        }
    }

    func refocusPreviousApp() {
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { [weak self] in
            self?.previousApp?.activate(options: [])
            self?.previousApp = nil
        }
    }

    func save(original: String, final: String, duration: Double) {
        let wasEdited = original != final

        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(final, forType: .string)

        Task {
            do {
                try await apiClient.saveTranscript(
                    rawText: original,
                    finalText: final,
                    duration: duration,
                    wasEdited: wasEdited
                )
            } catch {
                print("Failed to save: \(error)")
            }
        }
    }

    func cancel() {
        status = .ready
        Task {
            do {
                try await apiClient.cancelTranscript()
            } catch {
                print("Failed to cancel: \(error)")
            }
        }
    }

    func cancelRecording() {
        status = .ready
        Task {
            do {
                let statusResp = try await apiClient.getStatus()
                if statusResp.recording {
                    _ = try await apiClient.toggle()
                }
                try await apiClient.cancelTranscript()
            } catch {
                print("Failed to cancel recording: \(error)")
            }
        }
    }

    func toggleRecording() {
        Task {
            do {
                try await apiClient.toggle()
            } catch {
                print("Failed to toggle: \(error)")
            }
        }
    }
}

// MARK: - Unified Popup View

struct PopupView: View {
    @ObservedObject var appState: AppState
    let onSave: (String) -> Void
    let onCancel: () -> Void

    var body: some View {
        Group {
            switch appState.status {
            case .recording:
                RecordingContent(levels: appState.levelHistory, onCancel: onCancel)
            case .transcribing:
                TranscribingContent(onCancel: onCancel)
            case .showingTranscript:
                TranscriptContent(
                    text: appState.currentTranscript,
                    duration: appState.currentDuration,
                    onSave: onSave,
                    onCancel: onCancel
                )
            default:
                EmptyView()
            }
        }
    }
}

// MARK: - Recording Content

struct RecordingContent: View {
    let levels: [Double]
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            HStack(spacing: 8) {
                Circle()
                    .fill(Color.red)
                    .frame(width: 10, height: 10)
                    .pulsingAnimation()

                Text("Recording")
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.secondary)
            }
            .padding(.top, 16)

            WaveformView(levels: levels)
                .frame(height: 60)
                .padding(.horizontal, 20)

            Text("Esc to cancel")
                .font(.system(size: 11))
                .foregroundStyle(.tertiary)
                .padding(.bottom, 12)
        }
        .frame(width: 500, height: 200)
        .background(Color(NSColor.windowBackgroundColor))
        .onKeyPress(.escape) {
            onCancel()
            return .handled
        }
    }
}

// MARK: - Transcribing Content

struct TranscribingContent: View {
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            Spacer()

            HStack(spacing: 12) {
                ProgressView()
                    .scaleEffect(0.8)

                Text("Transcribing...")
                    .font(.system(size: 18, weight: .medium))
                    .foregroundStyle(.secondary)
            }

            Spacer()

            Text("Esc to cancel")
                .font(.system(size: 11))
                .foregroundStyle(.tertiary)
                .padding(.bottom, 12)
        }
        .frame(width: 500, height: 200)
        .background(Color(NSColor.windowBackgroundColor))
        .onKeyPress(.escape) {
            onCancel()
            return .handled
        }
    }
}

// MARK: - Transcript Content

struct TranscriptContent: View {
    @State var text: String
    let duration: Double
    let onSave: (String) -> Void
    let onCancel: () -> Void

    init(text: String, duration: Double, onSave: @escaping (String) -> Void, onCancel: @escaping () -> Void) {
        self._text = State(initialValue: text)
        self.duration = duration
        self.onSave = onSave
        self.onCancel = onCancel
    }

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

            // Text Editor
            TranscriptTextEditorInline(
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
        .frame(width: 500, height: 200)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

// MARK: - Inline Text Editor for Transcript

struct TranscriptTextEditorInline: NSViewRepresentable {
    @Binding var text: String
    let onSubmit: () -> Void
    let onCancel: () -> Void

    func makeNSView(context: Context) -> NSScrollView {
        let scrollView = NSScrollView()
        let textView = InlineCustomTextView()

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

        textView.string = text
        textView.selectAll(nil)

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            textView.window?.makeFirstResponder(textView)
        }

        return scrollView
    }

    func updateNSView(_ scrollView: NSScrollView, context: Context) {
        guard let textView = scrollView.documentView as? InlineCustomTextView else { return }
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
        var parent: TranscriptTextEditorInline

        init(_ parent: TranscriptTextEditorInline) {
            self.parent = parent
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            parent.text = textView.string
        }
    }
}

class InlineCustomTextView: NSTextView {
    var onSubmit: (() -> Void)?
    var onCancel: (() -> Void)?

    override func keyDown(with event: NSEvent) {
        if event.keyCode == 36 && !event.modifierFlags.contains(.shift) {
            onSubmit?()
            return
        }
        if event.keyCode == 53 {
            onCancel?()
            return
        }
        super.keyDown(with: event)
    }
}

// MARK: - Waveform

struct WaveformView: View {
    let levels: [Double]

    var body: some View {
        GeometryReader { geo in
            HStack(spacing: 3) {
                ForEach(0..<levels.count, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Color.orange.opacity(0.8))
                        .frame(width: 8, height: max(4, CGFloat(levels[i]) * geo.size.height))
                        .animation(.easeOut(duration: 0.05), value: levels[i])
                }
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .center)
        }
    }
}

// MARK: - Pulsing Animation

struct PulsingModifier: ViewModifier {
    @State private var isPulsing = false

    func body(content: Content) -> some View {
        content
            .opacity(isPulsing ? 0.4 : 1.0)
            .scaleEffect(isPulsing ? 0.9 : 1.0)
            .animation(.easeInOut(duration: 0.6).repeatForever(autoreverses: true), value: isPulsing)
            .onAppear { isPulsing = true }
    }
}

extension View {
    func pulsingAnimation() -> some View {
        modifier(PulsingModifier())
    }
}

// MARK: - Menu Content

struct MenuContent: View {
    @ObservedObject var appState: AppState

    var body: some View {
        Text("Status: \(appState.statusText)")
            .foregroundStyle(.secondary)

        Divider()

        Button(appState.isRecording ? "Stop Recording" : "Start Recording") {
            appState.toggleRecording()
        }
        .keyboardShortcut("r", modifiers: [])

        Divider()

        Button("Open Training Data") {
            let path = FileManager.default.homeDirectoryForCurrentUser
                .appendingPathComponent("Desktop/Panokeet/training_data")
            NSWorkspace.shared.open(path)
        }

        Divider()

        Button("Quit Panokeet") {
            NSApp.terminate(nil)
        }
        .keyboardShortcut("q")
    }
}
