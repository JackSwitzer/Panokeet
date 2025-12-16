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
        case ready, recording, transcribing, error
    }

    var statusIcon: String {
        switch status {
        case .ready: return "mic.fill"
        case .recording: return "record.circle.fill"
        case .transcribing: return "ellipsis.circle.fill"
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
                        // Just stopped recording - show transcribing
                        status = .transcribing
                        NSSound(named: "Tink")?.play()
                        stopLevelPolling()
                        // Force UI update by notifying change
                        objectWillChange.send()
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
                            updatePopupWithTranscript()
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
                            closePopupWithError()
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

        let view = RecordingView(
            appState: self,
            onCancel: { [weak self] in
                self?.cancelRecording()
                panel.close()
                self?.popupWindow = nil
                self?.stopLevelPolling()
                self?.refocusPreviousApp()
            }
        )

        panel.contentView = NSHostingView(rootView: view)
        panel.setContentSize(NSSize(width: 400, height: 150))
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        popupWindow = panel
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

    func updatePopupWithTranscript() {
        guard let panel = popupWindow as? FloatingPanel else {
            showTranscriptPopup()
            return
        }

        let transcript = currentTranscript
        let duration = currentDuration

        let view = TranscriptView(
            text: transcript,
            duration: duration,
            onSave: { [weak self] finalText in
                self?.save(original: transcript, final: finalText, duration: duration)
                panel.close()
                self?.popupWindow = nil
                self?.refocusPreviousApp()
            },
            onCancel: { [weak self] in
                self?.cancel()
                panel.close()
                self?.popupWindow = nil
                self?.refocusPreviousApp()
            }
        )

        panel.contentView = NSHostingView(rootView: view)
        panel.setContentSize(NSSize(width: 520, height: 220))
        status = .ready
    }

    func showTranscriptPopup() {
        if previousApp == nil {
            previousApp = NSWorkspace.shared.frontmostApplication
        }

        NSApp.activate(ignoringOtherApps: true)

        let panel = FloatingPanel()
        let transcript = currentTranscript
        let duration = currentDuration

        let view = TranscriptView(
            text: transcript,
            duration: duration,
            onSave: { [weak self] finalText in
                self?.save(original: transcript, final: finalText, duration: duration)
                panel.close()
                self?.popupWindow = nil
                self?.refocusPreviousApp()
            },
            onCancel: { [weak self] in
                self?.cancel()
                panel.close()
                self?.popupWindow = nil
                self?.refocusPreviousApp()
            }
        )

        panel.contentView = NSHostingView(rootView: view)
        panel.setContentSize(NSSize(width: 520, height: 220))
        panel.center()
        panel.makeKeyAndOrderFront(nil)
        popupWindow = panel
        status = .ready
    }

    func closePopupWithError() {
        stopLevelPolling()
        popupWindow?.close()
        popupWindow = nil
        status = .ready
        refocusPreviousApp()
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

// MARK: - Recording View

struct RecordingView: View {
    @ObservedObject var appState: AppState
    let onCancel: () -> Void

    var body: some View {
        VStack(spacing: 12) {
            if appState.status == .recording {
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

                WaveformView(levels: appState.levelHistory)
                    .frame(height: 60)
                    .padding(.horizontal, 20)

            } else if appState.status == .transcribing {
                Spacer()

                HStack(spacing: 12) {
                    ProgressView()
                        .scaleEffect(0.8)

                    Text("Transcribing...")
                        .font(.system(size: 18, weight: .medium))
                        .foregroundStyle(.secondary)
                }

                Spacer()
            } else {
                Spacer()
                Text("Waiting...")
                    .foregroundStyle(.tertiary)
                Spacer()
            }

            Text("Esc to cancel")
                .font(.system(size: 11))
                .foregroundStyle(.tertiary)
                .padding(.bottom, 12)
        }
        .frame(width: 380, height: 130)
        .background(.ultraThinMaterial)
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(.white.opacity(0.1), lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.3), radius: 30, y: 10)
        .onKeyPress(.escape) {
            onCancel()
            return .handled
        }
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
