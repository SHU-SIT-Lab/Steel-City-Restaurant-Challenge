import stt

while True:
    input("Press Enter, then speak after calibration...")
    text = stt.listen()
    print("TRANSCRIBED:", text)
