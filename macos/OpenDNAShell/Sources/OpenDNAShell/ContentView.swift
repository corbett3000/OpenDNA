import SwiftUI

struct ContentView: View {
    @ObservedObject var model: ShellViewModel

    var body: some View {
        NavigationSplitView {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    statusCard
                    actionsCard
                    repoCard
                    if model.showLogs {
                        logsCard
                    }
                }
                .padding(20)
            }
            .navigationSplitViewColumnWidth(min: 280, ideal: 320)
        } detail: {
            Group {
                if let serverURL = model.serverURL {
                    ServerWebView(
                        url: serverURL,
                        dnaFileInjection: $model.pendingDNAFileInjection
                    )
                    .overlay(alignment: .topTrailing) {
                        Text(serverURL.absoluteString)
                            .font(.system(size: 11, weight: .medium, design: .monospaced))
                            .padding(.horizontal, 10)
                            .padding(.vertical, 6)
                            .background(.ultraThinMaterial, in: Capsule())
                            .padding(16)
                    }
                } else {
                    placeholder
                }
            }
        }
        .frame(minWidth: 1120, minHeight: 760)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("OpenDNA")
                .font(.system(size: 28, weight: .bold))
            Text("Native macOS shell around the local-first analysis engine.")
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private var statusCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Label(model.phase.title, systemImage: model.phase.symbol)
                .font(.headline)
                .foregroundStyle(model.phase.color)

            Text(model.phase.message)
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            if let managedPort = model.managedPort {
                Text("Managed local engine on 127.0.0.1:\(managedPort)")
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
    }

    private var actionsCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            Button("Choose DNA File…") {
                model.chooseDNAFile()
            }
            .buttonStyle(.borderedProminent)

            Button("Restart Embedded Engine") {
                model.restartServer()
            }
            .buttonStyle(.bordered)
            .disabled(!model.canRestart)

            Button("Open in Browser") {
                model.openInBrowser()
            }
            .buttonStyle(.bordered)
            .disabled(model.serverURL == nil)

            Button(model.showLogs ? "Hide Engine Logs" : "Show Engine Logs") {
                model.showLogs.toggle()
            }
            .buttonStyle(.plain)
            .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
    }

    private var repoCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Engine Checkout")
                .font(.headline)

            if let repoRoot = model.repoRoot {
                Text(repoRoot.path)
                    .font(.system(size: 11, weight: .medium, design: .monospaced))
                    .textSelection(.enabled)
                    .foregroundStyle(.secondary)
            } else {
                Text("No valid OpenDNA checkout is currently selected.")
                    .foregroundStyle(.secondary)
            }

            HStack {
                Button("Choose Checkout…") {
                    model.chooseRepoRoot()
                }
                .buttonStyle(.bordered)

                Button("Reveal in Finder") {
                    model.revealRepoRoot()
                }
                .buttonStyle(.bordered)
                .disabled(model.repoRoot == nil)
            }
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
    }

    private var logsCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Engine Logs")
                .font(.headline)

            ScrollView {
                Text(model.logText.isEmpty ? "No engine output yet." : model.logText)
                    .font(.system(size: 11, weight: .regular, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding(10)
            }
            .frame(minHeight: 180, maxHeight: 260)
            .background(Color.black.opacity(0.08), in: RoundedRectangle(cornerRadius: 10))
        }
        .padding(16)
        .background(Color(NSColor.controlBackgroundColor), in: RoundedRectangle(cornerRadius: 14))
    }

    private var placeholder: some View {
        VStack(spacing: 14) {
            Image(systemName: model.phase.symbol)
                .font(.system(size: 40))
                .foregroundStyle(model.phase.color)

            Text(model.phase.title)
                .font(.title2.weight(.semibold))

            Text(model.phase.message)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 420)

            if model.phase.allowsRepoSelection {
                Button("Choose OpenDNA Checkout…") {
                    model.chooseRepoRoot()
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(NSColor.windowBackgroundColor))
    }
}

