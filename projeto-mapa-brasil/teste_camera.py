import cv2

for backend_name, backend in [("DSHOW", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF), ("ANY", cv2.CAP_ANY)]:
    for idx in range(4):
        cap = cv2.VideoCapture(idx, backend)
        ok, frame = cap.read() if cap.isOpened() else (False, None)
        print(f"{backend_name} índice {idx}: {'FUNCIONA' if ok else 'falhou'}")
        cap.release()