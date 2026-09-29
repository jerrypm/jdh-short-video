// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "JDHShortsStudio",
    platforms: [.macOS(.v14)],
    products: [.executable(name: "JDHShortsStudio", targets: ["JDHShortsStudio"])],
    targets: [.executableTarget(name: "JDHShortsStudio")]
)
