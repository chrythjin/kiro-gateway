Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\NEW PRG\kiro-gateway"
WshShell.Run "cmd.exe /c C:\Users\U-N-00658\AppData\Local\Programs\Python\Python313\python.exe main.py > gateway.stdout.log 2> gateway.stderr.log", 0, False
