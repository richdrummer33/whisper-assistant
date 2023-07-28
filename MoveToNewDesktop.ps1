param([string]$windowTitle)

# Get the window handle of the command prompt with the given title
$windowHandle = (Get-Process | Where-Object { $_.MainWindowTitle -eq $windowTitle }).MainWindowHandle

# Get the virtual desktop to move the window to. This gets the second desktop. Adjust as needed.
$virtualDesktop = (Get-DesktopList)[1]

# Move the window to the other desktop
Move-Window -Desktop $virtualDesktop -Hwnd $windowHandle
