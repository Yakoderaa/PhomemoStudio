namespace PhomemoStudio.Models;

public sealed class PrinterSnapshot
{
    public bool Ok { get; set; } = true;
    public bool Connected { get; set; }
    public string? DeviceName { get; set; }
    public string? Address { get; set; }
    public int? Battery { get; set; }
    public string? Paper { get; set; }
    public string? Cover { get; set; }
    public string? Firmware { get; set; }
    public string? Message { get; set; }
    public string? ServiceUuid { get; set; }
    public string? WriteUuid { get; set; }
}
