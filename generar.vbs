Option Explicit

Dim shell, files, folder, script, quote, errorCode
Set shell = CreateObject("WScript.Shell")
Set files = CreateObject("Scripting.FileSystemObject")
folder = files.GetParentFolderName(WScript.ScriptFullName)
script = files.BuildPath(folder, "interfaz.py")
quote = Chr(34)
shell.CurrentDirectory = folder

On Error Resume Next
shell.Run "pythonw.exe " & quote & script & quote, 0, False
errorCode = Err.Number
Err.Clear
If errorCode <> 0 Then
    shell.Run "pyw.exe -3 " & quote & script & quote, 0, False
    errorCode = Err.Number
    Err.Clear
End If
On Error GoTo 0

If errorCode <> 0 Then
    MsgBox "No se pudo iniciar Python. Instala Python para Windows con tkinter y agrega Python al PATH.", 16, "Horarios"
End If
