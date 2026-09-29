import AppKit
import SwiftUI
import WebKit

@MainActor
final class EditorController: ObservableObject {
    weak var webView: WKWebView?
    var origin: URL?
    @Published var failure: String?

    func save() async throws {
        guard let webView else { return }
        _ = try await webView.callAsyncJavaScript(
            "if (window.jdhFlushProject) { await window.jdhFlushProject(); } return true;",
            arguments: [:], in: nil, contentWorld: .page)
    }

    func reload() {
        Task {
            do { try await save(); webView?.reload() }
            catch { failure = "Naskah belum tersimpan: \(error.localizedDescription)" }
        }
    }
}

struct StudioWebView: NSViewRepresentable {
    let url: URL
    @ObservedObject var controller: EditorController

    func makeCoordinator() -> Coordinator { Coordinator(controller: controller, origin: url) }

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.mediaTypesRequiringUserActionForPlayback = []
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.uiDelegate = context.coordinator
        view.underPageBackgroundColor = NSColor(red: 16/255, green: 18/255, blue: 22/255, alpha: 1)
        view.allowsBackForwardNavigationGestures = false
        controller.webView = view
        controller.origin = url
        view.load(URLRequest(url: url))
        return view
    }

    func updateNSView(_ view: WKWebView, context: Context) {}

    @MainActor
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate, WKDownloadDelegate {
        private let controller: EditorController
        private let origin: URL
        private var destinations: [ObjectIdentifier: (temporary: URL, final: URL)] = [:]
        init(controller: EditorController, origin: URL) {
            self.controller = controller
            self.origin = origin
        }

        private func isLocal(_ url: URL?) -> Bool {
            guard let url else { return false }
            return url.scheme == origin.scheme && url.host == origin.host && url.port == origin.port
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping @MainActor @Sendable (WKNavigationActionPolicy) -> Void) {
            guard isLocal(navigationAction.request.url) else {
                if navigationAction.navigationType == .linkActivated,
                   let url = navigationAction.request.url, url.scheme == "https" {
                    NSWorkspace.shared.open(url)
                }
                decisionHandler(.cancel)
                return
            }
            decisionHandler(navigationAction.shouldPerformDownload ? .download : .allow)
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationResponse: WKNavigationResponse,
                     decisionHandler: @escaping @MainActor @Sendable (WKNavigationResponsePolicy) -> Void) {
            guard isLocal(navigationResponse.response.url) else { decisionHandler(.cancel); return }
            decisionHandler(navigationResponse.canShowMIMEType ? .allow : .download)
        }

        func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
            download.delegate = self
        }
        func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
            download.delegate = self
        }

        func webView(_ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor @Sendable ([URL]?) -> Void) {
            guard isLocal(frame.request.url), let window = webView.window else { completionHandler(nil); return }
            let panel = NSOpenPanel()
            panel.canChooseFiles = true
            panel.canChooseDirectories = false
            panel.allowsMultipleSelection = parameters.allowsMultipleSelection
            panel.beginSheetModal(for: window) { response in
                completionHandler(response == .OK ? panel.urls : nil)
            }
        }

        func download(_ download: WKDownload, decideDestinationUsing response: URLResponse,
                      suggestedFilename: String, completionHandler: @escaping @MainActor @Sendable (URL?) -> Void) {
            guard isLocal(response.url), let window = controller.webView?.window else { completionHandler(nil); return }
            let panel = NSSavePanel()
            panel.nameFieldStringValue = URL(fileURLWithPath: suggestedFilename).lastPathComponent
            panel.canCreateDirectories = true
            panel.beginSheetModal(for: window) { [weak self] result in
                guard result == .OK, let final = panel.url, let self else { completionHandler(nil); return }
                // WebKit requires a nonexistent destination. Keep an existing file
                // untouched until the entire download succeeds, then replace atomically.
                let temporary = final.deletingLastPathComponent().appendingPathComponent(".jdh-\(UUID().uuidString).download")
                self.destinations[ObjectIdentifier(download)] = (temporary, final)
                completionHandler(temporary)
            }
        }

        func downloadDidFinish(_ download: WKDownload) {
            guard let destination = destinations.removeValue(forKey: ObjectIdentifier(download)) else { return }
            do {
                if FileManager.default.fileExists(atPath: destination.final.path) {
                    _ = try FileManager.default.replaceItemAt(destination.final, withItemAt: destination.temporary)
                } else {
                    try FileManager.default.moveItem(at: destination.temporary, to: destination.final)
                }
                NSWorkspace.shared.activateFileViewerSelecting([destination.final])
            } catch {
                controller.failure = "Tidak dapat menyimpan hasil: \(error.localizedDescription)"
            }
        }

        func download(_ download: WKDownload, didFailWithError error: Error, resumeData: Data?) {
            if let destination = destinations.removeValue(forKey: ObjectIdentifier(download)) {
                try? FileManager.default.removeItem(at: destination.temporary)
            }
            if (error as NSError).code != NSURLErrorCancelled { controller.failure = error.localizedDescription }
        }

        func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
            controller.failure = "Tampilan editor berhenti. Proyek yang tersimpan tetap aman. Muat ulang editor untuk melanjutkan."
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            if (error as NSError).code != NSURLErrorCancelled { controller.failure = error.localizedDescription }
        }

        func webView(_ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
                     initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @Sendable (Bool) -> Void) {
            guard isLocal(frame.request.url), let window = webView.window else { completionHandler(false); return }
            let alert = NSAlert()
            alert.messageText = message
            alert.addButton(withTitle: "Lanjutkan")
            alert.addButton(withTitle: "Batal")
            alert.beginSheetModal(for: window) { completionHandler($0 == .alertFirstButtonReturn) }
        }
    }
}
