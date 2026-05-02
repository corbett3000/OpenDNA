import AppKit
import Foundation
import Darwin
import SwiftUI

struct DNAFileInjection: Identifiable, Equatable {
    let id = UUID()
    let path: String
}

@MainActor
final class ShellViewModel: ObservableObject {
    enum Phase: Equatable {
        case locating
        case needsRepo(String)
        case starting
        case running
        case failed(String)

        var title: String {
            switch self {
            case .locating:
                return "Locating checkout"
            case .needsRepo:
                return "Choose OpenDNA checkout"
            case .starting:
                return "Starting embedded engine"
            case .running:
                return "Running locally"
            case let .failed(message):
                return message.isEmpty ? "Engine failed" : "Engine failed"
            }
        }

        var message: String {
            switch self {
            case .locating:
                return "The shell is looking for this repo checkout and its local virtual environment."
            case let .needsRepo(message), let .failed(message):
                return message
            case .starting:
                return "Launching the local Python engine and waiting for the app to become ready."
            case .running:
                return "Your data still stays on this Mac. The shell is only talking to a localhost process."
            }
        }

        var symbol: String {
            switch self {
            case .locating:
                return "magnifyingglass"
            case .needsRepo:
                return "folder.badge.questionmark"
            case .starting:
                return "bolt.horizontal.circle"
            case .running:
                return "checkmark.circle.fill"
            case .failed:
                return "exclamationmark.triangle.fill"
            }
        }

        var color: Color {
            switch self {
            case .running:
                return .green
            case .failed:
                return .orange
            case .needsRepo:
                return .yellow
            case .locating, .starting:
                return .blue
            }
        }

        var allowsRepoSelection: Bool {
            switch self {
            case .needsRepo, .failed:
                return true
            case .locating, .starting, .running:
                return false
            }
        }
    }

    @Published var phase: Phase = .locating
    @Published var repoRoot: URL?
    @Published var serverURL: URL?
    @Published var managedPort: Int?
    @Published var pendingDNAFileInjection: DNAFileInjection?
    @Published var showLogs = false
    @Published var logText = ""

    private let candidatePorts = Array(8787...8795)
    private var process: Process?
    private var launchTask: Task<Void, Never>?
    private var isStopping = false

    init() {
        NotificationCenter.default.addObserver(
            forName: NSApplication.willTerminateNotification,
            object: nil,
            queue: .main
        ) { [weak self] _ in
            Task { @MainActor [weak self] in
                self?.shutdown()
            }
        }

        launchTask = Task { [weak self] in
            await self?.bootstrap()
        }
    }

    deinit {
        launchTask?.cancel()
    }

    var canRestart: Bool {
        process != nil && serverURL != nil
    }

    func chooseRepoRoot() {
        let panel = NSOpenPanel()
        panel.title = "Choose the OpenDNA checkout"
        panel.message = "Select the folder containing pyproject.toml and .venv for this repo."
        panel.prompt = "Use Checkout"
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = false
        panel.allowsMultipleSelection = false

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        repoRoot = url
        restartServer()
    }

    func revealRepoRoot() {
        guard let repoRoot else {
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([repoRoot])
    }

    func chooseDNAFile() {
        let panel = NSOpenPanel()
        panel.title = "Choose a DNA file"
        panel.message = "Select a raw DNA text file. The shell will paste its absolute path into the embedded UI."
        panel.prompt = "Use File"
        panel.allowedContentTypes = []
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false

        guard panel.runModal() == .OK, let url = panel.url else {
            return
        }

        pendingDNAFileInjection = DNAFileInjection(path: url.path)
    }

    func openInBrowser() {
        guard let serverURL else {
            return
        }
        NSWorkspace.shared.open(serverURL)
    }

    func restartServer() {
        shutdown()
        launchTask?.cancel()
        launchTask = Task { [weak self] in
            await self?.bootstrap()
        }
    }

    func shutdown() {
        isStopping = true
        process?.terminationHandler = nil
        if let process, process.isRunning {
            process.terminate()
            process.waitUntilExit()
        }
        process = nil
        isStopping = false
    }

    private func bootstrap() async {
        phase = .locating
        logText = ""
        serverURL = nil
        managedPort = nil

        guard let root = resolveRepoRoot() else {
            phase = .needsRepo(
                "The shell could not automatically find an OpenDNA checkout with a local .venv. Choose the repo root to continue."
            )
            return
        }

        repoRoot = root
        guard validateRepoRoot(root) else {
            phase = .needsRepo(
                "The selected checkout is missing either pyproject.toml, src/opendna, or .venv/bin/python3."
            )
            return
        }

        await launchServer(from: root)
    }

    private func resolveRepoRoot() -> URL? {
        let candidates = [
            ProcessInfo.processInfo.environment["OPEN_DNA_REPO_ROOT"].map(URL.init(fileURLWithPath:)),
            discoverRelativeToBundle(),
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath),
        ]
        for case let candidate? in candidates {
            if let root = walkUpToRepoRoot(startingAt: candidate) {
                return root
            }
        }
        return nil
    }

