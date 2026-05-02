import SwiftUI

@main
struct OpenDNAShellApp: App {
    @StateObject private var model = ShellViewModel()

    var body: some Scene {
        WindowGroup("OpenDNA") {
            ContentView(model: model)
        }
        .commands {
            CommandGroup(after: .newItem) {
                Button("Choose DNA File…") {
                    model.chooseDNAFile()
                }
                .keyboardShortcut("o")

                Button("Choose OpenDNA Checkout…") {
                    model.chooseRepoRoot()
                }
                .keyboardShortcut("o", modifiers: [.command, .shift])

                Divider()

                Button("Restart Embedded Engine") {
                    model.restartServer()
                }
                .keyboardShortcut("r", modifiers: [.command, .shift])
                .disabled(!model.canRestart)

                Button("Open in Browser") {
                    model.openInBrowser()
                }
                .keyboardShortcut("b", modifiers: [.command, .shift])
                .disabled(model.serverURL == nil)
            }
        }
    }
}

