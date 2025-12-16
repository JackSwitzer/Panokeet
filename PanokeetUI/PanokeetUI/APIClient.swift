import Foundation

/// HTTP client for communicating with the Python backend
class APIClient {
    private let baseURL = "http://localhost:8765"
    private let session: URLSession

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        session = URLSession(configuration: config)
    }

    // MARK: - Toggle

    func toggle() async throws {
        let url = URL(string: "\(baseURL)/toggle")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60

        let (_, _) = try await session.data(for: request)
    }

    // MARK: - Pending

    struct PendingResponse: Codable {
        let pending: Bool
        let transcript: String?
        let duration: Double?

        var hasPending: Bool { pending }
    }

    func getPending() async throws -> PendingResponse {
        let url = URL(string: "\(baseURL)/pending")!
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(PendingResponse.self, from: data)
    }

    // MARK: - Audio Level

    struct LevelResponse: Codable {
        let level: Double
        let recording: Bool
    }

    func getLevel() async throws -> LevelResponse {
        let url = URL(string: "\(baseURL)/level")!
        let (data, _) = try await session.data(from: url)
        return try JSONDecoder().decode(LevelResponse.self, from: data)
    }

    // MARK: - Recording

    func startRecording() async throws {
        let url = URL(string: "\(baseURL)/record/start")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }
    }

    struct TranscriptResult: Codable {
        let transcript: String
        let duration: Double
    }

    func stopRecording() async throws -> TranscriptResult {
        let url = URL(string: "\(baseURL)/record/stop")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60 // Transcription can take a while

        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }

        return try JSONDecoder().decode(TranscriptResult.self, from: data)
    }

    // MARK: - Saving

    struct SaveRequest: Codable {
        let rawText: String
        let finalText: String
        let duration: Double
        let wasEdited: Bool

        enum CodingKeys: String, CodingKey {
            case rawText = "raw_text"
            case finalText = "final_text"
            case duration
            case wasEdited = "was_edited"
        }
    }

    func saveTranscript(rawText: String, finalText: String, duration: Double, wasEdited: Bool) async throws {
        let url = URL(string: "\(baseURL)/save")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        let body = SaveRequest(rawText: rawText, finalText: finalText, duration: duration, wasEdited: wasEdited)
        request.httpBody = try JSONEncoder().encode(body)

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }
    }

    func cancelTranscript() async throws {
        let url = URL(string: "\(baseURL)/cancel")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let (_, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }
    }

    // MARK: - Status

    struct StatusResponse: Codable {
        let status: String
        let recording: Bool
    }

    func getStatus() async throws -> StatusResponse {
        let url = URL(string: "\(baseURL)/status")!

        let (data, response) = try await session.data(from: url)
        guard let httpResponse = response as? HTTPURLResponse,
              httpResponse.statusCode == 200 else {
            throw APIError.requestFailed
        }

        return try JSONDecoder().decode(StatusResponse.self, from: data)
    }

    // MARK: - Health Check

    func isBackendRunning() async -> Bool {
        do {
            _ = try await getStatus()
            return true
        } catch {
            return false
        }
    }
}

enum APIError: Error, LocalizedError {
    case requestFailed
    case invalidResponse
    case backendNotRunning

    var errorDescription: String? {
        switch self {
        case .requestFailed: return "API request failed"
        case .invalidResponse: return "Invalid response from server"
        case .backendNotRunning: return "Python backend is not running"
        }
    }
}