    private func discoverRelativeToBundle() -> URL? {
        let bundleURL = Bundle.main.bundleURL
        if let repo = walkUpToRepoRoot(startingAt: bundleURL) {
            return repo
        }
        return walkUpToRepoRoot(startingAt: bundleURL.deletingLastPathComponent())
    }

    private func walkUpToRepoRoot(startingAt start: URL) -> URL? {
        var current = start.standardizedFileURL
        if current.pathExtension == "app" {
            current = current.deletingLastPathComponent()
        }

        for _ in 0..<10 {
            if validateRepoLayout(current) {
                return current
            }
            let parent = current.deletingLastPathComponent()
            if parent.path == current.path {
                break
            }
            current = parent
        }
        return nil
    }

    private func validateRepoLayout(_ root: URL) -> Bool {
        let fileManager = FileManager.default
        return fileManager.fileExists(atPath: root.appendingPathComponent("pyproject.toml").path)
            && fileManager.fileExists(atPath: root.appendingPathComponent("src/opendna/server.py").path)
    }

    private func validateRepoRoot(_ root: URL) -> Bool {
        validateRepoLayout(root)
            && FileManager.default.fileExists(
                atPath: root.appendingPathComponent(".venv/bin/python3").path
            )
    }

    private func launchServer(from root: URL) async {
        phase = .starting

        guard let port = candidatePorts.first(where: isPortAvailable(_:)) else {
            phase = .failed("No free localhost port was available in the 8787–8795 range.")
            return
        }

        let python = root.appendingPathComponent(".venv/bin/python3")
        let process = Process()
        process.executableURL = python
        process.currentDirectoryURL = root
        process.arguments = ["-m", "opendna", "serve", "--host", "127.0.0.1", "--port", "\(port)"]

        var environment = ProcessInfo.processInfo.environment
        environment["PYTHONUNBUFFERED"] = "1"
        process.environment = environment

        let stdout = Pipe()
        let stderr = Pipe()
        process.standardOutput = stdout
        process.standardError = stderr

        wireOutput(stdout, prefix: "")
        wireOutput(stderr, prefix: "stderr: ")

        process.terminationHandler = { [weak self] finishedProcess in
            DispatchQueue.main.async {
                guard let self else { return }
                self.process = nil
                self.managedPort = nil
                if self.isStopping {
                    return
                }
                let status = finishedProcess.terminationStatus
                self.phase = .failed(
                    "The embedded engine exited before the shell could use it (status \(status))."
                )
            }
        }

        do {
            try process.run()
        } catch {
            phase = .failed("Failed to launch .venv Python: \(error.localizedDescription)")
            return
        }

        self.process = process
        self.managedPort = port

        let baseURL = URL(string: "http://127.0.0.1:\(port)")!
        let panelsURL = baseURL.appending(path: "api/panels")
        let ready = await waitForHealthCheck(at: panelsURL, timeoutSeconds: 12)
        guard ready else {
            shutdown()
            phase = .failed(
                "The engine never became ready on port \(port). Check the engine logs in the shell sidebar."
            )
            return
        }

        serverURL = baseURL
        phase = .running
    }

    private func wireOutput(_ pipe: Pipe, prefix: String) {
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let fragment = String(data: data, encoding: .utf8) else {
                return
            }
            DispatchQueue.main.async {
                self?.appendLog(prefix + fragment)
            }
        }
    }

    private func appendLog(_ fragment: String) {
        logText += fragment
        if logText.count > 24_000 {
            logText = String(logText.suffix(24_000))
        }
    }

    private func waitForHealthCheck(at url: URL, timeoutSeconds: Int) async -> Bool {
        for _ in 0..<(timeoutSeconds * 5) {
            if Task.isCancelled {
                return false
            }
            if await isHealthy(url: url) {
                return true
            }
            try? await Task.sleep(for: .milliseconds(200))
        }
        return false
    }

    private func isHealthy(url: URL) async -> Bool {
        var request = URLRequest(url: url)
        request.timeoutInterval = 1
        do {
            let (data, response) = try await URLSession.shared.data(for: request)
            guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                return false
            }
            let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any]
            return payload?["panels"] != nil
        } catch {
            return false
        }
    }

    private func isPortAvailable(_ port: Int) -> Bool {
        let descriptor = socket(AF_INET, SOCK_STREAM, 0)
        guard descriptor >= 0 else {
            return false
        }
        defer { close(descriptor) }

        var reuse = Int32(1)
        setsockopt(
            descriptor,
            SOL_SOCKET,
            SO_REUSEADDR,
            &reuse,
            socklen_t(MemoryLayout<Int32>.size)
        )

        var address = sockaddr_in()
        address.sin_len = UInt8(MemoryLayout<sockaddr_in>.stride)
        address.sin_family = sa_family_t(AF_INET)
        address.sin_port = in_port_t(UInt16(port).bigEndian)
        address.sin_addr = in_addr(s_addr: inet_addr("127.0.0.1"))

        let result = withUnsafePointer(to: &address) {
            $0.withMemoryRebound(to: sockaddr.self, capacity: 1) { sockaddrPtr in
                bind(descriptor, sockaddrPtr, socklen_t(MemoryLayout<sockaddr_in>.stride))
            }
        }
        return result == 0
    }
}
