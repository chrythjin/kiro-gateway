Option Explicit

Dim shell, fso, scriptDir, rootDir, stdoutLog, stderrLog, command
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
If fso.FileExists(fso.BuildPath(scriptDir, "main.py")) Then
    rootDir = scriptDir
Else
    rootDir = fso.GetParentFolderName(scriptDir)
End If

stdoutLog = fso.BuildPath(rootDir, "gateway.stdout.log")
stderrLog = fso.BuildPath(rootDir, "gateway.stderr.log")
command = "cmd.exe /c cd /d " & Chr(34) & rootDir & Chr(34) & " && py main.py >> " & Chr(34) & stdoutLog & Chr(34) & " 2>> " & Chr(34) & stderrLog & Chr(34)

shell.Run command, 0, False
