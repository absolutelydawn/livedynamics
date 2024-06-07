import easyocr

reader = easyocr.Reader(['ko', 'en'])
result = reader.readtext('screen.png')
for detection in result:
    print(detection[1])  # 추출된 텍스트 출력
