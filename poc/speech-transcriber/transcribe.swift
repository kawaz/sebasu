@preconcurrency import AVFoundation
import CoreMedia
import Foundation
import Speech

@main
struct Transcribe {
    static func main() async throws {
        let args = Array(CommandLine.arguments.dropFirst())
        guard (args.count == 1 || args.count == 2 && args[1] == "--fast"), args[0] == "--mic" || args[0].hasSuffix(".wav") else {
            fputs("Usage: transcribe [--mic | file.wav] [--fast]\n", stderr)
            exit(2)
        }
        let locale = Locale(identifier: "ja-JP")
        let supported = await SpeechTranscriber.supportedLocales.map(\.identifier).sorted()
        let installed = await SpeechTranscriber.installedLocales.map(\.identifier).sorted()
        print("supportedLocales=\(supported)", terminator: "\n")
        print("installedLocales=\(installed)", terminator: "\n")
        guard supported.contains(where: { $0.replacingOccurrences(of: "_", with: "-") == locale.identifier }) else {
            fputs("ja-JP is not supported\n", stderr)
            exit(1)
        }
        let transcriber = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [.volatileResults, .fastResults], attributeOptions: [.audioTimeRange])
        let status = await AssetInventory.status(forModules: [transcriber])
        print("assetStatusBefore=\(status)")
        if status != .installed, let request = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            let start = ProcessInfo.processInfo.systemUptime
            print("assetDownload=start")
            try await request.downloadAndInstall()
            print(String(format: "assetDownloadSeconds=%.3f", ProcessInfo.processInfo.systemUptime - start))
        }
        print("assetStatusAfter=\(await AssetInventory.status(forModules: [transcriber]))")
        guard let format = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber]) else {
            throw NSError(domain: "SpeechPoC", code: 1, userInfo: [NSLocalizedDescriptionKey: "No compatible audio format"])
        }
        print("analyzerFormat=\(format)")
        let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        let analyzer = SpeechAnalyzer(modules: [transcriber])
        let start = ProcessInfo.processInfo.systemUptime
        let fast = args.count == 2
        let results = Task {
            for try await result in transcriber.results {
                let now = ProcessInfo.processInfo.systemUptime - start
                let range = result.range
                print(String(format: "t=%.3f audio=%.3f..%.3f lagFromRangeEnd=%.3f %@ %@", now, range.start.seconds, range.end.seconds, now - range.end.seconds, result.isFinal ? "final" : "partial", String(result.text.characters)))
                fflush(stdout)
            }
        }
        try await analyzer.start(inputSequence: stream)
        if args[0] == "--mic" {
            let permission = AVCaptureDevice.authorizationStatus(for: .audio)
            print("microphoneAuthorization=\(permission.rawValue)")
            guard permission == .authorized else {
                continuation.finish()
                await analyzer.cancelAndFinishNow()
                try await results.value
                fputs("Microphone permission not granted; exiting without triggering a system prompt.\n", stderr)
                return
            }
            let engine = AVAudioEngine()
            let input = engine.inputNode
            let inputFormat = input.outputFormat(forBus: 0)
            guard let converter = AVAudioConverter(from: inputFormat, to: format) else {
                throw NSError(domain: "SpeechPoC", code: 2, userInfo: [NSLocalizedDescriptionKey: "Cannot convert mic audio"])
            }
            input.installTap(onBus: 0, bufferSize: 2048, format: inputFormat) { buffer, _ in
                let outputCapacity = AVAudioFrameCount(Double(buffer.frameLength) * format.sampleRate / inputFormat.sampleRate) + 32
                guard let converted = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: outputCapacity) else { return }
                var supplied = false
                var error: NSError?
                _ = converter.convert(to: converted, error: &error) { _, status in
                    if supplied { status.pointee = .noDataNow; return nil }
                    supplied = true
                    status.pointee = .haveData
                    return buffer
                }
                if error == nil && converted.frameLength > 0 { continuation.yield(AnalyzerInput(buffer: converted)) }
            }
            try engine.start()
            print("micStarted=true")
            fflush(stdout)
            try await Task.sleep(for: .seconds(10))
            engine.stop()
            input.removeTap(onBus: 0)
        } else {
            let file = try AVAudioFile(forReading: URL(fileURLWithPath: args[0]))
            let sourceFormat = file.processingFormat
            guard let converter = AVAudioConverter(from: sourceFormat, to: format) else {
                throw NSError(domain: "SpeechPoC", code: 3, userInfo: [NSLocalizedDescriptionKey: "Cannot convert WAV audio"])
            }
            let frameCount: AVAudioFrameCount = 2048
            var sentFrames: Int64 = 0
            while true {
                guard let input = AVAudioPCMBuffer(pcmFormat: sourceFormat, frameCapacity: frameCount) else { break }
                let remaining = file.length - file.framePosition
                if remaining <= 0 { break }
                try file.read(into: input, frameCount: min(frameCount, AVAudioFrameCount(remaining)))
                if input.frameLength == 0 { break }
                let outputCapacity = AVAudioFrameCount(Double(input.frameLength) * format.sampleRate / sourceFormat.sampleRate) + 32
                guard let converted = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: outputCapacity) else { break }
                var supplied = false
                var conversionError: NSError?
                _ = converter.convert(to: converted, error: &conversionError) { _, status in
                    if supplied { status.pointee = .noDataNow; return nil }
                    supplied = true
                    status.pointee = .haveData
                    return input
                }
                if let conversionError { throw conversionError }
                continuation.yield(AnalyzerInput(buffer: converted))
                sentFrames += Int64(input.frameLength)
                let target = Double(sentFrames) / sourceFormat.sampleRate
                let elapsed = ProcessInfo.processInfo.systemUptime - start
                if !fast && target > elapsed { try await Task.sleep(for: .seconds(target - elapsed)) }
            }
            print(String(format: "audioDuration=%.3f feedElapsed=%.3f", Double(sentFrames) / sourceFormat.sampleRate, ProcessInfo.processInfo.systemUptime - start))
        }
        continuation.finish()
        try await analyzer.finalizeAndFinishThroughEndOfInput()
        try await results.value
        print(String(format: "totalElapsed=%.3f", ProcessInfo.processInfo.systemUptime - start))
    }
}
