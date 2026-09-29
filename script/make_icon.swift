import AppKit
import Foundation
let destination = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
for size in [16, 32, 64, 128, 256, 512, 1024] {
    let image = NSImage(size: NSSize(width: size, height: size))
    image.lockFocus()
    let scale = CGFloat(size) / 1024
    let transform = NSAffineTransform()
    transform.scale(by: scale)
    transform.concat()
    NSColor(red: 0.10, green: 0.12, blue: 0.15, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 70, y: 70, width: 884, height: 884), xRadius: 190, yRadius: 190).fill()
    NSColor(red: 200/255, green: 245/255, blue: 106/255, alpha: 1).setFill()
    NSBezierPath(roundedRect: NSRect(x: 294, y: 220, width: 436, height: 600), xRadius: 60, yRadius: 60).fill()
    NSColor(red: 0.08, green: 0.12, blue: 0.06, alpha: 1).setFill()
    let play = NSBezierPath()
    play.move(to: NSPoint(x: 446, y: 400)); play.line(to: NSPoint(x: 446, y: 626)); play.line(to: NSPoint(x: 620, y: 513)); play.close(); play.fill()
    let text = "JDH" as NSString
    text.draw(at: NSPoint(x: 437, y: 266), withAttributes: [.font: NSFont.systemFont(ofSize: 68, weight: .black), .foregroundColor: NSColor(red: 0.08, green: 0.12, blue: 0.06, alpha: 1)])
    image.unlockFocus()
    guard let tiff = image.tiffRepresentation, let bitmap = NSBitmapImageRep(data: tiff), let data = bitmap.representation(using: .png, properties: [:]) else { fatalError("Icon rendering failed") }
    if size <= 512 { try data.write(to: destination.appendingPathComponent("icon_\(size)x\(size).png")) }
    if size >= 32 { try data.write(to: destination.appendingPathComponent("icon_\(size/2)x\(size/2)@2x.png")) }
}
