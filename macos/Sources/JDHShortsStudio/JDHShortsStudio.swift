import AppKit
import SwiftUI
import Darwin
import OSLog

@main
enum JDHShortsStudioApp {
    @MainActor static func main() {
        let application = NSApplication.shared
        let delegate = StudioAppDelegate()
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}

@MainActor
final class StudioAppDelegate: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let runtime = StudioRuntime()
    let editor = EditorController()
    private var window: NSWindow?
    private var closing = false
    private var terminationApproved = false
    private var terminationSignal: DispatchSourceSignal?
    private let logger = Logger(subsystem: "com.jrdevhub.JDHShortsStudio", category: "lifecycle")

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        makeMenus()
        signal(SIGTERM, SIG_IGN)
        let source = DispatchSource.makeSignalSource(signal: SIGTERM, queue: .main)
        source.setEventHandler { NSApp.terminate(nil) }
        source.resume()
        terminationSignal = source
        let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1440, height: 960),
                              styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.title = ProcessInfo.processInfo.arguments.contains("--isolated-qa")
            ? "JDH Shorts Studio · QA" : "JDH Shorts Studio"
        window.minSize = NSSize(width: 960, height: 700)
        window.appearance = NSAppearance(named: .darkAqua)
        window.delegate = self
        window.setFrameAutosaveName("JDHStudioWindow")
        window.contentView = NSHostingView(rootView: StudioRootView(runtime: runtime, editor: editor))
        window.center()
        window.makeKeyAndOrderFront(nil)
        self.window = window
        NSApp.activate(ignoringOtherApps: true)
        runtime.start()
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        window?.makeKeyAndOrderFront(nil)
        return true
    }
    func windowShouldClose(_ sender: NSWindow) -> Bool { NSApp.terminate(nil); return false }

    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        logger.info("Quit requested")
        if terminationApproved { return .terminateNow }
        guard !closing else { return .terminateCancel }
        closing = true
        Task {
            do {
                logger.info("Saving before quit")
                try await editor.save()
                logger.info("Save completed; checking worker")
                if (try? await runtime.health()) == true, let window {
                    let alert = NSAlert()
                    alert.messageText = "Pekerjaan masih berjalan"
                    alert.informativeText = "Keluar akan membatalkan render, narasi, atau permintaan AI yang sedang diproses. Proyek sudah tersimpan."
                    alert.addButton(withTitle: "Tetap di studio")
                    alert.addButton(withTitle: "Batalkan pekerjaan & keluar")
                    let response = await alert.beginSheetModal(for: window)
                    if response != .alertSecondButtonReturn { closing = false; return }
                }
                runtime.stop()
                logger.info("Sidecar shutdown requested; quitting")
                terminationApproved = true
                sender.terminate(nil)
            } catch {
                let alert = NSAlert()
                alert.messageText = "Perubahan terakhir belum tersimpan"
                alert.informativeText = error.localizedDescription
                alert.addButton(withTitle: "Kembali ke editor")
                alert.addButton(withTitle: "Keluar tanpa menyimpan")
                let response = window == nil ? alert.runModal() : await alert.beginSheetModal(for: window!)
                let shouldQuit = response == .alertSecondButtonReturn
                closing = false
                if shouldQuit {
                    runtime.stop()
                    terminationApproved = true
                    sender.terminate(nil)
                }
            }
        }
        // Keep the normal run loop alive while MainActor awaits WebKit's save.
        // terminateLater can enter AppKit's termination loop before this Task
        // gets a chance to run. Re-enter termination only after saving finishes.
        return .terminateCancel
    }
    func applicationWillTerminate(_ notification: Notification) { runtime.stop() }

    @objc private func saveProject() {
        Task { do { try await editor.save() } catch { editor.failure = error.localizedDescription } }
    }
    @objc private func reloadEditor() { editor.reload() }
    @objc private func undoEditor() { history("undo") }
    @objc private func redoEditor() { history("redo") }
    private func history(_ direction: String) {
        Task {
            _ = try? await editor.webView?.callAsyncJavaScript(
                "if (window.jdhEditorHistory) window.jdhEditorHistory(direction); else document.execCommand(direction);",
                arguments: ["direction": direction], in: nil, contentWorld: .page)
        }
    }
    @objc private func showProjects() { runtime.revealProjects() }
    @objc private func showLog() { runtime.revealLog() }
    @objc private func showAbout() {
        NSApp.orderFrontStandardAboutPanel(options: [
            .applicationName: "JDH Shorts Studio",
            .applicationVersion: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "",
            .credits: NSAttributedString(string: "macOS desktop app · local media, Kokoro, and FFmpeg\nJRDEVHUB")
        ])
    }

    private func makeMenus() {
        let main = NSMenu()
        func menu(_ title: String) -> NSMenu {
            let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
            let submenu = NSMenu(title: title)
            item.submenu = submenu; main.addItem(item)
            return submenu
        }
        func add(_ menu: NSMenu, _ title: String, _ selector: Selector, _ key: String = "", target: AnyObject? = nil) {
            let item = NSMenuItem(title: title, action: selector, keyEquivalent: key)
            item.target = target
            menu.addItem(item)
        }
        let application = menu("JDH Shorts Studio")
        add(application, "About JDH Shorts Studio", #selector(showAbout), target: self)
        application.addItem(.separator())
        add(application, "Hide JDH Shorts Studio", #selector(NSApplication.hide(_:)), "h")
        application.addItem(.separator())
        add(application, "Quit JDH Shorts Studio", #selector(NSApplication.terminate(_:)), "q")
        let file = menu("File")
        add(file, "Save Project", #selector(saveProject), "s", target: self)
        add(file, "Show Project Folder", #selector(showProjects), target: self)
        let edit = menu("Edit")
        add(edit, "Undo", #selector(undoEditor), "z", target: self)
        add(edit, "Redo", #selector(redoEditor), "Z", target: self)
        edit.addItem(.separator())
        add(edit, "Cut", #selector(NSText.cut(_:)), "x")
        add(edit, "Copy", #selector(NSText.copy(_:)), "c")
        add(edit, "Paste", #selector(NSText.paste(_:)), "v")
        add(edit, "Select All", #selector(NSText.selectAll(_:)), "a")
        let view = menu("View")
        add(view, "Reload Editor", #selector(reloadEditor), "r", target: self)
        let windows = menu("Window")
        add(windows, "Minimize", #selector(NSWindow.miniaturize(_:)), "m")
        add(windows, "Zoom", #selector(NSWindow.performZoom(_:)))
        NSApp.windowsMenu = windows
        let help = menu("Help")
        add(help, "Show Diagnostic Log", #selector(showLog), target: self)
        NSApp.mainMenu = main
    }
}

private struct StudioRootView: View {
    @ObservedObject var runtime: StudioRuntime
    @ObservedObject var editor: EditorController
    var body: some View {
        ZStack {
            Color(red: 16/255, green: 18/255, blue: 22/255).ignoresSafeArea()
            switch runtime.phase {
            case .starting:
                VStack(spacing: 20) {
                    Text("JDH").font(.system(size: 36, weight: .black)).foregroundStyle(lime)
                    Text("Shorts Studio").font(.title2.bold())
                    ProgressView().controlSize(.small)
                    Text(runtime.status).foregroundStyle(.secondary)
                }
            case .ready(let url):
                StudioWebView(url: url, controller: editor)
            case .failed(let message):
                VStack(spacing: 18) {
                    Image(systemName: "exclamationmark.triangle").font(.largeTitle).foregroundStyle(lime)
                    Text("Studio belum bisa dibuka").font(.title2.bold())
                    Text(message).multilineTextAlignment(.center).frame(maxWidth: 520)
                    HStack { Button("Lihat log") { runtime.revealLog() }; Button("Coba lagi") { runtime.start() }.buttonStyle(.borderedProminent) }
                }.padding(32)
            }
        }
        .preferredColorScheme(.dark)
        .tint(lime)
        .alert("JDH Shorts Studio", isPresented: Binding(get: { editor.failure != nil }, set: { if !$0 { editor.failure = nil } })) {
            Button("Tutup", role: .cancel) { editor.failure = nil }
        } message: { Text(editor.failure ?? "") }
    }
    private var lime: Color { Color(red: 200/255, green: 245/255, blue: 106/255) }
}
