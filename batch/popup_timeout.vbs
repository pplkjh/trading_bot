' popup_timeout.vbs - timeout이 있는 팝업
' 사용법: cscript popup_timeout.vbs "제목" "메시지" 초
' 반환값: 6=Yes, 7=No, -1=Timeout

If WScript.Arguments.Count >= 3 Then
    title = WScript.Arguments(0)
    msg = Replace(WScript.Arguments(1), "\n", vbCrLf)
    timeout = CInt(WScript.Arguments(2))
    ' 4 = YesNo 버튼, 32 = Question 아이콘
    result = CreateObject("WScript.Shell").Popup(msg, timeout, title, 4 + 32)
    WScript.Echo result
Else
    WScript.Echo "-1"
End If
