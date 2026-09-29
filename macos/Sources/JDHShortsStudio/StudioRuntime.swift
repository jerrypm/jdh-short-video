import AppKit
import Foundation
import SwiftUI

@MainActor
final class StudioRuntime: ObservableObject {
    enum Phase { case starting, ready(URL), failed(String) }
    @Published var phase: Phase = .starting
    @Published var status = "Menyiapkan studio lokal…"
    private var process: Process?
    private var input: Pipe?
    private var logHandle: FileHandle?
    private var task: Task<Void, Never>?
    private var token = UUID().uuidString
    private(set) var origin: URL?
    private(set) var dataDirectory: URL!
    private(set) var logURL: URL!
    private var intentionalStop = false
    private let qaDirectory: URL? = ProcessInfo.processInfo.arguments.contains("--isolated-qa")
        ? FileManager.default.temporaryDirectory.appendingPathComponent("JDHShortsStudio-QA-" + UUID().uuidString, isDirectory: true)
        : nil

    func start() {
        guard process == nil else { return }
        phase = .starting
        intentionalStop = false
        token = UUID().uuidString
        do {
            guard let resources = Bundle.main.resourceURL else { throw RuntimeError("Bundle aplikasi tidak lengkap.") }
            let fileManager = FileManager.default
            let support: URL
            if let qaDirectory {
                support = qaDirectory
            } else {
                support = try fileManager.url(for: .applicationSupportDirectory, in: .userDomainMask, appropriateFor: nil, create: true)
                    .appendingPathComponent("JDH Shorts Studio", isDirectory: true)
            }
            dataDirectory = support.appendingPathComponent("Projects", isDirectory: true)
            try fileManager.createDirectory(at: dataDirectory, withIntermediateDirectories: true)
            logURL = support.appendingPathComponent("desktop.log")
            // One previous launch log is retained for diagnosis, without script/media content.
            if fileManager.fileExists(atPath: logURL.path) {
                let previous = support.appendingPathComponent("desktop.previous.log")
                try? fileManager.removeItem(at: previous)
                try? fileManager.moveItem(at: logURL, to: previous)
            }
            fileManager.createFile(atPath: logURL.path, contents: nil)
            logHandle = try FileHandle(forWritingTo: logURL)
            let studio = resources.appendingPathComponent("studio", isDirectory: true)
            let runtime = resources.appendingPathComponent("python", isDirectory: true)
            let executable = runtime.appendingPathComponent("bin/python3.13")
            guard fileManager.isExecutableFile(atPath: executable.path),
                  fileManager.fileExists(atPath: studio.appendingPathComponent("web/out/index.html").path)
            else { throw RuntimeError("Runtime tidak lengkap. Build ulang aplikasi dari source.") }

            var environment = ProcessInfo.processInfo.environment
            for key in ["PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "JDH_PORT", "JDH_KOKORO_DIR", "JDH_DATA_DIR", "DYLD_LIBRARY_PATH"] {
                environment.removeValue(forKey: key)
            }
            environment["PYTHONHOME"] = runtime.path
            environment["PYTHONPATH"] = runtime.appendingPathComponent("lib/python3.13/site-packages").path
            environment["PYTHONDONTWRITEBYTECODE"] = "1"
            environment["PYTHONNOUSERSITE"] = "1"
            environment["PYTHONUNBUFFERED"] = "1"
            environment["PATH"] = resources.appendingPathComponent("tools/bin").path + ":/usr/bin:/bin:/usr/sbin:/sbin"
            environment["JDH_DATA_DIR"] = dataDirectory.path
            environment["JDH_KOKORO_DIR"] = resources.appendingPathComponent("models/kokoro").path
            environment["JDH_ESPEAK_DIR"] = resources.appendingPathComponent("espeak-ng-data").path
            environment["JDH_DESKTOP_TOKEN"] = token
            environment["HF_HUB_OFFLINE"] = "1"
            environment["TRANSFORMERS_OFFLINE"] = "1"
            environment["HF_HUB_DISABLE_TELEMETRY"] = "1"
            let child = Process()
            let inputPipe = Pipe()
            let outputPipe = Pipe()
            child.executableURL = executable
            child.arguments = ["-u", studio.appendingPathComponent("scripts/desktop_server.py").path]
            child.currentDirectoryURL = studio
            child.environment = environment
            child.standardInput = inputPipe
            child.standardOutput = outputPipe
            child.standardError = logHandle
            let launchToken = token
            child.terminationHandler = { [weak self] child in
                Task { @MainActor in
                    guard let self, self.token == launchToken else { return }
                    self.process = nil
                    if !self.intentionalStop {
                        self.phase = .failed("Layanan lokal berhenti (kode \(child.terminationStatus)). Proyek tetap tersimpan. Coba buka ulang studio atau lihat log.")
                    }
                }
            }
            try child.run()
            process = child
            input = inputPipe
            status = "Menjalankan renderer dan penyimpanan lokal…"
            task = Task { [weak self] in
                do {
                    let handle = outputPipe.fileHandleForReading
                    let port = try await Task.detached {
                        var buffer = Data()
                        while buffer.count < 4096 {
                            let chunk = try handle.read(upToCount: 1) ?? Data()
                            if chunk.isEmpty { throw RuntimeError("Layanan tidak mengirim alamat lokal.") }
                            buffer.append(chunk)
                            if chunk == Data([10]) {
                                let line = String(decoding: buffer, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
                                guard line.hasPrefix("JDH_PORT="), let port = Int(line.dropFirst(9)), (1024...65535).contains(port)
                                else { throw RuntimeError("Respons startup tidak valid.") }
                                return port
                            }
                        }
                        throw RuntimeError("Respons startup terlalu panjang.")
                    }.value
                    guard let self, !Task.isCancelled else { return }
                    let address = URL(string: "http://127.0.0.1:\(port)")!
                    self.origin = address
                    for _ in 0..<80 {
                        if Task.isCancelled { return }
                        if (try? await self.health()) != nil {
                            self.phase = .ready(address)
                            self.status = "Studio siap"
                            return
                        }
                        try await Task.sleep(for: .milliseconds(250))
                    }
                    throw RuntimeError("Layanan belum siap setelah 20 detik. Lihat log lalu coba lagi.")
                } catch {
                    guard let self, !self.intentionalStop else { return }
                    self.stop()
                    self.phase = .failed(error.localizedDescription)
                }
            }
        } catch {
            stop()
            phase = .failed(error.localizedDescription)
        }
    }

    func health() async throws -> Bool {
        guard let origin else { throw RuntimeError("Layanan belum siap.") }
        var request = URLRequest(url: origin.appendingPathComponent("api/desktop/health"))
        request.setValue(token, forHTTPHeaderField: "X-JDH-Desktop")
        request.timeoutInterval = 2
        let (data, response) = try await URLSession.shared.data(for: request)
        guard (response as? HTTPURLResponse)?.statusCode == 200,
              let payload = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              payload["ready"] as? Bool == true else { throw RuntimeError("Layanan belum siap.") }
        return payload["busy"] as? Bool ?? false
    }

    func stop() {
        intentionalStop = true
        task?.cancel()
        task = nil
        try? input?.fileHandleForWriting.close()
        input = nil
        // EOF triggers graceful worker cancellation. The sidecar owns a bounded
        // shutdown deadline and also notices unexpected parent termination.
        process = nil
        origin = nil
        try? logHandle?.close()
        logHandle = nil
    }

    func revealProjects() {
        if let dataDirectory { NSWorkspace.shared.open(dataDirectory) }
    }

    func revealLog() {
        if let logURL { NSWorkspace.shared.activateFileViewerSelecting([logURL]) }
    }
}

struct RuntimeError: LocalizedError, Sendable {
    let message: String
    init(_ message: String) { self.message = message }
    var errorDescription: String? { message }
}
