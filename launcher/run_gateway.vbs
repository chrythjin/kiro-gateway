Set WshShell = CreateObject("WScript.Shell")
' Get the folder path where this VBS file resides
vbsPath = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.CurrentDirectory = vbsPath
' Run uvicorn server in the parent directory of launcher using relative cd .. command
WshShell.Run "cmd.exe /c cd .. && py main.py > launcher\gateway.stdout.log 2> launcher\gateway.stderr.log", 0, False
