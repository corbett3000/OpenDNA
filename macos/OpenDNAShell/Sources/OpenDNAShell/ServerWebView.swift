import SwiftUI
import WebKit

struct ServerWebView: NSViewRepresentable {
    let url: URL
    @Binding var dnaFileInjection: DNAFileInjection?

    func makeCoordinator() -> Coordinator {
        Coordinator(parent: self)
    }

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.allowsBackForwardNavigationGestures = true
        webView.setValue(false, forKey: "drawsBackground")
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        context.coordinator.parent = self
        if webView.url?.absoluteString != url.absoluteString {
            webView.load(URLRequest(url: url))
        }
        context.coordinator.tryInjectFilePath(into: webView)
    }

    final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: ServerWebView
        private var isLoaded = false
        private var lastInjectedID: UUID?

        init(parent: ServerWebView) {
            self.parent = parent
        }

        func webView(_ webView: WKWebView, didStartProvisionalNavigation _: WKNavigation!) {
            isLoaded = false
            lastInjectedID = nil
        }

        func webView(_ webView: WKWebView, didFinish _: WKNavigation!) {
            isLoaded = true
            tryInjectFilePath(into: webView)
        }

        func tryInjectFilePath(into webView: WKWebView) {
            guard isLoaded, let injection = parent.dnaFileInjection else {
                return
            }
            guard injection.id != lastInjectedID else {
                return
            }

            let jsString = quotedJavaScriptString(injection.path)
            let script = """
            (function() {
              const input = document.getElementById('file-path');
              if (!input) { return false; }
              input.value = \(jsString);
              input.dispatchEvent(new Event('input', { bubbles: true }));
              input.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            })();
            """
            webView.evaluateJavaScript(script) { _, _ in
                self.lastInjectedID = injection.id
            }
        }

        private func quotedJavaScriptString(_ value: String) -> String {
            let payload = try? JSONSerialization.data(withJSONObject: [value], options: [])
            let arrayLiteral = String(data: payload ?? Data("[]".utf8), encoding: .utf8) ?? "[]"
            return String(arrayLiteral.dropFirst().dropLast())
        }
    }
}
