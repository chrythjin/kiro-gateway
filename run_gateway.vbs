Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\NEW PRG\kiro-gateway"
WshShell.Run "C:\Users\U-N-00658\AppData\Local\Programs\Python\Python313\python.exe main.py", 0, False
